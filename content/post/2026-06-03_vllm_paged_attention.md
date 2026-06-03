---
title: "vllm 深度解析：一切从 PagedAttention 谈起"
date: 2026-06-03
categories: ["技术"]
tags: ["vLLM", "PagedAttention", "LLM推理", "KV Cache"]
toc: true
---

## 一、背景与问题

在大语言模型（LLM）的推理服务中，KV Cache 是性能的关键瓶颈之一。传统推理框架（如 HuggingFace Transformers）为每个请求预分配一块**连续的**显存空间来存储 KV Cache，其大小按最大序列长度分配。这种方式带来三个核心问题：

1. **显存浪费严重**：实际序列长度通常远小于最大长度，大量预分配空间被闲置。据统计，实际利用率仅 60%~80%。
2. **显存碎片化**：请求的生成长度不可预知，连续分配导致大量外部碎片，无法被新请求复用。
3. **并发受限**：由于上述浪费和碎片，系统能同时服务的请求数（batch size）被严重限制，直接影响吞吐量。

vLLM 是 UC Berkeley 团队开源的高性能 LLM 推理引擎（2023 年 SOSP 论文），其核心创新 **PagedAttention** 正是为解决上述问题而生——借鉴操作系统虚拟内存的分页思想，将 KV Cache 从连续内存改为**按块（block）离散存储**，通过 Block Table 实现逻辑地址到物理地址的映射。

本文将以 vLLM 源码为线索，从四个层次深入解析 PagedAttention 的完整实现：

- **层次 1**：KV 缓存管理（块分配/释放）
- **层次 2**：Block Table（逻辑到物理的映射）
- **层次 3**：CUDA 内核（核心计算）
- **层次 4**：Python 接口层

---

## 二、PagedAttention 实现全景

PagedAttention 是 vLLM 的核心创新（来自 2023 年 SOSP 论文），本质是**将 KV 缓存从连续内存改为分页（块）存储**，类比操作系统的虚拟内存分页。代码实现涉及 **4 个层次**：

### 层次 1：KV 缓存管理（块分配/释放）

工作机制：
```
Request → Scheduler → KVCacheManager.allocate(request)
  → SingleTypeKVCacheManager.get_num_blocks_to_allocate()
  → BlockPool.allocate() → 返回 KVCacheBlock 列表
  → req_to_blocks[req_id] = [blocks]
  → Scheduler 拿到 KVCacheBlocks（含 block_id 列表）
  → Worker 将 block_id 写入 BlockTable
```

#### `KVCacheBlock` — 物理 block 元数据

**文件**: `vllm/v1/core/kv_cache_utils.py:116`

```python
@dataclass(slots=True)
class KVCacheBlock:
    """KV-cache block metadata.
    元数据与数据分离: 不存储实际 KV 张量, 仅通过 block_id 计算显存偏移地址.
    """

    block_id: int                                  # 物理 block ID [0, num_gpu_blocks)
    ref_cnt: int = 0                               # 引用计数, =0 时可被回收
    _block_hash: BlockHashWithGroupId | None = None # 写满后的哈希值, prefix caching 用
    prev_free_block: "KVCacheBlock | None" = None   # 双向链表前驱 (FreeKVCacheBlockQueue 内部)
    next_free_block: "KVCacheBlock | None" = None   # 双向链表后继 (FreeKVCacheBlockQueue 内部)
    is_null: bool = False                          # null block 永不参与 prefix caching

    @property
    def block_hash(self) -> BlockHashWithGroupId | None:
        """获取 block 哈希值 (仅写满且被缓存后有效)"""
        return self._block_hash

    @block_hash.setter
    def block_hash(self, value: BlockHashWithGroupId):
        """设置 block 哈希值 (仅允许设置一次)"""
        assert self._block_hash is None, "block already has a hash"
        self._block_hash = value

    def reset_hash(self):
        """驱逐时清空哈希值, 使 block 重新可被分配"""
        self._block_hash = None
```

设计要点：元数据与数据分离——`KVCacheBlock` 不存储实际 KV 张量数据，仅通过 `block_id` 计算显存偏移地址。

##### `ref_cnt` 详解 — 通用引用计数，非 prefix caching 专属

`ref_cnt` 是一个通用的引用计数器，追踪"有多少个请求正在使用这个 block"，**不是**仅为 prefix caching 预留的。无论是否开启 prefix caching，ref_cnt 都会正常工作：

- **常规分配**（`block_pool.py:354`）：`get_new_blocks()` 从空闲队列取出 block 时，`ref_cnt += 1`，表示 1 个请求持有该 block。请求结束时 `free_blocks()` 执行 `ref_cnt -= 1`，归零后 block 回到空闲队列。未开启 prefix caching 时 ref_cnt 始终为 0 或 1。
- **Prefix caching 共享**（`block_pool.py:402-415`）：`touch()` 是专为 prefix caching 设计的方法。当新请求的 prefix hash 命中已有 block 时，`ref_cnt += 1` 并从空闲队列移出，此时 ref_cnt >= 2，表示多个请求共享同一物理 block。共享 block 不会被驱逐，直到所有引用者都释放（ref_cnt 回到 0）。

