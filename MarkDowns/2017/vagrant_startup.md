Title: Vagrant的快速使用
Date: 2017-05-10
Category: Tech
Tags: vagrant, cloud
Slug: vagrant_startup
Author: subond
Summary: Vagrant是为了方便的实现虚拟化环境而设计的，使用Ruby语言开发，基于VirtualBox等虚拟机管理软件的接口，提供了一个可配置、轻量级的便携式虚拟开发环境。使用Vagrant可以很方便的就建立起来一个虚拟环境，而且可以模拟多台虚拟机，形成分布式系统。

Vagrant是为了方便的实现虚拟化环境而设计的，使用Ruby语言开发，基于VirtualBox等虚拟机管理软件的接口，提供了一个可配置、轻量级的便携式虚拟开发环境。使用Vagrant可以很方便的就建立起来一个虚拟环境，而且可以模拟多台虚拟机，形成分布式系统。

其次，Vagrant还可以实现文件共享，即用于主机和虚拟之间共享文件，方便开发人员在主机上写程序，再往虚拟里拷贝的麻烦。而且，Vagrant的package功能还可以将完整的开发环境进行打包，供其他人使用，极大地提高了工作效率。

## 1.Vagrant安装

Vagrant只是一个方便创建，管理虚拟的便携式工具，底层支持由VirtualBox、VMware等虚拟机系统支持。本文以VirtualBox为例，主机系统为Mac OSX。

### VirtualBox安装

这是Virtual官网链接[https://www.virtualbox.org/wiki/Downloads](https://www.virtualbox.org/wiki/Downloads)，可以依据自己的系统选择合适的安装包进行安装。

### Vagrant安装

Vagrant官网[https://www.vagrantup.com/downloads.html](https://www.vagrantup.com/downloads.html)，同样需要依据自己的系统选择合适的安装包进行安装。

## 2.Vagrant配置

Vagrant配置主要在`Vagrantfile`文件中，通过`vagrant init`命令可以获得。

```bash
$ mkdir MyHost
$ cd MyHost
$ vagrant init
```

在MyHost文件夹下就会出现`Vagrantfile`文件，该文件是配置虚机的主要的文件。例如，我们想要创建一个Ubuntu Xenial 64位的虚机，并设置虚机的hostname为ubuntu64，则`Vagrantfile`中进行如下修改：

```ruby
config.vm.box = "ubuntu/xenial64"
config.vm.hostname = "ubuntu64"
```

## 3.启动虚拟

在MyHost目录下，通过命令`vagrant up`即可启动在`Vagrantfile`文件中配置的虚拟。

```bash
$ vagrant up
# 进入虚拟
$ vagrant ssh
```

## 4.Vagrantfile详解

1) 语言版本

```ruby
Vagrant.configure("2") do |config|
```
其中"2"指定Vagrantfile所使用的语言版本，一般为`2`。

2) box相关

指定创建虚机vm所需的box

```ruby
config.vm.box = "ubuntu/xenial64"
```

设置vm的hostname

```ruby
config.vm.hostname = "ubuntu64"
```

设置vm的网络，如果是设置私有网络，需指定ip地址；如果设置公有网络，则不需要。

```ruby
# 设置私有网络
config.vm.network "private_network", ip: "192.168.33.10"
# 设置公有网络
config.vm.network "public_network"
# 设置端口映射，即vm80端口映射到主机8080端口
config.vm.network "forwarded_port", guest: 80, host: 8080
```
3) 文件同步

将主机的文件(或目录)挂载到vm中，实现文件同步。  
第一个参数是主机的文件路径，第二个参数是vm里面的路径。

```ruby
config.vm.synced_folder "../data", "/vagrant_data"
```

## 5.Vagrant常用命令

1) box管理

包括添加、删除、更新等等。

```sh
$ vagrant box
```

2) 虚机的管理

包括启动，摧毁、打包，重载等等。

```sh
# 关掉虚拟
$ vagrant halt

# 重载虚拟，即修改虚拟的配置后(Vagrantfile)需要重载才能生效
$ vagrant reload

# 摧毁整个虚拟及其相关文件
$ vagrant destory

# 将整个虚拟打包成一个box文件,
$ vagrant package
```

## 参考资料

[1]. Getting Started Vagrant[https://www.vagrantup.com/intro/index.html](https://www.vagrantup.com/intro/index.html)  
[2]. Vagrant安装配置[https://github.com/astaxie/go-best-practice/blob/master/ebook/zh/01.2.md](https://github.com/astaxie/go-best-practice/blob/master/ebook/zh/01.2.md)  
