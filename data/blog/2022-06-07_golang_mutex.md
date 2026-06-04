---
title: 'Go 互斥锁与读写锁'
date: '2022-06-07'
tags: ['go', 'mutex', 'Go高性能编程', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

`Go` 语言标准包 `sync` 中提供了两种锁，互斥锁 `Mutex` 和读写锁 `RWMutex` ，那两者有什么样的区别和差异呢？

## 互斥锁（sync.Mutex)

互斥意味着加锁的多个代码块不可能同时执行。只有抢到锁的 `goroutine` 才可以执行，其他 `goroutine` 只能等待（阻塞在 `Lock()`方法）锁释放后，获得互斥锁才能继续执行。

互斥锁提供了两种操作：

- Lock()，即上锁
- Unlock()，即解锁

通常我们将`Unlock()` 放到 `defer`函数中执行，确保退出代码块时一定会解锁。



## 读写锁（sync.RWMutex）

读写锁是为了解决这样的场景：只要保证写操作安全就可，读操作可以并行执行，从而提高读的效率。

读写锁也称为 `多读单写锁`，它包括读锁和写锁，读写可以同时执行，但是写锁是互斥的。通常有下面三中场景：

- 在没有写锁的情况下，读锁是不互斥的，允许多个同时执行
- 写锁之间是互斥的，只能一个写锁工作，其他写锁阻塞
- 读锁和写锁是互斥的，如果存在读锁，写锁阻塞；如果存在写锁，读锁阻塞

从这三种场景可以看到，读写锁主要是为了解决读多写少的性能问题。

因此读写锁提供了四个操作：

- Lock()，上写锁
- Unlock()，解写锁

- RLock()，上读锁
- RUnlock()，解读锁



## 互斥锁和读写锁的性能对比

下面我们分三种场景，对比下互斥锁和读写锁的性能差异。

- 读多写少，读900次，写100次
- 读少写多，读100次，写900次
- 读写对半，读写各500次

假设我们读写操作均耗时1微妙。

```go
$ go test -bench .
goos: darwin
goarch: amd64
pkg: gopatterns/mutex
cpu: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz
BenchmarkLockWriteMore-12      	       1	1074382041 ns/op
BenchmarkWRLockWriteMore-12    	       2	 959679281 ns/op
BenchmarkLockReadMore-12       	       1	1067316664 ns/op
BenchmarkWRLockReadMore-12     	      10	 108199306 ns/op
BenchmarkLockWrite-12          	       1	1066590485 ns/op
BenchmarkWRLockWrite-12        	       2	 535516139 ns/op
PASS
ok  	gopatterns/mutex	9.292s
```

通过基准测试结果我们可以发现：

- 读写比例9:1时，读写锁的性能约为互斥锁的10倍
- 读写比例1:9时，读写锁性能差不多
- 读写比例5:5时，读写锁的性能约为互斥锁的2倍



> 互斥锁有两种状态：正常状态和饥饿状态。
>
> 在正常状态下，所有等待锁的goroutine按照**FIFO**顺序等待。唤醒的goroutine不会直接拥有锁，而是会和新请求锁的goroutine竞争锁的拥有。新请求锁的goroutine具有优势：它正在CPU上执行，而且可能有好几个，所以刚刚唤醒的goroutine有很大可能在锁竞争中失败。在这种情况下，这个被唤醒的goroutine会加入到等待队列的前面。 如果一个等待的goroutine超过1ms没有获取锁，那么它将会把锁转变为饥饿模式。
>
> 在饥饿模式下，锁的所有权将从unlock的gorutine直接交给交给等待队列中的第一个。新来的goroutine将不会尝试去获得锁，即使锁看起来是unlock状态, 也不会去尝试自旋操作，而是放在等待队列的尾部。
>
> 如果一个等待的goroutine获取了锁，并且满足一以下其中的任何一个条件：(1)它是队列中的最后一个；(2)它等待的时候小于1ms。它会将锁的状态转换为正常状态。
>
> 正常状态有很好的性能表现，饥饿模式也是非常重要的，因为它能阻止尾部延迟的现象。



## 附录

1.[sync.Mutex源码分析](https://colobu.com/2018/12/18/dive-into-sync-mutex/)
