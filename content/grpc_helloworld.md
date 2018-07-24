Title: Protobuf中的repeated关键字的使用
Date: 2018-07-14
Category: Tech
Tags: tech, c++, grpc
Slug: protobuf_repeated
Author: subond

在protobuf中我们可以使用`repeated`字段来限定一个字段，其意为可重复，类似std中的vector。当使用cpp版本的protobuf时，若定义repeated字段，则在生成的接口中包含一个名为`add_xxx()`的api，意味着可以向其中添加数据。但是,`add_xxx()`并没有生效，即server中设置后，client端读不到，造成的原因是add_xxx()并没有真正地创建一个数组.

例如：

```proto3
message High {
  uint32 high = 1;
}

message HelloReply {
  repeated uint32 weigh = 1;
  repeated High high = 2;
}
```

在server.cc中添加下面的函数`reply->add_weigh(90);`，然后在client.cc中读取该值，`printf("the weigh is %d\n", reply.weigh());`则读取失败

有一个可行的办法就是使用`message`关键字进行包装一下，例如high字段。两者的主要区别就是一个在message里面，一个在message外面。

service代码示例：

```cpp
# server.cc
Status SayHello(ServerContext* context, const HelloRequest* request, HelloReply* reply) override {
  // 直接使用add_xxx()向repeated字段中添加值，不成功
  reply->add_weigh(90);

  // 通过message封装一层，先添加后设置即可，成功
  ::helloworld::High *high = reply->add_high();
  high->set_high(175);
  return Status::OK;
}
```


client代码示例：

```cpp
# client.cc
if (status.ok()) {
  const ::helloworld::High& high = reply.high(0);
  printf("the high is %d\n", high.high());
  printf("the weigh is %d\n", reply.weigh());
} else {
  std::cout << status.error_code() << ": " << status.error_message() << std::endl;
  return "RPC failed";
}
```

结论：在一个message中如果对一个基本数据类型使用repeated关键字，其生成的api无法添加值；对复杂数据类型使用repeated关键字，其生成的api可以添加值。