```
示例: block_size=16, 两个请求共享前缀 "Hello, how are"

时间线:
  T1: Request A 生成 "Hello, how are" 的 KV cache, 写满 block P3
      → P3._block_hash = hash("Hello, how are")
      → P3.ref_cnt = 1

  T2: Request B 以 "Hello, how are" 开头, prefix hash 命中 P3
      → touch(P3): P3.ref_cnt = 2   ← 两个请求共享同一物理 block

  T3: Request A 结束, free_blocks()
      → P3.ref_cnt = 1              ← B 仍在用, P3 不会回到空闲队列

  T4: Request B 结束, free_blocks()
      → P3.ref_cnt = 0              ← 无人引用, 回到 FreeKVCacheBlockQueue
```

#### 设计要点

1. **元数据与数据分离**：不存 KV 张量，只持有一个 block_id，通过 block_id * block_size + offset 计算显存地址。数据全在 GPU，元数据全在 CPU，各司其职。
2. **空闲块管理**：`FreeKVCacheBlockQueue`（`kv_cache_utils.py:164`）通过 `prev_free_block` / `next_free_block` 将空闲 block 组织为双向链表，支持 O(1) 在链表中间删除（任意 block 回收），性能接近 C++ `std::deque`。
3. **LRU 驱逐顺序**：空闲链表按 LRU 排序——least recent used 的 block 在前。当同一序列的多个 block 同时释放时，尾部 block（含更多 hash token）排在前面，优先被驱逐。
4. **Prefix Caching 生命周期**：
   - block 写满 → 计算 hash → 写入 `_block_hash` → 加入全局哈希索引
   - 新请求到达 → 通过哈希索引匹配 → 命中则复用物理 block（`ref_cnt++`）
   - block 被驱逐 → `reset_hash()` 清空 `_block_hash` → 从哈希索引移除
5. **`is_null` 标志**：用于标记占位 block（如 padding），这些 block 永远不会参与 prefix caching，防止无效缓存污染。

### 层次 2：Block Table（逻辑到物理的映射）

核心文件：`vllm/v1/worker/gpu/block_table.py`

`BlockTables` 管理一组 `[max_num_reqs, max_num_blocks]` 的 int32 tensor，
本质是**一个二维查找表**，将每个请求的逻辑块序号映射为物理 block ID。

#### 逻辑视图（每个请求的视角）

每个请求看到的是**从 token 0 开始连续编号**的线性序列，按 `block_size` 切分为逻辑块。
以 `block_size = 16` 为例，Request 1（25 tokens）、Request 2（12 tokens）：

```
Request 1 (25 tokens, 2 个逻辑块):

  逻辑块 0 (token 0~15)      逻辑块 1 (token 16~24)
  ┌────────────────┬────────────────┐
  │████████████████│█████████░░░░░░░│
  └────────────────┴────────────────┘
     16/16 满          9/16 部分

Request 2 (12 tokens, 1 个逻辑块):

  逻辑块 0 (token 0~11)
  ┌────────────────┐
  │████████████░░░░│
  └────────────────┘
    12/16 部分
```

#### 物理视图（GPU 显存布局）

物理 block 按页式分配，空闲 block 被 `FreeKVCacheBlockQueue` 以双向链表管理。
分配时从链表头部取出，**同一请求的物理 block 不一定连续**：

```
GPU KV Cache 物理地址空间 (block_size=16, 每个物理 block 可存 16 个 token 的 KV):

┌────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┐
│  P0    │  P1    │  P2    │  P3    │  P4    │  P5    │  P6    │  P7    │
│  FREE  │ Req2   │  FREE  │ Req1   │  FREE  │  FREE  │  FREE  │ Req1   │
│        │ T0~T11 │        │ T0~T15 │        │        │        │T16~T24 │
│  [  ]  │ [██▓]  │  [  ]  │ [███]  │  [  ]  │  [  ]  │  [  ]  │ [██▓]  │
└────────┴────────┴────────┴────────┴────────┴────────┴────────┴────────┘
         ↑                  ↑                                   ↑
      被 Req2 占用       被 Req1 占用                       被 Req1 占用
      (逻辑块0)        (逻辑块0, 满)                     (逻辑块1, 部分满)

FreeKVCacheBlockQueue 双向链表:
  HEAD ⇄ P0 ⇄ P2 ⇄ P4 ⇄ P5 ⇄ P6 ⇄ TAIL
         ↑ 这些物理 block 空闲，等待分配
```

#### Block Table 映射表

Block Table 是连接逻辑视图与物理视图的**核心数据结构**——
一个 `[max_num_reqs, max_num_blocks]` 的 int32 tensor，存储在 GPU 上：

