---
Title: "Go Slice性能与技巧"
Date: 2022-09-13
Categories: ["Go高性能编程"]
Tags: ["go", "slice"]
---

## Go Slice性能与技巧

`slice`是Go语言中一个重要的数据类型，而且很好用，但是也有一些坑，需要我们对`slice`有深入的理解。

`slice`跟数组`array`很类似，可以使用下标进行访问，如果越界则会产生panic。但是两者却有很大的区别，一个数组中的所有元素都存放在此数组的直接部分，而一个切片的所有元素存放在此切片的间接部分。

### 1、切片到底是个啥

为了更好地理解切片类型和和切片值，我们需要对切片内部结构有一个基本的认识。在Go语言中，切片类型的内部定义大致如下：

```go
// runtime/slice.go
type slice struct {
  array unsafe.Pointer  // 引用着底层存储在间接部分上的元素
  len   int             // 长度
  cap   int             // 容量
}
```

通过定义我们可以看到`slice`有三个属性，分别：

- 指针：指向底层数据
- 长度：表示此切片当前元素的个数
- 容量：表示此切片的容量，即底层数组可容纳的元素个数，容量>=长度

**注意**：底层数组`array`可以被多个`slice`引用，所以对一个`slice`的元素进行操作，可能会影响到其他slice。

举个例子

```go
func main() {
	a := []int{1, 2, 3, 4, 5, 6, 7}
	s1 := a[:4]
	s2 := a[1:2]
	fmt.Printf("a %d\n", a)    // [1,2,3,4,5,6,7]
	fmt.Printf("s1 %d\n", s1)  // [1,2,3,4]
	fmt.Printf("s2 %d\n", s2)  // [2]
	s2 = append(s2, 50)        // 对切片2进行追加操作
	fmt.Printf("a %d\n", a)    // [1,2,50,4,5,6,7]
	fmt.Printf("s1 %d\n", s1)  // [1,2,50,4]
	fmt.Printf("s2 %d\n", s2)  // [2, 50]
}
```

从最终的输出结果我们可以看到切片`a[2]`和切片`s1[2]`都变成了50，这是因为切片`s1`，`s2`以及`a`共享底层数据，所以对`s2`进行追加操作，影响了底层数组a[2]位置上的元素，导致`a[2]`, `s1[2]`都变成了50。

据此我们可以知道：

1）slice 的底层数据就是数组，slice是对数组的封装，描述一个数组的片段

2）slice 和 array 都可以通过下标访问

3）slice 更加灵活，可以动态扩容



### 2、切片的创建

通常创建`slice`有下面几种方式：

1. 直接声明

```go
var s []int
```

2. 通过make内置函数，函数定义如下

```go
func make([]T, len, cap) []T
```

第一个参数是`[]T`，`T`表示元素类型，第二个参数是长度len，即初始化的切片拥有多少个元素，第三个参数是容量cap，容量是可选参数，默认等于长度，即指定切片的容量。

深入研究可以发现，其实`make`函数创建了一个无名数组，并返回了它的一个切片，而且该数组只能通过这个切片来访问。

容量是当前切片已经预分配的内存能够容纳的元素个数，如果不断向切片中增加元素，超过了当前切片的容量，就需要分配新的内存，将当前切片所有的元素拷贝到新的内存上，这就是扩容。

```go
// 创建[]int切片，指定长度为0, 容量为1024
s := make([]int, 0, 1024)
```

3. 字面量

```go
s := []int{1,2,3,4}
```

4. 从切片或者数组中截取

```go
s = a[:len(a)]
```



### 3、切片的操作

#### 3.1 Copy

```go
b := make([]T, len(a))
copy(b, a)  // 将a中所有元素拷贝到b中
```

当然也可以使用下面的方式

```go
b = append([]T(nil), a...)
b = append(a[:0:0], a...)
```



#### 3.2 Append

`append`是内置函数，用于向切片中追加元素，其函数原型为：

```go
func append(slice []Type, elems ...Type) []Type
```

可以看到`append`函数的参数是可变的，也就是说允许追加多个值到切片中，也可以使用`...`传入切片，追加一个切片到目标切片。

```go
b = append(b, s1, s2)
b = append(b, s3...)
```

`append`有两个场景：

- 当append之后的长度小于等于容量时，直接利用此此切片原有的底层数组
- 当append之后的长度大于容量时，则会分配更大的内存来存储新的底层数组

**需要知道的是**：`append`函数的返回值是一个新的切片，Go 编译器不允许调用了`append`函数后不使用返回值。



#### 3.3 Delete

```go
a = append(a[:i], a[i+1:])   // 删除下标i上的元素
// or
a = a[:i+copy(a[i:], a[i+1:])]
```

如果不关心切片中原有元素的顺序，也可以这样的删除：

```go
a[i] = a[len(a)-1]
a = a[:len(a)-1]
```

**注意**：如果切片的元素类型是指针或带有指针的结构体，那么将需要垃圾回收，上面的Delete方式会产生内存泄漏，因为部分元素依旧被a引用着，不能够得到释放。下面的代码可以解决这个问题。

```go
copy(a[i:], a[i+1:])
a[len(a)-1] = nil // zero of T
a = a[:len(a)-1]
```

如果不关心切片中原有元素的顺序，也可以这样的删除：

```go
a[i] = a[len(a)-1]
a[len(a)-1] = nil // zero of T
a = a[:len(a)-1]
```



#### 3.4 Expand

在位置`i`插入`n`个元素：

