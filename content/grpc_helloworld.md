Title: gRPC使用指南
Date: 2018-05-01
Category: TECH
Tags: tech, golang, rpc
Slug: grpc_helloworld
Author: subond
Summary: gRPC是一个高性能、开源、通用的RPC框架，面向移动和HTTP/2设计，并且提供多个语言版本支持。本文章基于golang语言，通过概述和一个简单的HelloWorld来介绍gRPC的基本概念和使用方法。

gRPC是一个高性能、开源、通用的RPC框架，面向移动和HTTP/2设计，并且提供多个语言版本支持。本文章基于golang语言，通过概述和一个简单的HelloWorld来介绍gRPC的基本概念和使用方法。

## 1. gRPC概述

gRPC允许客户端应用可以像调用本地对象一样直接调用另一台不同机器上的服务端应用，使开发人员更容易地创建分布式应用和服务。

在gRPC里，首先需要 **定义一个服务**，指定其能够被远程调用的方法(包含参数和返回类型)。然后，服务端将实现这个接口，并运行一个gRPC服务器来处理客户端的调用。客户端则拥有一个 **存根** 能够像服务端一样的方法。

**Protocol Buffers**

gRPC默认使用Protocol Buffers，这是Google开源的一套成熟的结构数据序列化机制。在proto文件中创建gRPC服务，并且用消息类型来定义相关的参数和返回类型都比较方便，这里我们使用`proto3`版本。

## 2. 安装gRPC和proto

安装golang，且版本大于等于1.6；并设置相应的环境变量GOPATH,GOROOT等。

安装gRPC，gRPC使用golang语言编写的，可以直接使用go命令去下载。

```go
go get -u google.golang.org/grpc
```

安装protobuf，参考[https://github.com/google/protobuf/releases](https://github.com/google/protobuf/releases)，依据相应的系统平台选择安装包。

安装protobuf go插件。

```go
go get -u github.com/golang/protobuf/protoc-gen-go
```

## 3. HelloWorld gRPC

这个HelloWorld程序位于gRPC源码的`examples`目录下，它展示了一个简单的客户端-服务端应用。

+ 通过proto文件定义一个简单的带有HelloWorld方法的gRPC服务

+ 创建一个实现这个接口的服务端

+ 创建一个客户端来访问你的服务端

### 指定protobuf版本

```protobuf
syntax = "proto3";
```

### 指定包名

这个包名就是生成golang源码后所使用的包名。

```protobuf
package helloworld;
```

### 定义服务

通过`service`关键字来定义一个服务，并指定其参数和返回类型。参数和返回类型一般通过`message`关键字进行定义。

```protobuf
service Greeter {
  // Sends a greeting
  rpc SayHello (HelloRequest) returns (HelloReply) {}
}

// The request message containing the user's name.
message HelloRequest {
  string name = 1;
}

// The response message containing the greetings
message HelloReply {
  string message = 1;
}
```

值得说明的是，在proto文件中定义的service *转化* 成golang源码中的interface类型；message类型 *转化* 成struct类型。

### 生成golang源码

命令`protoc helloworld/helloworld.proto --go_out=plugins=grpc:.`可生成proto文件中定义的service和message，文件以`.pb.go`结尾。

## 4. 服务端应用

服务端编程中，需要首先import刚才生成的包，然后定义server类型，并实现SayHello接口。部分代码如下：

```go
import "google.golang.org/grpc"
import pb "google.golang.org/grpc/examples/helloworld/helloworld"

// server is used to implement helloworld.GreeterServer.
type server struct{}

// SayHello implements helloworld.GreeterServer
func (s *server) SayHello(ctx context.Context, in *pb.HelloRequest) (*pb.HelloReply, error) {
	return &pb.HelloReply{Message: "Hello " + in.Name}, nil
}
```

main中先生成grpc服务，并注册该服务，部分代码如下：

```go
s := grpc.NewServer()
pb.RegisterGreeterServer(s, &server{})
```

## 5. 客户端应用

同样，客户端编程中也需要import相应的包，然后通过`grpc.Dial()`建立与server的连接，并根据连接生成客户端，在进行rpc调用。部分代码如下：

```go
// import相应的包
import "google.golang.org/grpc"
import pb "google.golang.org/grpc/examples/helloworld/helloworld"

// 建立与server的连接
conn, err := grpc.Dial(address, grpc.WithInsecure())

// 生成客户端
c := pb.NewGreeterClient(conn)

// 调用server的方法
r, err := c.SayHello(ctx, &pb.HelloRequest{Name: name})
```

值得注意的是，调用结束后连接需要释放。

```go
defer conn.Close()
```

## 6. 启动服务端与客户端

```go
// 启动服务端
go run server/main.go

// 启动客户端
go run client/main.go
```
