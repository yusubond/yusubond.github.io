Title: Socket编程之基础篇
Date: 2016-05-14
Category: Tech
Tags: socket, newtork programming
Slug: socket-bian-cheng-ji-chu
Author: subond
Summary: Socket，又称为“套接字”，是进程间进行通信的一种方式，即通过网络库的API函数实现分布在不同主机的相关进程间的数据交换。在TCP/IP网络应用中，通信的两个进程的主要模式是客户/服务器模式， 即客户向服务器发送服务请求，服务器接收到请求后，提供相应的服务。Socket编程接口是指从顶上三层（网际协议的应用层）进入传输层的接口，涉及两个方向上的传递：从进程到内核和从内核到进程，如图1-1所示。

Socket，又称为“套接字”，是进程间进行通信的一种方式，即通过网络库的API函数实现分布在不同主机的相关进程间的数据交换。在TCP/IP网络应用中，通信的两个进程的主要模式是客户/服务器模式， 即客户向服务器发送服务请求，服务器接收到请求后，提供相应的服务。Socket编程接口是指从顶上三层（网际协议的应用层）进入传输层的接口，涉及两个方向上的传递：从进程到内核和从内核到进程，如图1-1所示。

![tcp-ip-stack](http://on64c9tla.bkt.clouddn.com/20160514socket-yu-xie-yi-ge-ceng.jpg)

## 套接字地址结构

学习套接字编程，首先要知道套接字的地址结构，大多数套接字函数都需要一个指向套接字的地址结构的指针作为参数。每个协议族都有自己的套接字地址结构， 均以sockaddr_开头，并以对应的每个协议族的唯一后缀结尾。

### 1.IPv4套接字地址结构

IPv4套接字地址结构以sockaddr_in命名，定义在<netinet/in.h&mt头文件中，如下所示。

```c
struct in_addr{
    in_addr_t s_addr;       /*32-bit IPv4 address;network byte ordered*/
    struct sockaddr_in {
        uint8_t            sin_len;
        sa_family_t        sin_family;        /*AF_INET*/
        in_port_t          sin_port;          /16-bit TCP or UDP port number;network byte ordered*/
        struct in_addr     in_addr sin_addr;  /*32-bit IPv4 address;network byte ordered*/
        char               sin_zero[8];       /*unused*/
    }
}
```

**说明**: 一般情况下，我们只使用这个结构中的3个字段：sin_family,sin_addr和sin_port，其分别对应套接字地址结构的协议族、IP地址和端口号。套接字地址结构仅在给定主机上使用 其结构中的某些字段用在不同主机间的通信，但结构本身不在主机之间传递。

### 2.IPv6套接字地址结构

IPv4套接字地址结构以sockaddr_in6命名，定义在<netinet/in.h&mt头文件中，如下所示。

```c
struct in6_addr{
    uninet8_t s6_addr[16];       /*128-bit IPv4 address;network byte ordered*/
    struct sockaddr_in {
      uint8_t          sin6_len;
      sa_family_t      sin6_family;        /*AF_INET6*/
      in_port_t        sin6_port;          /*transport layer port;network byte ordered*/
      uint32_t         sin6_flowinfo       /*flow information,undefined*/
      struct in6_addr  sin6_addr;          /*128-bit IPv6 address;network byte ordered*/
      uint32_t         sin6_zero[8];       /*unused*/
  }
}
```

### 3.值-结果参数

当往一个套接字函数传递一个套接字地址结构时，结构以引用形式来传递，也就是说传递的是指向该结构的一个指针，该结构的长度作为一个参数来传递，其传递方向取决于传递方向：是内核到进程，还是进程到内核。

(1)从进程到内核传递套接字地址结构的函数有3个：bind(),connet()和sendto()。这些函数的一个参数是指向某个套接字地址结构的指针，一个参数是该结构的整数大小，如下所示。

```
int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen);
```

(2)从内核到进程传递套接字地址结构的函数有4个：accept(),recvfrom(),getsockname()和getpeername()。这4个函数其中的两个参数是指向某个套接字地址结构的指针和指向该地址结构大小的整数变量指针，如下所示。

```
int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen);
```

### 4.字节排序函数

简单来说，主机和网络存储整形数据的字节顺序一般是不一样的，我们将他们称之为主机字节序和网络字节序，分别对应内核处理和进程处理。两种字节序之间的互转使用以下4个函数，其对应套接字地址结构（IP地址＋端口号）的字节序的转换。

```c
#include <netinet.h>
    uint16_t htons(uint16_t host16bitvalue);
    uint32_t htonl(uint32_t host32bitvalue);  //返回：网络字节序的值
    uint16_t ntohs(uint16_t host16bitvalue);
    uint32_t ntohs(uint32_t host32bitvalue);  //返回：主机字节序的值
```

### 5.地址转换函数

地址转换函数可以在ASCII字符串与网络字节序的二进制值之间转换网际地址。常用的地址转换函数有inet_pton()和inet_ntop()，其中p代表表达（presentation），n代表数值（numeric）。地址的表达格式通常是ASCII字符串，数值格式是存放到 套接字地址结构中的二进制值。

```
#include <arpa/inet.h>
int inet_pton(int family, const char *strptr, void *addrptr);
//返回：1-成功；0-输入不是有效表达式；-1-出错。
const char *inet_ntop(int family, const void *addrptr, char *strptr, size_t len);
//返回：成功则为指向结果的指针，出错为NULL。
```

### 6.字节操作函数

字节操作函数用于处理多字节字段，例如bzero()函数。

```
#include <strings.h>
void bzero(void *dest, size_t nbytes);
```