```
BlockTable (行 = 请求, 列 = 逻辑块序号, 值 = 物理 block id):

            逻辑块0  逻辑块1  逻辑块2  ...  逻辑块N-1
           ┌────────┬────────┬────────┬──┬────────┐
  Req1     │   P3   │   P7   │   -1   │..│   -1   │  num_blocks=2
           ├────────┼────────┼────────┼──┼────────┤
  Req2     │   P1   │   -1   │   -1   │..│   -1   │  num_blocks=1
           ├────────┼────────┼────────┼──┼────────┤
  Req3     │   -1   │   -1   │   -1   │..│   -1   │  (空闲槽位，未分配)
           ├────────┴────────┴────────┴──┴────────┤
  ...                                              │
           └───────────────────────────────────────┘

  -1 = 无效/未分配,  num_blocks = 该请求已分配的逻辑块数量
```

#### Token → 物理地址 完整映射链

Kernel 拿到 position 后，通过两步查表获得物理地址（`_compute_slot_mappings_kernel`）：

```
输入: req_idx=Req1, position=18
                         │
                         ▼
  ┌──────────────────────────────────────────────────┐
  │ Step 1: position → 逻辑块索引 + 块内偏移          │
  │                                                    │
  │   block_index  = 18 // 16 = 1    (第 1 号逻辑块)   │
  │   block_offset = 18 %  16 = 2    (块内第 2 个位置) │
  └──────────────────────┬───────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────┐
  │ Step 2: 查 BlockTable 获取物理 block              │
  │                                                    │
  │   physical_block = BlockTable[Req1][1] = P7        │
  └──────────────────────┬───────────────────────────┘
                         │
                         ▼
  ┌──────────────────────────────────────────────────┐
  │ Step 3: 计算最终 slot_id，访问 GPU 显存            │
  │                                                    │
  │   slot_id = P7 * 16 + 2                           │
  │           = 物理 block 基址 + 块内偏移              │
  │                                                    │
  │   访问: k_cache[slot_id, kv_head, ...]             │
  └──────────────────────────────────────────────────┘
```

#### 映射公式

```python
# block_table.py:264-275 (_compute_slot_mappings_kernel)
block_index    = position // block_size          # 逻辑块号
block_offset   = position %  block_size          # 块内偏移
physical_block = block_table[req_idx][block_index]  # 查表 → 物理块号
slot_id        = physical_block * block_size + block_offset
```

#### 两请求对比

| | Request 1 (25 tokens) | Request 2 (12 tokens) |
|---|---|---|
| 逻辑块数 | `⌈25/16⌉ = 2` | `⌈12/16⌉ = 1` |
| 占用的物理 block | P3, P7 | P1 |
| BlockTable 行 | `[P3, P7, -1, ...]` | `[P1, -1, ...]` |
| num_blocks | 2 | 1 |
| 最后一个 block 利用率 | 9/16 = 56% | 12/16 = 75% |

**本质**：Block Table 让每个请求都以为自己在使用"从 0 开始、连续排布"的私有 KV 缓存，而底层物理内存是离散分页的——完全类比操作系统的虚拟内存页表。

#### `BlockTables`（GPU 版）— GPU 端 Block Table

**文件**: `vllm/v1/worker/gpu/block_table.py:12`

```python
class BlockTables:
    """GPU 端 Block Table: 管理 [max_num_reqs, max_num_blocks] 的 int32 映射张量."""

    def __init__(self, block_sizes: list[int], max_num_reqs: int,
                 max_num_batched_tokens: int, max_num_blocks_per_group: list[int],
                 device: torch.device, kernel_block_sizes: list[int]):
        self.num_kv_cache_groups = len(block_sizes)
        # 核心映射表: 行=请求, 列=逻辑块序号, 值=物理 block_id
        self.block_tables: list[StagedWriteTensor] = []
        for i in range(self.num_kv_cache_groups):
            max_blocks = max_num_blocks_per_group[i]
            self.block_tables.append(
                StagedWriteTensor((max_num_reqs, max_blocks), dtype=torch.int32, device=device)
            )
        # 每请求已分配的逻辑块数量 [num_groups, max_reqs]
        self.num_blocks = UvaBackedTensor(
            (self.num_kv_cache_groups, max_num_reqs), dtype=torch.int32)
        # 模型 forward 用的 block table 副本
        self.input_block_tables: list[torch.Tensor] = [
            torch.zeros_like(b.gpu) for b in self.block_tables]
        # 每个 token 到显存 slot 的直接映射 [num_groups, max_tokens]
        self.slot_mappings = torch.zeros(
            self.num_kv_cache_groups, max_num_batched_tokens,
            dtype=torch.int64, device=device)

    def append_block_ids(self, req_index: int, new_block_ids: tuple[list[int], ...],
                         overwrite: bool):
        """追加新的 block ID 到某请求行"""
        for i in range(self.num_kv_cache_groups):
            start = self.num_blocks.np[i, req_index] if not overwrite else 0
            self.block_tables[i].stage_write(req_index, start, new_block_ids[i])
            self.num_blocks.np[i, req_index] = start + len(new_block_ids[i])

    def compute_slot_mappings(self, idx_mapping: torch.Tensor,
                              query_start_loc: torch.Tensor,
                              positions: torch.Tensor) -> torch.Tensor:
        """计算每个 token 的 slot_id = physical_block * block_size + offset"""
        # Triton kernel 实现, 逻辑等价于:
        # block_index    = position // block_size
        # block_offset   = position %  block_size
        # physical_block = block_table[req_idx][block_index]
        # slot_id        = physical_block * block_size + block_offset
        ...
```

