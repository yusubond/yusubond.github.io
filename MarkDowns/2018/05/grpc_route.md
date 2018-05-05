Title: gRPC使用指南2
Date: 2018-05-03
Category: Tech
Tags: tech, golang, rpc
Slug: grpc_route
Author: subond
Summary:

## 创建服务端



## 创建客户端

### 创建存根

为了能够调用service的方法，首先需要创建gRPC *channel* 来连接服务端，将ip地址和port传递给gRPC.Dial()。

```go
conn, err := grpc.Dial(*serverAddr)
if err != nil {
    ...
}
defer conn.Close()
```

一旦 *channel* 建立连接，就可以创建客户端存根来调用RPC服务。

```go
client := pb.NewRouteGuideClient(conn)
```

### 调用service的方法

1）**简单RPC**

```go
feature, err := client.GetFeature(context.Background(), &pb.Point{409146138, -746188906})
if err != nil {
        ...
}
```

通过使用`context.Context`对象，可以在必要的时候改变RPC的行为，比如超时和取消(timeout, cancle)。

2）**服务器端流式RPC**

```go
rect := &pb.Rectangle{ ... }  // initialize a pb.Rectangle
stream, err := client.ListFeatures(context.Background(), rect)
if err != nil {
    ...
}
for {
    feature, err := stream.Recv()
    if err == io.EOF {
        break
    }
    if err != nil {
        log.Fatalf("%v.ListFeatures(_) = _, %v", client, err)
    }
    log.Println(feature)
}
```

通过Recv()方法反复读取服务器的响应，直到消息读取完毕。*每次调用完Recv()，客户端都要检查从Recv()返回的错误类型*。如果返回为`nil`，表示流依然完好并且可以继续读取；如果返回为`io.EOF`，则说明消息流已经结束；否则就一定是一个通过err传过来的RPC错误。

3) **客户端流式RPC**

```go
// Create a random number of random points
r := rand.New(rand.NewSource(time.Now().UnixNano()))
pointCount := int(r.Int31n(100)) + 2 // Traverse at least two points
var points []*pb.Point
for i := 0; i < pointCount; i++ {
	points = append(points, randomPoint(r))
}
log.Printf("Traversing %d points.", len(points))
stream, err := client.RecordRoute(context.Background())
if err != nil {
	log.Fatalf("%v.RecordRoute(_) = _, %v", client, err)
}
for _, point := range points {
	if err := stream.Send(point); err != nil {
		log.Fatalf("%v.Send(%v) = %v", stream, point, err)
	}
}
reply, err := stream.CloseAndRecv()
if err != nil {
	log.Fatalf("%v.CloseAndRecv() got error %v, want %v", stream, err, nil)
}
log.Printf("Route summary: %v", reply)
```

RouteGuide_RecordRouteClient有一个Send()方法，用来给服务器发送请求。一旦我们完成使用 Send() 方法将客户端请求写入流，就需要调用流的 CloseAndRecv()方法，让 gRPC 知道我们已经完成了写入同时期待返回应答。我们从 CloseAndRecv() 返回的 err 中获得 RPC 的状态。如果状态为nil，那么CloseAndRecv()的第一个返回值将会是合法的服务器应答。
