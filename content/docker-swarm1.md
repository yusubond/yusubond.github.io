Title: Docker集群：服务部署
Date: 2017-04-22
Category: TECH
Tags: Cloud, Docker
Slug: docker-swarm-fu-wu-bu-shu
Author: subond
Summary:一个Swarm是一组Docker引擎或节点的集群，并在这个集群之上部署服务和应用。我们可以使用Docker命令行工具或者API管理集群中的节点，并且还可以通过Swarm部署和编排相应的服务。当我们没有使用Swarm模式的时候，我们只是简单地对容器进行操作；而在Swarm模式下，我们就可以对服务进行编排。值得注意的是，在同一个Docker实例上既可以运行Swarm的服务，也可以运行独立的容器。

一个Swarm是一组Docker引擎或节点的集群，并在这个集群之上部署服务和应用。我们可以使用Docker命令行工具或者API管理集群中的节点，并且还可以通过Swarm部署和编排相应的服务。当我们没有使用Swarm模式的时候，我们只是简单地对容器进行操作；而在Swarm模式下，我们就可以对服务进行编排。值得注意的是，在同一个Docker实例上既可以运行Swarm的服务，也可以运行独立的容器。

本文目录：

+ [核心概念](#核心概念)
+ [搭建Swarm集群](#搭建Swarm集群)

### 核心概念

**Swarm**

一个Swarm是一组Docker引擎或节点的集群，并在这个集群之上部署服务和应用。我们可以使用Docker命令行工具或者API管理集群中的节点，并且还可以通过Swarm部署和编排相应的服务。当我们没有使用Swarm模式的时候，我们只是简单地对容器进行操作；而在Swarm模式下，我们就可以对服务进行编排。值得注意的是，在同一个Docker实例上既可以运行Swarm的服务，也可以运行独立的容器。

**节点**

一个节点即是参与Swarm集群的Docker引擎实例。我们可以将其理解为一个Docker节点。虽然，我们可以在同一物理主机或云服务上运行一个或多个节点，但是典型的Swarm生产环境则是在分布式的物理主机或云服务上部署多个Docker节点。

当部署一个服务到Swarm集群中时，我们需要率先在 **管理节点** 上注册该服务。然后，管理节点将该服务（称之为 **任务**）分派给各个 **工作节点**。

管理节点(Swarm Manager)负责服务编排和集群管理以保证整个集群的正常运行，并负责选出一个leader进行任务编排工作。

工作节点(Swarm Agent)负责接收并执行管理节点派发下来的任务。默认情况下，管理节点同时扮演工作节点的角色，即接收并执行任务。当然，我们也可以通过配置让管理节点只负责任务管理的功能，使之成为“只具备管理”的节点。Agent在每个工作节点上运行，并报告分派给它的任务。工作节点向管理节点报告其分派到的任务的当前状态，以便管理节点可以维护每个工作节点所需的状态。

**服务和任务**

一个服务是指运行在工作节点上任务的定义。它是Swarm系统的中心结构，也是用户与Swarm交互的主要根据。当创建一个服务时，我们需要指定容器即将使用的镜像以及容器中要执行的命令。在服务分派模型中，Swarm的管理节点根据我们在所需状态下设置的比例，在工作节点中分配特定数量的任务副本。对于全局服务，Swarm在集群中的每个可用工作节点上为服务运行一个任务。

一个任务带有一个Docker容器和在容器中执行的命令。任务是Swarm进行服务管理的原子调度单元。管理节点根据服务规模中设置的副本数量将任务分派给工作节点。一旦一个任务分派给某个节点，任务就不能移动到另一个节点，它只能在分配的节点上运行或者失败，这即是任务的原子性。

**负载均衡**

Swarm集群管理使用的是 **入口负载均衡** 策略来暴露想要从外部访问的服务。Swarm的管理节点可以自动地给服务分配一个PublishedPort，也可以为该服务自行配置一个PublishedPort。如果不指定端口，Swarm管理节点将分配30000-32767之间的某个端口。

外部组件，像云端负载均衡，可以访问集群中任何一个节点的PublishedPort，无论这个节点当前是否在运行某个服务的任务。Swarm路由中的所有节点都将连接到正在运行任务实例的节点上。

Swarm中还有一个内部DNS组件，可自动为集群中的每个服务分配DNS条目。Swarm管理节点使用内部负载均衡，根据服务的DNS名称在集群内部的服务之间分配请求。

### 搭建Swarm集群

搭建Swarm集群过程中，所使用的系统环境环境如下：

* 三个节点(manager, worker1, worker2)均为xenial64系统  
* 节点的IP分布，manager(172.28.128.3), worker1(172.28.128.4), worker2(172.28.128.5)  

**1.创建一个Swarm集群**

在manager所在的主机创建Swarm集群，即创建Swarm管理节点。

```
# 在manager节点上
# 使用docker swarm init --advertise-addr <manager-ip>命令创建Swarm的管理节点
$ docker swarm init --advertise-addr 172.28.128.0.3
Swarm initialized: current node (utfwatnlalniyo5glt734m4sj) is now a manager.
To add a worker to this Swarm, run the following command:
    docker Swarm join \
    --token SWMTKN-1-3pa0dv3m2spedchgfrt2zuv9x2ykuxdj3liegogxub9fijimy1-4xrv3f26wk7lkrrf2q672ew3m \
    172.28.128.3:2377
To add a manager to this Swarm, run 'docker Swarm join-token manager' and follow the instructions.
# docker node ls查看管理节点的状态
$ docker node ls
ID                           HOSTNAME       STATUS  AVAILABILITY  MANAGER STATUS
utfwatnlalniyo5glt734m4sj *  ubuntu-xenial  Ready   Active        Leader
```

**2.向Swarm中注册工作节点**

在worker[1-2]所在的主机创建Swarm工作节点，并加入到Swarm集群中。

```
# 在worker1节点上
$ docker Swarm join \
$ --token SWMTKN-1-3pa0dv3m2spedchgfrt2zuv9x2ykuxdj3liegogxub9fijimy1-4xrv3f26wk7lkrrf2q672ew3m \
$ 172.28.128.3:2377
This node joined a Swarm as a worker.

# 在worker2节点上
$ docker Swarm join \
$ --token SWMTKN-1-3pa0dv3m2spedchgfrt2zuv9x2ykuxdj3liegogxub9fijimy1-4xrv3f26wk7lkrrf2q672ew3m \
$ 172.28.128.3:2377
This node joined a Swarm as a worker.
# 使用命令docker Swarm leave将节点移除Swarm集群

# 在manager节点上
$ docker node ls
ID                           HOSTNAME       STATUS  AVAILABILITY  MANAGER STATUS
i8yofrrddqu8mkved5s2uwb0s    ubuntu-xenial  Ready   Active
utfwatnlalniyo5glt734m4sj *  ubuntu-xenial  Ready   Active        Leader
xf5ysyp7n2biukskzigc5f3bd    ubuntu-xenial  Ready   Active
# 可以看到当前Swarm集群中已经存在三个节点，并且用*指出管理节点的ID
# 需要注意的是，命令docker node ls只能工作在管理节点上，用于查看Swarm集群中的节点状态
```

**3.向Swarm集群中部署服务**

服务的部署和管理均在管理节点上进行。

```
# 在manager节点上
$ docker service create --replicas 1 --name helloworld alpine ping docker.com
kugt1fx2j2es172l4zmvr0fbk
# --name 指定服务名称
# --replicas 指定任务的副本数量
# alpine ping docker.com 表示该服务所使用的容器镜像和容器中要执行的命令

# 使用命令docker ps可以查看主机上服务运行所在的docker容器的状态
$ docker ps
CONTAINER ID        IMAGE                                                                            COMMAND             CREATED             STATUS              PORTS               NAMES
8a0bd7183d20        alpine@sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96   "ping docker.com"   3 minutes ago       Up 3 minutes                            helloworld.1.f1b58uxk5c1l56736uznzapjm

# 使用docker service ls查看服务
ID            NAME        MODE        REPLICAS  IMAGE
kugt1fx2j2es  helloworld  replicated  1/1       alpine:latest
```
**4.服务检查**

当我们向Swarm集群中部署服务后，可以使用docker命令查看服务的运行状态。

```
# 命令docker service inspect --pretty <SERVICE-ID>可以以可读的格式显示服务的细节信息
# 在manager节点上
$ docker service inspect --pretty helloworld
ID:		kugt1fx2j2es172l4zmvr0fbk
Name:		helloworld
Service Mode:	Replicated
 Replicas:	1
Placement:
UpdateConfig:
 Parallelism:	1
 On failure:	pause
 Max failure ratio: 0
ContainerSpec:
 Image:		alpine:latest@sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96
 Args:		ping docker.com
Resources:
Endpoint Mode:	vip

# 命令docker service ps <SERVICE-ID>可查看服务/任务运行在哪个节点上
$ docker service ps helloworld
ID            NAME          IMAGE          NODE           DESIRED STATE  CURRENT STATE           ERROR  PORTS
f1b58uxk5c1l  helloworld.1  alpine:latest  ubuntu-xenial  Running        Running 13 minutes ago
# 在任务运行的节点上，可使用docker ps查看容器运行的信息
```

**5.Swarm集群中服务的缩放**

一旦向Swarm中部署服务后，我们还可以调整某项服务的容器数量，即任务的数量。命令如下:

```
$ docker service scale <SERVICE-ID>=<NUMBERS-OF-TASKS>
```

```
# 在manager节点上
# 将之前部署的helloworld服务扩大至5个任务
$ docker service scale helloworld=5
helloworld scaled to 5

# 查看5个任务的分布情况及运行状态
$ docker service ps helloworld
ID            NAME          IMAGE          NODE           DESIRED STATE  CURRENT STATE           ERROR  PORTS
f1b58uxk5c1l  helloworld.1  alpine:latest  ubuntu-xenial  Running        Running 28 minutes ago
xkgyz1874p3r  helloworld.2  alpine:latest  ubuntu-xenial  Running        Running 2 minutes ago
0rnlxcv4487o  helloworld.3  alpine:latest  ubuntu-xenial  Running        Running 2 minutes ago
izu5oeb5qerp  helloworld.4  alpine:latest  ubuntu-xenial  Running        Running 2 minutes ago
m2v2uzgoy9g1  helloworld.5  alpine:latest  ubuntu-xenial  Running        Running 2 minutes ago

$ docker ps
CONTAINER ID        IMAGE                                                                            COMMAND             CREATED             STATUS              PORTS               NAMES
ea297aa56bc4        alpine@sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96   "ping docker.com"   2 minutes ago       Up 2 minutes                            helloworld.5.m2v2uzgoy9g1sdohtdyenjclu
8a0bd7183d20        alpine@sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96   "ping docker.com"   29 minutes ago      Up 29 minutes                           helloworld.1.f1b58uxk5c1l56736uznzapjm
# 可以看到在manager主机上运行着1和5号任务

# 在worker1节点上
$ docker ps
CONTAINER ID        IMAGE                                                                            COMMAND             CREATED             STATUS              PORTS               NAMES
ebd0c448b9a4        alpine@sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96   "ping docker.com"   15 minutes ago      Up 15 minutes                           helloworld.2.xkgyz1874p3rsaih8e1jbfmyx
# 运行着2号任务

# 在worker2节点上
$ docker ps
CONTAINER ID        IMAGE                                                                            COMMAND             CREATED             STATUS              PORTS               NAMES
a30267238db2        alpine@sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96   "ping docker.com"   5 minutes ago       Up 5 minutes                            helloworld.3.0rnlxcv4487o0y4qqaot7n0yt
bb5b75e55b30        alpine@sha256:c0537ff6a5218ef531ece93d4984efc99bbf3f7497c0a7726c88e2bb7584dc96   "ping docker.com"   5 minutes ago       Up 5 minutes                            helloworld.4.izu5oeb5qerpkfjde4bna47e5
```

**6.服务删除**

在Swarm集群的管理节点上，我们可以使用命令`docker service rm <SERVICE-ID>`删除服务。

```
# 在manager节点上
$ docker service rm helloworld
helloworld
# 通过命令docker service inspect <SERVICE-ID>可以看到服务已经不存在
# 通过命令docker ps可以看到相应的容器也随之删除
```
