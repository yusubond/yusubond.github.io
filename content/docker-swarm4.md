Title: Docker进阶：以Swarm模式运行Docker引擎
Date: 2017-04-28
Category: TECH
Tags: Cloud, Docker
Slug: docker-swarm-jin-jie1
Author: subond
Summary:Docker Engine 1.12及后续版本支持Swarm模式，我们可以通过以下两种方式开始Swarm模式：创建一个Swarm集群和加入一个已有的Swarm集群。

Docker Engine 1.12及后续版本支持Swarm模式，我们可以通过以下两种方式开始Swarm模式：

+ 创建一个Swarm集群
+ 加入一个已有的Swarm集群

本文目录：

+ [创建Swarm](#创建Swarm)
+ [加入Swarm](#加入Swarm)
+ [节点管理](#节点管理)

### 创建Swarm

当我们使用命令行创建一个Swarm集群时，Docker引擎将启用Swarm模式。当执行`docker swarm init`命令时，Docker引擎将启动一个Swarm集群，主要过程如下：

+ 将当前的模式切换至Swarm模式，并创建一个名为`default`的Swarm
+ 指定当前节点为Swarm的管理节点，并以当前主机名命名当前节点
+ 配置网络监听端口，端口号为2377
+ 将当前节点设置为`Active`状态，意味着该节点可以接收调度器分派的任务
+ 启动一个全局分布式数据中心，存储并维护Swarm信息和服务信息
+ 默认情况下，为Swarm集群生成自签名根CA
+ 默认情况下，生成工作节点和管理节点的token(令牌)，用于其他节点加入该Swarm
+ 创建一个名为`ingress`的overlay网络，用于对外发布服务端口

```
# 创建一个swarm
$ docker swarm init
```

**配置通告地址**

管理节点通过通告地址(advertise address)来允许Swarm集群中的其他节点访问Swarmkit API和覆盖网络。Swarm集群上的其他节点必须能够访问其通告地址(Ip地址)上的管理节点。

如果不指定通告地址，Docker则通过检查系统IP，设置其中一个为通告地址，并监听2377端口。如果系统有多个Ip，最好通过--advertise-addr配置通告地址，以便其他节点能够与管理节点进行通信。

```
# 设置通告地址
$ docker swarm init --advertise-addr 172.28.128.3:2377
Swarm initialized: current node (34y77dgnqon4soj2kqyb65a9y) is now a manager.

To add a worker to this swarm, run the following command:

    docker swarm join \
    --token SWMTKN-1-1omg2k2e92snxv3wlja3komux5wan4hynn80ikkma2s9rd5cxz-9hq2vf8n0jysukytfqpavd8j7 \
    172.28.128.3:2377

To add a manager to this swarm, run 'docker swarm join-token manager' and follow the instructions.

```

**查看节点加入指令**

如前所述，其他节点加入Swarm需要使用正确的token值。对于管理节点和工作节点，其加入Swarm使用的token值是不同的。

```
# 向Swarm中加入管理节点 docker swarm join-token manager
$ docker swarm join-token manager
To add a manager to this swarm, run the following command:

    docker swarm join \
    --token SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-86w02153sf0kbncz42aoa41p9 \
    10.0.2.15:2377

# 向Swarm中加入工作节点 docker swarm join-token worker
$ docker swarm join-token worker
To add a worker to this swarm, run the following command:

    docker swarm join \
    --token SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-6t4a6w0shlr78nc55hh9si3ll \
    10.0.2.15:2377
# 通过对比可以发现，管理节点和工作节点使用的是不同的token值
# 两个token值的前半部分是一样的，即根证书的摘要是一样的；后半部分是不一样的，即随机生成的密钥
```

通过传递--quiet标志，可以仅输出token值。

```
# 输出工作节点的token值
$ docker swarm join-token --quiet worker
SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-6t4a6w0shlr78nc55hh9si3ll

# 输出管理节点的token值
$ docker swarm join-token --quiet manager
SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-86w02153sf0kbncz42aoa41p9
```

Swarm集群的token值是需要保护的，因为它允许新的工作节点/管理节点加入该Swarm。Docker建议我们在以下情况下轮换token值：

+ 如果token被意外登记到版本控制系统中，群聊或日志中。
+ 如果怀疑某个节点被入侵。
+ 如果希望保证没有新的节点加入Swarm集群。

出于对Swarm集群的保护，建议至少每6个月轮换一次token值。

```
# 轮换工作节点token值
$ docker swarm join-token --roteate worker
# 轮换管理节点token值
$ docker swarm join-token --rotate manager
```

### 加入Swarm

当我们创建一个Swarm集群时，只是创建一个包含单个管理节点的Swarm集群。为了充分利用Swarm集群的优势，我们可以向Swarm集群中加入其它节点。

+ 加入工作节点(worker node)以实现Swarm的增容。当我们向Swarm集群中部署服务时，调度器可以通过random/binpacking/spread策略向可用的节点上分派任务。因此，增加工作节点可以提高Swarm对于服务的处理能力。

+ 加入管理节点(manager node)以提高Swarm的容错性。管理节点负责Swarm集群的编排和管理。如果存在多个管理节点时，当单一的主管理节点出现宕机时，其他管理节点则可以通过选举产生新的主管理节点来保证整个Swarm集群的正常运行。默认情况下，管理节点也运行任务。

**加入工作节点**

在管理节点上，通过命令`docker swarm join-token worker`查看加入工作节点的token值。

```
# 在管理节点上
$ docker swarm join-token worker
To add a worker to this swarm, run the following command:

    docker swarm join \
    --token SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-6t4a6w0shlr78nc55hh9si3ll \
    10.0.2.15:2377

# 在预接入的工作节点上
$ docker swarm join \
--token SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-6t4a6w0shlr78nc55hh9si3ll \
10.0.2.15:2377
```

命令`docker swarm join`主要的工作流程包括：

+ 将当前节点Docker Engine切换至Swarm模式
+ 向管理节点请求一个TLS证书
+ 基于token将当前节点加入到管理节点监听地址所在的Swarm集群
+ 设置当前节点为`Active`状态，意味着该节点可以接收分派的任务
+ 将入口翻盖网络扩展至当前节点

**加入管理节点**

当我们向Swarm集群中加入管理节点时，Docker引擎同样将当前节点切换至Swarm模式。与工作节点不同的是，管理节点的状态是`Reachable`（可达的），已经存在的管理节点将成为Leader管理节点，即主管理节点。

Docker建议在每个Swarm集群中放置三到五个管理节点以提高整个集群的高可用性。因为，Swarm模式下管理节点之间通过Raft共享数据，因此需要奇数个管理节点。

在管理节点上，通过命令`docker swarm join-token manager`查看加入管理节点的token值。

```
# 在管理节点上
$ docker swarm join-token manager
To add a manager to this swarm, run the following command:

    docker swarm join \
    --token SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-86w02153sf0kbncz42aoa41p9 \
    10.0.2.15:2377

# 在预加入的管理节点上
$ docker swarm join \
--token SWMTKN-1-35n1uqy8q7si9lvkapojdkxjcntl5uixtdg1xo0ib3b2sg9t8g-86w02153sf0kbncz42aoa41p9 \
10.0.2.15:2377
```

### 节点管理

作为Swarm集群管理生命周期的一部分，我们需要掌握节点的主要操作：

+ [列出Swarm集群中的所有节点](#列出节点)
+ [检查单个节点](#检查节点)
+ [节点的更新](#更新节点)
+ [节点离开Swarm集群](#节点离开)

#### 列出节点

在管理节点上通过命令`docker node ls`可以查看Swarm集群中的所有节点。

```
# 在管理节点上
$ docker node ls
ID                           HOSTNAME  STATUS  AVAILABILITY  MANAGER STATUS
i8yofrrddqu8mkved5s2uwb0s    worker2   Ready   Active
utfwatnlalniyo5glt734m4sj *  manager   Ready   Active        Leader
xf5ysyp7n2biukskzigc5f3bd    worker1   Ready   Active
```

`AVAILABILITY`标志状态，描述了调度器是否可以将任务分派至该节点，有三个值：

+ Active:激活状态，意味着调度器可以向该节点分派任务
+ Pause:暂停状态，意味着调度器不可以向该节点分派新的任务，但是原有的任务将正常运行
+ Drain:排水状态，意味着调度器不可以向该节点分派新的任务，并且将其原来负责的任务迁移至其他可用节点。

`MANAGER STATUS`标志状态，显示了节点的是否参与Raft共识过程，有四个值：

+ 无状态标记，意味着该节点是工作节点，不参与Swarm集群管理
+ Leader:意味着该节点是主管理节点，负责整个Swarm集群的管理和服务编排
+ Reachable:意味着该节点参与Raft共识过程。如果Leader节点变成不可达状态，该节点则参与选举产生新的Leader过程。
+ Unavailable:意味着该节点不能够与其他管理节点进行通信。当一个管理节点变成不可达状态，最好向Swarm集群中加入新的管理节点或者将其中的一个工作节点变成管理节点。

#### 检查节点

我们可以通过命令`docker node inspect <NODE-ID>`查看单个节点的信息，默认信息的输出格式为JSON格式，也可以通过--pretty标志以可读的方式输出节点信息。

```
# 在管理节点上
$ docker node inspect self --pretty
ID:			utfwatnlalniyo5glt734m4sj
Hostname:		manager
Joined at:		2017-05-11 08:23:12.477597386 +0000 utc
Status:
 State:			Ready
 Availability:		Active
 Address:		172.28.128.3
Manager Status:
 Address:		172.28.128.3:2377
 Raft Status:		Reachable
 Leader:		Yes
Platform:
 Operating System:	linux
 Architecture:		x86_64
Resources:
 CPUs:			2
 Memory:		992.2 MiB
Plugins:
  Network:		bridge, host, macvlan, null, overlay
  Volume:		local
Engine Version:		17.03.1-ce

$ docker node inspect worker1 --pretty
ID:			xf5ysyp7n2biukskzigc5f3bd
Hostname:		worker1
Joined at:		2017-05-11 08:31:54.044503498 +0000 utc
Status:
 State:			Ready
 Availability:		Active
 Address:		172.28.128.4
Platform:
 Operating System:	linux
 Architecture:		x86_64
Resources:
 CPUs:			2
 Memory:		992.2 MiB
Plugins:
  Network:		bridge, host, macvlan, null, overlay
  Volume:		local
Engine Version:		17.03.1-ce
```

### 更新节点

在Swarm集群中，我们可以修改节点的以下属性：

+ 改变节点的可用性
+ 添加/移除标签元数据
+ 改变节点的角色

**改变节点的可用性**

改变节点的可用性主要包括：

+ 将管理节点置为`Drain`状态，这样做意味着该节点只负责Swarm集群的管理工作，而不具备运行任务的功能，使节点成为“纯管理节点”。
+ 将节点置为`Drain`状态，以便将其停止并进行维护工作。
+ 将节点置为`Pause`状态，使它不再接收新的任务
+ 将节点由暂停或不可达状态置为可达状态，使其重新接收新任务

```
# 将worker1节点置为drain状态
$ docker node update --availability drain worker1
worker1
$ docker node ls
ID                           HOSTNAME  STATUS  AVAILABILITY  MANAGER STATUS
i8yofrrddqu8mkved5s2uwb0s    worker2   Ready   Active
utfwatnlalniyo5glt734m4sj *  manager   Ready   Active        Leader
xf5ysyp7n2biukskzigc5f3bd    worker1   Ready   Drain
```

**添加/移除标签元数据**

节点标签提供了一种节点管理的灵活方式，当然，在进行服务部署和限制时也可以使用节点标签。在管理节点上运行命令`docker node update --label-add`，可以向一个节点添加标签，`--label-add`标志接收键参数(<key>)，也可以接收键值对(<key>=<value>)。

```
# docker node update --label-add subond worker1
# docker node inspect worker1 --pretty
ID:			xf5ysyp7n2biukskzigc5f3bd
Labels:
 - subond =
Hostname:		worker1
Joined at:		2017-05-11 08:31:54.044503498 +0000 utc
Status:
 State:			Ready
 Availability:		Active
 Address:		172.28.128.4
Platform:
 Operating System:	linux
 Architecture:		x86_64
Resources:
 CPUs:			2
 Memory:		992.2 MiB
Plugins:
  Network:		bridge, host, macvlan, null, overlay
  Volume:		local
Engine Version:		17.03.1-ce
```

**节点角色的转换**

Docker允许提升工作节点为管理节点，尤其是在管理节点宕机时，这个方法很有用。当然，我们也可以将管理节点降为工作节点。

```
# 提升节点角色命令 docker node promote
$ docker node promote worker1

# 降低节点角色命令 docker node demote
$ docker node demote worker1
```

`docker node promote`和`docker node demote`命令是`docker node update --role manager`和`docker node update --role worker`命令的简化版，两者具有同样的作用。

#### 节点离开

命令`docker swarm leave`可以使一个节点离开Swarm集群。当一个节点离开Swarm集群时，该节点的Docker引擎将停止运行Swarm模式，调度器不再将任务分派值该节点。如果该节点是管理节点，移除节点将收到警告信息，可以通过--force参数强制移除。