核心方法：

- `append_block_ids()` — 追加新的 block ID 到某请求行
- `gather_block_tables()` — 按调度顺序从源表收集到 `input_block_tables`
- `compute_slot_mappings()` — 计算每个 token 的 `slot_id = physical_block * block_size + offset`



#### 其他数据结构

#####  `FreeKVCacheBlockQueue` — 空闲 block 双向链表

**文件**: `vllm/v1/core/kv_cache_utils.py:164`

```python
class FreeKVCacheBlockQueue:
    """空闲 block 双向链表, 按 LRU 排序 (队头 = 最久未用).
    用 fake head/tail 哨兵节点减少边界判断分支, 支持 O(1) 中间删除.
    """

    def __init__(self, blocks: list[KVCacheBlock]):
        self.num_free_blocks = len(blocks)
        self.fake_free_list_head = KVCacheBlock(block_id=-1)  # 哨兵头, 永不弹出
        self.fake_free_list_tail = KVCacheBlock(block_id=-1)  # 哨兵尾, 永不弹出
        # 初始化: 将所有 block 串联为双向链表
        for i in range(self.num_free_blocks):
            if i > 0:
                blocks[i].prev_free_block = blocks[i - 1]
            if i < self.num_free_blocks - 1:
                blocks[i].next_free_block = blocks[i + 1]
        # 连接哨兵
        self.fake_free_list_head.next_free_block = blocks[0]
        blocks[0].prev_free_block = self.fake_free_list_head
        self.fake_free_list_tail.prev_free_block = blocks[-1]
        blocks[-1].next_free_block = self.fake_free_list_tail
```

核心方法：`popleft()` / `popleft_n(n)` 从头部取出、`append()` / `append_n()` 从尾部放回、`remove()` O(1) 删除中间节点。排序策略为 LRU——least recent used 在队头，优先被分配/驱逐。

##### `BlockPool` — block 池管理器

**文件**: `vllm/v1/core/block_pool.py:130`

```python
class BlockPool:
    """Block 池管理器: 负责分配, 释放, 缓存 KVCacheBlock."""

    def __init__(self, num_gpu_blocks: int, enable_caching: bool, hash_block_size: int):
        self.num_gpu_blocks = num_gpu_blocks
        self.enable_caching = enable_caching
        self.hash_block_size = hash_block_size
        # 所有 kv-cache blocks, 索引即为 block_id
        self.blocks: list[KVCacheBlock] = [
            KVCacheBlock(idx) for idx in range(num_gpu_blocks)
        ]
        # 空闲 block 双向链表 (含驱逐候选), LRU 排序
        self.free_block_queue = FreeKVCacheBlockQueue(self.blocks)
        # prefix caching 哈希索引: block_hash → KVCacheBlock
        self.cached_block_hash_to_block = BlockHashToBlockMap()
        # 占位 block (block_id=0), 滑动窗口等场景用于替换跳过的 block
        self.null_block = self.free_block_queue.popleft()
        self.null_block.is_null = True

    def get_new_blocks(self, num_blocks: int) -> list[KVCacheBlock]:
        """从空闲池分配新 block, 若启用 caching 则可能驱逐 LRU 缓存块"""
        if num_blocks > self.get_num_free_blocks():
            raise ValueError(f"Not enough free blocks: need {num_blocks}")
        ret = self.free_block_queue.popleft_n(num_blocks)
        for block in ret:
            if self.enable_caching:
                self._maybe_evict_cached_block(block)  # 驱逐 LRU 缓存块
            block.ref_cnt += 1
        return ret

    def touch(self, blocks: Sequence[KVCacheBlock]):
        """增加引用计数, prefix cache 命中时使用; ref_cnt=0 的 block 会从空闲队列移除"""
        for block in blocks:
            if block.ref_cnt == 0 and not block.is_null:
                self.free_block_queue.remove(block)
            block.ref_cnt += 1

    def free_blocks(self, ordered_blocks: Iterable[KVCacheBlock]):
        """释放 block 列表 (按驱逐优先级排序, 首块最先被驱逐)"""
        blocks_list = list(ordered_blocks)
        for block in blocks_list:
            block.ref_cnt -= 1
        # 仅回收 ref_cnt 归零且非 null 的 block
        self.free_block_queue.append_n(
            [b for b in blocks_list if b.ref_cnt == 0 and not b.is_null]
        )

    def get_num_free_blocks(self) -> int:
        return self.free_block_queue.num_free_blocks

    def get_usage(self) -> float:
        """返回 KV cache 利用率 [0.0, 1.0]"""
        total = self.num_gpu_blocks - 1  # 减去 null_block
        return 1.0 - (self.get_num_free_blocks() / total) if total else 0.0
```

##### `BlockHashToBlockMap` — prefix caching 哈希索引

**文件**: `vllm/v1/core/block_pool.py:34`

