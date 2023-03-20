---
Title: "Go defer如何调用"
Date: 2022-09-26
Categories: ["Go高性能编程", "技术"]
Tags: ["go", "defer"]
---

## 1、在defer语句声明时进行估值

我们都知道go中`defer`是延时调用，一般在return语句结束后调用。但是如果defer语句中包含变量呢，那变量该如何计算？

看这样一个例子

```go
type (
	su struct {}
)

func (s *su) add(i int) *su {
	fmt.Println(i)
	return s
}

func main() {
	x := su{}
	defer x.add(2).add(3)
	fmt.Println(1)
}
```

请问该函数的输出是什么呢？1,2,3还是2,13？

其实结果是这样的：

```go
2
1
3
```

解释下，其实是这样的，在执行代码12行的时候，编译器先进行了`x.add(2)`的计算，然后进行`.add(3)`的压栈操作。所以就出现了这样的结果，执行12行时对语句进行了估值，先输出了`2`，紧接着执行13行，输出`1`；最后执行`defer`的出栈操作，输出`3`。

我们在看这样一个例子：

```go
type (
	su struct {
		num int
	}
)

func (s *su) add(i int) *su {
	s.num++
	fmt.Println("add", i, s.num)
	return s
}

func inc() int {
	x := &su{num: 0}
	defer x.add(2).add(3)
	fmt.Println("inc", x.num)
	return x.num
}

func main() {
	fmt.Println("main", inc())
}
```

与上面的例子不同的是，在结构体中增加了一个字段num。可以思考下这种情况的输出。

其结果是：

```go
add 2 1
inc 1
add 3 2
main 1
```

首先输出`add 2 1`应该没有疑问，因为在执行15行的时候，先对`x.add(2)`进行了估值；

紧接着输出`inc 1`，因为在`x.add(2)`中对`num`进行了`+1`操作；

然后执行defer函数`.add(3)`，输出`add 3 2`，此时`num`又进行了一次`+1`操作；

最后执行main函数，输出`main 1`，为啥不是2呢，因为17行先返回。

那如果做一个小的修改，就`inc`函数返回`su`结构体指针，在main函数中查看其num值。应该得到`main 2`。

修改后是这样的：

```go
type (
	su struct {
		num int
	}
)

func (s *su) add(i int) *su {
	s.num++
	fmt.Println("add", i, s.num)
	return s
}

func inc() *su {
	x := &su{num: 0}
	defer x.add(2).add(3)
	fmt.Println("inc", x.num)
	return x
}

func main() {
	fmt.Println("main", inc().num)
}
```

其输出结果是，符合预期。

```go
add 2 1
inc 1
add 3 2
main 2
```



在文章https://go.dev/blog/defer-panic-and-recover中，描述了defer语句的三个原则，其分别是：

> 1.A deferred function’s arguments are evaluated when the defer statement is evaluated.

即defer函数中的参数在defer语句声明时已经被估值。

所以像下面的写法，将输出`0`。

```go
func a() {
  i := 0
  defer fmt.Println(i)
  i++
  return
}
```



> 2. Deferred function calls are executed in Last In First Out order after the surrounding function returns.

这个比较好理解，defer函数的顺序满足 *后入先出* 的原则。

像下面的例子，将输出”3210“：

```go
func b () {
  for i := 0; i < 4; i++ {
    defer fmt.Print(i)
  }
}
```



> 3. Deferred functions may read and assign to the returning function’s named return values.

defer函数能够读取并对函数的命名返回值赋值

看下面这个例子，其结果是”main 2"

```go
func inc() (i int) {
	defer func() {
		i++
	}()
	return 1
}

func main() {
	fmt.Println("main", inc())
}
```



## 附录：

Defer,Panic,and Recover：https://go.dev/blog/defer-panic-and-recover

