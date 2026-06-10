---
title: 'vLLM PD 分离架构实现详解'
date: '2026-06-07'
tags: ['vLLM', 'LLM推理', 'KV Cache', '技术', 'PD分离']
draft: false
authors: ['default']
layout: PostLayout
---

## 1. 整体架构：两进程 + 一代理

vLLM 的调度器内部确实没有区分 prefill/decode phase，但 PD 分离不是在调度器层面做的，而是在部署层面做的 — 启动两个独立的 vLLM 实例，一个专职 prefill，一个专职 decode，中间通过 **KV Connector** 传递 KV cache。

```
                         +-----------------+
    Client Request  ---> |  Proxy Server   |
                         |  (路由代理)      |
                         +--+-----------+--+
                            |           |
                   Step 1:  |           | Step 2:
                   Prefill  v           v  Decode
                +-----------+--+  +-----+----------+
                | Prefill Node  |  | Decode Node   |
                | (kv_producer) |  | (kv_consumer) |
                |               |  |                |
                | GPU 0         |  | GPU 1          |
                +------+--------+  +--------+-------+
                       |                      ^
                       |    KV Cache Transfer |
                       +----NCCL/RDMA/ZMQ----+
```

每个 node 都是一个完整的 vLLM 实例（有自己的 Scheduler、EngineCore、KVCacheManager），只是通过 `KVTransferConfig` 配置了不同的角色。

**源码依据：**
- `examples/disaggregated/disaggregated_prefill.py` — 基础 1P1D 示例，GPU 0 做 prefill (L18-19)，GPU 1 做 decode (L66-67)

## 2. 配置方式

通过 `KVTransferConfig` (`vllm/config/kv_transfer.py`) 指定角色：

```python
# Prefill 实例 (kv_producer)
ktc_prefill = KVTransferConfig(
    kv_connector="P2pNcclConnector",   # 传输实现
    kv_role="kv_producer",              # 角色：生产者
    kv_rank=0,                          # rank 0
    kv_parallel_size=2,                 # 参与传输的实例数
)

# Decode 实例 (kv_consumer)
ktc_decode = KVTransferConfig(
    kv_connector="P2pNcclConnector",
    kv_role="kv_consumer",              # 角色：消费者
    kv_rank=1,                          # rank 1
    kv_parallel_size=2,
)
```

三种角色定义（`vllm/config/kv_transfer.py:11-13`）：
- `kv_producer` — 只生产 KV cache（Prefill 节点）
- `kv_consumer` — 只消费 KV cache（Decode 节点）
- `kv_both` — 既生产又消费

`KVTransferConfig` 关键字段（`vllm/config/kv_transfer.py:23-71`）：

| 字段 | 含义 |
|------|------|
| `kv_connector` | Connector 类型名称 |
| `kv_role` | `kv_producer` / `kv_consumer` / `kv_both` |
| `kv_rank` | 传输中的 rank（0=prefill, 1=decode） |
| `kv_parallel_size` | 参与传输的实例数 |
| `kv_ip` / `kv_port` | 传输地址 |
| `kv_buffer_device` | buffer 设备 (`cuda` / `cpu` / `xpu`) |
| `kv_load_failure_policy` | 加载失败策略 (`recompute` / `fail`) |

属性方法（`vllm/config/kv_transfer.py:109-119`）：
- `is_kv_transfer_instance` — 是否配置了 KV 传输
- `is_kv_producer` — 是否为生产者
- `is_kv_consumer` — 是否为消费者

**源码依据：**
- `examples/disaggregated/disaggregated_prefill.py:37-42` — Prefill 配置 `kv_role="kv_producer"`, `kv_rank=0`
- `examples/disaggregated/disaggregated_prefill.py:81-86` — Decode 配置 `kv_role="kv_consumer"`, `kv_rank=1`
- `examples/disaggregated/disaggregated_prefill.py:31` — Prefill 使用 `max_tokens=1`

## 3. 请求流转过程

以 Proxy Demo (`examples/disaggregated/disaggregated_serving/disagg_proxy_demo.py`) 为例：