```python
class BlockHashToBlockMap:
    """Prefix caching 哈希索引.
    单 block 时直接存 KVCacheBlock; 多 block 同哈希时退化为 dict 以减少 GC 开销.
    """

    def __init__(self):
        self._cache: dict[
            BlockHashWithGroupId,
            KVCacheBlock | dict[int, KVCacheBlock]
        ] = {}

    def get_one_block(self, key: BlockHashWithGroupId) -> KVCacheBlock | None:
        """根据哈希键获取任意一个匹配的 block"""
        blocks = self._cache.get(key)
        if blocks is None:
            return None
        if isinstance(blocks, KVCacheBlock):
            return blocks
        return next(iter(blocks.values()))  # 多 block 时返回第一个

    def insert(self, key: BlockHashWithGroupId, block: KVCacheBlock):
        """插入 block 到缓存"""
        existing = self._cache.get(key)
        if existing is None:
            self._cache[key] = block                           # 首次: 直接挂 block
        elif isinstance(existing, KVCacheBlock):
            self._cache[key] = {existing.block_id: existing,
                                block.block_id: block}         # 第二次: 升级为 dict
        else:
            existing[block.block_id] = block                   # 后续: 追加到 dict

    def pop(self, key: BlockHashWithGroupId, block_id: int) -> KVCacheBlock | None:
        """驱逐时按 block_id 精确弹出"""
        blocks = self._cache.pop(key, None)
        if blocks is None:
            return None
        if isinstance(blocks, KVCacheBlock):
            if blocks.block_id == block_id:
                return blocks
            self._cache[key] = blocks  # ID 不匹配, 放回去
            return None
        block = blocks.pop(block_id, None)
        if blocks:                     # dict 中还有剩余 block
            self._cache[key] = blocks
        return block
```

##### `BlockTable`（Worker 版）— Worker 端 Block Table

**文件**: `vllm/v1/worker/block_table.py:18`

```python
class BlockTable:
    """Worker 端 Block Table: CPU/GPU 双缓冲的二维映射表."""

    def __init__(self, block_size: int, max_num_reqs: int,
                 max_num_blocks_per_req: int, max_num_batched_tokens: int,
                 pin_memory: bool, device: torch.device,
                 kernel_block_size: int):
        # Hybrid block: 当 block_size != kernel_block_size 时拆分
        if kernel_block_size == block_size:
            self.block_size = block_size
            self.blocks_per_kv_block = 1
            self.use_hybrid_blocks = False
        else:
            self.block_size = kernel_block_size
            self.blocks_per_kv_block = block_size // kernel_block_size
            self.use_hybrid_blocks = True

        self.max_num_blocks_per_req = max_num_blocks_per_req * self.blocks_per_kv_block
        # CPU/GPU 双缓冲映射表: [max_reqs, max_blocks_per_req] int32
        self.block_table = CpuGpuBuffer(
            max_num_reqs, self.max_num_blocks_per_req,
            dtype=torch.int32, device=device, pin_memory=pin_memory)
        # 每行有效 block 数量
        self.num_blocks_per_row = np.zeros(max_num_reqs, dtype=np.int32)
        # token → slot 映射
        self.slot_mapping = CpuGpuBuffer(
            max_num_batched_tokens, dtype=torch.int64,
            device=device, pin_memory=pin_memory)

    def append_row(self, block_ids: list[int], row_idx: int):
        """向指定请求行追加 block IDs"""
        if not block_ids:
            return
        if self.use_hybrid_blocks:
            block_ids = self.map_to_kernel_blocks(block_ids)
        start = self.num_blocks_per_row[row_idx]
        self.num_blocks_per_row[row_idx] += len(block_ids)
        self.block_table.np[row_idx, start:start + len(block_ids)] = block_ids

    def add_row(self, block_ids: list[int], row_idx: int):
        """覆盖写入指定请求行 (先清零再追加)"""
        self.num_blocks_per_row[row_idx] = 0
        self.append_row(block_ids, row_idx)

    def clear_row(self, row_idx: int):
        """清空指定请求行"""
        n = self.num_blocks_per_row[row_idx]
        if n > 0:
            self.block_table.np[row_idx, :n] = 0
        self.num_blocks_per_row[row_idx] = 0

    def commit_block_table(self, num_reqs: int):
        """将 CPU 端 block table 拷贝到 GPU"""
        self.block_table.copy_to_gpu(num_reqs)

    @staticmethod
    def map_to_kernel_blocks(kv_block_ids: list[int],
                             blocks_per_kv_block: int) -> list[int]:
        """将 KV manager block ID 展开为 kernel block ID.
        例: block_size=32, kernel_block_size=16, blocks_per_kv_block=2
            [0, 1] → [0, 1, 2, 3]
        """
        if blocks_per_kv_block == 1:
            return kv_block_ids
        return [b * blocks_per_kv_block + k
                for b in kv_block_ids for k in range(blocks_per_kv_block)]
```

核心方法：`append_row()` / `add_row()` / `clear_row()` / `move_row()` / `swap_row()` — 行级 CRUD；`commit_block_table()` — CPU→GPU 拷贝。

