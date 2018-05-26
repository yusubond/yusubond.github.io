Title: LTE系统网络架构
Date: 2016-05-10
Category: TECH
Tags: architecture, lte
Slug: lte-xi-tong-wang-luo-jia-gou
Author: subond
Summary: 整个LTE网络是由核心网（EPC,Evolved Packet Core）和接入网（E-UTRAN）组成，如图1-1所示。核心网由许多逻辑节点组成，而接入网只有一个节点，即与用户终端（UE）相连的eNodeB。所有网元都通过接口相互连接，通过对接口的标准化，可以满足众多供应商产品间的互操作性。

整个LTE网络是由核心网（EPC,Evolved Packet Core）和接入网（E-UTRAN）组成，如图1-1所示。核心网由许多逻辑节点组成，而接入网只有一个节点，即与用户终端（UE）相连的eNodeB。所有网元都通过接口相互连接，通过对接口的标准化，可以满足众多供应商产品间的互操作性。

![lte-xitong](http://on64c9tla.bkt.clouddn.com/20160510lte-xitong.jpg)

图1-1&nbsp;LTE系统网络架构示意图

与3G系统相比，LTE系统重新定义了系统网络架构，核心网和接入网之间的功能划分也随之有所变化，针对LTE系统架构，网络功能划分如图1-2所示。

![lte-xieyi](http://on64c9tla.bkt.clouddn.com/20160510lte-xitong-gongneng-xieyi.jpg)

图1-2&nbsp;LTE系统功能实体划分、协议架构示意图

### 1.接入网

LTE接入网E-UTRAN仅由eNodeB组成，网络架构中节点数量减少，网络架构更加趋于扁平化，这种扁平化的网络架构可以有效地降低呼叫时延以及用户数据传输时延。E-UTRAN系统提供用户平面和控制平面的协议，用户平面用户平面包括分组数据汇聚协议（PDCP,Packet Data Convergence Protocol）层、 无线链路层控制（RLC,Radio Link Control）层、媒体接入层（MAC,Medium Access Control）层；控制平面包括无线资源控制（RRC,Radio Resource Control）层。eNodeB之间通过X2接口进行连接，通过S1接口与EPC连接，具体来说就是，通过S1-MME接口连接到MME，通过S1-U接口连接到S-GW。eNodeB与UE间的协议为接入层（AS）协议。

eNodeB具有如下功能：

（1）无线资源管理相关的功能，如无线资源承载控制、接纳控制、连接移动性管理、上/下行动态资源分配/调度等；  
（2）IP头压缩与用户数据流的加密；  
（3）UE附着时的MME选择。由于eNodeB可以与 多个MME/S-GW之间存在S1接口相连，因此，UE初始接入到网络时，需要选择一个MME进行附着;  
（4）寻呼信息的调度和传输；  
（5）广播信息的调度和传输；  
（6）用于移动和调度的测量和测量报告的配置。  

### 2.核心网

核心网负责对用户终端的全面控制和有关承载的建立。EPC的主要逻辑节点有：

+ 分组数据网关（P-GW,Packet Data Network Gateway）  
+ 服务网关（S-GW,Serving Gateway）  
+ 移动性管理实体（MME, Mobility Management Entity）  
+ 归属签约用户服务器（HSS,Home Subscriber Server）  
+ 策略及计费规则功能（RCPF,Policy and Charging Rules Function）  

EPC逻辑主要节点的功能，下面详细介绍。

(1) **P-GW：分组数据网关**

P-GW提供与外部分组数据网络的连接，是主要的移动性处理节点。P-GW负责用户IP地址分配和QoS保证，并根据PCRF规则进行基于流量的计费。一个UE可能和多个P-GW相连 ，P-GW同时负责UE IP地址的分配。P-GW为保证比特率承载提供QoS保证。另外，P-GW可以通过一系列不同的接口，成为其他3GPP网络或非3GPP网络。

(2) **S-GW：服务网关**

S-GW通过S1-U接口来实现用户数据包的路由和转发。实现的功能主要有数据通道、IP头压缩处理、用户数据流加密、针对移动性的用户面的切换、寻呼时用户面数据包的终止。当用户在eNodeB之间移动时，S-GW作为数据承载的本地移动性管理实体。当用户处于空闲状态时， S-GW将保留承载信息并临时把下行数据存储在缓存区里，以便当MME开始寻呼UE时重新建立承载。同时，在与其他3GPP技术如GPRS和UMTS等交互工作时，它可以作为“**移动性管理锚点**”。

(3) **MME：移动性管理实体**
MME是处理UE和核心网络信令交互的控制节点。在UE和核心网络间所执行的协议栈成为非接入层协议（NAS）。MME具有如下功能：

+ 寻呼信息分发。MME负责将寻呼信息按照一定的原则分发到相关的eNodeB;    
+ 安全控制;  
+ 空闲状态的移动性管理;  
+ SAE（系统架构演进）承载控制;  
+ 非接入层信令的加密和完整性保护。  

(4) **HSS：归属签约用户服务器**

HSS作为用户的集中签约管理数据库，存放了用户的EPS网络签约信息，并完成对UE的位置登记管理，以及结合AUC（鉴权中心）网元完成用户鉴权参数管理，并通过S6a接口下发给 MME完成对UE的鉴权即安全功能。

(5) **PCRF：策略及计费规则功能**

PCRF网元是SAE架构中提供集中策略和计费控制的网元。PCRF主要完成策略控制的决定功能及基于不同IP流的计费控制功能。因此，PCRF要结合PCEE（Policy and Charging Enforcement Function）网元 检测后上报的不同业务类型来进行QoS及计费策略方面的决策，并通过Ｇx接口将策略下发给PCEF网元去执行。

### 3.主要业务接口

### S1接口

S1接口是MME/S-G网关和eNodeB之间的接口。S1接口又可以分为两个接口，一个用于用户平面S1-U，一个用于控制平面S1-MME。

+ 用户平面

S1-U接口用于提供eNodeB与S-GW网元之间用户数据传输功能，其协议栈如图3-1所示。S1-U的传输网络层基于IP传输，UDP/IP协议之上采用GTP-U（GPRS Tunnelling Protocol for User Plane：GPRS用户平面隧道协议）来传输S-GW与eNodeB之间的用户平面PDU。

![s1-u](http://on64c9tla.bkt.clouddn.com/20160510s1-u-xie-yi-zhan.jpg)

图3-1&nbsp;S1-U接口协议栈

+ 控制平面

S1-MME也是基于IP传输的，不同的是控制平面在IP层的上面采用SCTP（Stream Control Transmission Protocol：流控制传输协议），为无线网络层信令消息提供可靠的传输，其协议栈如图3-2所示。

![s1-mme](http://on64c9tla.bkt.clouddn.com/20160510s1-mme-xie-yi-zhan.jpg)

图3-2&nbsp;S1-MME接口协议栈

### X2接口

X2接口是eNodeB与eNodeB之间的接口，采用了与S1接口一致的原则，其用户平面协议接口与控制平面协议接口均与S1接口类似。

+ 用户平面

X2接口是eNodeB与eNodeB之间的接口，采用了与S1接口一致的原则，其用户平面协议接口与控制平面协议接口均与S1接口类似。
