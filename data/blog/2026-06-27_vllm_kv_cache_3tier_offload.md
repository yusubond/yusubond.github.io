---
title: 'vLLM v1 的 KV Cache 三级缓存是怎么做的？'
date: '2026-06-27'
tags: ['vLLM', 'KV Cache', 'KV Offload', 'LLM推理', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

> 写给后端研发。基于 vLLM 源码（v1 引擎主干）分析。代码块为逐字精简摘录，结论标注 `文件:行号`；想深挖对着文件看即可。

---

## 0. 先说清"三级"指什么

大模型推理时，每个 token 算出的 K/V 要存起来给后续 attention 用，这就是 **KV cache**。它占显存极大（往往比权重还大），而 GPU 显存（HBM）有限——请求一多、上下文一长就放不下。

vLLM 的解法是把 KV cache 做成**多级存储层次**，像 CPU 的 L1/L2/L3 一样，热数据在快的小介质，冷数据在慢的大介质：

| 层级 | 介质 | 角色 | vLLM 里的名字 |
|---|---|---|---|
| **L1（主层/热）** | GPU HBM | attention 直接读写 | paged KV cache（GPU block pool） |
| **L2（主层 offload）** | CPU DRAM（pinned） | GPU 放不下的 KV 换出来 | **CPU primary tier** |
| **L3（二级层）** | 磁盘 / 对象存储 / 网络 | CPU 也放不下的再下沉 | **secondary tier**（fs / obj） |

源码里的级联语义（`vllm/v1/kv_offload/tiering/base.py:43` 注释）一句话讲透：

```
Secondary tiers cannot directly access GPU memory. All data transfers
must go through the CPU (primary) tier:
  - Store: GPU -> CPU (primary) -> secondary  (cascade)
  - Load:  secondary -> CPU (primary) -> GPU  (promotion)
```

- **Store（下沉）**：GPU → CPU → secondary，逐级**级联**。
- **Load（上浮）**：secondary → CPU → GPU，逐级**提升（promotion）**。

secondary 层**不能直接碰 GPU**，必须经 CPU 中转——因为 GPU↔磁盘没有直连，而 CPU↔磁盘、GPU↔CPU 都通畅。

> ⚠️ 关键认知：**整个三级 offload 是作为一种「KV connector」实现的**（复用了 P/D 分离的 KV transfer 框架）。它跑在调度器进程里，通过标准 connector 钩子被驱动。这点后面会展开。

---

## 1. 全景图

```
                     ┌───────────────────────────────────────────────┐
                     │  v1 Scheduler（schedule 一步）                 │
                     │    self.connector : KVConnectorBase_V1         │
                     │    （三级 offload 是其中一种实现）               │
                     └─────────────────────┬─────────────────────────┘
                                           │ lookup / prepare_load
                                           │ prepare_store / touch
                                           ▼
                     ┌───────────────────────────────────────────────┐
                     │  OffloadingManager（跑在 scheduler 进程）       │
                     │    跟踪哪些 block 在哪一层（账本，不搬数据）     │
                     └─────────────────────▲─────────────────────────┘
                                           │ complete_* / take_events
   ┌───────────────────────────────────────┴──────────────────────────┐
   │  worker: OffloadingHandler（跑在 worker 进程）—— 真正搬运 KV 张量   │
   └──────────┬───────────────────────────────────────┬───────────────┘
              │ GPU↔CPU swap kernel                     │ GPU↔CPU swap kernel
              ▼                                         ▼
   ┌─────────────────────┐   级联 / 提升 store / load   ┌─────────────────────┐
   │ L1  GPU HBM         │ ◄─────────────────────────► │ L2  CPU DRAM         │
   │   （paged KV）       │                             │ （pinned mmap）       │
   └─────────────────────┘                             │ /dev/shm/...mmap     │
                                                       └──────────┬──────────┘
                                              async cascade（CPU→sec）│
                                                                        ▼
                                          ┌────────────────────────────────────┐
                                          │ L3  secondary tier                 │
                                          │   fs: 本地文件 / obj: S3 兼容 / example │
                                          └────────────────────────────────────┘
```

关键分工：
- **Manager（scheduler 进程）**：只做"账本"——记录哪个 block 在哪一层、引用计数、淘汰决策。本身**不搬数据**，只产出"搬哪些、从哪到哪"的描述（`LoadStoreSpec`）。
- **Handler（worker 进程）**：拿到描述后，在 GPU 上真正执行张量拷贝。
- **secondary tier**：CPU↔磁盘/网络的 I/O，异步线程池/NIXL。

---

## 2. 核心抽象：`OffloadingManager`（跑在调度器里的"账本"）

`vllm/v1/kv_offload/base.py:150`。它定义了一套原语（`base.py:102-126` 注释逐字列出）：

| 原语 | 作用 |
|---|---|
| `lookup(key)` | 查某个 block 是否已在 offload 层且可读。返回 `True/False/None`，**`None` = 正在传输中，下轮再试**（会延迟该请求） |
| `prepare_load(keys)` | 准备读：pin 住这些 block（防淘汰），返回 `LoadStoreSpec` 给 worker 去搬 |
| `complete_load(keys)` | 搬完了，解除 pin |
| `touch(keys)` | 标记"最近用过"（更新 LRU），但不 pin、不读 |
| `prepare_store(keys)` | 准备写：分配 CPU 槽位、按需淘汰、返回要写哪些 + 淘汰了哪些 |
| `complete_store(keys)` | 写完了，这些 block 变成"可被 load" |
| `on_new_request` / `on_request_finished` | 请求生命周期钩子 |
| `take_events` / `on_schedule_end` / `has_pending_work` | 每步收尾、刷延迟工作、告诉引擎"我还有活没干完，继续 stepping" |

**block 的标识**：`OffloadKey = block_hash + group_idx`（`base.py:36-48`），打包成裸 bytes 避免 tuple 的 GC 开销。`group_idx` 是 KV cache group（多头注意力/MLA 等不同组）。

**block 的搬运描述**：`LoadStoreSpec` 系列（`base.py:71`），关键的两种：
- `GPULoadStoreSpec`（`medium() == "GPU"`）：带 `block_ids`、`group_sizes`、`block_indices`。后两者是为了处理"offload block 比 GPU block 大"（`block_size_factor`）时第一个 block 不对齐的情况。
- `CPULoadStoreSpec`（`medium() == "CPU"`）。

worker 端就是按 `(src.medium(), dst.medium())` 路由到对应的搬运 handler。

**canonical 化**：不同 attention 后端的 KV 张量布局不同（比如 FlashAttention 是 `(2, num_blocks, ...)`），`CanonicalKVCaches`（`base.py:405`）把它们统一成 `(num_blocks, page_size_bytes)` 的 int8 视图，这样搬运逻辑跟后端无关。

---

## 3. 三级的编排：`TieringOffloadingManager`

`vllm/v1/kv_offload/tiering/manager.py:111`。它把上面的原语实现成"CPU primary + 一堆 secondary tier"的编排。两条主线：

### 3.1 Store 级联（GPU → CPU → secondary）

分两段（`manager.py:397` / `manager.py:481`）：

```python
# prepare_store: 只做 GPU->CPU 这半段
primary_result = self.primary_tier.prepare_store(keys, req_context)

# complete_store: GPU->CPU 拷完确认后, 再级联到所有 secondary tier
for tier in self.secondary_tiers:
    primary_blocks_spec = self.primary_tier.prepare_read(keys, req_context)  # pin 住
    job_metadata = JobMetadata(job_id=..., keys=keys,
        block_ids=primary_blocks_spec.block_ids, is_promotion=False, ...)
    tier.submit_store(job_metadata)   # 异步 CPU->sec
```

要点：
- **级联是异步的**，且只在 GPU→CPU 拷贝确认完成后才发起（避免读到半成品）。
- 级联时对 primary block 取**读引用（ref_cnt++）**，保证 CPU→sec 传输期间这块不被淘汰。
- `is_promotion=False` 标记"这是下沉级联，不是上浮"。

#### 何时触发、下沉哪些 block

上面两段是"级联怎么走"，而"何时走、走哪些"由调度器侧 connector 在每步 `schedule()` 步末决定。入口是 `OffloadingConnectorScheduler.build_connector_meta`（`offloading/scheduler.py:997`），它调 `_build_store_jobs`（`:819`）逐请求收集待下沉 block：

```python
# offloading/scheduler.py:819  _build_store_jobs (精简)
num_offloadable_tokens = min(
    req.num_computed_tokens + num_scheduled_tokens,   # 只有"已算完"的 token 才有 KV 可存
    req.num_tokens)
if self.config.offload_prompt_only:                   # 默认 True: 钳到 prompt 长度
    num_offloadable_tokens = min(num_offloadable_tokens, req.num_prompt_tokens)

num_blocks = num_offloadable_tokens // group_config.offloaded_block_size
start_block_idx = group_state.next_stored_block_idx  # 增量游标: 上次下沉到哪
if num_blocks <= start_block_idx:
    continue                                           # 本步无新增, 跳过
offload_keys = group_state.offload_keys[start_block_idx:num_blocks]  # 只取还没下沉过的那段
# ... 再过滤 sliding window / SSM 不可达的 block (block_id==0 等) ...
store_output = self.manager.prepare_store(new_offload_keys, req_status.req_context)
```

四条筛选逻辑（对应 `scheduler.py:831-893`）：
1. **请求本步有新计算的 token**：`num_offloadable_tokens = num_computed_tokens + num_scheduled_tokens`，没算过的 token 没有 KV 可存。
2. **默认只下沉 prompt 段**：`offload_prompt_only=True` 钳到 `num_prompt_tokens`，`next_stored_block_idx` 不越过 prompt 边界 → decode 段永不下沉（`scheduler.py:843-846`）。
3. **增量下沉**：`next_stored_block_idx` 游标只取 `[start:num_blocks]` 这段新增，不重复。
4. **跳过不可达 block**：sliding window / SSM 跳过的（`block_id==0`）、SWA 对齐段里 load 永远命不中的。

store 的两段式时序（前段"决定 + CPU 占位"在步末，后段"真拷 + 级联"跨到下步）：

```
store 的两段式时序（前段"决定 + CPU 占位"在步末，后段"真拷 + 级联"跨到下步）

═══════════════════ Step N 步末 ═══════════════════
 Scheduler.build_connector_meta
   │
   └─► _build_store_jobs → Mgr.prepare_store(keys)
                  └─► CPU：分配 slot / LRU·ARC 淘汰
   ◄── Mgr 返回 store_spec（keys_to_store）
   ※ 此时只做"账本"：决定搬哪些、在 CPU 占位

═════════════════ Step N+1 开头（延迟到步首，不挡采样）════════════════
 Worker（独立 CUDA stream）：swap kernel GPU→CPU
   ◄── 完成后报告 Scheduler：GPU→CPU done

═══════════════════ Step N+1 前向后 ═══════════════════
 Scheduler → Mgr.complete_store(keys)            (scheduler.py:1106)
   ├─► CPU.complete_store → 标记这些 block 可读
   └─► 对每个 secondary tier（fan-out 复制）：
         · CPU.prepare_read（ref_cnt++ 保护传输中块）
         · Sec.submit_store：异步 CPU→sec（is_promotion=False）
```

> ⚠️ **关键纠正："一层一层" ≠ "满了才溢出"**。三级 offload 不像 CPU 的 L1/L2/L3 那样"上一层满了才把冷的溢到下一层"。源码事实：①**不是容量溢出触发**——只要请求有新算完的 prompt block，每步都主动尝试下沉，CPU 容量不够时是"淘汰腾位 / 放弃本次"（`cpu/manager.py:166`），而非"满了才触发"；②**级联是 fan-out 复制**——`complete_store` 里 `for tier in self.secondary_tiers: tier.submit_store(...)`，GPU→CPU 成功后**同一批 block 同时往所有 secondary 各存一份**，不是"CPU 满了才往 secondary 推"；③**"一层一层"指数据流向的逐跳推进 + 前一跳确认才发后一跳**（防读到半成品），是**时序级联**，不是**容量溢出**。这才是 §0 `base.py` 注释 "Store: GPU → CPU → secondary (cascade)" 里 cascade 的真正含义。

### 3.2 Load 提升（secondary → CPU → GPU）

由 `lookup` 驱动（`manager.py:228`）：primary miss → 查 secondary → 命中就 `_initiate_promotion`：

```python
def _initiate_promotion(self, tier, key, req_context) -> bool:
    primary_write_result = self.primary_tier.prepare_write([key], req_context)
    if primary_write_result is None:
        return False  # primary 满了, 放弃提升
    ...
    return True
```

- 提升时**立刻**在 primary 占槽（`ref_cnt=-1` 标记"传输中"），这样同一步内重复 lookup 不会重复触发。
- 真正的 `submit_load` **延迟到步末**批量提交（`on_schedule_end` → `_flush_pending_promotions`，`manager.py:320`），按 (tier, request) 攒批，减少提交次数。
- 完成后（`_process_finished_jobs`，`manager.py:192`）：提升完成 → `primary_tier.complete_write`（标记可读）；级联完成 → `primary_tier.complete_read`（解 pin）。

### 3.3 `has_pending_work`：让引擎继续跑

```python
# manager.py:581
def has_pending_work(self):
    return bool(self._transfer_jobs) or any(
        tier.has_pending_work() for tier in self.secondary_tiers)
```

只要有异步传输在飞，就返回 True，引擎即使没新请求也会继续 stepping 来 poll 完成事件——否则异步级联/提升的结果永远没人收。

### 3.4 下沉的 block 怎么标识：prompt 段、内容哈希与前缀复用

一个易混点要先澄清：`offload_prompt_only` 里的 "prompt block" 和**前缀缓存（prefix cache）是两件事**，但用的是**同一套内容哈希**，所以下沉的 prompt block 客观上构成了 CPU/secondary 上的一层前缀缓存。

**prompt block 的定义**：一个请求 = **prompt 段**（输入，prefill 一次性算出）+ **decode 段**（生成的新 token，逐个算出）。`offload_prompt_only=True`（默认，`base.py:447-453`）只下沉前者，decode 段不下沉。

**block 的标识复用了前缀缓存的哈希**：

```python
# base.py:31-38
OffloadKey = NewType("OffloadKey", bytes)
def make_offload_key(block_hash: bytes, group_idx: int) -> OffloadKey:
    return OffloadKey(block_hash + group_idx.to_bytes(4, "big", signed=False))
```

其中 `block_hash` 取自 `req.block_hashes`（`offloading/scheduler.py:262-271` 的 `update_offload_keys` 逐块 `make_offload_key(req_block_hash, ...)`）——这正是 vLLM 前缀缓存用的同一套内容哈希（`request.py:179` `block_hashes: list[BlockHash]`）。

后果：
- 多个请求共享的 prompt 前缀 → 相同内容 → 相同 `block_hash` → 相同 `OffloadKey` → 在 CPU/secondary **只存一份、按内容去重**。
- 后到的请求 `lookup` 能命中先到请求下沉的块 → 下沉的 prompt block 在 CPU/secondary 上构成一层**跨请求前缀缓存**。
- 默认 `BLOCK_LEVEL` 策略（`base.py:57-60`）会**跳过"已被前序请求下沉过的命中块"**不重复下沉；`REQUEST_LEVEL` 才会把整段（含命中）都下沉（`manager.py:432-442`）。

> 一句话：`offload_prompt_only` 管的是 **prompt/decode 边界**；前缀复用是 OffloadKey 复用内容哈希带来的**附带语义**，不是这个开关本身。

### 3.5 下沉过程实例：4 个并发请求

**配置**：offloaded `block_size=16`（GPU block 同 16，`block_size_factor=1`）；`offload_prompt_only=True`；一个 secondary tier = `fs`；CPU primary 容量足够；默认 `BLOCK_LEVEL`。

**请求**（Pi = 内容哈希标识的 block 身份，**加粗**为共享前缀）：

| 请求 | prompt | block 序列 |
|---|---|---|
| R1 | 48 tok | **P1, P2**, P3 |
| R2 | 48 tok | **P1, P2**, P4 |
| R3 | 32 tok | P5, P6（完全不同）|
| R4 | 48 tok | **P1, P2**, P7 |

P1、P2 被 R1/R2/R4 共享。4 个请求共 11 个 block-instance，但唯一 block 只有 7 个。

**Step N**（4 个请求 prefill 刚算完，prompt KV 已在 GPU）：步末 `build_connector_meta` → `_build_store_jobs` 逐请求跑：

| 请求 | num_offloadable | prompt_only 钳位 | num_blocks (÷16) | next_stored_idx | 候选 keys | `prepare_store` 后 CPU 新增 |
|---|---|---|---|---|---|---|
| R1 | 48 | 48 | 3 | 0→3 | K(P1),K(P2),K(P3) | **P1,P2,P3**（全新）|
| R2 | 48 | 48 | 3 | 0→3 | K(P1),K(P2),K(P4) | **仅 P4**（P1,P2 已被 R1 放进 CPU，命中跳过）|
| R4 | 48 | 48 | 3 | 0→3 | K(P1),K(P2),K(P7) | **仅 P7**（同上）|
| R3 | 32 | 32 | 2 | 0→2 | K(P5),K(P6) | **P5,P6**（全新）|

依据：`primary_tier.prepare_store` 只返回"primary 里还没有的新块"（`manager.py:423-427` "new blocks only"）；`BLOCK_LEVEL` 下命中块不重复下沉（`base.py:57-60`）。

> CPU primary 最终只有 **7 个唯一块**（P1..P7），不是 11 个 —— 内容哈希去重 / 前缀复用在 offload 层的直接体现。

**Step N+1 开头**：worker 执行 GPU→CPU 实际拷贝（`offloading_connector.py:111-118`，`get_finished`→`prepare_store_kv`），独立 CUDA stream 上 swap kernel 把各批 `keys_to_store` DMA 到 CPU primary 的 slot。

**Step N+1 前向后**：`complete_store`（`scheduler.py:1106` → `manager.py:481`）：①`primary_tier.complete_store` 标记可读；②对 fs tier `prepare_read`（`ref_cnt++`）→ `submit_store` 异步 CPU→fs。fs 也得到 P1..P7（**fan-out，非溢出**）。

**Step N+2**（R1 已 decode 出 20 token，`num_computed_tokens=68`）：R1 的 `_build_store_jobs`：`prompt_only` 钳到 48 → `num_blocks=3`，`next_stored_idx` 已是 3 → `3 <= 3` → `continue`，**无新增下沉**。decode 段（第 49~68 token）永不下沉 —— 正演示 `offload_prompt_only` 的边界。

**容量不够时**：若 CPU primary 容量不够、淘汰也凑不齐 → `prepare_store` 返回 `None` → 该请求本次 store 失败（`scheduler.py:902-903` 打 warning、不重试，下步再来）。这是 CPU 层内部腾位，不是触发条件。

---

## 4. CPU primary tier：零拷贝 mmap + LRU/ARC 淘汰

### 4.1 SharedOffloadRegion —— 一块所有 worker 共享的 mmap

`vllm/v1/kv_offload/cpu/shared_offload_region.py:28`。这是 CPU 层的物理存储：

- 位于 `/dev/shm/vllm_offload_{instance_id}.mmap`（`shared_offload_region.py:36`），**同一 vLLM 实例的所有 TP worker 共享**。
- 一个 worker 赢得 `O_CREAT|O_EXCL` 竞争创建并 `ftruncate`，其余打开并等大小就绪（`:64-78`）。
- 布局按 worker 交错：`w0_b0 | w1_b0 | ... | w0_b1 | w1_b1 | ...`（`:122-133`）。
- 用 `MADV_POPULATE_WRITE` 预_fault 页面，避免首次访问缺页（`:88-114`）。
- **pinned memory 是事后注册的**：mmap 本身不 pinned，`CpuGpuOffloadingHandlers.__init__` 调 `cudaHostRegister` 把整块注册成 pinned（`gpu_worker.py:126-153`）。失败不致命，退化为非 pinned DMA。

**零拷贝契约**（`shared_offload_region.py:159`）——这是 secondary tier 能高效读 CPU 数据的关键：

```python
def create_kv_memoryview(self) -> memoryview:
    kv_tensor = self._base.view(self.num_blocks, self._row_stride)
    np_arr = kv_tensor.numpy()
    assert np_arr.ctypes.data == self._base.data_ptr(), (
        "view()/numpy() created a copy instead of sharing the mmap buffer; "
        "secondary tiers require zero-copy access to primary KV data")
    return memoryview(np_arr)
```

secondary tier 读 block `b` 就是直接 `view[b]` 索引同一块物理页，**没有中间 staging buffer**。

### 4.2 block 跟踪

`CPUOffloadingManager`（`cpu/manager.py:35`）维护：
- `_free_list`：回收的 block id 栈。
- `_num_allocated_blocks`：已分配高水位。
- `_policy`：`CachePolicy`，持有 `OffloadKey -> BlockStatus` 映射（地址表）。`BlockStatus`（`policies/base.py:10`）是 ctypes 结构：`ref_cnt`（-1 = 传输中未就绪）、`block_id`。

### 4.3 淘汰策略：LRU / ARC

配置项 `eviction_policy`（`cpu/spec.py:112`，默认 `"lru"`，可选 `"arc"`）。

**LRU**（`cpu/policies/lru.py:12`）：一个 `OrderedDict`，`touch` 移到 MRU 端，`evict` 从冷端扫 `ref_cnt==0` 且不在 protected 集合的：

```python
def evict(self, n, protected):
    for key, block in self.blocks.items():
        if block.ref_cnt == 0 and key not in protected:
            candidates.append((key, block))
            if len(candidates) == n: break
    if len(candidates) < n: return None   # 淘汰不够, 原子地不改状态
    ...
```

**ARC**（`cpu/policies/arc.py:12`）：自适应替换缓存，4 个链表（T1 近、T2 频、B1/B2 幽灵链），`target_t1_size` 根据 ghost hit 自适应调整（`arc.py:75-101`）——比 LRU 更抗扫描、抗混合负载。

**何时触发淘汰**：`prepare_store` 里算容量缺口（`cpu/manager.py:166`）：

```python
num_blocks_to_evict = len(keys_to_store) - self._get_num_free_blocks()
if num_blocks_to_evict > 0:
    if num_blocks_to_evict > self._num_evictable_cache_blocks:
        return None   # 淘汰也凑不齐, 整个 store 失败
    evicted = self._policy.evict(num_blocks_to_evict, protected)
```

淘汰不够就返回 `None`，store 失败——**不会无限重试**，而是把这块当作"不可用"。

---

## 5. Secondary tier（第三层）：fs / obj / example

通过 `SecondaryTierFactory` 注册（`tiering/factory.py:55`）：

| type 字符串 | 类 | 介质 | 同步/异步 | 容量管理 |
|---|---|---|---|---|
| `example` | `ExampleSecondaryTierManager` | Python dict（内存） | 同步立即完成 | 无（参考实现） |
| `fs` | `FileSystemTierManager` | 本地文件（`.bin`, O_DIRECT） | 异步线程池（16读+16写） | 写时 `os.path.exists` 去重，无显式淘汰 |
| `obj` | `ObjectStoreSecondaryTierManager` | S3 兼容对象存储（经 NIXL） | 异步 NIXL transfer + 轮询 | 无（依赖对象存储容量） |

### 5.1 SecondaryTierManager 契约

`tiering/base.py:42`。构造函数：`(offloading_spec, primary_kv_view: memoryview, tier_type)`。必须实现：

```python
lookup(key) -> bool|None          # 同 OffloadingManager.lookup 契约
submit_store(job_metadata)        # 异步 GPU->CPU->sec 级联
submit_load(job_metadata)         # 异步 sec->CPU 提升准备
get_finished_jobs() -> [JobResult]  # 轮询完成
on_new_request(req_context)
drain_jobs()                      # 阻塞到所有在飞 I/O 完成 (reset_cache 用)
```

**所有方法跑在 scheduler 进程，必须轻量非阻塞**——只提交异步任务，不在调用线程搬数据（`base.py:90-115`）。

### 5.2 fs tier：本地文件

- 路径布局由 `FileMapper`（`file_mapper.py:112`）决定：`<base>_r<rank>/<hhh>/<hh>_g<group_idx>/<hash>.bin`，base 是 `<root>/<model>_<sha256前12位>/`。
- **原子写**：先写 `<dest>.tmp`，再 `os.replace` 成正式名（`fs/io.py:32`）。写前 `os.path.exists` 去重。
- **读**：`O_RDONLY|O_DIRECT` + `os.readv` 直接读进 memoryview 切片；读失败就删文件防重复损坏（`fs/io.py:75`）。
- 双队列线程池 `DualQueueThreadPool`：读写两组线程共享一个条件变量，读优先线程先排空 `_load_q` 再 `_store_q`（`fs/thread_pool.py`）。

### 5.3 obj tier：S3 兼容（经 NIXL）

- 用 NIXL 的 "OBJ" 后端连 S3 兼容存储（`obj/manager.py`），配置 `bucket/endpoint/access_key/...`（`obj/config.py`）。
- block key 复用 `FileMapper.get_file_name()`，所以**同一个 block 在 fs 和 obj 里 key 相同**——存储后端可互换。
- I/O：NIXL `register_memory → prep_xfer_dlist → make_prepped_xfer → transfer`，`check_xfer_state` 轮询完成（`obj/manager.py:169-269`）。

### 5.4 async_lookup：lookup 不阻塞调度器

`tiering/async_lookup.py`。secondary 的 lookup（查磁盘/对象存储）慢，不能在调度器线程同步做。设计：

- 一个后台守护线程 `vllm_offloading_lookup_{tier_type}`（`:100-105`）。
- 调度器线程把 key 攒进 `_lookup_batch`，首次见到某 key 时**返回 `None`**（`:125-145`）——按 lookup 契约，`None` 让调度器本轮跳过、下轮再试。
- 后台线程批量 `batch_lookup`（如 fs 的 `os.path.exists`、obj 的 `query_memory`），结果在 `drain_results` 回灌，下轮 lookup 就能命中。

---

## 6. Worker 侧：GPU↔CPU 真正的搬运

### 6.1 接口：按 `(src.medium(), dst.medium())` 路由

`worker/worker.py`。`OffloadingWorker` 是个 demux，持有 `dict[(src_medium, dst_medium), handler]`，`transfer_async(job_id, (src_spec, dst_spec))` 按两个 medium 字符串查 handler（`:118-150`）：

```python
def transfer_async(self, job_id, spec):
    src, dst = spec
    handler = self.transfer_type_to_handler.get((src.medium(), dst.medium()))
    success = handler.transfer_async(job_id, spec)
```

GPU↔CPU 的 handler 是 `SingleDirectionOffloadingHandler`（`cpu/gpu_worker.py`），各起一个（`gpu_to_cpu=True` / `False`），**共享同一组张量视图**。

### 6.2 搬运内核：swap_blocks

- **GPU→CPU 恒定用** `ops.swap_blocks_batch`（C++ 批量 DMA，带宽受限场景专用拷贝引擎胜过 Triton，`gpu_worker.py:43`）。
- **CPU→GPU** 小页（`<28KiB`）且 8 字节对齐时用 Triton `_swap_blocks_kernel`，否则回落 C++（`gpu_worker.py:50-61`）。

Triton 内核（`cpu/swap_blocks_triton.py:24`）就是**真正的 D2H/H2D 拷贝**（不是 GPU 内重排），解引用描述符数组里的裸虚拟地址：

```python
@triton.jit
def _swap_blocks_kernel(src_addrs, dst_addrs, sizes, n_jobs, BYTES_PER_CHUNK):
    pid = tl.program_id(0); num_progs = tl.num_programs(0)
    job = pid
    while job < n_jobs:
        src = tl.load(src_addrs + job).to(tl.pointer_type(tl.int64))
        dst = tl.load(dst_addrs + job).to(tl.pointer_type(tl.int64))
        words = tl.load(sizes + job) // 8
        for start in range(0, words, WORDS_PER_CHUNK):
            idx = start + offsets; mask = idx < words
            data = tl.load(src + idx, mask=mask, other=0)
            tl.store(dst + idx, data, mask=mask)
        job += num_progs
```

### 6.3 时序：独立 CUDA stream，不挡前向

- 每次传输从池里借一个专用 `Stream` + start/end `Event`（`gpu_worker.py:371`）。
- **GPU→CPU**：swap stream 先 `wait_stream(计算流)`，确保模型算完的 KV 可见后才 DMA 出去（`:385`）；多次传输按 `end_event` 串行。
- **CPU→GPU**：源是 pinned host memory，driver 可重排读，`is_src_access_order_any=True`。
- 全异步，**模型前向路径上没有同步 memcpy**。

集成点：模型 runner 的 forward 被一对 connector 上下文管理器包住（`gpu_model_runner.py:4297`，`kv_connector_model_runner_mixin.py:77`）：

```
start_load_kv()          # 前向前: 提交 CPU->GPU load (含上步延迟的 store)
  yield -> _model_forward()   # 前向: attention 在计算流上跑
finally:
  get_finished()         # 前向后: 轮询完成, 把新的 store 排到下步开头
```

store 故意延迟到**下个 step 开头**才提交（`offloading/worker.py:276`），让 offload 在 token 采样相关传输之后才开始，避免拖慢 token 生成。

---

## 7. 调度器怎么驱动（connector 钩子序列）

三级 offload 是一种 `KVConnectorBase_V1`（`OffloadingConnector`，`distributed/kv_transfer/kv_connector/v1/offloading_connector.py:46`）。调度器**不认识 offload 细节**，只调通用 connector 钩子（`vllm/v1/core/sched/scheduler.py`）：

每步 `schedule()` 里的顺序：
1. **lookup（前缀命中式）**：对每个新请求，`connector.get_num_new_matched_tokens()` 问 offload 层有没有命中（`scheduler.py:723`）——三级系统里这就是查 CPU/secondary 有没有这段 KV。
2. **prepare_load**：`allocate_slots` 后，`connector.update_state_alloc()` 把 GPU 新块和 offload 命中块配对，准备异步 load（`scheduler.py:901`）。
3. **build_connector_meta（准备 store）**：步末 `connector.build_connector_meta()` 把待传输打包进 `SchedulerOutput.kv_connector_metadata`（`scheduler.py:1081`），三级系统里这里决定哪些 GPU 块要下沉。
4. **complete_*（收异步完成）**：模型输出回来后 `connector.update_connector_output()` 处理完成事件（`scheduler.py:2429`）。
5. **request_finished**：`connector.request_finished_all_groups()` 清理（`scheduler.py:2297`）。

> 注意 `on_request_finished` **不保证数据已落盘**——CPU→secondary 的异步级联可能还在飞（`base.py:266` 注释明确说）。这是 `has_pending_work` 存在的原因。

---

## 8. 还有套更简单的：`simple_kv_offload`（纯 2 级）

容易混淆：vLLM v1 有**两套**并列的 offload 实现：

| | 三级系统 `vllm/v1/kv_offload/` | 简单系统 `vllm/v1/simple_kv_offload/` |
|---|---|---|
| 层级 | GPU ↔ CPU ↔ secondary | **仅 GPU ↔ CPU**（2 级） |
| 搬运内核 | swap_blocks (C++/Triton) | `cuMemcpyBatchAsync` 原生批量 DMA |
| connector 名 | `OffloadingConnector` | `SimpleCPUOffloadConnector` |
| 复杂度 | 高（多 secondary 后端、淘汰策略、零拷贝 mmap） | 低（最小化） |
| 何时用 | 需要磁盘/对象存储第三层 | 只要把 KV 换到 CPU 即可 |

两者都是 `KVConnectorBase_V1`，**互斥**（`self.connector` 单槽，`scheduler.py:127`）。要同时用 P/D 传输 + 本地 offload，得靠 `MultiConnector`（`multi_connector.py:128`）组合。

简单系统的关键点：
- `_derive_cpu_config`（`manager.py:189`）按显存比例从 GPU 配置派生 CPU 配置。
- worker 用后台线程跑 `DmaCopyBackend`，`copy_blocks` 走 `cuMemcpyBatchAsync`（`cuda_mem_ops.py:157`）。
- `start_load_kv`/`save_kv_layer` 都是 no-op，load/store 全在 `get_finished()` 里发起（`worker.py:194`），躲在 GPU 计算后面藏掉约 5ms 的 CPU 端块拷贝开销。

---

## 9. 配置怎么开

三级 offload 通过 `--kv-transfer-config` 开启（它复用 KV transfer 配置入口），关键在 `kv_connector_extra_config`：

```bash
vllm serve <model> \
  --kv-transfer-config \
    '{"role": "dual", 
      "kv_connector": "OffloadingConnector",
      "kv_connector_extra_config": {
        "spec_name": "TieringOffloadingSpec",
        "cpu_bytes_to_use": 53687091200,   # 50GB CPU 主层
        "block_size": 32,                  # 可选, offload block 可大于 GPU block
        "eviction_policy": "arc",          # 可选, lru|arc
        "secondary_tiers": [
          {"type": "fs", "root_dir": "/data/kv_offload"},
          {"type": "obj", "bucket": "my-kv-bucket", "endpoint_override": "..."}
        ]
      }}'
```

字段含义（`tiering/spec.py` + `cpu/spec.py`）：
- `spec_name`：`"CPUOffloadingSpec"`（仅 2 级 GPU↔CPU）或 `"TieringOffloadingSpec"`（3 级）。顶层工厂 `kv_offload/factory.py:32` 按 `spec_name` 选。
- `cpu_bytes_to_use`：**必填**，CPU 主层字节数。
- `block_size`：可选，offload block 大小（须是 GPU block 的整数倍，`block_size_factor`）。
- `eviction_policy`：`lru`（默认）/ `arc`。
- `secondary_tiers`：二级层列表，每个 `{"type": "fs"|"obj"|"example", ...}`。
- `offload_prompt_only`：默认 `True`，只 offload prompt 块（decode 生成的块不下沉，适合会丢弃思考过程的推理模型）。

---

## 10. 设计要点回顾

1. **三级 = GPU(HBM) → CPU(pinned DRAM) → secondary(磁盘/对象存储)**，级联 store、逐级 promotion load，secondary 必经 CPU 中转。
2. **它是一种 KV connector**，复用 P/D 分离的 KV transfer 框架，跑在调度器进程，被通用 connector 钩子驱动——调度器本身**不感知 offload 细节**。
3. **Manager（账本）vs Handler（搬运）分离**：scheduler 进程只跟踪"哪个 block 在哪层"+ 淘汰决策，worker 进程才真正搬张量，两者用 `LoadStoreSpec` 解耦。
4. **零拷贝 mmap**：`/dev/shm` 共享区 + `cudaHostRegister` + `memoryview`，secondary tier 直接 `view[b]` 读 CPU 数据，无 staging。
5. **淘汰 LRU/ARC**，淘汰不够就 store 失败（不无限重试）；`ref_cnt` 保护传输中的块不被淘汰。
6. **全异步 + 延迟提交**：CPU→sec 级联、sec→CPU 提升都是异步，store 延迟到下步开头提交，`has_pending_work` 让引擎持续 poll 完成；搬运在独立 CUDA stream，不挡前向。
7. **lookup 的 `None` 契约**：secondary lookup 慢，首次返回 `None` 让调度器本轮跳过、下轮再试，避免阻塞。
8. **两套并列**：`simple_kv_offload`（2 级、原生 DMA、最小化）与 `kv_offload`（3 级、可扩展），按 connector 名二选一。
9. **下沉是请求驱动增量 + fan-out，不是容量溢出**：每步对"有新算完 prompt block"的请求**增量**下沉（`offload_prompt_only` 默认只下 prompt 段、decode 段不下沉）；GPU→CPU 确认后**对所有 secondary 各存一份（fan-out 复制）**，而非"上一层满了才溢到下一层"——"级联"是逐跳确认的时序，不是容量溢出。
10. **OffloadKey 复用前缀哈希**：`OffloadKey = block_hash + group_idx`，`block_hash` 取自 `req.block_hashes`（前缀缓存同一套内容哈希），所以共享前缀在 CPU/secondary **按内容去重、跨请求共享**，下沉的 prompt block 客观上构成一层前缀缓存；`BLOCK_LEVEL`（默认）还会跳过命中块不重复下沉。

---

## 附录：源码索引

| 主题 | 关键文件 |
|---|---|
| 核心抽象（OffloadingManager/Spec/Key） | `vllm/v1/kv_offload/base.py` |
| 三级编排（TieringOffloadingManager） | `vllm/v1/kv_offload/tiering/manager.py` |
| TieringOffloadingSpec（配置） | `vllm/v1/kv_offload/tiering/spec.py` |
| SecondaryTierManager 契约 | `vllm/v1/kv_offload/tiering/base.py` |
| secondary tier 注册工厂 | `vllm/v1/kv_offload/tiering/factory.py` |
| fs / obj / example secondary | `vllm/v1/kv_offload/tiering/{fs,obj,example}/` |
| async lookup | `vllm/v1/kv_offload/tiering/async_lookup.py` |
| block→文件/key 映射 | `vllm/v1/kv_offload/file_mapper.py` |
| CPU 主层管理 + 淘汰 | `vllm/v1/kv_offload/cpu/{manager,spec}.py`、`cpu/policies/{lru,arc}.py` |
| 共享 mmap（零拷贝） | `vllm/v1/kv_offload/cpu/shared_offload_region.py` |
| worker 搬运 handler | `vllm/v1/kv_offload/worker/worker.py`、`cpu/gpu_worker.py` |
| swap kernel | `vllm/v1/kv_offload/cpu/swap_blocks_triton.py` |
| 顶层 spec 工厂 | `vllm/v1/kv_offload/factory.py` |
| 简单 2 级 offload | `vllm/v1/simple_kv_offload/` |
| connector（调度器/worker 适配） | `vllm/distributed/kv_transfer/kv_connector/v1/offloading_connector.py` |
| 调度器钩子调用点 | `vllm/v1/core/sched/scheduler.py` |

> 行号随主干演进可能漂移，以最近 commit 为准。