##### `MultiGroupBlockTable` — 多组 KV cache 的 Block Table 聚合

**文件**: `vllm/v1/worker/block_table.py:223`

```python
class MultiGroupBlockTable:
    """多组 KV cache 的 Block Table 聚合.
    为混合注意力模型 (full attention + sliding window) 设计,
    每个 KV cache group 独立管理自己的 block table.
    """

    def __init__(self, block_sizes: list[int], kernel_block_sizes: list[int],
                 max_num_reqs: int, max_model_len: int,
                 max_num_batched_tokens: int, pin_memory: bool,
                 device: torch.device):
        max_num_blocks = [cdiv(max_model_len, bs) for bs in block_sizes]
        self.block_tables: list[BlockTable] = [
            BlockTable(block_size, max_num_reqs, blocks_per_req,
                       max_num_batched_tokens, pin_memory, device, kbs)
            for block_size, kbs, blocks_per_req
            in zip(block_sizes, kernel_block_sizes, max_num_blocks)
        ]

    def append_row(self, block_ids: tuple[list[int], ...], row_idx: int):
        """向所有 group 的指定行追加 block IDs"""
        for i, bt in enumerate(self.block_tables):
            bt.append_row(block_ids[i], row_idx)

    def clear_row(self, row_idx: int):
        """清空所有 group 的指定行"""
        for bt in self.block_tables:
            bt.clear_row(row_idx)

    def __getitem__(self, idx: int) -> BlockTable:
        """获取第 i 个 KV cache group 的 BlockTable"""
        return self.block_tables[idx]
```

为混合注意力模型（如 full attention + sliding window）设计，每组独立管理自己的 block table。

##### `KVCacheBlocks` — Scheduler 与 KVCacheManager 之间的接口

**文件**: `vllm/v1/core/kv_cache_manager.py:26`

```python
@dataclass
class KVCacheBlocks:
    """Scheduler 与 KVCacheManager 之间的接口对象.
    隐藏 KVCacheManager 内部数据结构, Scheduler 只通过此对象交互.
    blocks[i][j] = 第 i 个 kv_cache_group 的第 j 个 block.
    """

    blocks: tuple[Sequence[KVCacheBlock], ...]

    def __add__(self, other: "KVCacheBlocks") -> "KVCacheBlocks":
        """合并两组 blocks (跨调度步骤时拼接)"""
        return KVCacheBlocks(
            tuple(list(a) + list(b) for a, b in zip(self.blocks, other.blocks)))

    def get_block_ids(self) -> tuple[list[int], ...]:
        """提取所有 block_id, 用于写入 Block Table"""
        return tuple([blk.block_id for blk in group] for group in self.blocks)

    def new_empty(self) -> "KVCacheBlocks":
        """创建同结构但无 block 的空对象"""
        return KVCacheBlocks(tuple(() for _ in range(len(self.blocks))))
```

核心方法：`get_block_ids()` → `tuple[list[int], ...]`，提取所有 block ID，用于写入 Block Table。

##### `BlockHashWithGroupId` — 哈希键

**文件**: `vllm/v1/core/kv_cache_utils.py:47`

本质是 `NewType("BlockHashWithGroupId", bytes)` = `BlockHash`(32字节) + `group_id`(4字节大端 uint32) 的拼接。

```python
BlockHash = NewType("BlockHash", bytes)                     # 32 字节哈希
BlockHashWithGroupId = NewType("BlockHashWithGroupId", bytes)  # BlockHash + 4 字节 group_id

def make_block_hash_with_group_id(block_hash: BlockHash, group_id: int) -> BlockHashWithGroupId:
    """打包: BlockHash(32B) + group_id(4B big-endian)"""
    return BlockHashWithGroupId(block_hash + group_id.to_bytes(4, "big", signed=False))

def get_block_hash(key: BlockHashWithGroupId) -> BlockHash:
    """解包: 取前 32 字节"""
    return BlockHash(key[:-4])

def get_group_id(key: BlockHashWithGroupId) -> int:
    """解包: 取后 4 字节"""
    return int.from_bytes(key[-4:], "big", signed=False)
```

##### 数据结构关系总览

```
                            Scheduler
                               |
                    KVCacheManager.allocate_slots()
                               |
               +---------------+---------------+
               |                               |
         SingleTypeKVCacheManager    SingleTypeKVCacheManager
          (FullAttention)              (SlidingWindow)
               |                               |
               +---------------+---------------+
                               |
                          BlockPool
                    +-------+-------+
                    |               |
          FreeKVCacheBlockQueue   BlockHashToBlockMap
            (doubly linked, LRU)   (hash index, prefix cache)
                    |
              KVCacheBlock[]
              (physical block metadata)

                    |  allocation result

              KVCacheBlocks
             (Scheduler interface object)
                    |
                    |  get_block_ids()

            BlockTables / BlockTable
         [max_num_reqs, max_num_blocks]  <- GPU int32 tensor
                    |
                    |  compute_slot_mappings()

            slot_mappings[token] = physical_block * block_size + offset
                    |
                    v
            CUDA Kernel reads k_cache[slot_id] / v_cache[slot_id]
```

