---
title: 'vLLM Prefix Cache 原理深读：是什么、为什么这么做（含 SGLang 对照）'
date: '2026-06-29'
tags: ['vLLM', 'Prefix Cache', 'LLM推理', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

> 本文基于 vLLM 源码（`vllm/v1/core/`）逐行整理，并对照 SGLang `radix_cache.py`。
> 写作目标：把 **是什么（What）** 与 **为什么这么做（Why）** 讲透，原理、源码、示例优先。

**TL;DR** —— vLLM 的 prefix cache = **分页物理块（paged block）+ 链式哈希索引 + 引用计数共享 + LRU 双向链表淘汰**。一句话：把已算好的 KV 按 token 块缓存，用“链式哈希”让“求最长公共前缀”退化成“逐块查哈希表、首次 miss 即停”；命中的物理块靠引用计数零拷贝复用，没人用了再按 LRU 回收。

---

## 一、问题与定义

大模型推理时，**Prompt 前缀被反复重算**是最大的浪费来源：

- 多轮对话：每轮把“系统提示 + 历史”整个 prefill 一遍；
- few-shot / RAG：不同样本共享同一长 system prompt 或检索文档；
- 同源聚类：同一篇文档的多次提问、函数库的多次调用。

**Prefix Cache（vLLM 称 APC, Automatic Prefix Caching）** 的做法：把算好的 KV cache 按 **block（默认 16 token）** 粒度缓存，给每个块算一个哈希；新请求只要前缀哈希命中，就直接复用这些物理 KV，**跳过对应 token 的 prefill**。

它由三个设计支柱组成，理解它们就理解了全部：

| 支柱 | 做什么 | 为什么这么做 |
|---|---|---|
| **链式哈希** | 第 i 块哈希 = `H(第i-1块哈希, 第i块token)` | 让“前缀匹配”退化成 O(1)/块的查表，遇 miss 即停 |
| **分页物理块 + 引用计数** | KV 切成定长块，命中即 `ref_cnt++` 复用 | 不连续存储、跨请求零拷贝共享 |
| **LRU 双向链表** | 无人引用的块进空闲链表，按 LRU 回收 | 淘汰时优先保留可复用的长前缀 |

下面逐个展开。

---

## 二、链式哈希是灵魂

整条机制最聪明的一步在 `hash_block_tokens`（`kv_cache_utils.py:577`）：

```python
def hash_block_tokens(hash_function, parent_block_hash, curr_block_token_ids, extra_keys=None):
    if not parent_block_hash:
        parent_block_hash = NONE_HASH          # 随机种子（urandom 或 PYTHONHASHSEED）
    return BlockHash(hash_function((
        parent_block_hash,                     # ★ 依赖前一块的哈希
        tuple(curr_block_token_ids),           #   + 本块的 token
        extra_keys,                            #   + LoRA名 / 多模态hash / cache_salt
    )))
```

请求在创建时、以及每追加新 token 后，由 `request_block_hasher`（`kv_cache_utils.py:687`）按 `hash_block_size` **增量计算并追加**满块哈希（`request.py:237` 的 `update_block_hashes`）。也就是：`block_hashes[i]` 的计算依赖 `block_hashes[i-1]`。

**这个“依赖”决定了全局性质**：

> `block_hashes[i]` 唯一指纹了“从 token 0 到第 i 块末尾”的**整段前缀**。

于是得到两个极其好用的推论：

1. **前缀匹配 = 顺序查表、遇 miss 即停**：第 i 块没命中，第 i+1 块（依赖 i）必然也不命中，直接 `break`。
2. **天然支持任意长度前缀复用**：只要前 k 块哈希相同，就复用这 k 块，与请求总长无关。

**`extra_keys` 的隔离作用**（容易被忽略，但很关键）：

- **多模态**：相同占位 token 若对应不同图像，哈希必须不同。vLLM 给每个块带上图像哈希 + 块内偏移（`_gen_mm_extra_hash_keys`，`kv_cache_utils.py:431`），布局形如：
  ```
  Block 0  parent=None   tokens=[1,3,...,<p>...]   extra=<image hash>
  Block 1  parent=Blk0   tokens=[<p>,...,<p>]      extra=<image hash>
  ```
- **LoRA / cache_salt**：`cache_salt` 注入**第一个块**的哈希，使只有持相同 salt 的请求才能复用缓存——这能**防止时序侧信道攻击**（攻击者本可借“是否命中”带来的延迟差异推断他人缓存内容），把复用限制在一个互信组内，且几乎不损性能。

---

## 三、数据结构

### 3.1 `KVCacheBlock` —— 一个物理块的元数据（`kv_cache_utils.py:117`）

```python
@dataclass(slots=True)
class KVCacheBlock:
    block_id: int                          # 物理块号 [0, num_gpu_blocks)
    ref_cnt: int = 0                       # 引用计数
    _block_hash: BlockHashWithGroupId|None # 满块且被缓存后才有；None=未缓存
    _block_hash_num_tokens: int|None       # 该哈希覆盖的前缀 token 数
    prev_free_block / next_free_block      # 空闲链表前驱/后继
    is_null: bool = False                  # 占位块（block_id=0），永不缓存
```

**为什么 `_block_hash` 只在满块后才非空？** 因为缓存索引登记的是“完整的满块”——部分块无法作为他人复用的边界。

### 3.2 `FreeKVCacheBlockQueue` —— 双向链表 LRU（`kv_cache_utils.py:179`）

两个官方点明的设计动机：

1. **初始化时一次性预分配全部 `KVCacheBlock`**，运行期不再 new Python 对象——避免热路径上的对象创建开销。
2. **把 `prev/next` 指针直接内嵌进 `KVCacheBlock`**，而非包一层 `deque`：好处是 (a) O(1) 把链表中间的块移到尾部（`ref_cnt` 从 0 变正时要摘除块）；(b) 省掉 `deque` 的元素包装层。用 fake head/tail 哨兵减少分支，**不分配任何新对象**。

队列顺序约定（决定淘汰质量）：

> 1. 队头 = LRU（先被淘汰）；
> 2. 同一次释放的块里，**覆盖 token 更多（链更靠尾）的块排前面**——靠“释放时逆序入队”实现（见 5.1）。

### 3.3 `BlockHashToBlockMap` —— 哈希索引（`block_pool.py:34`）

```python
self._cache: dict[BlockHashWithGroupId, KVCacheBlock | dict[int, KVCacheBlock]]
```

- **为什么 value 是联合类型？** 因为 vLLM **不主动去重**（`block_pool.py:48-52` NOTE #1）。原因：要保证**块表 append-only**（已分配 block id 永不回改，利于 CUDA graph 等假设块表稳定的优化）。于是两个请求独立算出相同内容的满块时，两块都登记在同一 key 下，存成 `dict`；重复在请求 free 时自然消除。
  > 对比：v0 会检测重复并改写块表 `[0,3]→[0,1]` 复用块 1；v1 块表 append-only，改为**临时容忍重复块**。代价是极少数情况短暂多占一份显存，收益是块表只追加不改写。
- **`BlockHashWithGroupId` = 块哈希 + 4 字节 group_id**（`kv_cache_utils.py:57`）：相同 token 内容、不同 attention group → 不同 key，是 hybrid 模型分组建索引的基础。

### 3.4 `BlockPool` 与分层架构

```python
class BlockPool:                          # block_pool.py:144
    self.blocks: list[KVCacheBlock]       # 所有块（Block Pool）
    self.free_block_queue                 # Free Block Queue（只存头尾指针）
    self.cached_block_hash_to_block       # Cache blocks: hash→block
    self.cached_block_hashes_by_block     # 反向索引：block→它挂的所有哈希（淘汰时一次清干净）
```

整套 KV cache 管理分四层，调度器只接触最上层：

```
+--------------------------+   scheduler.py:711/874  get_computed_blocks / allocate_slots
|       Scheduler          |
+--------------------------+
              v
+--------------------------+   kv_cache_manager.py     门面：get_computed_blocks/allocate_slots/free
|     KVCacheManager       |
+--------------------------+
              v
+--------------------------+   kv_cache_coordinator.py 多组联合求最长命中(Unitary/Hybrid)
|   KVCacheCoordinator     |
+--------------------------+
              v
+--------------------------+   single_type_kv_cache_manager.py  每种注意力一个(Full/SWA/Mamba..)
| SingleTypeKVCacheManager |
+--------------------------+
              v
+--------------------------+   block_pool.py   物理块分配/释放/索引/淘汰（所有 manager 共享）
|       BlockPool          |
+--------------------------+
```

---

## 四、三条数据通路

### 4.1 读：求最长前缀命中 —— `get_computed_blocks`

调度器对每个 WAITING 请求调一次（`kv_cache_manager.py:202`）：

```python
def get_computed_blocks(self, request):
    if not self.enable_caching or request.skip_reading_prefix_cache:
        return self.empty_kv_cache_blocks, 0
    max_cache_hit_length = request.num_tokens - 1   # ★ 强制重算最后一个 token 以拿 logits
    computed_blocks, num_new_computed_tokens = self.coordinator.find_longest_cache_hit(
        request.block_hashes, max_cache_hit_length)
    return self.create_kv_cache_blocks(computed_blocks), num_new_computed_tokens
```

> **为什么 `num_tokens - 1`？** 若整条 prompt 全命中，模型无 logits 可输出；故即使最后一块也命中也强制丢掉，保证至少重算最后一 token。

单组（full attention）匹配逻辑（`single_type_kv_cache_manager.py:541`）——链式哈希让这里极简：

```python
computed_blocks = tuple([] for _ in kv_cache_group_ids)
max_num_blocks = max_length // block_size
for block_hash in itertools.islice(block_hashes, max_num_blocks):
    if cached_block := block_pool.get_cached_block(block_hash, kv_cache_group_ids):
        for computed, cached in zip(computed_blocks, cached_block):
            computed.append(cached)
    else:
        break                          # ★ 链式哈希保证：一旦 miss，后面必 miss，直接停
return computed_blocks
```

`get_cached_block`（`block_pool.py:199`）拼出 `BlockHashWithGroupId` 查表，**任一组 miss 就整体 miss**。

> ⚠️ **块粒度的代价（重要）**：命中只能停在整块边界。官方例子：block_size=4，两个请求共享前 10 个 token，但**只命中前 2 块（8 token）**——因为第 3 块只匹配 2/4，整块作废。块内分歧最坏浪费 `block_size-1` 个 token 的重算（这正是 SGLang token 级 radix tree 的发力点，见第七节）。

### 4.2 满块入缓存 —— `cache_full_blocks`

块被填满后登记进哈希表（`block_pool.py:226`）：

```python
new_full_blocks = blocks[num_cached_blocks:num_full_blocks]   # 本次新变满的块
for i, blk in enumerate(new_full_blocks):
    if blk.is_null or (block_mask and not block_mask[i]):     # null / SWA屏蔽块 跳过
        continue
    block_hash = request.block_hashes[num_cached_blocks + i]
    key = make_block_hash_with_group_id(block_hash, kv_cache_group_id)
    if blk.block_hash is not None:                            # 部分块升级为满块：先清旧哈希
        self._remove_cached_block_hashes(blk)
    self._insert_block_hash(key, blk, num_tokens=...)         # 写入缓存表
```

**触发时机**：每个调度步 `allocate_slots` 末尾 `cache_blocks(...)` → `cache_full_blocks`，**把新算满的块顺手缓存**。

### 4.3 认领命中块 + 分配新块 —— `allocate_slots`（`kv_cache_manager.py:244`）

```python
def allocate_slots(self, request, num_new_tokens, new_computed_blocks=None, ...):
    # 1) 容量检查：估算需要多少新块，不足返回 None（请求继续等待）
    num_blocks_to_allocate = self.coordinator.get_num_blocks_to_allocate(...)
    if num_blocks_to_allocate + watermark_blocks > available_blocks: return None

    # 2) 认领命中的本地缓存块：touch 它们（ref_cnt+1，从空闲队列摘除）
    self.coordinator.allocate_new_computed_blocks(...)   # 内部 block_pool.touch(...)

    # 3) 为待计算的新 token 分配全新物理块（从 LRU 队头取，顺便淘汰旧缓存块）
    new_blocks = self.coordinator.allocate_new_blocks(request.request_id, ...)

    # 4) 把新算满的块写进缓存表（见 4.2）
    self.coordinator.cache_blocks(request, num_tokens_to_cache)
    return self.create_kv_cache_blocks(new_blocks)
```

三个底层动作（`block_pool.py`）：

- **`touch`**（:597）：`ref_cnt==0 且非 null` → 从空闲队列摘除；`ref_cnt += 1`。
- **`get_new_blocks`**（:542）：从队头 `popleft_n`；若块带哈希（是缓存块）先 `_maybe_evict_cached_block` 剔除再复用，然后 `ref_cnt += 1`。

---

## 五、淘汰与共享

### 5.1 LRU 双队列淘汰 —— `free_blocks`（`block_pool.py:614`）

请求结束时释放一批块，按“有无哈希”分流：

```python
def free_blocks(self, ordered_blocks):
    blocks_with_hash, blocks_without_hash = [], []
    for block in ordered_blocks:
        block.ref_cnt -= 1
        if block.ref_cnt == 0 and not block.is_null:
            (blocks_without_hash if block.block_hash is None
             else blocks_with_hash).append(block)
    self.free_block_queue.prepend_n(blocks_without_hash)  # 无哈希块 → 插队头（最先淘汰）
    self.free_block_queue.append_n(blocks_with_hash)      # 有哈希块 → 接队尾（LRU 最后淘汰）
```

两个细节决定了缓存质量：

1. **无哈希块先淘汰**：`ref_cnt` 归 0 且没哈希（命中不了任何前缀）的块，留着毫无价值，最先回收。
2. **释放时逆序入队**：`free()` 调 `free_blocks(reversed(...))`（`single_type_kv_cache_manager.py:408`），即**链尾块（覆盖 token 多）排在 region 前面**。于是淘汰时“长前缀的尾部块先被淘汰，短前缀的头部块尽量保留”——另一条相同前缀的请求仍可能命中靠前的块。

> 主动失效：`reset_prefix_cache()`（RLHF 权重更新后整表失效）、`evict_blocks(ids)`（按 id 精确驱逐，供 KV connector 用）。

### 5.2 引用计数与跨请求共享

- 两请求命中**同一个**满块 → 第二个 `touch` 时 `ref_cnt` 1→2，物理 KV 完全不复制，只是 block table 多一个引用。
- 谁先 `free` 只把 `ref_cnt` 减 1、不回收；最后一个引用释放（`ref_cnt==0`）才进空闲队列。

**衍生物**：`get_num_common_prefix_blocks`（`single_type_kv_cache_manager.py:590`）统计“所有在跑请求**共同**引用的前缀块数”（`ref_cnt == len(req_to_blocks)`），用于触发 **Cascade Attention**（把公共前缀的 attention 合并算）。

```python
for block in blocks:
    if block.ref_cnt == len(self.req_to_blocks): num_common_blocks += 1
    else: break
```

---

## 六、block_size = 4 全流程

设单 group（`group_id=0`），`block_size = 4`。

**Step 0：请求 A 完整 prefill**。A 有 16 个 token，4 块：

```
block 0: t0 t1 t2 t3   block 1: t4 t5 t6 t7
block 2: t8 t9 t10 t11 block 3: t12 t13 t14 t15
```

A 被 prefill，分到物理块 5/7/9/11，算完后写入缓存表：

```
H(NONE,[t0..t3]) -> 块5(h0)   H(h0,[t4..t7]) -> 块7(h1)
H(h1,[t8..t11])  -> 块9(h2)   H(h2,[t12..t15]) -> 块11(h3)
```

A 输出完、`free(A)`：5/7/9/11 的 `ref_cnt` 归 0，逆序 `[11,9,7,5]` 入空闲队尾（h3 朝队头），仍是合法命中项。

**Step 1：请求 B 到达，前缀与 A 重合 3 块**（只最后一块不同）：

```
block 0~2: 与 A 完全相同    block 3: t20 t21 t22 t23
```

`get_computed_blocks(B)`：`max_num_blocks = 15//4 = 3`，遍历 `[h0,h1,h2]` 全命中 → `computed_blocks=[5,7,9]`, 命中 12 token。B 的 prefill **只需算最后 4 个 token**。

`allocate_slots(B, new_computed_blocks=[5,7,9])`：`touch([5,7,9])` 把它们从空闲队列摘除、`ref_cnt` 0→1（“复活”了被 A 释放的缓存块）；再分配 1 个新块给 t20~t23，算满后登记 `H(h2,[t20..t23])`。

**Step 2：若 A 此时仍在 RUNNING**：B 到达时块 5/7/9 的 `ref_cnt` 还是 1，`touch` 后 → **2**，A、B 共用同一份物理 KV，零拷贝；任一结束只减回 1，块继续留存。

**收益**：无 cache 时 B 需 prefill 全部 16 token；有 cache 只算 4 token，命中率 75%。多轮对话里前缀越长、共享越多，收益越接近 100% prefill 消除。

---

## 七、混合注意力（简述）

Gemma3（full + sliding window）、LLaMA4（full + chunked-local）等有**多种注意力类型**，每种算各自的块哈希（group_id 不同 → key 不同）。`HybridKVCacheCoordinator.find_longest_cache_hit`（`kv_cache_coordinator.py:621`）用 **fixed-point 迭代**求多组公共命中长度：每轮让各类型各自承认一个命中长度，取最短者重算，直到不再缩短（长度单调不增、下界为 0，必收敛）。SWA/ChunkedLocal 的命中需一段连续块覆盖窗口，未命中位置用 `null_block` 占位——但主干仍是“哈希查表 + 引用计数”。

---

## 八、对照 SGLang（RadixAttention）

> 基于 SGLang 源码 `python/sglang/srt/mem_cache/radix_cache.py`（main 分支）。

### 8.1 核心差别：一棵显式的 Radix Tree

vLLM 用链式哈希把前缀结构**隐式**编码进哈希表；SGLang 维护一棵**显式基数树（压缩前缀树）**，token 序列是“从根到叶的路径”，每个 `TreeNode` 存一段 token + 其 KV 池索引。**整棵树就是索引结构本身**，不再额外维护哈希表。

```python
class TreeNode:
    children: dict[child_key -> TreeNode]
    key: RadixKey          # 入边上的 token 段
    value: torch.Tensor    # ★ 这段 token 对应的 KV 池物理索引
    lock_ref: int          # 引用计数（>0 受保护）
    last_access_time: float
```

**读 `match_prefix`** —— 遍历树，命中处**分裂节点**，精度到 token：

```python
def _match_prefix_helper(self, node, key):
    while len(key) > 0 and child_key in node.children:
        child = node.children[child_key]
        prefix_len = child.key.match(key, page_size)
        if prefix_len < len(child.key):         # 只匹配了子节点段的一部分
            new_node = self._split_node(...)    # ★ 在分歧点把节点劈开 -> 命中到任意 token 边界
            value.append(new_node.value); break
        else:
            value.append(child.value); node = child; key = key[prefix_len:]
```

`RadixKey.match` 用**指数搜索 + 二分（galloping）**找首个不同 token，长公共前缀上不做逐 token Python 循环，缓解 GIL 开销。

**淘汰 `evict`** —— 在**树的叶子**上做，父节点随子清空而塌缩：

```python
heap = [(priority(n), n) for n in self.evictable_leaves]; heapq.heapify(heap)
while num_evicted < num_tokens and heap:
    _, x = heapq.heappop(heap)                  # 取优先级最低的叶子
    self.token_to_kv_pool_allocator.free(x.value)
    self._delete_leaf(x)
    if len(x.parent.children)==0 and x.parent.lock_ref==0:
        heapq.heappush(heap, (priority(x.parent), x.parent))   # 父节点塌缩为新叶子
```

**引用计数** `inc_lock_ref`/`dec_lock_ref` **沿路径上溯到 root，逐祖先 ±1**（vLLM 是单块 ±1），保证只要某前缀被引用，整条祖先链都被锁定。淘汰策略可插拔（LRU / WLFU / priority）。

### 8.2 逐维度对比

| 维度 | **vLLM（V1 APC）** | **SGLang（RadixAttention）** |
|---|---|---|
| 索引结构 | 扁平哈希表，前缀靠**链式哈希隐式**编码 | 显式 **radix tree**，前缀由树形物理共享 |
| 匹配单元 | **块**（block_size 默认 16），命中在块边界 | **token/page**（page_size 默认 1 可配），命中到分歧点 |
| 匹配算法 | 逐块查表，首次 miss 即停 | 树遍历 + galloping 比 token |
| 命中精度 | 块内分歧算全 miss | `_split_node` 精确到 token |
| 写入时机 | 每步把**新满块**即时入表 | 请求**结束/chunk 边界**整段插树 |
| 引用计数 | 单块 `ref_cnt` | **沿路径到根** `lock_ref` |
| 淘汰 | 单块；固定“无哈希优先+链尾优先+LRU” | 叶子节点塌缩；**策略可插拔** |
| 多注意力类型 | coordinator fixed-point，成熟 | 单树为主，hybrid 较弱 |

### 8.3 设计哲学：哈希即前缀 vs 树即前缀

- **vLLM = “哈希即前缀”**：用链式哈希把树压扁成哈希表，换来 O(1)/块的查表与极简块级管理，工程上更轻、更易与 paged attention / hybrid 组合；代价是命中粒度被 block_size 钉死。
- **SGLang = “树即前缀”**：显式 radix tree 精确表达共享结构，前缀复用率理论上更高、淘汰粒度更自然（叶子塌缩保护公共前缀）；代价是树遍历与 GIL 开销（galloping 缓解）。

二者底层都是 **paged KV + 引用计数 + LRU**，差异只在“前缀结构是隐式（哈希）还是显式（树）”。孰优孰劣强烈依赖模型/负载/版本，请以最新基准为准。

---

## 九、总结

**是什么**：把已算好的 KV 按块缓存，用链式哈希把“求最长公共前缀”变成“逐块查表、首次 miss 即停”，命中的物理块靠引用计数零拷贝复用。

**为什么这么做**：

1. **链式哈希** —— 让前缀匹配 O(1)/块、遇 miss 即停，无需维护任何树形结构；
2. **分页块 + 引用计数** —— 不连续存储便于回收，跨请求零拷贝共享，append-only 块表利于底层优化（代价是临时容忍重复块）；
3. **LRU 双向链表** —— 无哈希块先淘汰、同批链尾先淘汰，最大化保留可复用前缀；
4. **块粒度的取舍** —— 简单但块内分歧会浪费（最坏 block_size-1 token），这正是 SGLang token 级 radix tree 的差异化优势。

---

### 源码索引

| 关注点 | 位置 |
|---|---|
| 顶层门面 `get_computed_blocks` / `allocate_slots` | `vllm/v1/core/kv_cache_manager.py:202, 244` |
| 调度器调用点 | `vllm/v1/core/sched/scheduler.py:711, 874` |
| 单组/多组求命中 | `vllm/v1/core/kv_cache_coordinator.py:541, 621` |
| 物理块分配/释放/淘汰 | `vllm/v1/core/block_pool.py:542, 597, 614` |
| 满块入缓存表 / 哈希索引 | `vllm/v1/core/block_pool.py:226, 34` |
| **链式哈希** / 请求侧增量算哈希 | `vllm/v1/core/kv_cache_utils.py:577, 687`；`vllm/v1/request.py:237` |
| LRU 双向链表 / block_size 解析 | `vllm/v1/core/kv_cache_utils.py:179, 607` |

### 参考资料

- vLLM 官方设计文档：[docs.vllm.ai](https://docs.vllm.ai/en/latest/design/prefix_caching/)
- vLLM 源码 `vllm/v1/core/`：block_pool / kv_cache_manager / kv_cache_coordinator / single_type_kv_cache_manager / kv_cache_utils
- SGLang RadixAttention 博客（LMSys）：[lmsys.org](https://www.lmsys.org/blog/2024-01-17-sglang/)
- SGLang 论文（NeurIPS 2024）：[arXiv 2312.07104](https://arxiv.org/pdf/2312.07104)
- SGLang 源码 `radix_cache.py`：[sgl-project/sglang](https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/mem_cache/radix_cache.py)
- RadixAttention vs PagedAttention：[rajatpandit.com](https://rajatpandit.com/ai-engineering/radixattention-vs-pagedattention)
