---
title: 'Go逃逸分析与性能'
date: '2022-09-15'
tags: ['go', '技术', 'Go高性能编程']
draft: false
authors: ['default']
layout: PostLayout
---

## 1、变量与内存

通常每种编程语言都有自己的内存模型，每个变量，常量都存储在内存的某个物理位置上，并通过内存指针来访问。

我们都知道，程序运行时所使用的的内存分为两个区：堆和栈。那我们怎么知道变量是分配在堆还是栈上呢？Go 语言实现了垃圾回收机制，其内存是自动管理的，所以通常作为开发者并不需要关心内存分配在栈还堆上。但是站在性能的角度，在栈上分配内存和堆上分配内存，两者的性能却非常大。因为分配在栈上的内存，函数直接结束就能自动回收；而分配在堆上的内存，需要等待垃圾回收才能被回收释放。

在 Go 官网的FAQ上有个变量分配的问题如下：

> 如何知道变量是分配在堆上还是栈上？
>
> 从正确性的角度来看，你不需要知道。只要有对它的引用，Go 中的每个变量就存在，而且变量选择的存储位置与语言的语义无关。
>
> 存储位置确实对程序性能有影响。如果可能，Go 编译器将在函数的栈上分配该函数的本地变量。但是，如果函数返回后无法保证该变量不再被引用，那么编译器必须在垃圾回收的堆上分配该变量以避免悬空指针错误。此外，如果局部变量非常大，将其存储在堆上而不是栈上可能更有意义。
>
> 在当前的编译器中，如果一个变量的地址被占用，那么该变量就是在堆上分配的候选者。但是，基本的*逃逸分析*会识别某些情况，将函数返回后不再存活的变量分配在栈上。

由此我们可以发现，变量逃逸一般发生在以下几种情况：

- 函数返回地址
- 函数返回引用
- 函数返回值类型不确定，或者说不确定其大小
- 变量过大
- 变量大小不确定

那么，知道变量逃逸的原因后，我们就可以有意识地将变量控制在栈上，减少堆变量的分配，降低GC成本，提高程序性能。



## 2、逃逸分析

Go 语言内存分配是由编译器决定的，编译器会跨越函数和包的边界进行全局的分析，检查是否需要在堆上为一个变量分配内存，还是在栈本身的内存对其进行管理，这个过程称为逃逸分析(escape analysis)。



### 2.1 变量大小逃逸

举个例子，我们模拟一个变量大小不确定的情况：

```go
package main

func main() {
	num := 10
	s1 := make([]int, 0, num)
	for i := 0; i < num; i++ {
		s1 = append(s1, i)
	}

	s2 := make([]int, 0, 10)
	for i := 0; i < num; i++ {
		s2 = append(s2, i)
	}
}
```

编译时，指定编译参数`-gcflags="-m"`可以查看逃逸分析，结果如下：

```go
go build -gcflags="-m" main.go
# command-line-arguments
./subond.go:3:6: can inline main
./subond.go:5:12: make([]int, 0, num) escapes to heap
./subond.go:10:12: make([]int, 0, 10) does not escape
```

通过上面的结果我们可以看到，使用变量(非常量)来指定切片的容量，会发生逃逸，将切片分配在堆上；而使用常量指定切片的容量，没有发生逃逸。

**所以，如果使用局部切片，已知切片的长度和容量，请尽量使用常量或数值字面量来定义。**



### 2.2 返回值 vs 返回指针

函数返回值，如果是值传递方式会拷贝整个对象；如果返回指针只会拷贝地址，指向的对象是同一个。指针传递可以减少值的拷贝，但是内存分配在堆上，增加了垃圾回收(GC)的负担。在对象频繁创建和删除的场景中，返回指针导致的GC可能会严重影响性能。

所以，一般情况下，对于需要修改原对象，或者占用内存比较大的对象，返回指针更合适；对于只读，或者占用内存很小的对象，返回值更合适。

下面举个例子，一种方式是返回指针，一种是返回值，看下两者的性能差异。

```go
type (
	foo struct {
		data [1024]int
	}
)

func returnFooByValue() foo {
	var f foo
	return f
}

func returnFooByPointer() *foo {
	var f foo
	return &f
}

func BenchmarkReturnValue(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = returnFooByValue()
	}
}

func BenchmarkReturnPointer(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = returnFooByPointer()
	}
}
```



运行基准测试，结果如下：

```go
goos: darwin
goarch: amd64
cpu: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz
BenchmarkReturnValue-12      	 5176292	       223.3 ns/op	       0 B/op	       0 allocs/op
BenchmarkReturnPointer-12    	 1281316	       936.6 ns/op	    8192 B/op	       1 allocs/op
PASS
```



### 2.3 小的拷贝好过引用

小的拷贝好过引用，什么意思呢？就是说尽量使用栈变量，而不是堆变量。

Go 语言中数组是通过`pass-by-value`方式传递的，下面我们来比较下数组的值拷贝和切片的引用，哪个更好。

```go
const size = 1024

func arrayNums() [size]int {
	var nums [size]int
	for i := 0; i < size; i++ {
		nums[i] = i
	}
	return nums
}

func sliceNums() []int {
	var nums []int
	for i := 0; i < size; i++ {
		nums = append(nums, i)
	}
	return nums
}

func BenchmarkArray(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = arrayNums()
	}
}

func BenchmarkSlice(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = sliceNums()
	}
}
```

运行基准测试，结果如下：

```go
go test -gcflags="-l" -benchmem -bench .
goos: darwin
goarch: amd64
cpu: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz
BenchmarkArray-12    	 1892257	       628.2 ns/op	       0 B/op	       0 allocs/op
BenchmarkSlice-12    	  434859	      2784 ns/op	   16376 B/op	      11 allocs/op
PASS
```

从测试结果我们可以看出，对于数组的拷贝性能要比切片好。这是为什么呢？因为函数`sliceNums()`中分配的局部变量需要返回到函数外面，发生逃逸，需要在堆上分配内存空间；从结果还可以看到函数`arrayNums()`没有内存分配，完全在栈上完成数组的创建。

需要注意的是，运行上面的基准测试，传递了禁止内联的编译选项`-l`，如果发生内联，就不会出现变量逃逸，也就不存在堆上分配和回收，两者的性能将没有差异。

编译选项`-m`，可以查看编译器对上面两个函数的优化决策：

```go
go build -gcflags="-m" main.go
# command-line-arguments
./copy.go:5:6: can inline arrayNums
./copy.go:13:6: can inline sliceNums
```



## 3、总结

- 局部切片尽量确定长度或容量
- 大对象返回指针更合适，小对象返回值更合适
- 尽量避免返回`interface`类型，尽可能使用确定类型



附录：

Go FAQ：https://go.dev/doc/faq#stack_or_heap
