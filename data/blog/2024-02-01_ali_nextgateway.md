---
title: '阿里基于DPU的下一代边缘云网关实践'
date: '2024-02-01'
tags: ['云网络', 'DPU', 'SmartSwitch', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

## 前言

在过去的2023年 OCP 全球峰会上，阿里分享了基于 DPU 的下一代云网关的架构。

<a name="Nhckp"></a>

## 边缘云网关

阿里的云网关主要有两类，一类是中心云，一类是边缘云。在边缘云中，网关有两个重要的功能，分别是连接服务器的 TOR Switch 功能，和网关功能（包括VTEP，NAT，LB等）。<br />

![NwI67m](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/NwI67m.png)

<br />当前这一代云网关所面临的挑战，以及云网关所要完成的关键指标。<br />

![NJcWv7](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/NJcWv7.png)<br />![GYqWJ6](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/GYqWJ6.png)

<a name="lfPGy"></a>
## 架构升级
在上一代网关中采用 Server Switch 架构，即 P4 交换芯片 + X86 CPU。其中 ASIC 负责无状态的高性能转发，X86 CPU 负责有状态、复杂逻辑处理，包括 NAT，LB，Sec等。<br />而下一代云网关采用的是交换芯片 + X86 CPU + DPU 架构，称为 Smart Switch。两代架构相比，有几个区别：

- 把上一代的 P4 交换芯片，换成了通用交换芯片。这部分依然处理无状态流量，做高性能转发，好处就是减少了对特定 P4 芯片的依赖。
- 原来由 X86 CPU 处理的有状态流量，卸载到 DPU 上。这样做既能重复利用 DPU 上核心的处理能力，又能发挥 DPU 的硬件卸载。

![7dEzuW](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/7dEzuW.png)

<a name="F8949"></a>
## 硬件和软件架构
硬件方面，一个 1RU 的交换机，插上两块 AMD 的 DPU。<br />每张 DPU 卡最大可支持 200G 带宽，通过 PCIe 连接到交换机的 CPU 模块；<br />交换机上的 ASIC 可出 24 个 200G，和 8 个 400G 网卡，总共 8T 的带宽。<br />![ZM9Y6A](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/ZM9Y6A.png)

软件方面，交换机上运行 SONIC，DPU 上也运行 SONiC。同时，DPU 上做了快慢路径分离。<br />![A4nNqn](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/A4nNqn.png)<br />软件架构上采用的是 DASH 架构。<br />SONic DASH 是 SONiC 下的一个开源项目，旨在为关键云应用程序提供企业级网络性能，将功能扩展到有状态的网络负载。<br />首先，对业务需求进行分析，并进行建模，通过 P4 编写转发模型。第二步，对 P4 编译，并加载到 DPU 的 ASIC 上。<br />![qGmd3a](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/qGmd3a.png)<br />![em678o](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/em678o.png)<br />![1eKIFd](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/1eKIFd.png)<br />从用户角度来说，用户只需要关注自己的业务模型，并做好性能和测试用例；而 DPU 厂商，负责将关注用户模型和测试用例适配到 DPU 的 ASIC。

<a name="FaVhF"></a>
## AMD DPU介绍
阿里下一代云网关架构中的 DPU 采用的是 AMD Pensando，可以看到这款 DPU 上的 ASIC 支持 P4 编程。<br />

![hboWJJ](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/hboWJJ.png)

<a name="vV2Y4"></a>
## 收益
两代云网关相比，新一代云网关，TCO 降低了 50%，同时有状态的业务处理性能提升了 4 倍。<br />![v51CEh](https://wechat-1315555539.cos.ap-nanjing.myqcloud.com/uPic/v51CEh.png)
