Title: Docker技术：Docker系统架构
Date: 2017-04-16
Category: TECH
Tags: Cloud, Docker
Slug: docker-xi-tong-jia-gou
Author: subond

本文目录：

+ [Docker Engine](#Docker Engine)
+ [Docker交付内容](#Docker交付内容)
+ [Docker系统架构](#Docker系统架构)

### Docker Engine

Docker Engine主要包含三个组件，如下图所示：

+ Docker Server：一个长时间运行的守护进程。
+ REST API：指定程序可以用来与守护进程通信的接口。
+ Client：命令行CLI客户端。

![Docker全局预览](http://on64c9tla.bkt.clouddn.com/2017A/Docker-overview.png)

CLI利用脚本或直接输入命令的方式，通过REST API与Docker Daemon(守护进程)进行通信，并完成相关操作。Docker Damemon是负责容器对象的主体，例如镜像，容器实例，网络管理以及数据卷等。

### Docker交付内容

* 快速，一致地交付应用程序

Docker允许开发人员通过提供本地容器标准化环境，从而简化应用程序和服务的开发生命周期。容器可以适用于连续集成和持续开发的工作流程。Docker的便携性和轻量级性质使得轻松实现动态管理工作负载，按照业务需求来实现扩展或拆除应用程序和服务

* 在同一硬件上可允许多个工作流程

Docker重量轻，速度快。它为基于虚拟机管理程序的虚拟机提供了可行的，具有成本效益的替代方案，因此可以使用更多的计算能力来实现业务目标。Docker是高密度环境和中小型部署的理想选择，您需要用更少的资源来做更多的事情。

### Docker系统架构

Docker采用Client/Server架构模式，其系统架构如下图所示。

![Docker系统架构](http://on64c9tla.bkt.clouddn.com/2017A/docker.png)

Docker客户端与守护进程既可以运行在同一台主机，也运行在不同的主机上，两者利用Unix Socket或网络接口，通过REST API进行通信。

Docker Daemon监听Docker API来相应客户端的请求，完成Docker对象的管理。

Docker客户端是用户与Docker Daemon进行交互的主要方式。

Docker Registries用来管理Docker镜像。