```
Step 1: Proxy -> Prefill Node
  - 请求被改写：max_tokens=1 (只做 prefill，生成1个token)
  - Prefill 实例执行 prefill，计算 KV cache
  - Worker-side connector 调用 save_kv_layer() 保存每层 KV
  - request_finished() 触发异步发送 KV 到 Decode 实例

Step 2: Proxy -> Decode Node
  - 原始请求被发送 (完整 max_tokens)
  - Decode 实例的 Scheduler 检测到外部有可用 KV cache
  - 请求进入 WAITING_FOR_REMOTE_KVS 状态
  - Worker-side connector 调用 start_load_kv() 接收 KV
  - KV 传输完成后，请求恢复为 RUNNING
  - 跳过 prefill，直接开始 decode
```

Proxy 的关键代码（`disagg_proxy_demo.py:250-278`）：

```python
async def create_completion(self, raw_request: Request):
    request = await raw_request.json()

    # Step 1: 发给 Prefill 节点，max_tokens=1
    kv_prepare_request = request.copy()
    kv_prepare_request["max_tokens"] = 1
    prefill_instance = self.schedule(self.prefill_cycler)
    async for _ in self.forward_request(
        f"http://{prefill_instance}/v1/completions", kv_prepare_request
    ):
        continue

    # Step 2: 发给 Decode 节点，原始请求
    decode_instance = self.schedule(self.decode_cycler)
    generator = self.forward_request(
        f"http://{decode_instance}/v1/completions", request
    )
    return StreamingResponse(generator)
```

Chat completion 同样处理（`disagg_proxy_demo.py:292-294`）：
```python
kv_prepare_request["max_tokens"] = 1
if "max_completion_tokens" in kv_prepare_request:
    kv_prepare_request["max_completion_tokens"] = 1
```

**源码依据：**
- `examples/disaggregated/disaggregated_serving/disagg_proxy_demo.py:254-255` — max_tokens=1
- `examples/disaggregated/disaggregated_serving/disagg_proxy_demo.py:257` — round-robin 调度
- `examples/disaggregated/disaggregated_serving/disagg_proxy_demo.py:268-271` — 转发原始请求

## 4. KV Connector 的双面设计

KV Connector 在两个层面运行：

```
+------------------+                          +------------------+
|  Prefill Node    |                          |  Decode Node     |
|                  |                          |                  |
| +-------------+  |  Scheduler-side metadata | +-------------+  |
| | Scheduler   |  |  (build_connector_meta)  | | Scheduler   |  |
| | Connector   |--+------------------------->| | Connector   |  |
| +-------------+  |                          | +-------------+  |
|        |         |                          |        |         |
| +-------------+  |  Worker-side KV transfer | +-------------+  |
| | Worker      |  |  (save_kv_layer /        | | Worker      |  |
| | Connector   |--+-- start_load_kv)         | | Connector   |  |
| +-------------+  |  via NCCL/RDMA/etc.      | +-------------+  |
+------------------+                          +------------------+
```

### Scheduler-side 接口 (`base.py:439-561`)

| 方法 | 作用 |
|------|------|
| `get_num_new_matched_tokens()` | 查询外部有多少 KV 可用 |
| `update_state_after_alloc()` | 分配 block 后更新状态 |
| `build_connector_meta()` | 构建调度元数据传给 Worker |
| `request_finished()` | 请求完成时触发 KV 发送 |
| `on_new_request()` | 新请求加入时通知 connector |

### Worker-side 接口 (`base.py:207-401`)

| 方法 | 作用 |
|------|------|
| `start_load_kv()` | forward 开始前，加载外部 KV |
| `wait_for_layer_load()` | 逐层等待 KV 加载完成 |
| `save_kv_layer()` | 每层 attention 后，保存 KV |
| `wait_for_save()` | 等待所有保存完成 |
| `get_finished()` | 返回已完成异步传输的请求 ID |

**源码依据：**
- `vllm/distributed/kv_transfer/kv_connector/v1/base.py:124-129` — `KVConnectorRole` 枚举
- `vllm/distributed/kv_transfer/kv_connector/v1/base.py:292-355` — Worker-side 抽象方法
- `vllm/distributed/kv_transfer/kv_connector/v1/base.py:453-561` — Scheduler-side 抽象方法

## 5. Scheduler 中的 PD 交互

### 5.1 Connector 初始化

Scheduler 构造函数中（`scheduler.py:119-136`）：

```python
self.connector = None
if self.vllm_config.kv_transfer_config is not None:
    self.connector = KVConnectorFactory.create_connector(
        config=self.vllm_config,
        role=KVConnectorRole.SCHEDULER,
        kv_cache_config=self.kv_cache_config,
    )
```

