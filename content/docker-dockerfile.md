Title: Docker技术：Dockerfile的定义与使用
Date: 2017-04-18
Category: TECH
Tags: Cloud, Docker
Slug: dockerfile-ding-yi-he-shi-yong
Author: subond
Summary:Dockerfile是Docker用来构建镜像的文本文件，包括自定义指令和格式。命令`docker build`可以与Dockerfile文件中构建我们自己需要的镜像。

本文目录：

+ [Dockerfile的使用](#Dockerfile的使用)
+ [Dockerfile指令](#Dockerfile指令)

Dockerfile是Docker用来构建镜像的文本文件，包括自定义指令和格式。命令`docker build`可以与Dockerfile文件中构建我们自己需要的镜像。

### Dockerfile的使用

Dockerfile文件描述了构建镜像的步骤，其中每条指定都是单独执行的。除了FROM指令，**其他每条指令都会在上一条指令所生成镜像的基础上执行，执行完成后生成一个新的镜像层。新的镜像层覆盖在原来的镜像之上，进而形成新的镜像**。Dockerfile文件所生成的最终镜像是在基础镜像上叠加一层层的镜像形成的。

值得注意的是，Docker引擎在构建镜像的过程中会缓存中间镜像。当从一个已经存在的基础镜像开始构建新镜像时，则将Dockerfile中的下一个指令和基础镜像的所有子镜像进行比较，如果有一个子镜像是由相同的指令生成的，则命中缓存，直接使用该镜像。

### Dockerfile指令

Dockerfile的基本格式如下：

```
# 注释信息
INSTRUCTION arguments
```

Dockerfile指令不区分大小写，但是建议使用大写，方便区分；#开头的表示注释行。根据指令的作用可以分分为两种：构建指令和设置指令。构建指令用于构建镜像，其指定的操作不会运行在镜像的容器上；而设置指令用于设置镜像的属性，其指定的操作运行在镜像的容器上。

+ #### FROM

格式：FROM <image>或FROM <image>:<tag>  
分类：构建指令

FROM指令指定基础镜像，一个有效的Dockerfile文件必须以FROM作为第一条非注释指令。后续的指令都依赖于该指令指定的image。FROM指令指定的基础image可以是官方远程仓库中的，也可以位于本地仓库。

+ #### MAINTAINER

格式：MAINTAINER <name>  
分类：构建指令

用于将image的制作者相关的信息写入到image中。当我们对该image执行docker inspect命令时，输出中有相应的字段记录该信息。

+ #### RUN

格式：RUN <shell_cmd>  # shell格式  
  或 RUN ["exec", "param1", "param2"]  # exec格式  
分类：构建指令

RUN可以运行任何被基础image支持的命令。如基础image选择了ubuntu，那么软件管理部分只能使用ubuntu的命令。

+ #### ENV

格式：ENV <key> <value>  
分类：构建指令

ENV指令用于在image中设置一个环境变量。设置完环境变量后，后续的RUN命令都可以使用，container启动后，可以通过docker inspect查看这个环境变量，也可以通过在docker run --env key=value时设置或修改环境变量。

+ #### WORKDIR

格式：WORKDIR <path>  
分类：设置指令

WORKDIR用于指定工作目录，相当于切换指令，对RUN,CMD,ENTRYPOINT生效，可设置多次。

+ #### ADD

格式：ADD <src> <dest>  
分类：构建指令

<src> 是相对被构建的源目录的相对路径，可以是文件或目录的路径，也可以是一个远程的文件url  
<dest> 是container中的绝对路径

所有复制到容器中的文件和文件夹权限为0755，uid和gid为0；如果是一个目录，那么会将该目录下的所有文件添加到容器中，不包括目录；如果文件是可识别的压缩格式，则Docker引擎会进行解压缩；如果<src>是文件且<dest>中不使用斜杠结束，则会将<dest>视为文件，<src>的内容会写入<dest>；如果<src>是文件且<dest>中使用斜杠结束，则会<src>文件拷贝到<dest>目录下。

+ #### COPY

格式：COPY <src> <dest>  
分类：构建指令

COPY指令复制<src>所指向的文件或目录，将其添加至新镜像中，复制的文件或目录在镜像中的路径是<dest>。<src>所指定的源可以是多个，但必须使上下文根目录的相对路径；也可以使用通配符指向所有匹配通配符的文件或目录。

<dest>可以是文件或目录，但必须使镜像中的绝对路径或相对于WORKDIR的相对路径。

若<dest>以反斜杠/结尾则其指向是目录，否则指向文件。<src>同理。

若<dest>是文件，则<src>的内容被写入<dest>中；否则<src>所指向的文件或目录中的内容被复制到<dest>目录中。

当<src>指定多个源时，<dest>必须使目录。若<dest>不存在，则会被创建。

+ #### CMD

格式：RUN <shell_cmd>  # shell格式  
或者：RUN ["exec", "param1", "param2"]  # exec格式  
或者：RUN ["param1", "param2"]  # 为ENTRYPOINT指令提供参数  
分类：设置指令

CMD指令为容器运行时指定的操作默认操作。该操作可以是执行自定义脚本，也可以是执行系统命令。该指令只能在文件中存在一次，如果有多个，则只执行最后一条。

第三种情况时，ENTRYPOINT指定的是一个可执行的脚本或者程序的路径，该指定的脚本或者程序将会以param1和param2作为参数执行。所以如果CMD指令使用上面的形式，那么Dockerfile中必须要有配套的ENTRYPOINT。

+ #### ENTRYPOINT（设置container启动时执行的操作

格式：ENTRYPOINT <commond>  # shell格式  
或者：ENTRYPOINT ["exec", "param1", "param2"]  # exec格式  
分类：设置指令

ENTRYPOINT指定容器启动时执行的命令，可以多次设置，但是只有最后一个有效。该指令的使用分为两种情况，一种是独自使用，另一种和CMD指令配合使用。当独自使用时，如果你还使用了CMD命令且CMD是一个完整的可执行的命令，那么CMD指令和ENTRYPOINT会互相覆盖只有最后一个CMD或者ENTRYPOINT有效。

```
# CMD指令将不会被执行，只有ENTRYPOINT指令被执行  
CMD echo “Hello, World!”  
ENTRYPOINT ls -l  
```

CMD指令配合使用来指定ENTRYPOINT的默认参数，这时CMD指令不是一个完整的可执行命令，仅仅是参数部分；ENTRYPOINT指令只能使用JSON方式指定执行命令，而不能指定参数。

```
FROM ubuntu  
CMD ["-l"]  
ENTRYPOINT ["/usr/bin/ls"]  
```

+ #### USER

格式：USER <name>  
分类：设置指令

USER用于设置启动容器的用户，默认是root用户。

+ ####  EXPOSE 指定容器需要映射到宿主机器的端口）

格式：EXPOSE <port>  [<port>...]  
分类：设置指令

EXPOSE用于指定容器需要映射到宿主机器的端口。当你需要访问容器的时候，可以不是用容器的IP地址而是使用宿主机器的IP地址和映射后的端口。要完成整个操作需要两个步骤，首先在Dockerfile使用EXPOSE设置需要映射的容器端口，然后在运行容器的时候指定-p选项加上EXPOSE设置的端口，这样EXPOSE设置的端口号会被随机映射成宿主机器中的一个端口号。也可以指定需要映射到宿主机器的那个端口，这时要确保宿主机器上的端口号没有被使用。EXPOSE指令可以一次设置多个端口号，相应的运行容器的时候，可以配套的多次使用-p选项。

端口映射是docker比较重要的一个功能，原因在于每次运行容器的时候容器的IP地址不能指定而是在桥接网卡的地址范围内随机生成的。宿主机器的IP地址是固定的，我们可以将容器的端口的映射到宿主机器上的一个端口，免去每次访问容器中的某个服务时都要查看容器的IP的地址。对于一个运行的容器，可以使用docker port加上容器中需要映射的端口和容器的ID来查看该端口号在宿主机器上的映射端口。

```
# 映射一个端口  
EXPOSE port1  
# 相应的运行容器使用的命令  
docker run -p port1 image  

# 映射多个端口  
EXPOSE port1 port2 port3  
# 相应的运行容器使用的命令  
docker run -p port1 -p port2 -p port3 image  
# 还可以指定需要映射到宿主机器上的某个端口号  
docker run -p host_port1:port1 -p host_port2:port2 -p host_port3:port3 image
```

+ #### VOLUME（指定挂载点）

格式：VOLUME ["<mountpoint"]  
分类：设置指令

VOLUME指令用于指定容器中的一个目录具有持久化存储数据的功能，该目录可以被容器本身使用，也可以共享给其他容器使用。当容器中的应用有持久化数据的需求时可以在Dockerfile中使用该指令。

```
VOLUME ["<mountpoint>"]
FROM base  
VOLUME ["/tmp/data"]
# 运行通过该Dockerfile生成image的容器，/tmp/data目录中的数据在容器关闭后，里面的数据还存在。
# 例如另一个容器也有持久化数据的需求，且想使用上面容器共享的/tmp/data目录，那么可以运行下面的命令启动一个容器：
$ docker run -t -i -rm -volumes-from container1 image2 bash
# container1为第一个容器的ID，image2为第二个容器运行image的名字。
```
