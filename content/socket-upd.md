Title: Socket编程之基本UDP编程
Date: 2016-05-24
Category: TECH
Tags: socket, newtork programming
Slug: socket-bian-cheng-udp
Author: subond
Summary: UDP套接字编程模型。TCP编写的应用程序和UDP编写的应用程序之间存在本质的差别，其原因在于两者在传输层之间的差异：UDP是无连接不可靠的数据包协议，而不同于TCP提供的面向连接的可靠字节流。使用UDP编写的常见应用程序有：DNS(域名系统)， NFS(网络文件系统)和SNMP(简单网络管理协议)。典型的UDP客户/服务器程序的函数调用如下图1-1所示。

## 1.UDP套接字编程模型

TCP编写的应用程序和UDP编写的应用程序之间存在本质的差别，其原因在于两者在传输层之间的差异：UDP是无连接不可靠的数据包协议，而不同于TCP提供的面向连接的可靠字节流。使用UDP编写的常见应用程序有：DNS(域名系统)， NFS(网络文件系统)和SNMP(简单网络管理协议)。典型的UDP客户/服务器程序的函数调用如下图1-1所示。

![udp-socket](http://on64c9tla.bkt.clouddn.com/20160514udp-bian-cheng-mo-xing.jpg)

图1-1 UDP客户/服务器程序所用的套接字函数

## 2.recvfrom()和sendto()函数

```
#include<sys/socket.h>
ssize_t recvfrom(int sockfd, void *buff, size_t nbytes, int flags, struct sockaddr *from, socklen_t *addrlen);
ssize_t sendto(int sockfd, const void *buf, size_t nbytes, int flags, const struct sockaddr *to, socklen_t addrlen);
//均返回：若成功返回读或写的字节数，出错返回-1
```

前三个参数sockfd,buff和nbytes为：描述符、指向读入或写出的缓冲区的指针和读写字节数。
flags一般置为0。

sendto的to参数指向一个含有数据包接收者的协议地址的套接字地址结构，其大小由addrlen参数指定。recvfrom的from参数指向一个将由该函数在返回时填写数据报发送者的协议地址的套接字地址结构， 而在该套接字地址结构中填写的字节数则放在addrlen参数所所指的整数中返回给调用者。

**注意**:sendto的最后一个参数是一个整数值，而recvfrom的最后一个参数是一个指向整数值的指针（即值-结果参数）。

**注意**:recvfrom的最后两个参数类似accept的最后两个参数：返回时其中套接字地址结构的内容告诉我们是谁发送了数据报（UDP）或是谁发起了连接（TCP）。sendto的最后两个参数类似connect的最后两个参数： 调用时其中套接字地址结构被我们填入数据报发往（UDP）或预制建立连接（TCP）的协议地址。

## 3.消息回传程序示例

**服务端程序**

```
#include "socket_includes.h"
int main(int argc, char *argv[])
{
  int listenfd, sockfd;
  struct sockaddr_in server, client;
  char buf[MAX_BUFFER_SIZE], read_buf[MAX_BUFFER_SIZE];
  socklen_t lenserv,lencli;
  char str[20];
  bzero(&server, sizeof(server));
  bzero(&str, sizeof(str));
  memset(buf, 0x00, MAX_BUFFER_SIZE);
  memset(read_buf, 0x00, MAX_BUFFER_SIZE);
  lenserv = sizeof(server);
  lencli = sizeof(client);
  //创建套接字
  //listenfd = socket(AF_INET,SOCK_DGRAM, 0);
  if((listenfd = socket(AF_INET, SOCK_DGRAM, 0))< 0)
  {
    perror("Create socket fail!");
    return -1;
  }
  //绑定套接字
  server.sin_family = AF_INET;
  server.sin_port = htons(8888);                //主机字节序转网络字节序
  server.sin_addr.s_addr = htonl(INADDR_ANY);   //绑定主机的所有网卡
  if(bind(listenfd, (struct sockaddr*)&server, lenserv) < 0)
  {
    perror("bind socket error.");
    return -1;
  }
  ssize_t rv;
  while (1)
  {
    rv = recvfrom(listenfd, read_buf, MAX_BUFFER_SIZE, 0, (struct sockaddr *)&client, &lencli);
    if(rv < 0)
    {
      printf("recvfrom error.\n");
      close(sockfd);
      return -1;
    }
    inet_ntop(AF_INET, &client.sin_addr.s_addr, str, sizeof(str));
    printf("size of buf_client: %ld\n", rv);
    printf("client buf:%s\n", read_buf);
    printf("client IP: %s, Port: %d\n", str, ntohs(client.sin_port));
    sendto(listenfd, read_buf, sizeof(read_buf), 0, (struct sockaddr *)&client, lencli);
    bzero(&client, lencli);
    memset(buf, 0x00, MAX_BUFFER_SIZE);
    memset(read_buf, 0x00, MAX_BUFFER_SIZE);
  }
  close(sockfd);
  return 0;
}
```

**客户端程序**

```
#include "socket_includes.h"
int main(int argc, char const *argv[])
{
  int sockfd;
  char buf[MAX_BUFFER_SIZE] = "Hello UDP!";
  char read_buf[MAX_BUFFER_SIZE];
  struct sockaddr_in server, ser;
  int rv;
  socklen_t length,len;
  bzero(read_buf, MAX_BUFFER_SIZE);
  bzero(&server, sizeof(server));
  len = sizeof(ser);
  length = sizeof(server);
  //sockfd = socket(AF_INET,SOCK_DGRAM, 0);
  if((sockfd = socket(AF_INET,SOCK_DGRAM, 0)) < 0)
  {
    perror("Create socket fail!\n");
    return -1;
  }
  server.sin_family = AF_INET;
  server.sin_port = htons(8888);
  inet_pton(AF_INET, "10.103.14.28", &server.sin_addr.s_addr);
  sendto(sockfd, buf, strlen(buf), 0, (struct sockaddr *)&server, length);
  rv = recvfrom(sockfd, read_buf, MAX_BUFFER_SIZE, 0, (struct sockaddr *)&ser, &len);
  if(rv < 0)
  {
    printf("recvfr0m error!\n");
    close(sockfd);
    return -1;
  }
  printf("server buf_back:%s\n", read_buf);
  close(sockfd);
  return 0;
}
```

其中头文件均为socket_includes.h

```
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/shm.h>
#include <arpa/inet.h>

#include <unistd.h>
#include <fcntl.h>


#define MAX_LISTEN_QUE 5
#define SERV_PORT 8888
#define MAX_BUFFER_SIZE 100
```
