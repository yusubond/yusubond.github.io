---
title: 'vLLM 源码解析：从源码到运营，深度理解推理系统的 Metrics 体系搭建'
date: '2026-06-10'
tags: ['vLLM', 'Prometheus', 'LLM推理', 'Metrics', '可观测性', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

# vLLM 源码解析：从源码到运营，深度理解推理系统的 Metrics 体系搭建

## 背景

在 LLM 推理服务的生产化过程中，可观测性（Observability）是连接"模型跑起来"和"服务可用"之间的桥梁。作为一个高性能的 LLM 推理引擎，vLLM 不仅在调度算法（PagedAttention、Continuous Batching、Speculative Decoding）上做了大量工程优化，也在 Metrics 层面建设了一套覆盖完整的 Prometheus 指标体系。

本文基于 vLLM 源码（`vllm/v1/metrics/` 目录）进行逐行分析，系统梳理其 50+ Prometheus 指标的设计意图、采集机制与运营用法。阅读本文后，你将能够：

- 理解每个 metric 的精确含义与采集时机
- 基于 metrics 构建 SLO 监控与告警
- 掌握 SLO 驱动的扩缩容决策方法

---

## 一、Metrics 采集架构

### 1.1 整体数据流

vLLM 的 metrics 采集围绕 `StatLoggerManager`（`vllm/v1/metrics/loggers.py:1268`）展开。每个 engine iteration 结束后，调度器产出 `SchedulerStats` 和 `IterationStats`，由 `StatLoggerManager.record()` 分发给所有注册的 logger：

```
EngineCore (Rust/Python)
    |
    v
EngineCoreOutput (含 SchedulerStats + IterationStats)
    |
    v
StatLoggerManager.record()
    |
    +---> LoggingStatLogger       --> 周期性 stdout 摘要
    +---> PrometheusStatLogger    --> Prometheus /metrics 端点（pull 模式）
    +---> Custom Plugin Logger    --> 用户自定义后端（Datadog, CloudWatch 等）
```

### 1.2 双通道输出

vLLM 同时提供两种 metrics 输出通道：

- **Prometheus**（`PrometheusStatLogger`）：通过 `/metrics` 端点暴露，所有指标带 `model_name` + `engine` 标签，天然支持 Grafana + PromQL 查询
- **Stdout 日志**（`LoggingStatLogger`）：周期性输出格式化的运行摘要到标准输出，空闲时自动降级为 `debug` 级别以减少日志噪音

### 1.3 多引擎支持

在 Data Parallel（DP）部署下，多个 EngineCore 共存于一个 vLLM 实例中。`StatLoggerManager` 通过 `engine` 标签区分各引擎的指标。同时提供 `AggregatedLoggingStatLogger`（`loggers.py:293`）将多引擎指标聚合后统一输出。

### 1.4 插件化扩展

vLLM 提供了 `StatLoggerBase` 抽象类（`loggers.py:44`），用户只需实现三个方法即可自定义 metrics 后端：

```python
class MyCustomLogger(StatLoggerBase):
    def __init__(self, vllm_config, engine_index=0): ...
    def record(self, scheduler_stats, iteration_stats, ...): ...
    def log_engine_initialized(self): ...
```

通过 `STAT_LOGGER_PLUGINS_GROUP` 入口点注册，`StatLoggerManager` 自动加载。

### 1.5 统计数据的生命周期

一个请求从进入到完成，其统计数据经过以下阶段的演变：

```
RequestStateStats (请求到达时创建)
    |-- arrival_time (wall-clock)
    |-- queued_ts / scheduled_ts / first_token_ts / last_token_ts (monotonic clock)
    |
    v
IterationStats (每批 EngineCoreOutput 聚合一次)
    |-- prompt_token_stats (按来源细分：local_compute / local_cache_hit / external_kv_transfer)
    |-- time_to_first_tokens_iter   --> 记入 TTFT histogram
    |-- inter_token_latencies_iter  --> 记入 ITL histogram
    |-- finished_requests[]         --> 记入各项请求级 histogram
    |
    v
SchedulerStats (调度器快照，每个 iteration 更新)
    |-- num_running_reqs / num_waiting_reqs / num_skipped_waiting_reqs
    |-- kv_cache_usage
    |-- prefix_cache_stats / spec_decoding_stats / kv_connector_stats / perf_stats
    |
    v
FinishedRequestStats (请求完成时创建)
    |-- e2e_latency / queued_time / prefill_time / decode_time / inference_time
    |-- num_prompt_tokens / num_generation_tokens / num_cached_tokens
    |-- mean_time_per_output_token
```

---

## 二、全部 Metrics 详解

所有 Prometheus 指标带标签 `model_name` + `engine`，支持多引擎（Data Parallel）场景。下面按功能分组逐一解析。

### 2.1 调度器状态（Gauge — 实时快照）

| Metric | 含义 |
|--------|------|
| `vllm:num_requests_running` | 当前正在执行模型推理的请求数 |
| `vllm:num_requests_waiting` | 等待被调度的请求总数（waiting + skipped_waiting） |
| `vllm:num_requests_waiting_by_reason{reason="capacity"}` | 因调度容量不足而等待的请求数 |
| `vllm:num_requests_waiting_by_reason{reason="deferred"}` | 因 LoRA 预算、KV 传输、blocked 等临时约束被推迟的请求数 |
| `vllm:kv_cache_usage_perc` | KV cache 使用率（0~1，1=100%） |
| `vllm:engine_sleep_state{sleep_state="awake"}` | 引擎是否活跃（1=活跃，0=休眠） |
| `vllm:engine_sleep_state{sleep_state="weights_offloaded"}` | 是否处于 level 1 休眠（权重卸载到 CPU） |
| `vllm:engine_sleep_state{sleep_state="discard_all"}` | 是否处于 level 2 休眠（丢弃所有 KV cache） |

**源码要点**：`num_requests_waiting` 是 `num_waiting_reqs + num_skipped_waiting_reqs` 的总和（`loggers.py:1070-1074`）。`waiting_by_reason` 进一步区分了两种等待原因：`capacity`（调度器排不下）和 `deferred`（LoRA 预算满、KV 传输中等临时约束）。这个区分在运营中极为重要——它决定了你应该扩容还是调参。

### 2.2 令牌计数器（Counter — 累积量）

| Metric | 含义 |
|--------|------|
| `vllm:prompt_tokens` | 处理的 prefill token 总数（仅计实际计算量，不含缓存命中） |
| `vllm:prompt_tokens_by_source{source="local_compute"}` | 本地实际计算的 prompt token 数 |
| `vllm:prompt_tokens_by_source{source="local_cache_hit"}` | 本地 prefix cache 命中的 token 数 |
| `vllm:prompt_tokens_by_source{source="external_kv_transfer"}` | 从外部 KV 传输获取的 token 数 |
| `vllm:prompt_tokens_cached` | 缓存命中的 prompt token 总数（local + external） |
| `vllm:generation_tokens` | 生成的 decode token 总数 |
| `vllm:request_success{finished_reason="stop"/"length"/...}` | 按完成原因统计的请求完成数 |

**源码要点**：`prompt_tokens` 的计数发生在 `LoggingStatLogger._track_iteration_stats()`（`loggers.py:145`），使用的是 `iteration_stats.prompt_token_stats.computed`——即排除了缓存命中的部分。这意味着 `rate(vllm:prompt_tokens[1m])` 反映的是实际的 GPU 计算吞吐，而非业务层面的 token 总量。`prompt_tokens_by_source` 提供了更细粒度的三维分解（`stats.py:277-322`）：

```
total = local_compute + local_cache_hit + external_kv_transfer
cached_tokens = local_cache_hit + external_kv_transfer
```

### 2.3 请求延迟直方图（Histogram — 分布）

| Metric | Buckets 范围 | 含义 |
|--------|-------------|------|
| `vllm:time_to_first_token_seconds` | 1ms~2560s | 首 token 延迟（TTFT），从请求到达至第一个 token 生成 |
| `vllm:inter_token_latency_seconds` | 10ms~80s | decode 阶段相邻 token 间延迟（ITL） |
| `vllm:request_time_per_output_token_seconds` | 10ms~80s | 每个请求的"每输出 token 耗时" |
| `vllm:e2e_request_latency_seconds` | 0.3s~7680s | 端到端请求延迟（从到达至完成） |
| `vllm:request_queue_time_seconds` | 0.3s~7680s | 请求在 WAITING 队列中的排队时间 |
| `vllm:request_inference_time_seconds` | 0.3s~7680s | 请求在 RUNNING 阶段的总推理时间 |
| `vllm:request_prefill_time_seconds` | 0.3s~7680s | prefill（上下文处理）阶段耗时 |
| `vllm:request_decode_time_seconds` | 0.3s~7680s | decode（自回归生成）阶段耗时 |

**ITL 仅在 decode 阶段记录**。源码 `stats.py:396-401` 明确区分：

```python
if is_prefilling:
    req_stats.first_token_ts = engine_core_timestamp   # 为 TTFT 准备
else:
    itl = engine_core_timestamp - req_stats.last_token_ts
    self.inter_token_latencies_iter.append(itl)        # 仅 decode 阶段
```

**请求生命周期的时间分解**（`stats.py:437-460`）：

```
arrival_time                                                    (wall-clock)
    |--- queued_time ---|--- prefill_time ---|--- decode_time ---|
    |                   |--- inference_time ---------------------|
    |--- e2e_latency --------------------------------------------|
queued_ts           scheduled_ts  first_token_ts  last_token_ts  (monotonic clock)
```

- `queued_time` = `scheduled_ts - queued_ts`（首次 QUEUED 到首次 SCHEDULED）
- `prefill_time` = `first_token_ts - scheduled_ts`（含 prefill 期间的抢占）
- `decode_time` = `last_token_ts - first_token_ts`（含 decode 期间的抢占）
- `inference_time` = `last_token_ts - scheduled_ts`（含所有抢占）
- `e2e_latency` = 当前时间 - `arrival_time`（wall-clock）

`request_time_per_output_token` 的计算（`stats.py:455-459`）：`decode_time / (num_generation_tokens - 1)`，减 1 是因为 prefill 阶段生成的第一个 token 不计入 decode 阶段。

### 2.4 请求特征直方图

| Metric | 含义 |
|--------|------|
| `vllm:request_prompt_tokens` | 每个请求的 prompt token 数分布 |
| `vllm:request_generation_tokens` | 每个请求的生成 token 数分布 |
| `vllm:request_max_num_generation_tokens` | 请求中 max generation tokens 参数的分布 |
| `vllm:request_params_n` | 请求参数 `n`（并行生成序列数）的分布 |
| `vllm:request_params_max_tokens` | 请求参数 `max_tokens` 的分布 |
| `vllm:request_prefill_kv_computed_tokens` | prefill 阶段实际新计算的 KV token 数（排除缓存） |
| `vllm:iteration_tokens_total` | 每个 engine step 处理的总 token 数分布（prefill + decode） |

**Bucket 设计**：token 数相关的 histogram 使用 `build_1_2_5_buckets(max_model_len)`（`loggers.py:1259`）生成 1-2-5 序列的 buckets，例如 `[1, 2, 5, 10, 20, 50, 100, ...]`，直到 `max_model_len`。这种序列在双对数坐标下呈等间距分布，适合跨越多个数量级的 token 分布。

`iteration_tokens_total` 使用独立的 buckets `[1, 8, 16, 32, 64, 128, 256, 512, 1024, ...]`（`loggers.py:714`），反映 engine step 的 batch 粒度。

### 2.5 缓存命中率（Counter）

| Metric | 含义 |
|--------|------|
| `vllm:prefix_cache_queries` | 本地 prefix cache 查询的 token 总数 |
| `vllm:prefix_cache_hits` | 本地 prefix cache 命中的 token 总数 |
| `vllm:external_prefix_cache_queries` | 跨实例 KV connector 的外部 prefix cache 查询 token 数 |
| `vllm:external_prefix_cache_hits` | 跨实例 KV connector 的外部 prefix cache 命中 token 数 |
| `vllm:mm_cache_queries` | 多模态缓存查询条目数 |
| `vllm:mm_cache_hits` | 多模态缓存命中条目数 |

**源码要点**：prefix cache 命中率使用滑动窗口计算（`stats.py:35-111`，`CachingMetrics`），默认保留最近 1000 个请求的统计，避免历史数据稀释近期变化。当 `reset_prefix_cache` 被调用时，指标自动清零。

### 2.6 KV Cache 驻留指标（Histogram — 需 `--kv-cache-metrics` 开启）

| Metric | 含义 |
|--------|------|
| `vllm:kv_block_lifetime_seconds` | KV cache block 从分配到驱逐的生命周期 |
| `vllm:kv_block_idle_before_evict_seconds` | block 被驱逐前的空闲时间 |
| `vllm:kv_block_reuse_gap_seconds` | 两次连续访问同一 block 的时间间隔 |

**采样机制**：这三个指标使用采样以减少开销（默认 1%，通过 `--kv-cache-metrics-sample` 调整）。`reuse_gap` 仅记录最近几次访问（ring buffer），避免内存无限增长。

### 2.7 抢占与异常

| Metric | 含义 |
|--------|------|
| `vllm:num_preemptions` | 累计请求抢占次数 |
| `vllm:corrupted_requests` | 累计产生 NaN logits 的异常请求数（需 `VLLM_COMPUTE_NANS_IN_LOGITS`） |

**源码要点**：抢占计数发生在 `IterationStats.update_from_events()`（`stats.py:424`），当 `EngineCoreEventType.PREEMPTED` 事件触发时递增。`corrupted_requests` 需要显式开启 `VLLM_COMPUTE_NANS_IN_LOGITS` 环境变量才生效（`loggers.py:529-540`），用于检测 logits 中出现 NaN 的异常请求。

### 2.8 推测解码指标（Speculative Decoding）

| Metric | 含义 |
|--------|------|
| `vllm:spec_decode_num_drafts` | 推测解码 draft 次数 |
| `vllm:spec_decode_num_draft_tokens` | draft 生成的 token 总数 |
| `vllm:spec_decode_num_accepted_tokens` | 被 verifier 接受的 token 总数 |
| `vllm:spec_decode_num_accepted_tokens_per_pos{position=N}` | 每个 draft 位置被接受的 token 数 |

**衍生计算**（PromQL）：
- 接受率 = `rate(vllm:spec_decode_num_accepted_tokens[5m]) / rate(vllm:spec_decode_num_draft_tokens[5m])`
- 平均接受长度 = `1 + rate(vllm:spec_decode_num_accepted_tokens[5m]) / rate(vllm:spec_decode_num_drafts[5m])`

**源码要点**：`SpecDecodingStats`（`vllm/v1/spec_decode/metrics.py:18`）在每个 scheduler step 由调度器聚合后返回。`num_accepted_tokens_per_pos` 是一个向量，长度等于 `num_speculative_tokens`，用于分析 draft model 在各位置的预测质量。

### 2.9 MFU 性能指标（需 `--enable-mfu-metrics`）

| Metric | 含义 |
|--------|------|
| `vllm:estimated_flops_per_gpu_total` | 每 GPU 估算的浮点运算总量 |
| `vllm:estimated_read_bytes_per_gpu_total` | 每 GPU 估算的内存读取字节数 |
| `vllm:estimated_write_bytes_per_gpu_total` | 每 GPU 估算的内存写入字节数 |

**衍生计算**（PromQL）：
- TFLOPS/GPU = `rate(vllm:estimated_flops_per_gpu_total[1m]) / 1e12`
- 内存带宽 = `(rate(vllm:estimated_read_bytes_per_gpu_total[1m]) + rate(vllm:estimated_write_bytes_per_gpu_total[1m])) / 1e9`

**MFU 的组件级计算**（`vllm/v1/metrics/perf.py`）是 vLLM metrics 体系中最为精密的部分。`ModelMetrics`（`perf.py:985`）将模型拆解为三大组件，分别计算 FLOPs 和内存流量：

**AttentionMetrics**（`perf.py:400`）：
- FLOPs 细分：`qkv_proj`（QKV 投影）、`attn_qk`（QK^T 点积）、`attn_av`（注意力加权求和）、`out_proj`（输出投影）
- 考虑 GQA/MQA 中的 `num_key_value_heads` 与 `num_attention_heads` 的比例差异
- 区分 prefill 和 decode 阶段的内存读取模式：prefill 时 KV 激活全读，decode 时 KV 从 cache 读取（使用 `cache_byte_size` 而非 `activation_byte_size`）

**FfnMetrics**（`perf.py:662`）：
- 支持三类 FFN 结构：Dense FFN（标准 SwiGLU）、MoE Routed Experts、MoE Shared Experts
- Dense FFN 的 FLOPs = `2 * D * 3 * DI * T * Ld`（SwiGLU 有 3 个线性层：up, gate, down）
- MoE 考虑 `num_experts_per_tok`（每个 token 激活的专家数）、`num_shared_experts`、`moe_intermediate_size`
- 特殊模型支持：Llama4 的 `interleave_moe_layer_step`、DeepSeek 的 `moe_layer_freq + first_k_dense_replace`

**UnembedMetrics**（`perf.py:919`）：
- 仅 prefill 的最后一个 token 和 decode 的所有 token 需要 logits 计算（`ctx.num_logits_tokens()`）
- 词汇表按 TP 大小分片

**量化权重字节映射**（`perf.py:52-77`）：
- FP8 方法（fp8, fbgemm_fp8, modelopt 等）：1 字节/权重
- INT4/FP4 方法（awq, gptq, bitsandbytes, awq_marlin 等）：0.5 字节/权重

### 2.10 LoRA 指标

| Metric | 含义 |
|--------|------|
| `vllm:lora_requests_info{max_lora, waiting_lora_adapters, running_lora_adapters}` | LoRA 适配器的等待/运行统计 |

**源码要点**：这是一个 info 类型指标（值恒为当前时间戳），通过标签值编码状态信息。`waiting_lora_adapters` 和 `running_lora_adapters` 是逗号分隔的 adapter 名称列表，由 `LoRARequestStates`（`stats.py:507`）追踪每个 LoRA 的等待/运行请求数。

### 2.11 KV Connector 传输指标

通过 `KVConnectorProm` 框架实现（`vllm/distributed/kv_transfer/kv_connector/v1/metrics.py`），具体 metric 名称由各 connector 自定义注册。`KVConnectorStats` 基类定义了 `aggregate()`、`reduce()`、`is_empty()` 等方法，connector（如 LMCache、SharedStorage）实现自己的统计收集逻辑。

### 2.12 API 层指标

通过 `prometheus_fastapi_instrumentator`（`vllm/entrypoints/serve/instrumentator/metrics.py`）在 FastAPI 层自动采集 HTTP 请求延迟、状态码等指标，排除了 `/metrics`、`/health`、`/load`、`/ping`、`/version`、`/server_info` 等管理端点。

### 2.13 配置信息（Info Gauge）

| Metric | 含义 |
|--------|------|
| `vllm:cache_config_info{...}` | 缓存配置信息（block_size, gpu_memory_utilization 等），值恒为 1 |

---

## 三、Metrics 的配置与启用

### 3.1 ObservabilityConfig（`vllm/config/observability.py`）

| 配置项 | 类型 | 默认值 | 说明 |
|-------|------|--------|------|
| `show_hidden_metrics_for_version` | str? | None | 显示自指定版本后被隐藏的废弃指标（迁移用） |
| `kv_cache_metrics` | bool | False | 启用 KV cache 驻留指标（lifetime/idle/reuse_gap） |
| `kv_cache_metrics_sample` | float | 0.01 | KV cache 指标采样率（0~1） |
| `cudagraph_metrics` | bool | False | 启用 CUDA graph 指标 |
| `enable_mfu_metrics` | bool | False | 启用 MFU（Model FLOPs Utilization）指标 |
| `enable_mm_processor_stats` | bool | False | 多模态处理器计时统计（内部 benchmark 用） |
| `enable_logging_iteration_details` | bool | False | 详细迭代日志（含 context/generation token 数） |

### 3.2 启用建议

生产环境推荐的最小配置：

```bash
# 基础 metrics 默认开启，无需额外参数
# /metrics 端点自动暴露

# 可选：按需开启高级指标
--enable-mfu-metrics          # 量化 GPU 利用率
--kv-cache-metrics            # 分析 KV cache 驻留行为
--kv-cache-metrics-sample 0.05  # 5% 采样（默认 1% 可能不够精确）
```

---

## 四、SLO 定义与监控

### 4.1 核心 SLO 指标

| 运营指标 | 数据来源 | PromQL 示例 |
|---------|---------|-------------|
| TTFT P99 | `vllm:time_to_first_token_seconds` | `histogram_quantile(0.99, sum(rate(..._bucket[5m])) by (le))` |
| ITL P95 | `vllm:inter_token_latency_seconds` | `histogram_quantile(0.95, sum(rate(..._bucket[5m])) by (le))` |
| E2E 延迟 P99 | `vllm:e2e_request_latency_seconds` | `histogram_quantile(0.99, sum(rate(..._bucket[5m])) by (le))` |
| Decode 吞吐量 | `vllm:generation_tokens` | `sum(rate(vllm:generation_tokens[1m]))` |
| 请求成功率 | `vllm:request_success` | `sum(rate(...[5m])) by (finished_reason)` |
| KV Cache 使用率 | `vllm:kv_cache_usage_perc` | `avg(vllm:kv_cache_usage_perc) by (model_name)` |
| Prefix Cache 命中率 | Counter 计算 | `sum(rate(vllm:prefix_cache_hits[5m])) / sum(rate(vllm:prefix_cache_queries[5m]))` |

### 4.2 请求延迟的四维分解

一个请求的端到端延迟可以精确分解为四个阶段：

```
E2E Latency = Queue Time + Prefill Time + Decode Time + 网络开销
                  |              |              |
         request_queue_time  request_prefill  request_decode
         _seconds            _time_seconds    _time_seconds
```

这种分解的价值在于：当 E2E 延迟超标时，可以立即定位瓶颈在哪个阶段。

---

## 五、SLO 驱动的扩缩容策略

以下策略以 HPA（Horizontal Pod Autoscaler）或自定义扩缩容控制器为背景，给出基于 vLLM metrics 的扩容判断规则与具体案例。

### 策略 1：TTFT SLO 违约 → Prefill 扩容

**场景**：SLO 定义 TTFT P99 < 2s，但连续 5 分钟超标。

**根因判断**：
```promql
# TTFT P99 超标
histogram_quantile(0.99, rate(vllm:time_to_first_token_seconds_bucket[5m])) > 2

# 同时 prefill 时间高、queue 时间高 → 说明是 prefill 计算能力不足
histogram_quantile(0.99, rate(vllm:request_prefill_time_seconds_bucket[5m])) > 1.5
```

**扩容动作**：增加 vLLM 实例数（HPA replicas +1）。

**案例**：某在线客服平台使用 Qwen2.5-72B，用户对话平均 4K token 的 prompt。高峰期 TTFT P99 从 1.2s 飙升到 4.5s，但 ITL 稳定在 50ms。通过 Grafana 发现 `request_prefill_time_seconds` P99 达到 3.8s，`request_queue_time_seconds` 从 0.2s 涨到 1.2s。结论：大量长上下文请求在排队等 prefill。扩容 2 个副本后，TTFT P99 回落到 1.5s。

### 策略 2：KV Cache 使用率持续高位 → 内存扩容 / 实例扩容

**场景**：`kv_cache_usage_perc` 连续 10 分钟 > 85%，同时 `num_preemptions` 上升。

**根因判断**：
```promql
# KV cache 高位
vllm:kv_cache_usage_perc > 0.85

# 抢占开始发生
rate(vllm:num_preemptions[5m]) > 0

# ITL 受影响（preemption 导致 decode 中断）
histogram_quantile(0.95, rate(vllm:inter_token_latency_seconds_bucket[5m])) > 0.1
```

**扩容动作**：
- 如果 GPU 显存有余量 → 调大 `--gpu-memory-utilization`（如 0.90 → 0.95）
- 如果已是上限 → HPA 扩容实例数

**案例**：部署 DeepSeek-V3/R1（671B MoE）的推理服务，`max_model_len=32K`。当并发用户数从 50 涨到 120 时，`kv_cache_usage_perc` 从 60% 飙升到 95%，`num_preemptions` 每分钟增加 30+ 次，ITL P95 从 40ms 劣化到 200ms。分析 `kv_block_lifetime_seconds` 发现大量 block 在 5s 内就被驱逐。解决方案：将副本数从 4 扩容到 6，并将 `max_model_len` 从 32K 降到 16K（业务可接受），KV cache 使用率回落到 70%。

### 策略 3：等待队列深度持续增长 → 区分原因对症扩容

**场景**：`num_requests_waiting` 持续 > 50 且不下降。

**根因判断**：
```promql
# 等待队列持续积压
vllm:num_requests_waiting > 50

# 区分原因
vllm:num_requests_waiting_by_reason{reason="capacity"} > 40   # 容量不足
vllm:num_requests_waiting_by_reason{reason="deferred"} > 10   # LoRA 等约束
```

**扩容动作**：
- `capacity` 占主导 → 横向扩容（增加副本）
- `deferred` 占主导 → 检查 LoRA 配置（`max_loras` 是否过小）或 KV connector 瓶颈

**案例**：多租户 SaaS 平台为不同客户提供 LoRA 微调模型。某次大客户活动导致 `num_requests_waiting_by_reason{reason="deferred"}` 达到 80，而 `capacity` 仅 5。排查发现该客户使用了 8 个不同 LoRA adapter，但 `max_loras=4`，大量请求因 LoRA slot 满载被 defer。将 `max_loras` 从 4 提升到 8 后，deferred 降至 0。

### 策略 4：ITL SLO 违约 + MFU 偏低 → Batch 配置调优

**场景**：ITL P95 > 100ms 但 MFU 不到 30%。

**根因判断**：
```promql
# ITL 劣化
histogram_quantile(0.95, rate(vllm:inter_token_latency_seconds_bucket[5m])) > 0.1

# MFU 偏低（假设 H100 理论 989 TFLOPS）
rate(vllm:estimated_flops_per_gpu_total[5m]) / 989e12 < 0.3
```

**扩容动作**：不是扩容，而是调优。MFU 低说明 GPU 没有被充分利用，可能是 batch 太小或 CUDA graph 未生效。调大 `--max-num-seqs` 或检查 `--enforce-eager` 是否误开启了。

**案例**：某服务使用 Llama-3-8B，ITL P95 为 150ms，但 `estimated_flops_per_gpu_total` 换算的 MFU 仅 15%。检查发现 `max-num-seqs` 设为 4（调试时遗留），每批只有 4 个请求在 decode，GPU 大量空闲。将 `max-num-seqs` 提升到 256 后，MFU 提升到 55%，ITL P95 反而降到 30ms（因为 CUDA graph 和连续批处理更高效）。

### 策略 5：E2E 延迟正常但 Queue 时间占比过高 → 前置扩容

**场景**：E2E P99 在 SLO 内但 `request_queue_time_seconds` 占比 > 50%。

**根因判断**：
```promql
# Queue 时间占比
histogram_quantile(0.99, rate(vllm:request_queue_time_seconds_bucket[5m]))
/ histogram_quantile(0.99, rate(vllm:e2e_request_latency_seconds_bucket[5m])) > 0.5
```

**扩容动作**：E2E 还没超标是因为后续推理阶段很快，但 queue 积压是扩容的前兆。提前扩容，避免流量进一步增长后 E2E 超标。

**案例**：某搜索增强生成（RAG）服务，E2E P99 为 8s（SLO 10s），但 `request_queue_time_seconds` P99 达 5s，实际推理仅 3s。此时流量还在持续增长，按照趋势 2 小时后 E2E 将突破 SLO。运维基于 queue 占比指标提前触发扩容，从 3 副本扩到 5 副本，避免了 SLO 违约。

### 策略 6：Token 吞吐量接近上限 → 预测性扩容

**场景**：`generation_tokens` 吞吐量连续上升，接近单实例理论上限。

**根因判断**：
```promql
# 单实例 decode 吞吐量
sum(rate(vllm:generation_tokens[5m])) by (engine) > 30000
# 假设 H100 上 Llama-70B 的单实例 decode 吞吐上限约 35K tokens/s
```

**扩容动作**：基于吞吐量趋势做预测性扩容（比反应式扩容更早）。

**案例**：使用 Llama-3-70B 的代码补全服务，单实例 decode 吞吐约 32K tokens/s（理论极限 ~35K）。工作日上午 9 点开始，`generation_tokens` 速率从 15K 线性上升到 30K。扩容控制器检测到当前吞吐量 > 阈值的 85%，提前 15 分钟触发扩容，新增 2 副本。到 10 点流量峰值时，集群总吞吐量从容达到 90K tokens/s。

### 策略 7：Prefix Cache 命中率骤降 → 缓存策略调整 / PD 分离

**场景**：`prefix_cache_hits / prefix_cache_queries` 从 60% 骤降到 10%。

**根因判断**：
```promql
# 命中率骤降
rate(vllm:prefix_cache_hits[5m]) / rate(vllm:prefix_cache_queries[5m]) < 0.15

# 可能原因：KV cache 压力大导致频繁驱逐
vllm:kv_cache_usage_perc > 0.8

# 或者请求 pattern 变化（长尾 prompt 多样化）
histogram_quantile(0.99, rate(vllm:request_prompt_tokens_bucket[5m])) > 8000
```

**扩容动作**：
- 如果是 cache 驱逐导致 → 扩容实例，降低单实例 KV 压力
- 如果是请求 pattern 变化 → 考虑 PD 分离架构（Prefill-Decode Disaggregation），让 prefill 节点专门处理长 prompt

**案例**：某 RAG 服务平时 prefix cache 命中率 55%（大量相似的 system prompt + 检索模板）。一次业务变更后，每个请求的 system prompt 开始个性化，命中率骤降到 8%，TTFT 翻倍。短期方案：扩容 3 个副本缓解 KV 压力，命中率恢复到 25%。长期方案：引入 PD 分离，prefill 节点不计较小 KV cache，decode 节点保留更大 cache。

### 策略 8：跨实例 KV 传输瓶颈 → Connector 扩容 / 网络调优

**场景**：使用了 KV Connector 跨实例共享 KV cache，但传输延迟导致 TTFT 未见明显改善。

**根因判断**：
```promql
# 外部 cache 命中率高（说明传输在发生）
rate(vllm:external_prefix_cache_hits[5m]) / rate(vllm:external_prefix_cache_queries[5m]) > 0.4

# 但 TTFT 仍高（说明传输本身是瓶颈）
histogram_quantile(0.99, rate(vllm:time_to_first_token_seconds_bucket[5m])) > 3
```

**扩容动作**：这不是 vLLM 实例扩容，而是 KV Connector 的存储/网络层扩容（如增加 LMCache 实例、升级网络带宽）。

**案例**：使用 LMCache 实现跨节点 KV 复用。外部 cache 命中率 45%（每个请求平均省 2K token 的 prefill），但 TTFT P99 仍为 3.5s。通过 tracing 发现 `gen_ai.latency.time_in_model_prefill` 中 KV 传输等待占了 2s。原因是 KV 传输走的是普通 TCP 网络，带宽仅 10Gbps。升级到 RDMA 100Gbps 后，传输等待降至 200ms，TTFT P99 降到 1.8s。

### 策略 9：Speculative Decoding 接受率下降 → Draft Model 调整

**场景**：启用投机解码后，接受率突然下降，性能不升反降。

**根因判断**：
```promql
# 接受率低于 60%
rate(vllm:spec_decode_num_accepted_tokens[5m])
/ rate(vllm:spec_decode_num_draft_tokens[5m]) < 0.6

# 每个 draft 的平均接受长度
1 + rate(vllm:spec_decode_num_accepted_tokens[5m])
  / rate(vllm:spec_decode_num_drafts[5m]) < 2.0
```

**扩容动作**：不是扩容，而是调优。接受率低说明 draft model 与 target model 分布不匹配。需要更换 draft model 或减少 `num_speculative_tokens`。

**案例**：使用 Qwen2.5-7B 作为 draft model 为 Qwen2.5-72B 做投机解码，配置 `num_speculative_tokens=5`。正常时接受率 72%，平均接受长度 3.2。某次 target model 更新了权重但未同步更新 draft model，接受率降至 40%，平均接受长度 1.5。此时 draft 开销（计算 + verify）大于收益。通过 `spec_decode_num_accepted_tokens_per_pos{position="0"}` 发现 position 0 的接受率就只有 60%（正常应该 >90%），说明 draft model 的输出分布已经偏移。更新 draft model 后恢复。

### 策略 10：多引擎负载不均 → Data Parallel Rebalance

**场景**：Data Parallel 部署下，某些 engine 的指标明显差于其他。

**根因判断**：
```promql
# 各 engine 的 KV cache 使用率差异大
vllm:kv_cache_usage_perc{engine="0"} - vllm:kv_cache_usage_perc{engine="1"} > 0.2

# 或者各 engine 的等待队列差异大
vllm:num_requests_waiting{engine="0"} > 2 * vllm:num_requests_waiting{engine="1"}
```

**扩容动作**：检查负载均衡策略（如 API 层的轮询是否生效），而不是盲目扩容。

**案例**：2 个 Data Parallel engine 部署，发现 `engine=0` 的 `kv_cache_usage_perc` 为 92%，`engine=1` 仅 45%。API 层使用简单轮询，但 `engine=0` 恰好分到了更多长上下文请求（code generation，平均 8K prompt），`engine=1` 以短对话为主（平均 500 prompt）。解决方案：在 API 层引入基于 prompt token 数的加权路由，将长请求分散到两个 engine，使用率趋于均衡。

---

## 六、故障诊断速查表

| 现象 | 检查指标 | 可能原因 |
|------|---------|---------|
| TTFT 飙升但 ITL 正常 | `request_prefill_time_seconds` | 长上下文请求过多，prefill 成为瓶颈 |
| ITL 飙升伴随抢占 | `num_preemptions` + `kv_cache_usage_perc` | KV cache 压力过大，频繁抢占 |
| Queue 时间上升 | `num_requests_waiting` + `waiting_by_reason` | 调度容量不足或 LoRA slot 满载 |
| E2E 延迟正常但 queue 占比 > 50% | `request_queue_time_seconds / e2e_request_latency_seconds` | 流量即将突破 SLO 的前兆 |
| MFU 低但延迟不差 | `estimated_flops_per_gpu_total` + `iteration_tokens_total` | batch 太小或 CUDA graph 未生效 |
| Prefix cache 命中率骤降 | `prefix_cache_hits/queries` + `kv_block_lifetime_seconds` | KV 驱逐频繁或请求 pattern 变化 |
| Spec decode 接受率下降 | `spec_decode_num_accepted_tokens_per_pos` | draft model 与 target model 分布偏移 |
| 多引擎负载不均 | 按 `engine` 标签对比各指标 | API 层路由不均 |

---

## 七、总结

vLLM 的 Prometheus Metrics 体系覆盖了从 API 层到模型执行的完整链路，约 50+ 指标，具备以下设计特点：

1. **分层设计**：Gauge 做实时状态、Counter 做累积统计、Histogram 做分布分析，各司其职
2. **低开销**：KV cache 驻留指标使用采样、MFU 计算基于解析公式而非实测、空闲时日志降级
3. **生产就绪**：多进程 Prometheus 支持（`prometheus.py` 的 `setup_multiprocess_prometheus`）、engine 级标签隔离、配置信息 metric
4. **可扩展**：插件架构支持自定义 metric 后端、KV Connector 可注册自己的指标
5. **组件级精细度**：MFU 计算将模型拆解为 Attention/FFN/Unembed 组件，支持 Dense 和 MoE 架构，考虑 TP/PP/DP/EP 并行分区和量化

从运营角度看，这套 metrics 体系的核心价值在于**延迟的四维分解**（queue / prefill / decode / 网络开销）和**资源的三层监控**（KV cache 使用率 / 调度器队列 / GPU 计算利用率），使运维团队能够快速定位瓶颈并做出精确的扩缩容决策。