### 5.2 Prefill 节点行为

Prefill 节点的行为和普通 vLLM 实例几乎一样：
- 请求完成后，`_connector_finished()` 被调用，触发 KV cache 异步发送
- block 不立即释放（`delay_free_blocks=True`），等发送完成再释放

`_connector_finished()` （`scheduler.py:2075-2104`）：
```python
def _connector_finished(self, request):
    block_ids = self.kv_cache_manager.get_block_ids(request.request_id)
    return self.connector.request_finished(request, block_ids)
```

`_free_request()` 中的延迟释放逻辑（`scheduler.py:1869-1885`）：
```python
def _free_request(self, request, delay_free_blocks=False):
    connector_delay_free_blocks, kv_xfer_params = self._connector_finished(request)
    delay_free_blocks |= connector_delay_free_blocks
    if not delay_free_blocks:
        self._free_blocks(request)
```

### 5.3 Decode 节点行为

`schedule()` 阶段二处理 WAITING 请求时，多了 connector 交互（`scheduler.py:608-640`）：

```python
if request.num_computed_tokens == 0:
    # 先查本地 prefix cache
    new_computed_blocks, num_local_cached = (
        self.kv_cache_manager.get_computed_blocks(request)
    )
    # 再查外部 KV cache (来自 prefill 节点)
    if self.connector is not None:
        ext_tokens, load_kv_async = (
            self.connector.get_num_new_matched_tokens(
                request, num_local_cached
            )
        )
        num_external_computed_tokens = ext_tokens

    num_computed_tokens = num_local_cached + ext_tokens
```

### 5.4 异步加载状态机

如果外部 KV 需要异步加载（`scheduler.py:793-812`）：

```python
if load_kv_async:
    request.status = RequestStatus.WAITING_FOR_REMOTE_KVS
    step_skipped_waiting.prepend_request(request)
    request.num_computed_tokens = num_computed_tokens
    continue
```

Worker 完成传输后通过 `KVConnectorOutput.finished_recving` 通知 Scheduler（`scheduler.py:2186-2196`）：

```python
for req_id in kv_connector_output.finished_recving or ():
    req = self.requests[req_id]
    if req.status == RequestStatus.WAITING_FOR_REMOTE_KVS:
        self.finished_recving_kv_req_ids.add(req_id)
```

下一次 `schedule()` 时，`_try_promote_blocked_waiting_request()` 检测传输完成（`scheduler.py:2140-2171`）：

```python
def _try_promote_blocked_waiting_request(self, request):
    if request.status == RequestStatus.WAITING_FOR_REMOTE_KVS:
        if request.request_id not in self.finished_recving_kv_req_ids:
            return False
        self._update_waiting_for_remote_kv(request)
        request.status = RequestStatus.WAITING  # 恢复为可调度
        return True
```

`_update_waiting_for_remote_kv()` 缓存已接收的 blocks（`scheduler.py:2106-2138`）：

```python
def _update_waiting_for_remote_kv(self, request):
    self.kv_cache_manager.cache_blocks(request, request.num_computed_tokens)
    # 完全命中时需要重算最后一个 token
    if request.num_computed_tokens == request.num_tokens:
        request.num_computed_tokens = request.num_tokens - 1
```

### 5.5 完整状态流转

```
Decode 节点上的请求状态：

WAITING
  |
  | schedule() 检测到外部 KV
  | connector.get_num_new_matched_tokens() > 0
  |
  v
WAITING_FOR_REMOTE_KVS  <-- 异步加载 KV
  |
  | Worker 完成传输: finished_recving
  | _try_promote_blocked_waiting_request() 检测到
  |
  v
WAITING  (恢复，num_computed_tokens 已推进)
  |
  | schedule() 正常调度
  |
  v
RUNNING (直接开始 decode)
```

**源码依据：**
- `vllm/v1/core/sched/scheduler.py:119-136` — connector 初始化
- `vllm/v1/core/sched/scheduler.py:608-640` — 查外部 KV
- `vllm/v1/core/sched/scheduler.py:793-812` — 设为 WAITING_FOR_REMOTE_KVS
- `vllm/v1/core/sched/scheduler.py:2075-2104` — _connector_finished
- `vllm/v1/core/sched/scheduler.py:1869-1885` — delay_free_blocks
- `vllm/v1/core/sched/scheduler.py:2186-2196` — finished_recving 回调
- `vllm/v1/core/sched/scheduler.py:2140-2171` — _try_promote_blocked_waiting_request
- `vllm/v1/core/sched/scheduler.py:2106-2138` — _update_waiting_for_remote_kv