```go
a = append(a[:i], append(make([]T, n), a[i:]...)...)
```

在尾部插入`n`个元素：

```go
a = append(a, make([]T, n)...)
```

为了避免因插入`n`个元素导致内存重新分配，可以提前校验并扩容：

```go
if cap(a) - len(a) < n {
  a = append(make([]T, 0, len(a)+n), a...)
}
```



#### 3.5 Insert

方式1：

```go
a = append(a[i:], append([]T{x}, a[i:]...)...)
```

注意，以上的插入方式，第二个`append`实际上创建了一个新的切片，并且拥有自己的底层存储空间，并将`a[i:]`元素拷贝到次切片；然后再通过第一个`append`将新切片的元素拷贝到原来`a`切片的后面。

这种插入方式会产生很多内存垃圾，因为第二个`append`创建的切片值使用了一次，再没有任何对象引用的时候需要GC回收。

但是，下面的方式2能够很好地避免这种情况

方式2：

```
s = append(s, 0) // use the zero value of the element type
copy(s[i+1:], s[i:])
s[i] = x
```

方式2先在后面追加一个零值元素，然后将`a[i:]`元素拷贝到位置`a[i+1]`，空出`a[i]`位置，最后对`a[i]`赋值完成插入操作。

此方式没有产生内存垃圾，**更值得推荐**

#### 3.6 Filter, in place

```go
j := 0
for i, v := range a {
  if keep(v) {
    a[j] = v
    j++
  }
}
a = a[:j]
```

#### 3.7 Push

```go
a = append(a, x)
```

push front

```go
a = append([]T{x}, a...)
```



#### 3.8 Pop

```go
x := a[len(a)-1]
a = a[:len(a)-1]
```

pop front

```go
x := a[0]
a = a[1:]
```



### 4 性能陷阱

### 4.1 部分场景中大量内存得不到释放

在已有的切片上进行切片操作，如果没有超过切片的容量，那么其底层数组就不会发生变化，内存一直占用着。所以很可能出现这样一种情况：原切片有大量的元素，但某个时刻我们在原切片的基础上进行切片，只是用很小的一段，但底层数组在内存中依然占据着很大的内存，得不到释放，从而造成内存浪费。

这种情况下我们可以使用`copy`替代`re-slice`确保不再需要的数据能够及时得到释放。

下面我们验证下这个情况：

我们需要两个函数分别以`copy`和`re-slice`方式取得原切片的最后两个元素；还需要一个随机生产函数，能够产生指定大小的切片；最后通过runtime内置的`ReadMemStats`获取当前系统运行时所使用的内存大小。

```go
func lastNumsBySlice(origin []int) []int {
	return origin[len(origin)-2:]
}

func lastNumsByCopy(origin []int) []int {
	result := make([]int, 2)
	copy(result, origin[len(origin)-2:])
	return result
}

func randomSlice(n int) []int {
	rand.Seed(time.Now().UnixNano())
	nums := make([]int, 0, n)
	for i := 0; i < n; i++ {
		nums = append(nums, rand.Int())
	}
	return nums
}

func printMem(t *testing.T) {
	t.Helper()
	var rtm runtime.MemStats
	runtime.ReadMemStats(&rtm)
	t.Logf("%.2f MB", float64(rtm.Alloc)/1024/1024)
}
```

最后我们还需要两个测试函数：

```go
func testLastNums(t *testing.T, f func([]int) []int) {
	t.Helper()
	ans := make([][]int, 0)
	for k := 0; k < 100; k++ {
		origin := generateWithCap(128 * 1024)
		ans = append(ans, f(origin))
	}
	printMem(t)
	_ = ans
}

func TestLast2NumsBySlice(t *testing.T) {
	testLastNums(t, lastNumsBySlice)
}

func TestLast2NumsByCopy(t *testing.T)  {
	testLastNums(t, lastNumsByCopy)
}
```

运行结果如下：

```go
=== RUN   TestLast2NumsBySlice
    subond_test.go:20: 100.19 MB
--- PASS: TestLast2NumsBySlice (0.24s)
=== RUN   TestLast2NumsByCopy
    subond_test.go:24: 3.19 MB
--- PASS: TestLast2NumsByCopy (0.22s)
```

通过结果可以看到两者的差异还是挺大的。虽然切片只使用最后两个元素，但是`re-slice`的方式获得的新切片被保存在`ans`中，导致原切片中的元素一直被引用着，无法被释放，因此占用了很多内存；而`copy`方式得到的新切片拥有自己的底层数组，且只包含2个元素，当原切片不在被引用后，内存能够被及时GC。



如果我们在循环中，显式地调用`runtime.GC()`，效果更加明显。

```go 
func testLastNums(t *testing.T, f func([]int) []int) {
	t.Helper()
	ans := make([][]int, 0)
	for k := 0; k < 100; k++ {
		origin := generateWithCap(128 * 1024)
		ans = append(ans, f(origin))
    runtime.GC()
	}
	printMem(t)
	_ = ans
}
```

运行结果如下：

```go
=== RUN   TestLast2NumsBySlice
    subond_test.go:21: 100.19 MB
--- PASS: TestLast2NumsBySlice (0.26s)
=== RUN   TestLast2NumsByCopy
    subond_test.go:25: 0.19 MB
--- PASS: TestLast2NumsByCopy (0.22s)
```



### 附：推荐与参考

- https://geektutu.com/post/hpg-slice.html
- https://github.com/golang/go/wiki/SliceTricks
- https://qcrao.com/post/dive-into-go-slice/