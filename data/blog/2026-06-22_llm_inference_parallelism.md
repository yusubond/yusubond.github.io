---
title: '大模型推理为什么还要分 TP / DP / EP？'
date: '2026-06-22'
tags: ['LLM推理', 'vLLM', '并行计算', 'MoE', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

> 写给"略懂一点大模型的后端研发"。一篇讲清推理场景下三种核心并行策略各自解决什么问题、代价是什么、怎么组合。部分例子落在 vLLM，但原理通用。

---

## 先建立一个直觉

很多人熟悉**训练**时的 TP/DP/PP（切权重、多 worker 算梯度同步、流水线）。但**推理**时这套东西的存在理由和分工其实不一样。

核心一句话：**推理也需要并行，是因为单卡既"装不下"（显存），又"算不过来"（吞吐/延迟）。** TP 管"切模型"，DP 管"复制模型"，EP 是 MoE 层专用的"切专家"。

| 瓶颈 | 表现 | 对应策略 | 动作 |
|---|---|---|---|
| 显存装不下 | 权重 + KV cache 超出单卡 | **TP** / **PP** | 切模型，分摊到多卡 |
| 吞吐算不过来 | 单份模型 QPS 不够 | **DP** | 复制模型，各副本独立服务 |
| MoE 专家太多 | 256 个专家单卡放不下 | **EP** | 切专家（TP 的变体） |

下面逐个拆。

---

## 1. TP（张量并行）：解决"单层装不下 / 算不过来"

### 做法

把**单个算子的权重**按行/列切到 N 张卡，每张卡只存 `1/N` 的权重，每层算完用 **all-reduce** 把结果合并。

```
   一个 Linear: y = xW
   W 切成左右两半, 分到 2 张卡:
   +----------+   +----------+
   | G0: W_L  |   | G1: W_R  |
   +----------+   +----------+
        |              |
        +-- all-reduce -->  合并得到完整 y
```

### 推理时 TP 做三件事

1. **切权重**：大模型单卡放不下，TP 让每卡只存 `1/N` 权重 → 装得下。
2. **切 attention head + KV cache**（容易被忽略）：TP 顺带把多头注意力的 head 分到各卡，**每张卡只存自己那份 KV cache**。长上下文推理时，这是省显存的大头。
3. **大矩阵并行加速**：prefill 阶段是计算密集，矩阵很大，多卡并行提速。

### 代价

每层一次 **all-reduce** 通信。

### 推理特有的陷阱：prefill vs decode

这是后端研发最该记住的一点：

| 阶段 | 特性 | TP 表现 |
|---|---|---|
| **prefill** | 计算密集（大批 token，大矩阵） | TP 很值，计算能掩盖通信 |
| **decode** | 访存密集（每次算 1 个 token，小矩阵） | 算不满单卡，all-reduce 相对计算量占比变大 |

所以推理 **TP 不宜过大**，常见 2 / 4 / 8。decode 阶段开大 TP 通常是"为了省显存 / 降单请求延迟"，而不是为了提吞吐。

---

## 2. DP（数据并行）：解决"吞吐不够"

### 做法

**复制一份完整的模型**到每张卡（每个 DP rank），各副本**独立处理不同的请求**。

```
   +-------------------+     服务请求集 {R1, R2, R3}
   | G0: 完整模型副本 A |
   +-------------------+
   +-------------------+     服务请求集 {R4, R5, R6}
   | G1: 完整模型副本 B |
   +-------------------+
   （副本之间互不通信，各跑各的）
```

N 个 DP 副本 ≈ **近线性提升 N 倍吞吐**（只要显存够）。

### 代价

每个副本要完整持有模型 → **显存翻倍**。这是 DP 唯一的硬约束。

### 关键洞察：推理 DP 和训练 DP 本质不同

| | 训练 DP | 推理 DP |
|---|---|---|
| 各副本做什么 | 处理不同 batch，**但算同一份梯度** | 处理不同请求，**完全独立** |
| 通信 | 每步 all-reduce 同步梯度（重） | **几乎零通信** |
| 扩展性 | 卡数多了通信成瓶颈 | 极好，近似线性 |

正因为推理副本之间不需要同步梯度，**推理 DP 扩展性远好于训练 DP**。所以推理里提升吞吐，DP 几乎永远是最划算的手段——前提是显存够装下完整副本。

---

## 3. TP vs DP 对比一图流

```
            TP (切模型)                       DP (复制模型)
   +--------------------+            +--------------------+
   | G0: W*1/N + 对应KV |            | G0: 完整副本A      | <- 独立请求集
   | G1: W*1/N + 对应KV |            | G1: 完整副本B      | <- 独立请求集
   +--------------------+            +--------------------+
   每层 all-reduce 合并               副本间基本不通信
   解决: 显存 / 单层算力              解决: 吞吐
   代价: 每层通信                     代价: 显存翻倍
```

---

## 4. 为什么两者都要？典型组合

显存下限逼着你上 TP（单卡装不下），吞吐上限逼着你上 DP（单份不够快）。所以推理集群通常是 **TP × DP** 组合：

```
   16 张卡, 模型单卡装不下但 TP=4 能装下
   => 4 个 DP 副本, 每副本 TP=4

   DP0 = {G0,G1,G2,G3}   <- TP 内 all-reduce
   DP1 = {G4,G5,G6,G7}   <- TP 内 all-reduce
   DP2 = {G8,G9,...,G11}
   DP3 = {G12,...,G15}
   4 份独立服务不同请求 -> ~4 倍吞吐
```

### 经验法则

1. **先定 TP**：刚好让单份模型装下（含 KV cache 预算）的**最小** TP。
2. **剩下的卡做 DP**：复制副本提吞吐。
3. TP 能小则小——decode 阶段大 TP 的通信不划算，除非为了省 KV cache 显存或降单请求延迟。

---

## 5. EP（专家并行）：MoE 专用的 TP 变体

MoE 层太特殊（比如 256 个专家），用普通 TP 切权重很别扭。于是有 **EP（Expert Parallelism）**：

- **切专家，而不是切权重**：不同专家分到不同卡，每卡只存自己那组专家。
- **通信换成 all2all**：把 token 按"目标专家所在卡"搬过去算完再搬回来（TP 是 all-reduce 合并同一 token 的部分结果，EP 是 all2all 搬运不同 token）。

```
   TP (稠密层/注意力):                    EP (MoE FFN):
   切权重 W, 每卡算同一 token 的一部分      切专家, 每卡存不同专家
   all-reduce 合并                         all2all 搬 token 到目标专家卡
   +------+------+                        +E0..E63+E64..E127+ ...
   | G0   | G1   |  同一 token             每个 token 可能去别的卡
   +------+------+  的部分结果             -> all2all 搬运
```

### vLLM 里的关键设计

`enable_expert_parallel=True` 时（`vllm/model_executor/layers/fused_moe/config.py:1165`）：

- MoE FFN 的 **`tp_size` 归 1**（不再切权重），改用 **`ep_size = dp*pcp*tp`**。
- **只有 MoE FFN 受影响**：注意力层、稠密层继续用原 TP。

所以完整画面是：**稠密层/注意力用 TP，MoE FFN 用 EP，再用 DP 复制整套模型提吞吐**。EP 概念上就是"把 TP 的 all-reduce 换成 all2all，把切权重换成切专家"。

> 更多 EP / 通信调度 / EPLB 细节见同目录 `vllm-moe-scheduling-design.md`。

---

## 6. PP（流水线并行）：推理里很少用，要知道为什么

PP 把模型**按层切成几段**，每段放一张卡，请求像流水线一样穿过各段。

| | TP / EP | PP |
|---|---|---|
| 切法 | 切单个算子 / 专家 | 切层（按深度） |
| 通信 | 每层 collective | 只在段边界传一次激活 |
| 延迟 | 层内并行，不增加串行阶段 | **增加串行阶段数，抬高单请求延迟** |

**推理很少用 PP**：训练时 PP 能突破单层显存上限且能用 micro-batch 填满流水线；推理时尤其是 decode（每次 1 token），流水线很难填满，反而徒增延迟。只有模型极大、TP+DP 都撑不住时才考虑 PP。

---

## 7. 后端研发决策清单

面对"我这个模型怎么部署"时的思考顺序：

1. **显存够吗？** 单卡装得下权重 + KV cache 预算 → 直接 DP 提吞吐，最省心。
2. **装不下** → 上 TP（最小够用的 TP），把单份模型塞进 `tp_size` 张卡。
3. **是 MoE 且专家多** → 对 MoE FFN 开 EP（`enable_expert_parallel`），注意力层保留 TP。
4. **剩下卡做 DP** 复制副本提吞吐。
5. **极少情况**（超大模型）→ 才考虑 PP。
6. **decode 为主**的服务 → 控制 TP 大小，别为了并行而并行（通信会反噬）。

### vLLM 落地配置（`ParallelConfig`）

| 配置项 | 对应策略 |
|---|---|
| `tensor_parallel_size` | 稠密层/注意力的 TP |
| `data_parallel_size` | 复制副本提吞吐 |
| `enable_expert_parallel` | MoE FFN 改用 EP |
| `pipeline_parallel_size` | 分层流水线（少用） |
| `all2all_backend` | EP 的通信后端（DeepEP/NIXL/AG-RS…） |

---

## 8. 实战案例：Qwen3.6-35B-A3B 用 vLLM 部署的 TP/DP 分配

[Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) 是个典型 MoE，拿它把前面的心法走一遍。

### 8.1 模型画像

| 指标 | 值 | 对部署的影响 |
|---|---|---|
| 总参数 | 35B | BF16 权重 ≈ **70GB**；FP8 ≈ **35GB** |
| 激活参数 | 3B | 极稀疏 → decode 访存友好，单 token 计算量小 |
| 层数 | 40 | KV cache 层数适中 |
| 上下文 | 262K | 长上下文 → KV cache 吃显存，倾向更大 TP |
| 类型 | MoE | MoE FFN 该用 **EP**，不该纯 TP |

> 确切的 `num_experts / num_experts_per_tok / hidden_size` 见模型的 `config.json`，本节用"专家多、激活少"的 MoE 共性做策略推理。权重大小由 35B 参数直接算出（×2 BF16 / ×1 FP8），可靠。

### 8.2 四个决策 lever

1. **权重大小 → TP 下限**：BF16 70GB 决定单卡放不下（还要留 KV cache），必须切。
2. **MoE 层 → 开 EP**：专家多，EP（切专家 + all2all）比纯 TP（切权重 + all-reduce）高效。
3. **3B 小激活 → DP 收益高**：每 token 实际算得少，复制副本提吞吐很划算。
4. **262K 长上下文 → 倾向更大 TP**：KV cache 占显存大，TP 能把 KV cache 也切到各卡。

### 8.3 推荐配置（按硬件 + 精度）

| 场景 | 推荐配置 | 适用/理由 |
|---|---|---|
| 2× GPU | `--tp 2` | 显存只够纯 TP |
| 4× GPU（如 A10G 24G） | `--tp 4`（FP8 更佳） | 4×24=96GB 紧张，纯 TP |
| 8× H100 80G · BF16 · 通用 | `--tp 8 --enable-expert-parallel` | **官方默认**，最简单稳妥，KV cache 最宽 |
| 8× H100 80G · BF16 · 重吞吐 | `--tp 4 --enable-expert-parallel --dp 2` | 牺牲一点 KV cache 换并发 |
| 8× H100 80G · BF16 · 重并发 | `--tp 2 --enable-expert-parallel --dp 4` | decode 友好，副本多 |
| 8× H100 80G · FP8 · 重吞吐 | `--tp 2 --enable-expert-parallel --dp 4` | FP8 省一半显存，DP 最大化 |
| 8+ 卡 / 跨节点 | `--tp 8 --enable-expert-parallel`（+ DP 扩展） | 大规模，EP 后端用 `nixl`/`pynccl` |

### 8.4 命令示例

```bash
# 最稳：8× H100, BF16, 官方推荐
vllm serve Qwen/Qwen3.6-35B-A3B \
  --tensor-parallel-size 8 --enable-expert-parallel

# 重吞吐：BF16, 多副本并发
vllm serve Qwen/Qwen3.6-35B-A3B \
  --tensor-parallel-size 4 --enable-expert-parallel \
  --data-parallel-size 2

# FP8 重吞吐：单卡即可放权重，DP 最大化
vllm serve Qwen/Qwen3.6-35B-A3B-FP8 \
  --tensor-parallel-size 2 --enable-expert-parallel \
  --data-parallel-size 4
```

### 8.5 心法 + 一个易踩的坑

对"小激活大总量"的 MoE（A3B 这类），心法是：**EP 优先于 TP（针对 MoE 层），TP 够装下就行别贪大，剩下的卡和显存全拿去做 DP 提吞吐。FP8 是把"必须 TP=4+"松绑成"TP=2 甚至单卡"的关键 lever，能显著释放 DP 空间。**

> ⚠️ **易踩的坑**：vLLM 里开了 `enable_expert_parallel` 后，EP 组横跨 DP×TP（详见 `vllm-moe-scheduling-design.md`）。所以 `--dp N` 的副本在 MoE 层会通过 all2all 融合（batched DP-MoE），并非完全独立——这对 MoE 吞吐反而是好事（all2all 的 token 更多更高效），但意味着"DP=N 倍吞吐"是近似而非精确线性。

**参考来源**：[vLLM Expert Parallel Deployment 文档](https://docs.vllm.ai/en/latest/serving/expert_parallel_deployment/)、[vLLM Qwen3 Usage Guide #17327](https://github.com/vllm-project/vllm/issues/17327)、[AMD ROCm vLLM MoE Playbook](https://rocm.blogs.amd.com/software-tools-optimization/vllm-moe-guide/README.html)。

---

## 9. 一句话总结

- **TP** 解决"装得下、单层算得快"（切模型，付每层通信）；prefill 友好，decode 要克制。
- **DP** 解决"吞吐高"（复制模型，付显存）；推理 DP 因不同步梯度而扩展性极佳，和训练 DP 截然不同。
- **EP** 是 TP 在 MoE 专家维度上的特化（切专家 + all2all）。
- 组合心法：**TP 撑显存下限，DP 撑吞吐上限，MoE 换 EP，PP 尽量别用。**
