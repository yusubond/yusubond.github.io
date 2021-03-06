Title: Docker进阶：服务配置
Date: 2017-05-01
Category: TECH
Tags: Cloud, Docker
Slug: docker-swarm-jin-jie2
Author: subond
Summary:当使用Docker Swarm模式时，我们可以通过命令`docker service create`向Swarm集群部署应用服务。Swarm集群中的管理节点将服务描述视为应用服务所需的状态。其次，所有服务相关的命令，即`docker service`，一定要在管理节点上运行(管理节点负责Swarm集群中的服务管理和任务编排)。

当使用Docker Swarm模式时，我们可以通过命令`docker service create`向Swarm集群部署应用服务。Swarm集群中的管理节点将服务描述视为应用服务所需的状态。其次，所有服务相关的命令，即`docker service`，一定要在管理节点上运行(管理节点负责Swarm集群中的服务管理和任务编排)。

本文目录：

+ [创建服务](#创建服务)
+ [配置服务](#配置服务)

### 创建服务

Swarm集群中最简单创建服务的方式就是指定所要创建的服务镜像就可以，即命令`docker service create <IMAGE>`。当执行创建服务命令后，Swarm编排器则向可用节点分派服务任务。一个任务其实就是一个基于指定镜像生成的容器。比如，创建一个nginx web服务。

```
# 在管理节点上
# --name参数用于指定服务的名称
$ docker service create --name myweb nginx
l3w3x4df6tnia8qql64mkdm1s
# 查看Swarm集群中的服务
$ docker service ls
ID            NAME   MODE        REPLICAS  IMAGE
l3w3x4df6tni  myweb  replicated  1/1       nginx:latest
```

当然，我们也可以在部署服务时指定容器中将要运行的指令，其命令为`docker service create <IMAGE> <COMMAND>`。

```
$ docker service create --name myalpine ping www.bing.com
```

### 服务配置

当创建一个服务时，我们通过修改配置选项对服务进行限制，命令`docker service create --help`可以查看创建服务的帮助信息。

**配置服务的运行环境**

我们可以通过以下参数配置服务的运行环境：

+ --env参数可以指定环境变量
+ --workdir参数可以指定容器中的工作目录
+ --user参数可以指定用户名或者UID

```
# 通过不同的参数配置服务
$ docker service create --name myservice \
  --env MYSERVICE=/usr/local/service
  --workdir /tmp
  --user subond
  alpine ping www.baidu.com
```

**配置服务规模和位置**

前面的介绍中，我们讲到Swarm模式中有两种服务类型：复制服务(replicated service)和全局服务(global service)。对于复制服务类型，我们可指定--replicas参数来创建一定数量的服务任务，从而将任务分派到可用节点上；而对于全局服务，调度器则在每一个可用节点上均部署一个任务，--mode参数可以指定全局服务。具体如下：

```
# 在具有一个管理节点(manager)和一个工作节点(worker1)的Swarm集群中，部署一个具有两个副本的nginx web服务
# 在节点manger
$ docker node ls
ID                           HOSTNAME  STATUS  AVAILABILITY  MANAGER STATUS
34y77dgnqon4soj2kqyb65a9y *  manager   Ready   Active        Leader
nxb55hhu8kwp272z21xi9dhyy    worker1   Ready   Active
$ docker service create --name myweb1 --replicas 3 nginx
xpmhprvzqtl1fi0mdveowjdoa
# 创建成功
# docker service ls
ID            NAME    MODE        REPLICAS  IMAGE
xpmhprvzqtl1  myweb1  replicated  2/2       nginx:latest
$ docker ps
CONTAINER ID        IMAGE                                                                           COMMAND                  CREATED             STATUS              PORTS               NAMES
27aa642e7786        nginx@sha256:12d30ce421ad530494d588f87b2328ddc3cae666e77ea1ae5ac3a6661e52cde6   "nginx -g 'daemon ..."   59 seconds ago      Up 58 seconds       80/tcp              myweb1.1.ei5mappmkkcdhbnk6gv3tcgrf

# 在节点worker1
$ docker ps
CONTAINER ID        IMAGE                                                                           COMMAND                  CREATED              STATUS              PORTS               NAMES
245a257c56d5        nginx@sha256:12d30ce421ad530494d588f87b2328ddc3cae666e77ea1ae5ac3a6661e52cde6   "nginx -g 'daemon ..."   About a minute ago   Up About a minute   80/tcp              myweb1.2.y2am04ermd2b8d3qevfeyzn67
# 我们的可以看到在两个节点上均有一个myweb1服务

# 接下来，我们再部署一个myweb2服务，与myweb1不同的是，myweb2是全局服务
# 在manager节点上
$ docker service create --name myweb2 --mode global nginx
yfbd525ztbqpa688ego4u0de8
$ docker service ls
ID            NAME    MODE        REPLICAS  IMAGE
xpmhprvzqtl1  myweb1  replicated  2/2       nginx:latest
yfbd525ztbqp  myweb2  global      2/2       nginx:latest
$ docker ps
CONTAINER ID        IMAGE                                                                           COMMAND                  CREATED              STATUS              PORTS               NAMES
5a99dca94917        nginx@sha256:12d30ce421ad530494d588f87b2328ddc3cae666e77ea1ae5ac3a6661e52cde6   "nginx -g 'daemon ..."   About a minute ago   Up About a minute   80/tcp              myweb2.34y77dgnqon4soj2kqyb65a9y.rush02tpvachu294flrklw32p
27aa642e7786        nginx@sha256:12d30ce421ad530494d588f87b2328ddc3cae666e77ea1ae5ac3a6661e52cde6   "nginx -g 'daemon ..."   8 minutes ago        Up 8 minutes        80/tcp              myweb1.1.ei5mappmkkcdhbnk6gv3tcgrf

# 在worker1节点上
$ docker ps
CONTAINER ID        IMAGE                                                                           COMMAND                  CREATED              STATUS              PORTS               NAMES
3a00f5c5ce9b        nginx@sha256:12d30ce421ad530494d588f87b2328ddc3cae666e77ea1ae5ac3a6661e52cde6   "nginx -g 'daemon ..."   About a minute ago   Up About a minute   80/tcp              myweb2.nxb55hhu8kwp272z21xi9dhyy.on9e6cr8obz3y51e84b3s72z4
245a257c56d5        nginx@sha256:12d30ce421ad530494d588f87b2328ddc3cae666e77ea1ae5ac3a6661e52cde6   "nginx -g 'daemon ..."   8 minutes ago        Up 8 minutes        80/tcp              myweb1.2.y2am04ermd2b8d3qevfeyzn67

# 接下来，我们将工作节点worker2加入Swarm集群
$ 在worker2节点上
$ docker swarm join \
  --token SWMTKN-1-1omg2k2e92snxv3wlja3komux5wan4hynn80ikkma2s9rd5cxz-9hq2vf8n0jysukytfqpavd8j7 \
  172.28.128.3:2377
This node joined a swarm as a worker.
# 在manager节点上
$ docker node ls
ID                           HOSTNAME  STATUS  AVAILABILITY  MANAGER STATUS
34y77dgnqon4soj2kqyb65a9y *  manager   Ready   Active        Leader
nxb55hhu8kwp272z21xi9dhyy    worker1   Ready   Active
v0rmad0igl7xwn8alop33j3fu    worker2   Ready   Active

# 在worker2节点上
$ docker ps
CONTAINER ID        IMAGE                                                                           COMMAND                  CREATED             STATUS              PORTS               NAMES
356da4542dd5        nginx@sha256:12d30ce421ad530494d588f87b2328ddc3cae666e77ea1ae5ac3a6661e52cde6   "nginx -g 'daemon ..."   40 seconds ago      Up 39 seconds       80/tcp              myweb2.v0rmad0igl7xwn8alop33j3fu.5wa1pg01i73u3a1feb73ht5p5
# 可以看到worker2上具有myweb2的服务，而不具备myweb1服务
# 这是复制服务和全局的模式的重要区别
```

**配置发布端口**

当创建Swarm服务时，有两个方式将服务的端口发布到Swarm群外的主机端口上：

+ 依靠路由网络。当我们发布一个服务端口时，无论节点上是否运行着服务的任务，Swarm都会在每个节点的目标端口上访问该服务。
+ 直接在运行该服务任务的节点上发布服务端口。Docker1.13及其更高版本支持该功能。

第一种：依靠路由网络发布端口

我们可以通过参数--publish <target-port>:<service-port>发布服务的端口。Swarm使得服务在每个节点的目标端口均可达。如果外部主机连接到Swarm集群中的任何一个节点，都可以通过路由网络将其路由到服务任务所在的节点上。外部主机不要知道服务任务所在的ip和内部使用的服务端口就可以与服务进行交互。

例如，我们在一个具有3个节点的Swarm集群中运行一个具有2个副本的nginx web服务，并将发布端口设为8080。那么，在任何一个节点上可以使用8080端口上的nging服务。

```
# 在manger节点上部署nginx web服务，并发布8080端口
$ docker service create --name myweb --replicas 2 --publish 8080:80 nginx
# 通过检查，我们发现在manager节点和worker2节点均有myweb任务
# 在worker1节点请求nginx服务
$ curl localhost:8080
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
    body {
        width: 35em;
        margin: 0 auto;
        font-family: Tahoma, Verdana, Arial, sans-serif;
    }
</style>
</head>
<body>
...
</body>
</html>
```

外部主机上，使用任何一个节点的ip均可以访问到nginx服务，如下图：

![nginx服务](http://on64c9tla.bkt.clouddn.com/Comput/docker_nginx.png)

第二种：在Swarm节点上发布端口

通过指定mode=host来进行参数--publish的设定，我们可以将发布端口指定到每个运行服务任务的Swarm节点上。

主要注意的是：如果使用mode=host直接在Swarm节点上发布服务的端口，并且还设置published=<PORT>，则会创建一个隐式限制，只能在给定的群组节点上为该服务运行一个任务。 另外，如果使用mode=host，并且在docker服务创建时不使用--mode=global标志，那么将难以知道哪些节点正在运行服务，以便将工作路由到它们。

接下来，我们创建一个全局服务类型的nginx web服务，并将发布端口指定为8090。

```
# 在manager节点上
$ docker service create --name mynginx --mode global --publish mode=host,target=80,published=8090 nginx
# 这样我们可以在Swarm任何一个节点上访问到8090端口上的nginx服务，即使新加入的节点。
```
