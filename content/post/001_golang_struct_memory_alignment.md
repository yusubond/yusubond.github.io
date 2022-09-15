---
Title: "Go Struct内存对齐"
Date: 2022-09-07
Categories: ["Go高性能编程"]
Tags: ["go", "struct", "alignment"]
---



## Go Struct内存对齐

### 1 为什么需要考虑内存对齐

CPU访问内存时，并不是逐个字节访问，而是以字长来访问。字长是指在同一时间内处理二进制数的位数。32位系统的字长为32位，即4字节，64位系统的字长为64位，即8字节。

CPU以字长访问内存，可以减少访问次数，增加吞吐量。以32位系统为例，访问一个8字节的数据，一次读取4个字节，只需要访问2次。



### 2 如何计算结构体的内存空间

在Go中，可以使用`unsafe.Sizeof()`来计算一个数据类型实例所占用的内存大小。

```go
type Person struct {
	name    string
	age     int
	address string
}

func main() {
	var s1 int
	var str string
	var f1 float64
	var p Person
	fmt.Printf("int %d\n", unsafe.Sizeof(s1))             // int 8
	fmt.Printf("string %d\n", unsafe.Sizeof(str))					// string 16
	fmt.Printf("float64 %d\n", unsafe.Sizeof(f1))					// float64 8
	fmt.Printf("person struct %d\n", unsafe.Sizeof(p))    // person struct 40
}
```

运行上面的例子，将输出：

```sh
int 8
string 16
float64 8
person struct 40
```

以64位系统为例，Go语言中基本数据类型所占内存大小如下：

| 数据类型                         | 内存大小 |
| -------------------------------- | -------- |
| Int8, uint8, byte, bool          | 1        |
| int16, uint16                    | 2        |
| int32, uint32, float32,rune      | 4        |
| int, uint,int64, uint64, float64 | 8        |
| string                           | 16       |



### 3 struct如何内存对齐

#### 3.1 合理的布局减少内存占用

假设一个结构体只包含3个字段，分别是string, int16, int32，成员顺序对内存占用的影响。

```go
type (
	s1 struct {
		a string
		b int16
		c int32
	}
	s2 struct {
		b int16
		a string
		c int32
	}
)

func main() {
	var p1 s1
	var p2 s2
	fmt.Printf("s1 %d\n", unsafe.Sizeof(p1))  // s1 24
	fmt.Printf("s3 %d\n", unsafe.Sizeof(p2))  // s2 32
}
```

**每个字段按照自身的对齐倍数来确定在内存中的偏移量，所以字段排列顺序不同，上一个字段因偏移而浪费的大小也不同。**

先看s1：

- a是第一个字段，默认对齐，占用16个字节；
- b是第二个字段，对齐倍数为2，因为当前内存已经是对齐的，只接占用2个字节；
- c是第三个字段，对齐倍数为4，必须空出2个字节，才能对齐4字节；

16 + 2 + 2（被浪费的） + 4 = 24

因此，s1共占用24个字节。

再看s2：

- b是第一个字段，默认对齐，占用2个字节；
- a是第二个字段，对齐倍数为16，必须空出6个字节，才能对齐，直接占用16个字节
- c是第三个字段，对齐倍数为4，因为当前内存已经是对齐的，直接占用4个字节，后4个字节造成浪费

2+6（被浪费的）+16+4+4（被浪费的） = 32

因此，s2共占用32个字节。

**技巧**：通常将字段内存大小按照从大到小的顺序来排列，可以保证整个结构体所占内存最小。

#### 3.2 空struct{}的处理

空`struct{}`大小为0，不占用内存。但是当空`struct{}`作为其他结构体的最后一个字段时，需要内存对齐。如果有指针指向该字段，返回的地址将在结构体外，那么当指针一直存活不释放时，就会造成内存泄漏，即该内存不随结构体的释放而释放。

举个例子：

```go
type (
	s3 struct {
		b int32
		a struct{}
	}
	s4 struct {
		a struct{}
		b int32
	}
)

func main() {
	var p3 s3
	var p4 s4
	fmt.Printf("s3 %d\n", unsafe.Sizeof(p3)) // s3 8
	fmt.Printf("s4 %d\n", unsafe.Sizeof(p4)) // s4 4
}
```

s3为8个字节，即空`struct{}`填充了4个字节；s4为4个字节，空`struct{}`不占用内存。
