Title: Linux中的线程管理
Date: 2016-06-19
Category: Tech
Tags: linux, process, pthread
Slug: pthread2-management-in-linux
Author: subond
Summary: 线程是CPU使用的基本单元，由线程ID，程序计数器，寄存器和栈组成。同属一个进程的所有线程共享代码数据，系统资源。多线程具有如下优点：响应度高，资源共享，更经济(较进程)，充分利用多处理器系统的结构。

### 1.线程

线程是CPU使用的基本单元，由线程ID，程序计数器，寄存器和栈组成。同属一个进程的所有线程共享代码数据，系统资源。多线程具有如下优点：响应度高，资源共享，更经济(较进程)，充分利用多处理器系统的结构。

### 2.多线程模型

操作系统中有两种方法提供线程支持：用户层的 **用户线程** 和 内核层的 **内核线程**。用户线程受内核内核支持，而无需内核管理；内核线程由系统直接支持和管理。

1）多对一模型：多个用户线程映射到一个内核线程

特点：线程管理由线程库在用户空间进行，效率高；一个线程阻塞系统调用，整个进程阻塞；任意时刻，只有一个线程能访问内核(也就是，多线程不能并行运行在多处理器上)

2）一对一模型：每个用户线程映射到一个内核线程

特点：一个线程阻塞，其他线程不受影响，具有并发功能；允许多线程运行在多处理器上。

3）多对多模型：即多路复用，许多用户线程映射到同等数量或较少数量的内核线程

特点：结合多对一模型和一对一模型的优点，其对应的一个变形是 **二级模型** (先允许一个用户线程绑定到一个内核线程上，然后，其他用户线程多路复用)

### 3.线程库

线程库为程序员提供创建和管理线程的API函数，主要有两种方法来实现线程库：<b>系统调用</b>和<b>非系统调用</b>

1）在用户空间提供没有内核支持的库，称为 **非系统调用**；  
2）由系统支持的内核级库，称为 **系统调用**

<b>系统调用fork()和exec()</b>

exec():如果一个线程调用exec()，则其指定的程序替换整个进程，包括所有线程。  
fork(): 1）fork()之后立即调用exec()，则没有必要替换所有线程，因为exec()会替换所有线程；2）fork()之后没有调用exec()，则另一个进程复制所有线程。

### 4.线程取消

线程取消是在线程完成之前来终止线程的任务。要取消的线程称为 **目标线程**。目标线程可以在两种情况下发生：

1）**异步取消**: 一个线程立即终止目标线程。  (所有线程共享进程的数据，因为异步取消并不会使系统资源空闲)  
2）**延迟取消**: 目标线程不断检查自己是否应该终止，让线程有机会有序结束自己。  (因为具有 **取消点**，因此更安全)

### 5.信号处理

信号是用来通知进程某个事件已发生，可分为 **异步接收** 和 **同步接收**。所有的信号具有同样的模式：

1）信号是由特定事件发生；2）信号发送至进程；3）一旦发送，信号必须加以处理。  

**同步信号**: 指发送信号到执行操作的同一进程(例如，非法访问，被0除)  
**异步信号**: 指信号由进程外事件产生，发送到另一个进程。(例如，特定键(ctrl+c))

标准发送信号的函数:1) kill(pid_t id, int signal)指定信号的发送进程；2）pthread_kill(pthread_t id, int signal)允许信号被传送到一个指定的线程。

### 6.线程池

其思想是：进程开始时，创建一定数量的线程，放入线程池等待工作。其优点有，1）不必创建新线程，响应时间更快；2）可以限制线程数量，有效利用系统资源。

**Linux线程**

Linux系统中并不区分进程和线程，统称为 **任务**。其系统调用包括：fork()和clone()。

fork():传统复制进程——具备父任务的所有数据的副本  
clone()创建线程(子任务)——根据传递给clone()的标志位，子任务指向父任务的数据结构

## 线程小结

线程是进程内的控制流，多线程进程在同一地址空间内包括多个不同的控制流。用户线程对程序员是可见的，对内核来说却是未知的。操作系统支持和管理内核线程。有三种不同的模式将用户线程和内核线程关联起来：多对一模式，一对一模式和多对多模式。

## 一个小栗子

```
/*
*Author:subond
* Time: 2016-06-19
* Function: 用户在命令行输入一个数字，然后创建一个独立线程来输出小于或等于输入数的所有素数
*/
#include <pthread.h>
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
#include <sys/wait.h>
#include <math.h>
int n;
void *runner(void *param) {
  if(n <= 1) return(NULL);
  for(int i = 2; i <= n; i++) {
    int len = sqrt(i * 1.0);
    int flag = 1;
    for(int j = 2; j <= len; j++) {
      if(i % j == 0)
        flag = 0;
    }
    if(flag == 1)
      printf("%d ", i);
  }
  pthread_exit(0);
}
int main() {
  printf("Enter a number(>= 0):");
  scanf("%d", &n);
  int pid;
  pthread_t tid;
  pthread_attr_t attr;
  pthread_attr_init(&attr);
  pid = pthread_create(&tid, &attr, runner, NULL);
  if(pid != 0) {
    printf("Create pthread error\n");
    return 1;
  }
  pthread_join(tid, NULL);
  return 0;
}
```