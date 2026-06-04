---
title: '如何在 Shell 中实现并发执行'
date: '2023-09-08'
tags: ['Shell', '多进程', '并发', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

本文主要介绍如何在 Shell 脚本中实现多并发。



## 工作需求

工作中我们经常会遇到一些需要批量处理的操作，比如检测 100 台服务器的状态，或者向 100 台服务器分发文件。

这类操作一般没有依赖关系，所以考虑并发批量执行。

## 实现思路

正常情况下，Shell 脚本是串行执行的，一条命令执行结束才会执行下面的命令。比如以下代码：

```sh
#cat foo.sh
#!/bin/sh
for i in {1..20};do
	echo "do $i"
done
echo "all done"
```

脚本的输出结果如下：

```go
#./foo.sh
do 1
do 2
...省略...
do 19
do 20
all done
```

## 思路1

我们可以在 for 循环体里将每个任务放到后台执行，通过`&`符号实现。

```sh
for i in {1..20};do
	echo "do $i" &
done
```

其输出如下：

```sh
#./foo.sh > x.log
#cat x.log
do 2
do 1
do 3
do 4
do 6
do 11
do 8
do 5
all done
do 9
do 12
do 16
do 7
do 10
do 18
do 20
do 14
do 19
do 13
do 17
do 15
```

可以发现，这个方式可以实现放在后台执行。但是，有些时候，我们希望 for 循环体执行结束，在执行后面的命令，这时可以借助`wait`命令实现，如下：

```sh
#cat foo.sh
#!/bin/sh
for i in {1..20};do
	echo "do $i" &
done
wait
echo "all done"
```

这次执行结果如下：

```sh
#./foo.sh
do 1
do 3
do 4
do 6
do 5
do 9
do 8
do 7
do 10
do 11
do 15
do 17
do 14
do 12
do 16
do 18
do 13
do 19
do 20
do 2
all done
```

尽管这样做可以满足我们的要求，但不够优雅。

如果有多少任务，就需要将多少任务放在后台执行，当任务很大的时候，很可能耗尽系统资源，所以必须控制并发的数量才好。

## 思路2

在思路 1 的基础上，我们可以通过 linux 管道文件特性制作队列，控制并发的数量。

下面，我们使用管道和令牌原理实现并发控制。

```sh
#!/bin/sh

# 创建有名管道
[ -e /tmp/fd1 ] || mkfifo /tmp/fd1

# 创建文件描述符3，以可读(<)可写(>)的方式关联管道文件
# 此时文件描述符3就有了有名管道的所有特性
exec 3<>/tmp/fd1

# 这个时候可以删除管道文件，留下文件描述符3来用就可以了
rm -rf /tmp/fd1

# 向文件描述符3投放四个令牌
for i in {1..4};do
	echo >&3
done

for i in {1..20};do
	# read 从文件描述符读取一个令牌
	# 整个 {}& 代码块就是需要放在后台运行的内容
	read -u3
	{
		# sleep 模拟后台任务运行所花费的时间
		sleep 1
		echo "do $i"  
		# 任务结束，把令牌放回管道
		echo >&3
	}&
done
wait
echo "all done"
```

脚本执行如下：

```sh
do 2
do 1
do 3
do 4
do 6
do 5
do 8
do 7
do 9
do 10
do 12
do 11
do 13
do 14
do 16
do 15
do 17
do 18
do 19
do 20
all done
```

代码解析：

代码中有两个 for 循环。第一个 for 循环是在创建令牌，并放入文件描述符中，循环次数就是令牌个数，根据需要自行调整即可。

第二个 for 循环是真正要并发执行的任务数。`read -u3`表示取令牌，`echo >&3`表示存令牌，这样就实现了20个任务通过4个令牌实现并发，并发数量为四。

注意：创建一个文件描述符`exec 3<>/tmp/fd1`不能有空格，代表文件描述符3有可读`(<)`可写`(>)`权限。

打开权限可以写在一起，但关闭权限必须分开关闭。`exec 3<&-`关闭读权限；`exec 3>&-`关闭写权限。



另外，exec命令可以用来替代当前shell；换句话说，并没有启动子shell。使用这一命令时任何环境都将被清除，并重新启动一个shell。它的一半形式为：
命令格式：exec command
其中，command通常是一个shell脚本。
描述exec命令最贴切的说法是：它践踏了你当前的shell。
当这个脚本结束了，相应的会话可能也就结束了。
但是，exec在对文件描述符进行操作的时候（也只有在这个时候），它不会覆盖你当前的shell。
下面举几个例子：

```
exec 3</tmp/1.txt    //以“只读方式”打开/tmp/1.txt，文件描述符对应为3
exec 3>/tmp/1.txt    //以“只写方式”打开/tmp/1.txt，文件描述符对应为3
exec 3<>/tmp/1.txt   //以“读写方式”打开/tmp/1.txt，文件描述符对应为3
exec 3<&-            //关闭文件描述符3
```
