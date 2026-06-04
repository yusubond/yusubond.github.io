---
title: '《Go 细节和小技巧100》阅读记录'
date: '2023-07-07'
tags: ['golang', 'Go笔记']
draft: false
authors: ['default']
layout: PostLayout
---

最近读了老貘的[《Go细节和小技巧101》](https://gfw.go101.org/details-and-tips/101.html),很有收获，里面讲到很多实用的小技巧，记录于此。

## 1. for-range aContiner实际上迭代aContainer的一个副本

如下一段小程序，请问输出是 123，还是189？

```go
package main

func main() {
	var a = [...]int{1, 2, 3}
	for i, n := range a {
		if i == 0 {
			a[1], a[2] = 8, 9
		}
		print(n)
	}
}
```

结果输出是 123。

**这是因为 for-range 遍历的时候，实际上遍历的是只是容器的一个副本**。

就像上面的例子，a 是数组，range 遍历的时候，会将数组 a 拷贝一份，你改变了数组 a 本身，但并没有其副本。



由此可知，如果被遍历的容器是一个大数组，那么复制的成本就会很高。

但有一个例外：如果 for-range 中的第二个迭代变量被省略或忽略，那么被迭代的容器将不会被复制，因为没有必要。

在 Go 中，我们知道：一个数组拥有元素，但一个切片只是引用这元素。

在 Go 中，值的复制都是浅拷贝，复制一个值不会复制它所引用的值。

那么，请看这段代码，输出是123，还是189？

```go
package main

func main() {
	var s = []int{1, 2, 3}
	for i, n := range s {
		if i == 0 {
			s[1], s[2] = 8, 9
		}
		print(n)
	}
}
```

答案是 189。

这是因为 s 是一个切片。复制一个切片的时候不会复制切片所引用的元素，当引用着的元素发生变化时，输出的内容自然会变化。



## 2.迭代map

在迭代一个 map 的过程中，放入此 map 的条目可能会在当前迭代过程中显示出来，也可能会被跳过。



例如，下面这段代码的运行输出是不固定的：

```go
package main

func main() {
	var m = map[int]bool{0: true, 1: true}
	for k, v := range m {
		m[len(m)] = true
		println(k, v)
	}
}
```

一些可能得输出：

```go
$ go run subond.go
0 true
1 true
$ go run subond.go
1 true
2 true
3 true
4 true
5 true
6 true
7 true
0 true
$ go run subond.go
0 true
1 true
2 true
```

原因是新元素插入的时候，并不确定插入到具体哪个bucket。当前 bucket 可能已经被遍历了，也可能没有。



## 3.一个延迟函数调用的实参和被其调用的函数均在注册此延迟函数调用时被估值

在函数的退出阶段，被注册的延迟函数将按照它们的注册顺序逆序依次被执行。

在执行这些延迟函数调用时，它们的实参和被它们调用的函数值将不在被重新估值。



例如，下面的程序打印的是 1，而不是 2 或 3。

```go
package main

func main() {
	var f = func(x int) {
		println(x)
	}
	var n = 1
	defer f(n)    // 此时n=1已经被估值，并且放进defer中，就差执行了。
	f = func(x int) {
		println(3)
	}
	n = 2         // 此时改变n, 对 defer 不起作用
}
```



下面的程序运行中并不会产生恐慌。它打印出 123。

```go
package main

func main() {
	var f = func() {
		println(123)
	}
	defer f() // defer 注册时，f 为有意义的函数，非nil
	f = nil
}
```



下面的程序打印出 123，然后恐慌。

```go
package main

func main() {
	var f func() // nil
	defer f()
	println(123)
	f = func() {} // 对 f 进行函数实例化
}
```



## 4. 方法属主实参和其他普通实参一同被估值

当一个延迟方法调用被注册时，它的属主实参（和其他普通参数）将被估值。

在一个方法调用链 v.M1().M2() 中，方法调用 v.M1() 是 M2() 方法调用的属主参数，所以方法调用 v.M1() 将在延迟调用 defer v.M1().M2() 被注册时估值，即M1()被执行。



请看下面的程序，它打印出 132。

```go
package main

type T struct{}

func (t T) M(n int) T {
	println(n)
	return t
}

func main() {
	var t T
  defer t.M(1).M(2) // 注册时，M(1)已经被执行
	t.M(3)
}
```



知道这个事实，看下面的例子，会觉着很巧妙。

```go
import "sync"

type Counter struct {
	mu sync.Mutex
	n  int
}

func (c *Counter) Lock() *Counter {
	c.mu.Lock()
	return c
}

func (c *Counter) Unlock() *Counter {
	c.mu.Unlock()
	return c
}

func (c *Counter) Add(x int) {
	defer c.Lock().Unlock()
	c.n += x
}
```



## 5. 迭代变量在循环步之间是共享的

请看下面的代码，loop1 和 loop2 两个函数是不等同的。

在 loop1 中，变量 v 在三个循环步之间共享，而在 loop2 中，每个循环步声明一个新的变量 v。

```go
package main

func loop1(s []int) []*int {
	r := make([]*int, len(s))
	for i, v := range s {
		r[i] = &v
	}
	return r
}

func loop2(s []int) []*int {
	r := make([]*int, len(s))
	for i := range s {
		v := s[i]
		r[i] = &v
	}
	return r
}

func printAll(s []*int) {
	for i := range s {
		print(*s[i])
	}
	println()
}

func main() {
	var s1 = []int{1, 2, 3}
	printAll(loop1(s1))    // 333
	var s2 = []int{1, 2, 3}
	printAll(loop2(s2))    // 123
}
```

因为迭代变量在循环步中共享，所以 loop1 中，只有一个变量，就是 v，它的地址永远不变。经过三步循环后，它最终指向了最后一个元素 3。所以 loop1 的打印出 333。

而 loop2 中，每个循环步声明一个新的变量v，指向新的地址。所以 loop2 的打印为 123。



出于同样的原因，下面的代码第一个循环打印出 333，第二个循环打印出 123。

```go
package main

func main() {
	var s = []int{1, 2, 3}
  // 打印 333
	for _, v := range s {
		defer func() {
			print(v)
		}()
	}
  // 打印 321
	for _, v := range s {
		x := v
		defer func() {
			print(x)
		}()
	}
}
```

整体的打印结果为 321333。因为后注册的延迟函数先被调用。



## 6. 著名的 `:=` 陷阱

我们看一个简单的程序。

```go
package main

import (
   "fmt"
   "strconv"
)

func parseInt(s string) (int, error) {
   n, err := strconv.Atoi(s)
   if err != nil {
      fmt.Println("err: ", err)
      b, err := strconv.ParseBool(s)
      if err != nil {
         return 0, err
      }
      fmt.Println("err: ", err)
      if b {
         n = 123
      }
   }
   return n, err
}

func main() {
   fmt.Println(parseInt("true"))
}
```

我们知道函数调用 strconv.Atoi(s) 将返回一个非 nil 的错误，但函数调用 strconv.ParseBool(s) 将返回一个 nil 的错误。

那么，调用 parseInt("true") 是否也返回一个 nil 的错误？答案是它将返回一个非 nil 的错误。

下面是程序的输出：

```sh
err:  strconv.Atoi: parsing "true": invalid syntax
err:  <nil>
123 strconv.Atoi: parsing "true": invalid syntax
```

等等，在 parseInt("true") 返回之前，err 变量不是在内部代码块中被再声明(re- declared，即修改)，并且其值已经被修改为 nil 了吗?这是许多新的 Go 程序员，包括我在内，在刚刚开始使用 Go 语言时曾经遇到的困惑。

为什么函数调用 parseInt("true") 会返回一个非 nil 的错误?

**因为在内部代码块中声明的变量永远不会是外部代码块中声明的同名变量的再声明**。

这里，内部声明的 err 变量被初始化为 nil，这并不是对外部声明的 err 变量的修改。外层的 err 变量被设置(初始化)为一个非零值后就没有再被更改过。

**为了避免这种情况，请尽量不要在嵌套的代码中使用过多的同名变量，而是尽量在外部统一初始所需的变量，尤其是err变量**。



## 7. 在 fmt.Errorf 调用中使用`%w` 格式描述来构建错误链

当使用 fmt.Errorf 函数来包装一个更深的错误时，建议使用`%w`而不是 `%s` 格式描述，以避免丢失被包裹的错误信息。

例如，在下面的代码中，Bar 实现比 Foo 实现要好，因为调用者可以判断返回错误是否是有某个特定的错误（这里是 ErrNotImp）引发的。

```go
package main

import (
	"errors"
	"fmt"
)

var ErrNotImpl = errors.New("not implemented yet")

func doSomething() error {
	return ErrNotImpl
}

func Foo() error {
	if err := doSomething(); err != nil {
		return fmt.Errorf("Foo: %s", err)
	}
	return nil
}

func Bar() error {
	if err := doSomething(); err != nil {
		return fmt.Errorf("Bar: %w", err)
	}
	return nil
}

func main() {
	println(errors.Is(Foo(), ErrNotImpl))  // false
	println(errors.Is(Bar(), ErrNotImpl))  // true
}
```

在用户代码中，我们应该尝试使用 `errors.Is` 函数，而不是使用直接比较来判断错误的起因。



## 8. fmt.Println、fmt.Print 和 print 函数之间的细微差异

`fmt.Println`函数和（`println`）将在任何两个相邻的参数之间输出一个空格。`fmt.Print`函数只在两个相邻的参数都不是字符串才会这么做。`print` 函数永远不会在参数之间输出空格。

这可以通过下面的代码来证明。

```go
package main

import "fmt"

func main() {
	//123 789 abc xyz
	println(123, 789, "abc", "xyz")
	//123 789 abc xyz
	fmt.Println(123, 789, "abc", "xyz")
	//123 789abcxyz
	fmt.Print(123, 789, "abc", "xyz")
	println()
	//123789abcxyz
	print(123, 789, "abc", "xyz")
	println()
}
```



## 9. 不要将 strings 和 bytes 标准库包中的 TrimLeft 函数误用为 TrimPrefix

`TrimLeft` 函数的第二个参数是一个码点集，第一个参数中包含在此码点集中的任何起始 Unicode 码点将被剪除，这与 `TriimPrefix` 函数有很大的不同。

下面的程序显示了这两者的区别。

```go
package main

import "strings"

func main() {
	var hw = "DoDoDo!"
	println(strings.TrimLeft(hw, "Do"))   // !
	println(strings.TrimPrefix(hw, "Do")) // DoDo!
}
```

`TrimRight` 和 `TrimSuffix` 函数也类似。



## 10. `json.Unmarshal` 函数接收不区分大小写的键匹配

例如，下面的程序打印 bar，而不是 foo。

```go
package main

import (
	"encoding/json"
	"fmt"
)

type T struct {
	HTML string `json:"HTML"`
}

var s = `{"HTML": "foo", "html": "bar"}`

func main() {
	var t T
	if err := json.Unmarshal([]byte(s), &t); err != nil {
		fmt.Println(err)
		return
	}
	fmt.Println(t.HTML) // bar
}
```

`json.Unmarshal` 函数的文档中提到：preferring an exact match but also accepting a case-insensitive match（倾向于精确匹配，但也接收不区分大小写的匹配）。



## 11. 如何尝试尽早运行一个自定义的 init 函数？

假设项目的模块是`x.y/app`。添加一个`x.y/app/internal/init`包，并在`init`包中放置一个`init`函数。

然后在 `main` 包中引入此 `init` 包。

`init` 包将在一些核心包（比如 runtime 标准包）加载完成之后，但在其他包之前加载。



## 12. 在调用 os.Exit 函数后，已经注册的延迟函数调用将不会被执行

例如，下面代码中的延迟调用`cleamup()`完全没有意义。

```go
func run() {
  defer cleanup()
  if err := doSomething(); err != nil {
    log.Println(err)
    os.Exit(1)
  }
  os.Exit(0)
}
```

请注意，`log.Fetal` 函数调用了 `os.Exit` 函数。所以在调用 `log.Fetal` 函数后，已注册的延迟函数也不会被执行。

