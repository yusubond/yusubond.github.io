Title: Docker技术：快速上手教程
Date: 2017-04-20
Category: TECH
Tags: Cloud, Docker
Slug: docker-quickstart
Author: subond

本文目录：

+ [1.构建容器-Containers](#1.构建容器-Containers)
+ [2.组合服务-Compose](#2.组合服务-Compose)
+ [3.集群管理-Swarm](#3.集群管理-Swarm)
+ [4.应用协作-Stacks](#4.应用协作-Stacks)

### 1.构建容器-Containers

Dockerfile将定义容器中环境的内容。通过将访问资源（例如，网络接口和磁盘驱动器）进行虚拟化处理，实现与宿主机系统的隔离。为此，我们需要将端口映射到外部宿主系统环境中，并说明将要把那些文件“复制”到隔离的环境中，即容器。这样之后，我们就可以期望在Dockerfile中定义的应用程序可以在任何地方运行。

**Dockerfile**

创建一个新的空目录，在目录下创建名为`Dockerfile`的文件，并写入以下内容。

```
# Use an official Python runtime as a base image
FROM python:2.7-slim

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV NAME World

# Run app.py when the container launches
CMD ["python", "app.py"]
```

Dockerfile中用到两个我们还未创建的文件，即`requirements.txt`和`app.py`。接下来，创建这两个文件，内容分别如下：

`requirements.txt`

```
Flask
Redis
```

`app.py`

```
from flask import Flask
from redis import Redis, RedisError
import os
import socket

# Connect to Redis
redis = Redis(host="redis", db=0, socket_connect_timeout=2, socket_timeout=2)

app = Flask(__name__)

@app.route("/")
def hello():
    try:
        visits = redis.incr("counter")
    except RedisError:
        visits = "<i>cannot connect to Redis, counter disabled</i>"

    html = "<h3>Hello {name}!</h3>" \
           "<b>Hostname:</b> {hostname}<br/>" \
           "<b>Visits:</b> {visits}"
    return html.format(name=os.getenv("NAME", "world"), hostname=socket.gethostname(), visits=visits)

if __name__ == "__main__":
	app.run(host='0.0.0.0', port=80)
```

**构建并运行应用**

创建好Dockerfile和其所需的文件后，我们就可以利用docker命令构建Dockerfile中定义的应用。

```
# 构建应用，即为构建Dockerfile定义的应用镜像
$ docker build -t subond-hello .
# -t指定镜像名称
# .代表以当前目录为上下文内容

# 镜像创建成功后，可以通过docker images命令查看镜像信息
$ docker images
subond-hello        latest              e440849c12a4        3 hours ago         195 MB
python              2.7-slim            1c7128a655f6        5 days ago          183 MB
```

在Dockerfile中我们定义了容器需要暴露的端口，因此，在容器运行时需要将暴露出来的端口映射到宿主机的某个端口，这样在宿主机上就可以访问容器中的资源。-p可以指定宿主机与容器间的端口映射关系。

```
# 运行刚刚构建好的应用镜像
$ docker run -p 8080:80 subond-hello
* Running on http://0.0.0.0:80/ (Press CTRL+C to quit)

# 验证应用是否成功运行
# 在宿主机上
$ curl http://localhost:8080
<h3>Hello World!</h3><b>Hostname:</b> 3d8822177c83<br/><b>Visits:</b> <i>cannot connect to Redis, counter disabled</i>

$ docker ps
CONTAINER ID        IMAGE               COMMAND             CREATED             STATUS              PORTS                  NAMES
3d8822177c83        subond-hello        "python app.py"     57 seconds ago      Up 56 seconds       0.0.0.0:8080->80/tcp   heuristic_davinci
```

**共享镜像**

当自己创建的镜像能够正常运行时，我们可以选择将镜像上传到DockerHub上与别人分享。

```
# 登录DockerHub账号
$ docker login
# 给自己的镜像打上tag标签，如果不添加tag信息，则默认为最新，即latest
# username/repository:tag为DockerHub上的仓库
$ docker tag subond-hello username/repository:tag

# 上传镜像
$ docker push username/repository:tag
```

一旦上传成功，镜像就实现了共享。此后，运行该镜像的时候，就可以指定DockerHub仓库中的镜像了。

```
# 以DockerHub上的镜像启动容器
$ docker run -p 8080:80 username/repository:tag
```

#### 常用命令

```
docker build -t friendlyname .        # 使用当前目录下的Dockerfile创建应用镜像
docker run -p 4000:80 appname         # 运行”appname"的镜像，并进行端口映射
docker run -d -p 4000:80 friendlyname # 独立运行"appname"镜像，并进行端口映射
docker ps                             # 显示运行中的容器
docker stop <hash>                    # 停止运行中的容器
docker ps -a                          # 显示所有容器(运行的和未运行的)
docker kill <hash>                    # 杀死某个容器
docker rm <hash>                      # 移除容器
docker rm $(docker ps -a -q)          # 移除宿主机上的全部容器
docker images -a                      # 显示应用镜像
docker rmi <imagename>                # 移除应用镜像
docker rmi $(docker images -q)        # 移除所有应用镜像
docker images -f "dangling=true"      # 显示所有<none>:<none>的镜像
docker login                          # 登录DockerHub仓库
docker tag <image> username/repository:tag      # 为上传镜像打标签
docker push username/repository:tag             # 上传镜像至仓库
docker run username/repository:tag              # 运行仓库中的镜像
```

### 2.组合服务-Compose

在分布式应用程序中，应用的不同部分称为“服务”。例如，一个视频共享网站，它可能需要数据库服务，用于存储应用程序数据；还需要后台视频转码服务，用于用户上传视频；还需要前端服务等。

一个服务只是意味着“生产中的容器”。一个服务只运行一个镜像，但是它编码了镜像运行的方式——使用哪些端口，需要运行多少副本以及服务所需的容量等。因此，扩展服务实际上更改容器实例的数量，并提供扩展服务过程中所需的计算资源。

Docker平台可以让服务运行及扩展变得更为简单，只需一个`docker-compose.yaml`文件。`docker-compose.yaml`文件是一个YAML文件，定义了实际生产环境中Docker容器的行为。

`docker-compose.yaml`

```
version: "3"
services:
  web:
    image: subond/suker:v1.0
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "0.1"
          memory: 50M
      restart_policy:
        condition: on-failure
    ports:
      - "80:80"
    networks:
      - webnet
networks:
  webnet:
```

接下来，我们就可以利用`docker-compose.yml`文件运行带有 **负载均衡** 的应用服务。在使用`docker stack deploy`之前，需要将Docker切换至Swarm模式。

```
# 将Docker引擎切换至Swarm模式
$ docker swarm init
# 启动应用服务，并命名为suweb
$ docker stack deploy -c docker-compose.yml suweb
Creating network suweb_webnet
Creating service suweb_web

# 查看suweb的状态
$ docker stack ps suweb
ID            NAME         IMAGE              NODE       DESIRED STATE  CURRENT STATE           ERROR  PORTS
gcc9oupfdi8g  suweb_web.1  subond/suker:v1.0  Ubuntu-16  Running        Running 10 seconds ago
s7vrc9fwwnt7  suweb_web.2  subond/suker:v1.0  Ubuntu-16  Running        Running 9 seconds ago
ns8trslxt2n6  suweb_web.3  subond/suker:v1.0  Ubuntu-16  Running        Running 10 seconds ago

# 查看容器信息
$ docker ps
CONTAINER ID        IMAGE                                                                                  COMMAND             CREATED             STATUS              PORTS               NAMES
89f858d3e9ff        subond/suker@sha256:c2c33f0db407c195ae44dcafc5a81172afb1e88157efd489580148d73d8a532a   "python app.py"     2 minutes ago       Up 2 minutes        80/tcp              suweb_web.2.s7vrc9fwwnt7szj62cwf235zc
0999d38459a6        subond/suker@sha256:c2c33f0db407c195ae44dcafc5a81172afb1e88157efd489580148d73d8a532a   "python app.py"     2 minutes ago       Up 2 minutes        80/tcp              suweb_web.3.ns8trslxt2n6vsw5pcxo6iiw6
1bc62f75cdca        subond/suker@sha256:c2c33f0db407c195ae44dcafc5a81172afb1e88157efd489580148d73d8a532a   "python app.py"     2 minutes ago       Up 2 minutes        80/tcp              suweb_web.1.gcc9oupfdi8gflriegrsth272

# 命令docker stack rm suweb，可以移除服务
```

#### 常用命令

```
docker stack ls                                 # 列出所有运行着的应用程序
docker stack deploy -c <composefile> <appname>  # 以Compose文件运行容器服务
docker stack services <appname>                 # 列出与应用程序关联的服务
docker stack ps <appname>                       # 列出与应用程序关联的运行着的容器
docker stack rm <appname>                       # 删除应用程序
```

**小结**

通过`docker-compose.yml`文件，我们可以很方便的扩展应用服务的规模，只需要修理该文件里面的相关配置，然后重新运行命令`docker stack deploy -c docker-compose.yml suweb`即可。例如，修改replicas的值来增加或减少容器副本的数量。

命令`docker run`可以简单地实现应用服务的部署和管理；而对于实际生产环境需要大量部署应用服务时，Compose文件(即`docker-compose.yml`)可以方便地定义容器的行为，使得对服务的扩展，限制以及重新部署非常容易。命令`docker stack deploy`就是提供这样的一种方式。

### 3.集群管理-Swarm

**准备工作**

+ 两个虚拟机，并且均安装Docker引擎1.13或者更高版本
+ 完成[1.构建容器](#1.构建容器)和[2.组合服务](#2.组合服务)
+ 构建Swarm集群环境

关于Swarm集群环境说明：

两个虚拟机的主机名与ip的配置如下：

+ manager(ip:172.28.128.4)扮演Swarm集群中管理节点的角色
+ worker1(ip:172.28.128.5)扮演Swarm集群中工作节点的角色

**Swarm集群中部署应用**

```
# 第一步，将docker-compose.yml文件拷贝至manager的home目录下
# 第二步，在manager上通过composer文件部署应用服务
# 这个示例中，我使用的是vagrant虚拟机，如果你使用的是Docker-manchine方式
# 将下面指令中vagrant ssh 替换为docker-manchine，并且删除-c参数

$ vagrant ssh manager -c "docker stack deploy -c docker-compose.yml suweb"
Creating network suweb_webnet
Creating service suweb_web

# 查看容器分布及运行情况
$ vagrant ssh manager -c "docker stack ps suweb"
ID            NAME         IMAGE              NODE     DESIRED STATE  CURRENT STATE            ERROR  PORTS
d6g4m7qldta8  suweb_web.1  subond/suker:v1.0  worker1  Running        Preparing 3 seconds ago
nrginvlp568y  suweb_web.2  subond/suker:v1.0  manager  Running        Preparing 3 seconds ago
o61f0oc280et  suweb_web.3  subond/suker:v1.0  manager  Running        Preparing 3 seconds ago

# 可以看出：在worker1节点上运行着一个suweb容器服务
$ vagrant ssh worker1 -c "docker ps"
CONTAINER ID        IMAGE                                                                                  COMMAND             CREATED             STATUS              PORTS               NAMES
33a0a2a34b8b        subond/suker@sha256:c2c33f0db407c195ae44dcafc5a81172afb1e88157efd489580148d73d8a532a   "python app.py"     12 seconds ago      Up 11 seconds       80/tcp              suweb_web.1.d6g4m7qldta8mm16x80qimx8i
```

**小结**


### 4.应用协作-Stacks

[3.Swarm集群-Swarm](#3.Swarm集群-Swarm)中，我们学习了如何启用Swarm模式，并向Swarm集群中部署应用服务。接下来，我们将完成如何让多个应用服务进行协作，完成更加复杂的功能。这一部分，我们将接触分布式应用程序的结构层次的顶部，即Stacks。一个Stack是一组相互关联的服务，它们共享依赖关系，并可以一起进行编排和缩放。单个堆栈能够定义和协调整个应用程序的功能(更为复杂的功能可以需要使用多个堆栈)。

第一步：在`docker-compose.yml`文件中，增加新的服务，并重新部署

`docker-compose.yml`文件内容如下：

```
version: "3"
services:
  web:
    image: subond/suker:v1.0
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "0.1"
          memory: 50M
      restart_policy:
        condition: on-failure
    ports:
      - "80:80"
    networks:
      - webnet
  visualizer:
    image: dockersamples/visualizer:stable
    ports:
      - "8080:8080"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
    deploy:
      placement:
        constraints: [node.role == manager]
    networks:
      - webnet
networks:
  webnet:

```

接下来，将`docker-compose.yml`文件拷贝至manager节点的home目录下，并重新部署应用。

```
# 重新部署suweb应用程序
$ vagrant ssh manager -c "docker stack deploy -c docker-compose.yml suweb"
Creating network suweb_webnet
Creating service suweb_visualizer
Creating service suweb_web

# 查看stack中的服务
$ vagrant ssh manager -c "docker stack ls"
NAME   SERVICES
suweb  2

# 查看suweb应用的容器分布及运行情况
$ vagrant ssh manager -c "docker stack ps suweb"
ID            NAME                IMAGE                            NODE     DESIRED STATE  CURRENT STATE               ERROR  PORTS
eu18grghbpbq  suweb_web.1         subond/suker:v1.0                worker1  Running        Running about a minute ago
qw03jh0fibxi  suweb_visualizer.1  dockersamples/visualizer:stable  manager  Running        Running 32 seconds ago
7q2481c0p04b  suweb_web.2         subond/suker:v1.0                manager  Running        Running about a minute ago
6ugzg4hpvqio  suweb_web.3         subond/suker:v1.0                worker1  Running        Running about a minute ago

# manager节点上运行两个容器，suweb_visualizer.1和suweb_web.2
$ vagrant ssh manager -c "docker ps"
CONTAINER ID        IMAGE                                                                                              COMMAND             CREATED              STATUS              PORTS               NAMES
b26cef6f4852        dockersamples/visualizer@sha256:f924ad66c8e94b10baeaf7bdb9cd491ef4e982a1d048a56a17e02bf5945401e5   "npm start"         About a minute ago   Up About a minute   8080/tcp            suweb_visualizer.1.qw03jh0fibxizukjrep7ipkaj
6742285357df        subond/suker@sha256:c2c33f0db407c195ae44dcafc5a81172afb1e88157efd489580148d73d8a532a               "python app.py"     2 minutes ago        Up 2 minutes        80/tcp              suweb_web.2.7q2481c0p04b908m5knwexgsa

# worker1节点上运行两个容器，suweb_web.1和suweb_web.3
$ vagrant ssh worker1 -c "docker ps"
CONTAINER ID        IMAGE                                                                                  COMMAND             CREATED             STATUS              PORTS               NAMES
e9207afbd53f        subond/suker@sha256:c2c33f0db407c195ae44dcafc5a81172afb1e88157efd489580148d73d8a532a   "python app.py"     4 minutes ago       Up 4 minutes        80/tcp              suweb_web.1.eu18grghbpbqyzu3nbflx1d4z
4f841d8748fd        subond/suker@sha256:c2c33f0db407c195ae44dcafc5a81172afb1e88157efd489580148d73d8a532a   "python app.py"     4 minutes ago       Up 4 minutes        80/tcp              suweb_web.3.6ugzg4hpvqiouhoy8u6109y3h
```

第二步，持久化数据。利用Redis服务可进行数据的持久化数据，修改`docker-compose.yml`文件，文件内容如下：

```
version: "3"
services:
  web:
    image: subond/suker:v1.0
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "0.1"
          memory: 50M
      restart_policy:
        condition: on-failure
    ports:
      - "80:80"
    networks:
      - webnet
  visualizer:
    image: dockersamples/visualizer:stable
    ports:
      - "8080:8080"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
    deploy:
      placement:
        constraints: [node.role == manager]
    networks:
      - webnet
  redis:
    image: redis
    ports:
      - "6379:6379"
    volumes:
      - ./data:/data
    deploy:
      placement:
        constraints: [node.role == manager]
    networks:
      - webnet
networks:
  webnet:
```

接下来，在manager节点上创建数据卷，用于持久化数据；并更新`docker-compose.yml`文件。

```
# 创建数据卷目录
$ vagrant ssh manager -c "mkdir ./data"

# 更新`docker-compose.yml`文件，具体指令省略

# 更新之前的suweb服务或者删除suweb服务后重新部署，指令均如下
$ vagrant ssh manager -c "docker stack deploy -c docker-compose.yml suweb"
Creating network suweb_webnet
Creating service suweb_web
Creating service suweb_visualizer
Creating service suweb_redis

# 查看suweb应用的运行及分布情况
$ vagrant ssh manager -c "docker stack ps suweb"
ID            NAME                IMAGE                            NODE     DESIRED STATE  CURRENT STATE           ERROR  PORTS
r9j3wjnpkl9r  suweb_redis.1       redis:latest                     manager  Running        Running 15 seconds ago
5eyr3izyrv7h  suweb_visualizer.1  dockersamples/visualizer:stable  manager  Running        Running 19 seconds ago
ubdvzap007ml  suweb_web.1         subond/suker:v1.0                worker1  Running        Running 24 seconds ago
2dshgwsnfftp  suweb_web.2         subond/suker:v1.0                manager  Running        Running 24 seconds ago
v82zhyx225yu  suweb_web.3         subond/suker:v1.0                manager  Running        Running 23 seconds ago
```