## 6. 可用的 KV Connector 实现

| Connector | 文件路径 | 传输方式 | 适用场景 |
|-----------|---------|---------|---------|
| `P2pNcclConnector` | `vllm/distributed/kv_transfer/kv_connector/v1/p2p/` | NCCL 点对点 | 单机多卡、简单验证 |
| `NixlConnector` | `vllm/distributed/kv_transfer/kv_connector/v1/nixl/` | NIXL RDMA | 高性能跨节点 |
| `MooncakeConnector` | `vllm/distributed/kv_transfer/kv_connector/v1/mooncake/` | Mooncake Store + RDMA | 生产环境跨节点 |
| `LMCacheConnector` | `vllm/distributed/kv_transfer/kv_connector/v1/lmcache_connector.py` | LMCache | 支持 KV cache 共享复用 |
| `OffloadingConnector` | `vllm/distributed/kv_transfer/kv_connector/v1/offloading_connector.py` | CPU offload | KV cache 卸载到 CPU |
| `SimpleCPUOffloadConnector` | `vllm/distributed/kv_transfer/kv_connector/v1/simple_cpu_offload_connector.py` | 简单 CPU offload | 轻量级 CPU 卸载 |

## 7. PD 节点比例的影响因素

Prefill 和 Decode 的计算特征完全不同，决定了 PD 节点比例不是 1:1。

### 7.1 计算特征的根本差异

```
Prefill (计算密集型):
  - 对 prompt 中所有 token 做一次完整的矩阵乘法
  - GPU FLOPS 利用率高 (接近峰值)
  - 单次请求耗时短 (通常 10-100ms)

Decode (访存密集型):
  - 每步只生成 1 个 token，但要加载全部 KV cache
  - GPU FLOPS 利用率低 (受限于内存带宽)
  - 单次请求耗时长 (output_length 个 step，每个 step ~10-50ms)
```

这意味着 **1 个 Prefill 节点的吞吐通常可以喂饱多个 Decode 节点**。

### 7.2 因素一：Prompt/Output 长度比

最直接的影响因素。假设平均 prompt 500 tokens，平均 output 1000 tokens：

- Prefill 一步完成 500 tokens 的计算
- Decode 需要 1000 步，每步 1 token

如果单个 GPU 上 prefill 500 tokens 耗时 50ms，decode 1 token 耗时 20ms：
- 1 个 prefill 请求的 GPU 时间 = 50ms
- 1 个 decode 请求的 GPU 时间 = 1000 * 20ms = 20000ms

粗略估算：**1P : 20D** (不考虑 batching 和 KV 传输开销)

Prompt 越短、output 越长，需要的 Decode 节点越多。

### 7.3 因素二：请求并发度 (QPS)

- 高 QPS 时，Prefill 可以高效 batch（多个请求的 prompt 拼在一起做一次 forward），吞吐提升显著，需要更少的 P 节点
- Decode 的 batching 受 KV cache 内存限制，每个请求都要占用 KV cache 空间，并发数有上限

```
QPS 低:  P 节点空闲率高，P/D 比可以偏低 (如 1:3)
QPS 高:  P 节点 batch 后吞吐暴增，P/D 比需要更低 (如 1:8 甚至 1:15)
```

### 7.4 因素三：KV Cache 传输开销

PD 分离引入了额外的网络传输：

```
KV cache 大小 ≈ 2 * num_layers * seq_len * hidden_dim * sizeof(dtype)

例: Llama-3.1-70B, prompt=2048 tokens, FP16:
  ≈ 2 * 80 * 2048 * 8192 * 2 bytes ≈ 5.4 GB
```

网络带宽直接影响：
- 传输延迟增加 Decode 节点的等待时间 (TTFT)
- 如果网络成为瓶颈，需要减少 P 节点（每次传输的 KV 更少但更频繁），或增加 P 节点（并行传输）

### 7.5 因素四：GPU 硬件异构性

PD 分离的一个重要优势是可以用不同的硬件：