### 层次 3：CUDA 内核（核心计算）

核心文件：
- `csrc/libtorch_stable/attention/attention_kernels.cuh` — 核心设备函数 `paged_attention_kernel`
- `csrc/libtorch_stable/attention/paged_attention_v1.cu` — V1 启动器
- `csrc/libtorch_stable/attention/paged_attention_v2.cu` — V2 启动器 + Reduce 内核

#### 内核设计要点

| 维度 | 说明 |
|------|------|
| Grid | `(num_heads, num_seqs, max_num_partitions)` |
| 每个 Block | 处理 1 个 head × 1 个 seq × 1 个 partition |
| Thread Group | `WARP_SIZE / BLOCK_SIZE` 个线程协作处理 1 个 KV token |
| Warp | 每次迭代处理 1 个 block（在多个迭代中覆盖多 block） |
| Vec Size | 确保每 Thread Group 每次取 16 字节（内存合并） |

#### Q 加载（共享内存）

```
q_vecs[THREAD_GROUP_SIZE][NUM_VECS_PER_THREAD]  // 共享内存
每个 thread group 读取同一 query token 的不同部分
线程 0 读取 vec [0,4,8,...]，线程 1 读取 vec [1,5,9,...]
```

#### K 加载（寄存器）

```
k_vecs[NUM_VECS_PER_THREAD]  // 寄存器
通过 block_table 间接寻址获取物理 block
k_cache[physical_block_number, kv_head, physical_block_offset, vec_offset]
每个 warp 的 thread group 处理 block 中的不同 token
```

#### QK 计算 + Softmax

```
1. QK dot product（thread group 内规约） + scale + ALiBi bias
2. logits[] 存储到共享内存
3. qk_max = warp-reduce(fmax) → block-reduce(fmax) → broadcast
4. exp_sum = sum(exp(logits[i] - qk_max)) → block_reduce
5. logits = exp(logits - qk_max) / exp_sum  (softmax)
```

#### V 计算 + 输出

```
1. 按 block 迭代，从 v_cache[physical_block, kv_head, head_size, block_size] 读取
2. v_vec 与 logits_vec 做 dot product → accs[NUM_ROWS_PER_THREAD]
3. Warp 内规约 accs → Warp 间规约 accs
4. 最终输出到 out[seq_idx, head_idx, head_size]
```

#### V1 vs V2

| 特性 | V1 | V2 |
|------|----|----|
| Grid Z 维度 | 1（无分区） | max_num_partitions |
| PARTITION_SIZE | 0 | 512（默认） |
| 适用场景 | 短序列 | 长序列 |
| 工作机制 | 单 kernel 完成全部计算 | 多个 partition 并行 + Reduce 合并 |

V2 的分区合并策略：
```
1. V2 Kernel: 每个 partition 计算部分 KV blocks 的 attention
   输出: tmp_out[partition], exp_sums[partition], max_logits[partition]
2. Reduce Kernel: 用 LSE (Log-Sum-Exp) 算法合并各 partition:
   global_max = max(max_logits[:])
   weight[i] = exp_sums[i] * exp(max_logits[i] - global_max)
   out = sum(tmp_out[i] * weight[i]) / sum(weight)
```

#### ROCm 变体

`csrc/rocm/attention.cu` 使用 AMD MFMA 指令实现了相同算法。

### 层次 4：Python 接口层

**`vllm/v1/attention/ops/paged_attn.py`**：
```python
class PagedAttention:
    @staticmethod
    def split_kv_cache(kv_cache, num_kv_heads, head_size):
        # 将 [2, num_blocks, block_size, num_kv_heads, head_size]
        # 拆成 key_cache 和 value_cache
        # key: view(num_blocks, num_kv_heads, head_size//x, -1, x)
        # value: view(num_blocks, num_kv_heads, head_size, -1)

    @staticmethod
    def write_to_paged_cache(key, value, key_cache, value_cache, slot_mapping, ...):
        # 调用 ops.reshape_and_cache 将新 K/V 写入分页缓存
```

**`vllm/_custom_ops.py`**：
```python
paged_attention_v1(out, query, key_cache, value_cache, num_kv_heads, scale,
                   block_tables, seq_lens, block_size, max_seq_len, ...)
paged_attention_v2(out, exp_sum, max_logits, tmp_out, query, key_cache, ...)
paged_attention_rocm(out, exp_sum, max_logits, tmp_out, query, ...)
```
这三个函数是 PyTorch 自定义 C++ 拓展 (`torch.ops._C`) 的 Python 包装器。

---

## 三、注意力后端集成

PagedAttention 被多个注意力后端使用：

| 后端 | 文件 | 使用方式 |
|------|------|---------|
| ROCm | `vllm/v1/attention/backends/rocm_attn.py` | 直接用 `PagedAttention.split_kv_cache/write_to_paged_cache` |
| Triton Unified | `vllm/v1/attention/ops/chunked_prefill_paged_decode.py` | 自己实现了 Triton 版分页注意力 `kernel_paged_attention_2d` |
| FlashInfer | `vllm/v1/attention/backends/flashinfer.py` | 使用 FlashInfer 库自带的 `BatchDecodeWithPagedKVCacheWrapper` |
| FlashAttention | `vllm/v1/attention/backends/flash_attn.py` | 使用 `flash_attn_with_kvcache` 的变长分页模式 |

