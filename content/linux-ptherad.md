Title: Linux中的线程函数
Date: 2016-06-14
Category: Tech
Tags: linux, pthread, process
Slug: pthread-management-in-linux
Author: subond
Summary: 线程是CPU使用的基本单元，由线程ID，程序计数器，寄存器和栈组成。同属一个进程的所有线程共享代码数据，系统资源。多线程具有如下优点：响应度高，资源共享，更经济(较进程)，充分利用多处理器系统的结构。本节主要介绍5个基本线程函数。

线程是CPU使用的基本单元，由线程ID，程序计数器，寄存器和栈组成。同属一个进程的所有线程共享代码数据，系统资源。多线程具有如下优点：响应度高，资源共享，更经济(较进程)，充分利用多处理器系统的结构。以下内容，主要介绍5个基本线程函数。

### 1.pthread_create()函数

当一个程序由exec启动执行时，称为初始线程或主线程的单个线程就创建了。其余线程则由pthread_create函数创建。

```
#include <pthread.h>
int pthread_create(pthread_t *tid, const pthread_attr_t *attr, void *(*func)(void *), void *arg);
//返回：成功为0，出错为正的Exxx值
```

**tid**:一个进程内的每个线程都有一个线程ID标识，其数据类型为pthread_t(unsigned long int,即％lu)。如果新的线程创建成功，其ID通过tid指针返回。

**attr**:属性，每个线程都有许多属性（优先级，初始栈大小，是否成为一个守护线程等等）。若采用默认设置，可置attr参数为空指针（NULL）。

创建一个线程时最后指定的参数就是由该线程执行的函数func及其参数arg。**注意** func和arg的声明。func所指函数作为参数接受一个通用指针 (void \*)，又作为返回值返回一个通用指针(void \*)。另外该函数的唯一调用参数是指针arg，如果需要给函数传递多个参数，可以打包成一个结构，然后将结构的地址作为单个参数传递给函数。

### 2.pthread_join()函数

```
#include <pthread.h>
int pthread_join(pthread_t *tid, void **status);    //返回：成功为0，出错为正的Exxx值。
```

该函数的功能是等待一个给定线程终止

### 3.pthread_self()函数

```
#include <pthread.h>
int pthread_self(void)   //返回：调用线程的线程ID。
```

### 4.pthread_detach()函数

```
#include <pthread.h>
int pthread_detach(pthread_t tid)  //返回：成功返回0，出错为正的Exxx值。
```

一个线程或是可汇合的(joinable,默认值)，或是脱离的(detached)。当一个可汇合的线程终止时，它的线程ID和退出状态将留存到另一个线程对它的调用pthread_join。脱离的线程却像守护进程，当它们终止时，所有相关的资源 都被释放，我们不能等待它们终止。pthread_detach函数就是把指定的线程转变为脱离状态。


### 5.pthread_exit()函数

```
#include <pthread.h>
int pthread_exit(void *status)  //不返回
```

调用pthread_exit函数可使线程终止。

## 一个栗子

利用线程的方法，重新编写基本UDP套接字编程

其服务端源码地址：[https://github.com/yusubond/Socket-Programming/blob/master/udp_demo/serverv0.3.c](https://github.com/yusubond/Socket-Programming/blob/master/udp_demo/serverv0.3.c)

结果如下图所示：

![udp-socket](http://on64c9tla.bkt.clouddn.com/20160614pthread_udp.png)