| | Prefill | Decode |
|---|---------|--------|
| 核心需求 | 高 FLOPS | 高内存带宽 |
| 适合硬件 | H100 (SXM), A100 | L40S, 甚至是 CPU/专用推理卡 |
| 成本 | 高 | 可以低 |

如果用异构硬件，比例完全不同。比如 H100 做 Prefill，L40S 做 Decode：
- 1 张 H100 的 prefill 吞吐可能需要 5-10 张 L40S 来消化 decode

### 7.6 因素五：模型规模

模型越大，每个 token 的 KV cache 越大：
- KV 传输开销占比上升，网络更容易成为瓶颈
- Decode 单步耗时更长（attention 计算量随 KV cache 长度增长）
- 大模型倾向于需要更多 D 节点

### 7.7 因素六：SLO 约束 (TTFT vs TPOT)

- TTFT (Time To First Token) 主要由 Prefill 决定
- TPOT (Time Per Output Token) 主要由 Decode 决定

如果业务对 TTFT 要求严格（如实时对话），需要更多 P 节点降低排队延迟。
如果对吞吐量要求严格（如批量处理），可以适当减少 P 节点。

### 7.8 典型比例参考

| 场景 | Prompt 长度 | Output 长度 | 典型 P:D |
|------|-----------|------------|---------|
| 短对话 | ~100 | ~200 | 1:2 ~ 1:4 |
| 长文档问答 | ~2000 | ~500 | 1:1 ~ 1:2 |
| 代码补全 | ~500 | ~100 | 2:1 ~ 1:1 |
| 长文生成 | ~200 | ~4000 | 1:10 ~ 1:20 |
| RAG | ~3000 | ~300 | 1:1 ~ 1:3 |

### 7.9 实际调优方法

实际生产中通常不会静态固定比例，而是：

1. **基准测试**：在目标硬件上分别测量 P 和 D 的单请求延迟和吞吐
2. **建模估算**：根据 request 长度分布建立排队模型
3. **动态调整**：根据实时负载（QPS、队列深度）动态扩缩 P/D 节点
4. **A/B 验证**：观察 TTFT/TPOT 指标是否满足 SLO

核心公式思路：

```
P 节点吞吐 (tokens/s) = batch_prefill_throughput_per_gpu * num_P_gpus
D 节点吞吐 (tokens/s) = batch_decode_throughput_per_gpu * num_D_gpus

稳态条件: P 吞吐 * avg_output_len / avg_prompt_len ≈ D 吞吐

=> num_P / num_D ≈ (decode_throughput_per_gpu / prefill_throughput_per_gpu)
                   * (avg_prompt_len / avg_output_len)
```

这个比例随 workload 变化很大，所以生产环境通常会配合弹性调度来动态调整。

## 8. 总结

**v1 没有区分 prefill/decode phase，PD 分离通过三个层次的协作实现：** (以下为第 8 节)

1. **部署层**：启动两个独立的 vLLM 实例，配置不同的 `kv_role`
2. **路由层**：Proxy 将同一请求先发 Prefill（max_tokens=1），再发 Decode（完整请求）
3. **传输层**：KV Connector 负责 Prefill 和 Decode 实例之间的 KV cache 传输，调度器通过 `WAITING_FOR_REMOTE_KVS` 状态和 connector 接口与之协作

调度器本身保持 "不区分 prefill/decode" 的统一模型。Prefill 实例自然只做 prefill（因为 `max_tokens=1`），Decode 实例自然跳过 prefill（因为外部 KV 已就绪，`num_computed_tokens` 直接推进），直接进入 decode 循环。

## 关键源码文件索引

| 文件路径 | 核心职责 |
|---------|---------|
| `vllm/config/kv_transfer.py` | KVTransferConfig 定义（kv_role, kv_connector 等） |
| `vllm/distributed/kv_transfer/kv_connector/v1/base.py` | KVConnectorBase_V1 接口（Scheduler-side + Worker-side） |
| `vllm/distributed/kv_transfer/kv_connector/v1/p2p/p2p_nccl_connector.py` | P2pNcclConnector 实现 |
| `vllm/v1/core/sched/scheduler.py` | Scheduler 与 connector 的集成 |
| `examples/disaggregated/disaggregated_prefill.py` | 基础 1P1D 示例 |
| `examples/disaggregated/disaggregated_serving/disagg_proxy_demo.py` | XpYd 代理路由示例 |
