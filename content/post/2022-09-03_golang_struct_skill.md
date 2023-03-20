---
Title: "Go 空struct的使用技巧"
Date: 2022-09-13
Categories: ["技术","Go高性能编程"]
Tags: ["go", "struct"]
---

## 1、空struct{}不占用内存空间

Go语言中，使用`unsafe.Sizeof()`可以计算一个数据类型实例所占用的字节数。

```go
package main

import (
	"fmt"
	"unsafe"
)

func main() {
	fmt.Printf("struct{} %d\n", unsafe.Sizeof(struct {}{})) // struct{} 0
}
```

通过上面的结果可以看到，Go中空结构体`struct{}`是不占用内存空间。

因为空结构体不占用内存空间，所以在各种场景下被广泛使用，一是能够节省内存，二是空结构体本身没有任何实际意义，也不需要任何值，仅作为占位符，能够达到代码即注释的效果。



## 2、实现集合

Go语言中没有标准的Set的实现，一般用map来替代。因为对于集合来说，只需要`map`的key，而不需要值，所以将值设置为空结构体，能够节省内存。

以下是一个简单的Set实现，仅做参考：

```go
type Set map[string]struct{}

func (s Set) Add(k string) {
	s[k] = struct{}{}
}

func (s Set) Delete(k string) {
	if _, ok := s[k]; ok {
		delete(s, k)
	}
}

func (s Set) Has(k string) bool {
	_, ok := s[k]
	return ok
}
```



## 3、作为信号量

有时候我们需要通知子协程执行任务或者结束任务，仅作为信号量在`channel`中传递。因为不需要在`changnel`中传递任何数据，所以`struct{}`作为信号量就非常合适。

举个例子，主协程main通知任务协程task开始工作。

```go
package main

import (
	"fmt"
)

func doTask(ch chan struct{}) {
	<-ch
	fmt.Printf("start do task\n")
}

func main() {
	sig := make(chan struct{})
	go doTask(sig)
	
	sig <- struct{}{}
	
	close(sig)
}
```



## 4、仅包含方法的结构体

有些场景下，我们只需要实现某些方法，而不需要任何字段。那这种情况下用空结构体`struct{}`作为方法的接受者很合适。

举个例子：

```go
type foo struct{}

func (f *foo) Do() {
	// do some thing
}
```



