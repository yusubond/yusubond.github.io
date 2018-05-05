Title: Vagrant使用案例
Date: 2017-05-15
Category: Tech
Tags: vagrant, cloud
Slug: vagrant_usage
Author: subond

### 单机配置

1. 配置一个centos7系统，要求使用私有网络地址`192.168.10.10`，hostname为dbserver。

```Ruby
Vagrant.configure("2") do |dbserver|
  dbserver.vm.box = "centos/7"
  dbserver.vm.network "private_network", ip: "192.168.10.10"
  dbserver.vm.hostname = "dbserver"
end
```
需要说明的是：使用私有地址，vm的私有ip只能在各vm间互访，而不能访问Internet，即HOST_ONLY模式；使用公有地址，vm的公有地址将于主机某个网卡(启动vm时需指定)的地址同一网段，vm能够使用该地址访问Internet。

2. 配置一个ubuntu xenial64系统，并将工程目录下的`data`目录同步到vm中，目录为`/vagrant/project_data`；同时将vm的80端口映射到主机的8080端口。

```Ruby
Vagrant.configure("2") do |ubuntu16|
  ubuntu16.vm.box = "ubuntu/xenial64"
  ubuntu16.vm.network "forwarded_port", guest: 80, host: 8080
  ubuntu16.vm.synced_folder "/Users/subond/UCloud/VHost/data", "/project_data"
end
```

需要说明的是：指定同步文件时，第一个参数既可以当前工程目录的相对目录，也可以是主机上的绝对路径；第二个参数是vm中的绝对路径。默认情况下，当前工程目录下的文件将同步至vm中的`/vagrant`目录下。

3. 配置一个centos7系统，要求设置vm的名字为`foobar`,内存大小为512M。

```Ruby
Vagrant.configure("2") do |centos|
  centos.vm.box = "centos/7"
  centos.vm.provider "virtualbox" do |vm|
    vm.customize ["modifyvm", :id, "--name", "foobar", "--memory", "512"]
  end
end
```

### 分布式系统配置

1. 创建两个主机，一个做服务端，hostname为`server`,一个做客户端，hostname为`client`，两个虚拟均设置私有网络，并配置dhcp服务。

```Ruby
Vagrant.configure("2") do |subond|
    subond.vm.box = "centos/7"
    subond.vm.define "server" do |server|
        server.vm.network "private_network", type: "dhcp"
        server.vm.hostname = "server"
    end

    subond.vm.define "client" do |client|
        client.vm.network "private_network", type: "dhcp"
        client.vm.hostname = "client"
    end
end
```

2. 创建一个具有三个节点的集群，hostname分别为`node1`,`node2`,`node3`,并设置私有网络；节点大小Mem = 2048,CPU = 1；同时将其配置成docker开发环境。

```Ruby
Vagrant.configure("2") do |cluster|
  (1..3). each do |i|
    cluster.vm.define "node#{i}" do |node|
      node.vm.box = "centos/7"
      node.vm.hostname = "node#{i}"
      node.vm.network "private_network", ip: "192.168.10.#{i+10}"
      node.vm.provider "virtualbox" do |v|
         v.name = "node#{i}"
         v.memory = 2048
         v.cpus = 1
      end
      node.vm.provision "shell", inline: <<-SHELL
        yum install wget -y
        wget -P /home/vagrant https://download.docker.com/linux/centos/7/x86_64/stabl    e/Packages/docker-ce-18.03.1.ce-1.el7.centos.x86_64.rpm
        yum install /home/vagrant/docker-ce-18.03.1.ce-1.el7.centos.x86_64.rpm -y
       SHELL
    end
  end
end
```

需要的说明的是：如果需要shell功能，最好的方式就是单独写shell脚本，通过文件同步的方式注入虚机；安装包文件也最好使用这种方式，速度会快一些。

## 参考资料

[1]. [使用Vagrant创建多节点虚拟机集群](https://segmentfault.com/a/1190000005875116)  
[2]. [docker安装](https://docs.docker.com/install/linux/docker-ce/centos/#upgrade-docker-ce)  
[3]. [vagrant provider配置](https://www.vagrantup.com/docs/providers/configuration.html)  
[4]. [vagrant provision配置](https://www.vagrantup.com/docs/provisioning/)  