---

## 四、KV 缓存的完整生命周期

```
1. 模型 forward
   → Attention 层计算新 K/V tensor（当前 token）
   → PagedAttention.write_to_paged_cache(key, value, key_cache, value_cache, slot_mapping)
   → reshape_and_cache 将 [num_tokens, heads, dim] → [blocks, block_size, heads, dim]

2. 调度器调度
   → KVCacheManager.get_num_blocks_to_allocate(request)
   → BlockPool.allocate(num_blocks)
   → 返回 KVCacheBlocks(blocks=[KVCacheBlock(block_id=3), ...])

3. Worker 准备输入
   → BlockTables.append_block_ids(req_index, new_block_ids)
   → 构建 input_block_tables: [num_reqs, max_blocks] 的 int32 tensor
   → 传递给 CUDA kernel

4. CUDA kernel 执行 PagedAttention
   → 通过 block_table[seq_idx] 查物理 block_id
   → k_cache[physical_block, kv_head, ...] 读取 K
   → v_cache[physical_block, kv_head, ...] 读取 V
   → 计算 attention 输出

5. 请求完成
   → KVCacheManager.free(request)
   → BlockPool.free(block_ids)
   → 物理块回收复用
```

---

## 五、关键设计决策

1. **K/V 内存布局不同**：K 使用交错布局 `[num_blocks, num_kv_heads, head_size/x, block_size, x]` 以支持 16 字节合并读取；V 使用 `[num_blocks, num_kv_heads, head_size, block_size]` 布局，因读取模式不同。

2. **分区支持**：V2 内核针对长序列将 KV 序列切分为 `PARTITION_SIZE=512` 的分区并行计算，最后用 LSE 归约合并，避免了单个线程块的共享内存瓶颈。

3. **块稀疏注意力**：内核编译时支持 `IS_BLOCK_SPARSE`，在循环中跳过不参与的 block，结合 `blocksparse_vert_stride` 和 `blocksparse_local_blocks` 参数实现。

4. **FP8 KV 缓存**：支持 4 种精度（Auto/Fp8E4M3/Fp8E5M2），读取时通过 `fp8::scaled_convert` 在线反量化，减少缓存内存占用。

5. **前缀缓存**：通过 `BlockHash` 计算块哈希值，相同前缀的请求共享物理块，`enable_caching=True` 时在 `SingleTypeKVCacheManager` 中实现。

---

## 六、参考文件索引

### Python 层
- `vllm/v1/attention/ops/paged_attn.py` — PagedAttention 类定义
- `vllm/_custom_ops.py` — paged_attention_v1/v2/rocm Python 包装器
- `vllm/_aiter_ops.py` — ROCm AIter 库绑定
- `vllm/v1/attention/ops/chunked_prefill_paged_decode.py` — Triton 分页注意力内核
- `vllm/v1/worker/gpu/block_table.py` — GPU Block Table 管理
- `vllm/v1/core/kv_cache_manager.py` — KV 缓存管理器
- `vllm/v1/core/single_type_kv_cache_manager.py` — 单类型 KV 缓存管理
- `vllm/v1/core/kv_cache_utils.py` — KVCacheBlock 数据结构

### CUDA 内核
- `csrc/libtorch_stable/attention/attention_kernels.cuh` — paged_attention_kernel 核心设备函数
- `csrc/libtorch_stable/attention/paged_attention_v1.cu` — V1 内核启动器
- `csrc/libtorch_stable/attention/paged_attention_v2.cu` — V2 内核启动器 + Reduce 内核
- `csrc/libtorch_stable/attention/attention_utils.cuh` — QK 点积辅助函数
- `csrc/rocm/attention.cu` — ROCm 分页注意力实现
- `csrc/attention/attention_generic.cuh` — 通用注意力 CUDA 头文件
- `csrc/attention/attention_dtypes.h` — FP16/FP32/BF16/FP8 dtype 定义

### 注意力后端
- `vllm/v1/attention/backends/rocm_attn.py` — ROCm 注意力后端（直接使用 PagedAttention）
- `vllm/v1/attention/backends/rocm_aiter_fa.py` — ROCm AIter 后端
- `vllm/v1/attention/backends/flash_attn.py` — FlashAttention 后端
- `vllm/v1/attention/backends/flashinfer.py` — FlashInfer 后端
- `vllm/v1/attention/backends/triton_attn.py` — Triton 注意力后端
- `vllm/v1/attention/backend.py` — 注意力后端抽象基类
- `vllm/v1/attention/selector.py` — 后端选择逻辑

### 测试和文档
- `tests/kernels/attention/test_attention.py` — PagedAttention 测试
- `benchmarks/kernels/benchmark_paged_attention.py` — 性能基准测试
- `docs/design/paged_attention.md` — 原始设计文档
