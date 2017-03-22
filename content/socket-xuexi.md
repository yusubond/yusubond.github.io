Title: Socket编程之函数学习篇
Date: 2016-05-17
Category: Tech
Tags: socket, newtork programming
Slug: socket-bian-cheng-xue-xi
Author: subond
Summary: Socket编程涉及多个函数，本篇主要介绍其相关函数。

Socket编程涉及多个函数，本篇主要介绍其相关函数。

## 基本API函数

### 1.socket()函数-创建套接字

```c
#include <sys/socket.h>
int socket(int domain, int type, int protocol);  //成功返回sockfd;出错返回-1.
```

sockfd是一个socket描述符，它唯一标识一个socket。这个socket描述符跟其他文件描述符一样，后续的读写操作都需用到这个socket描述符。

创建socket的时候，可以指定不同的参数创建不同的socket描述符，socket()函数的三个参数分别为：

**domain:协议域**

协议域规定了socket的地址类型，在通信中必须采用对应的地址类型。AF_INET(IPv4协议),AF_INET6(IPv6协议),AF_LOCAL(Unix域协议),AF_ROUTE(路由套接口)。

**type:socket类型**

常见的socket类型有SOCK_STREAM(字节流套接口),SOCK_DGRAM(数据包套接口),SOCK_RAW(原始套接口),SOCK_PACKET,SOCK_SEQPACKET(有序分组套接口)等等。

**protocol:协议类型**

常见的通信协议有IPPROTO_TCP(TCP传输协议),IPPROTO_UDP(UDP传输协议),IPPROTO_SCTP(SCTP传输协议),IPPROTO_TIPC等等

**注意**：type和protocol并不是可以随意组合的。一般情况下设置protocol为０，系统会自动选择type类型所对应的默认协议。

### 2.bind()函数

```
#include <sys/socket.h>
int bind(int sockfd, const struct sockaddr *addr, socklen_t addrlen);  //返回:0-成功，-1-出错
```

bind()函数涉及三个对象：套接口，地址和端口，负责把特定的地址和端口赋给socket描述符，即sockfd，是从进程到内核传递套接口地址结构的函数。

**sockfd**:socket描述符，即socket()函数创建的唯一标识一个socket。

**addr**:一个const struct sockaddr * 指针,指向要绑定给sockfd的协议地址。其中ipv4地址对应如下：

```
struct sockaddr_in{
    sa_family_t sin_family;
    in_port_t sin_port;       //port in network byte order
    struct in_addr sin_addr;
}
struct in_addr{
    uint32_t s_addr;  //address in network byte order
}
```

**addrlen**:对应的是地址的长度。

函数示例

```
struct sockaddr_in serv;
bind(sockfd, (struct sockaddr *)&serv, sizeof(serv));
```

### 3.listen()函数

```
#include <sys/socket.h>
int listen(int sockfd, int backlog)
```

listen()函数用于服务器端，服务器通过调用listen()函数来监听某个socket。其两个参数如下：

**sockfd**:socket描述符，及socket()函数创建的唯一标识一个socket。

**backlog**:该sockfd可以允许的最大连接数。

### 4.connect()函数

```
#include <sys/socket.h>
int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen);
//返回:0-成功，-1-出错
```

connect()函数用在客户端，客户端通过这个函数连接服务器端，是从进程到内核传递套接口地址结构的函数。其各参数如下：

**sockfd**:socket描述符，即socket()函数创建的唯一标识一个socket。

**addr**:一个const struct sockaddr * 指针,指向要绑定给sockfd的协议地址。

**addrlen**:对应的是地址的长度。

### 5.accept()函数

```
#include <sys/socket.h>
int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen);  //返回连接connect_fd
```

TCP服务器端依次调用<font color="#ff0000">socket(),bind(),listen()</font>之后，进入监听状态，并监听制定的socket地址。TCP客户端依次调用socket(),connect()之后，开始向TCP服务器端发送一个连接请求。TCP服务器端 监听到这个请求后，调用accept()函数接受请求，这样连接就建立好了。accept()函数是从内核到进程传递套接口地址结构的函数。


+ **sockfd**:socket描述符，及socket()函数创建的唯一标识一个socket。

+ **addr**:一个结果参数，用来接受一个返回值，指向客户端的地址。若对客户的地址不感兴趣，可设这个值为NULL。

+ **addrlen**:一个结果参数，用来接受上addr的结构的大小，可以设置为NULL。

### 6.网络I/O函数

常见的网络I/O函数有read()/write(),recv()/send(),readv()/writev(),recvmsg()/sendmsg()和recvfrom()/sendto()。

```
#include <sys/socket.h>
ssize_t recvmsg(int sockfd, struct msghdr *msg, int flags);
ssize_t sendmsg(int sockfd, struct msghdr *msg, int flags);
//返回：成功返回读入/写出的字节数，出错为-1
```

其中函数的大部分参数封装到一个msghdr结构中，如下所示。

```
struct msghdr{
    void          *msg_name;       /*protocol address*/
    socklen_t     msg_namelen;     /*size of protocol address*/
    struct iovec  *msg_iovlen;     /*scatter/gather array*/
    int           msg_iovlen;      /*  elements in msg_iov*/
    void          *msg_control;    /*ancillary data*/
    socklen_t     msg_controllen;  /*length of ancillary data*/
    int           msg_flags;       /*flags returned by recvmsg*/
}
```
