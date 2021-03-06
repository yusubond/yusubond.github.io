Title: Docker技术：认识Docker
Date: 2017-04-14
Category: TECH
Tags: Cloud, Docker
Slug: docker-ren-shi-docker
Author: subond
Summary:Docker是使用Go语言进行开发实现，基于Linux内核的cgroup, namespace, 以及AUFS类的Union FS等技术，对进程进行封装隔离，属于操作系统层面的虚拟化技术。由于隔离的进程独立于宿主和其他隔离的进程，因此成为容器。

Docker和传统虚拟化方式的不同如下图所示。传统虚拟化技术是虚拟出一套硬件，在其上运行一个完整操作系统，再在该系统之上再运行所需的应用进程；而容器内的应用进程直接运行于宿主的内核，容器内没有自己的内核，而且也没有进行硬件虚拟。

本文目录：

+ [1.什么是Docker](#1.什么是Docker)
+ [2.Docker基本概念](#2.Docker基本概念)
+ [3.Docker安装](#3.Docker安装)
+ [4.Docker网络](#4.Docker网络)

### 1.什么是Docker

Docker是使用Go语言进行开发实现，基于Linux内核的cgroup, namespace, 以及AUFS类的Union FS等技术，对 **进程** 进行封装隔离，属于 **操作系统层面的虚拟化技术**。*由于隔离的进程独立于宿主和其他隔离的进程，因此成为容器*。

Docker和传统虚拟化方式的不同如下图所示。传统虚拟化技术是虚拟出一套硬件，在其上运行一个完整操作系统，再在该系统之上再运行所需的应用进程；而容器内的 **应用进程直接运行于宿主的内核，容器内没有自己的内核，而且也没有进行硬件虚拟**。

![Docker与虚拟化技术](http://on64c9tla.bkt.clouddn.com/2017A/Docker-vm.png)

### 2.Docker基本概念

Docker包括三个基本概念：**镜像**、**容器**、**仓库**。

**1 镜像(Image)**

众所周知，操作系统分为内核和用户空间。对于Linux而言，内核启动后，会挂载`root`文件系统为其提供用户空间支持。而Docker镜像，就相当于一个`root`文件系统。

Docker镜像是一个特殊的文件系统，除了提供容器运行时所需的程序、库、资源、配置等文件，也包含一些为应用运行时准备的配置参数。**镜像不包含任何动态数据，其内容在构建之后也不会被改变**。

**分层存储**

镜像在构建时，一层层构建，前一层是后一层的基础。每一层构建完成后就不会再发生改变，后一层上的任何改变值发生在自己这一层。当我们使用命令`docker pull ubuntu:14.04`获取ubuntu14.04镜像时，可以看到每一层的镜像，及其相互依赖关系。

```
# 获取DockerHub中的ubuntu14.04镜像
$ docker pull ubuntu:16.04
16.04: Pulling from library/ubuntu
b6f892c0043b: Pull complete
55010f332b04: Pull complete
2955fb827c94: Pull complete
3deef3fcbd30: Pull complete
cf9722e506aa: Pull complete
Digest: sha256:382452f82a8bbd34443b2c727650af46aced0f94a44463c62a9848133ecb1aa8
Status: Downloaded newer image for ubuntu:16.04
# 可以看到，整个ubuntu16.04镜像由五层存储构成

# 仓库的元数据
# 在文件/var/lib/docker/image/graph_dirver/repositories.json中可以看到仓库的元数据
$ cat repositories.json | python -mjson.tool
{
    "Repositories": {
        "ubuntu": {
            "ubuntu:16.04": "sha256:ebcd9d4fca80e9e8afc525d8a38e7c56825dfb4a220ed77156f9fb13b14d4ab7",
            "ubuntu@sha256:382452f82a8bbd34443b2c727650af46aced0f94a44463c62a9848133ecb1aa8": "sha256:ebcd9d4fca80e9e8afc525d8a38e7c56825dfb4a220ed77156f9fb13b14d4ab7"
        }
    }
}

# 镜像的元数据
# 在文件/var/lib/docker/image/graph_dirver/imagedb/content/sha256/[image_id]中可以看到镜像的元数据
# 命令cat image_id | python -mjson.tool

# 镜像层的元数据
# 在文件/var/lib/docker/image/graph_dirver/layerdb/sha256/[chain_id]
# [chain_id]是某一层镜像层的存储索引
```

**2 容器(Container)**

**容器的实质是进程**。每一个容器运行时，是以镜像为基础层，在其上创建一个当前容器的存储层，称为“容器存储层”。容器存储层的生命周期与容器一样，容器消亡时，容器存储层也随之消亡。因此，任何保存在容器存储层的信息都会随容器删除而丢失。

容器是Docker的核心概念。简单来讲，容器是 **独立运行的一个或一组应用，以它们的运行态环境**。与之对应的，容易混淆的概念是虚拟机。虚拟机可以理解为 **模拟运行的一整套操作系统(包括运行态环境和其他系统环境)和运行在操作系统上的应用**。

容器的核心为所执行的应用程序，所需要的资源都是应用程序所必需的的。当Docker容器中指定的应用终结时，容器也自动终止。当利用`docker run`创建容器时，Docker在后台运行的标准操作包括：

* 检查本地是否存在指定的镜像，不存在就从公有仓库下载  
* 利用镜像创建并启动一个容器  
* 分配一个文件系统，并在只读的镜像层外面挂载一层可读写层  
* 从宿主主机配置的网桥接口中桥接一个虚拟接口到容器中  
* 从地址池配置一个ip地址给容器  
* 执行用户指定的应用程序  
* 执行完毕后容器被终止

**3 仓库(Repository)**

仓库(Repository)是集中存放镜像的地方，每个仓库下面有多个镜像。因此，仓库可以被认为是一个具体的项目或目录。仓库分为公有仓库和本地仓库(私有仓库)，公有仓库Docker Hub由Docker公司或用户维护，主要包括根镜像和用户镜像；而本地仓库可供私人使用。

### 3.Docker安装

对于Ubuntu系列，Docker CE支持以下三种64位发行版：

+ Yakkety 16.10
+ Xenial 16.04
+ Trusty 14.04

第一步：设置仓库。可以通过`lsb_release -cs`命令查看Ubuntu系统版本，然后添加相应的仓库。

```
$ sudo apt-get -y install apt-transport-https ca-certificates curl
$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
$ sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
$ sudo apt-get update
```

第二步：获取Docker CE

```
$ sudo apt-get install -y docker-ce
```

第三步：检查Docker版本，查看是否安装成功。

```
$ docker --version
# Docker version 17.04.0-ce, build 4845c56
```

第四步：建立Docker用户组

默认情况下，docker命令使用Unix Socket与Docker Daemon通信，而只有root用户和docker组用户才可以与Docker Daemon的Unix Socket建立通信。因此，出于安全考虑，我们可以将使用docker的用户加入Docker用户组。

```
# 建立docker用户组
$ sudo groupadd docker
# 将当前用户加入docker用户组
$ sudo usermod -aG docker $USER
```

### 4.Docker网络

Docker使用-p参数指定网络端口，将宿主主机的端口与容器中的端口形成映射关系。容器的连接(linking)系统是除了端口映射外，另一种与容器中应用的方式。**连接系统可以在源和接收容器之间创建一个隧道，接收容器可以看到源容器指定的信息，而且不用映射容器的端口到宿主主机上**。

Docker通过2种方式为容器公开连接信息：

* 环境变量  
* 更新/etc/hosts文件

**高级网络配置**

当Docker启动时，自动在宿主机上创建一个`docker0`虚拟网桥，实际上是Linux的一个网桥，对挂载到它的网口进行数据转发。同时，Docker随机分配一个本地未占用的私有网段中的一个地址给`docker0`接口。

当创建一个Docker容器的时候，同时会创建一对`veth pair`接口(虚拟网络设备对：即一对端口，当数据包发送到一个端口时，另一个端口也可以收到相同的数据包)。这对接口一端在容器内，即`eth0`；另一端在本地并被挂载到`docker0`网桥，名称以`veth`开头。通过这种方式，主机可以跟容器通信，容器之间也可以通信。

![Docker网络](http://on64c9tla.bkt.clouddn.com/Comput/docker_network.png)
