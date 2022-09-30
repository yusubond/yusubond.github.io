---
Title: "Go字符串拼接性能对比"
Date: 2022-09-23
Categories: ["Go高性能编程"]
Tags: ["go", "string"]
---

## Go字符串拼接性能对比

Go 语言中提供了基础数据结构类型 `string`，在实际使用中我们经常遇到将字符串拼接的问题，即需要将多个字符串拼接在一起，形成新的字符串。那么 go 语言有哪些方式可以完成字符串拼接，以及它们的性能如何，我们一起研究下。



## 1. 操作符+

最简单的一种方式就是通过操作符`+`来完成拼接，例如下面这段小代码，字符串 `s3` 就是直接将s1和s2拼接在一起，其值等于`foobar`

```go
s1 := "foo"
s2 := "bar"
s3 := s1 + s2
```



### 2. 通过strings.join函数

`strings` 库中的`strings.join` 函数可以拼接多个字符串，并且还能指定字符串之间的分隔符。

```go
// "" 不指定分隔符
s3 := strings.join(s1, s2, "")
```



### 3. 通过strings.Builder

`strings.Builder` 有 `WriteString` 方法，可以直接写入，同时还有`Grow`方法，即预先申请内存大小空间

```go
s1 := "foo"
s2 := "bar"
var str strings.Builder
str.Grow(9)
_, _ = str.WriteString(s1)
_, _ = str.WriteString(s2)
_, _ = str.WriteString(s3
```



### 4. 通过bytes.Buffer

`bytes.Buffer` 有 `WriteString` 方法，可以直接写入：

```go
s1 := "foo"
s2 := "bar"
var buf bytes.Buffer
_, _ = buf.WriteString(s1)
_, _ = buf.WriteString(s2)
s3 := buf.String
```



### 5. 通过[]byte切片

像下面这段代码就是通过`[]byte`，将s1和s2拼接在一起，并存入s3。

```go
s1 := "foo"
s2 := "bar"
data := make([]byte, 0, 0)
data = append(data, s1...)
data = append(data, s2...)
s3 := string(data)
```



接下来，我们针对上面的几种方式写点基准测试，看下各自的性能。

```go
package string_join

import (
	"bytes"
	"strings"
	"testing"
)

var (
	s1 = "foo"
	s2 = "bar"
	s3 = "hello"
)

func BenchmarkStringJoinWithOperator(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = s1 + s2 + s3
	}
}

func BenchmarkStringJoinWithStringsJoin(b *testing.B) {
	for i := 0; i < b.N; i++ {
		_ = strings.Join([]string{s1, s2, s3}, "")
	}
}

func BenchmarkStringJoinWithStringsBuilder(b *testing.B) {
	for i := 0; i < b.N; i++ {
		var str strings.Builder
		_, _ = str.WriteString(s1)
		_, _ = str.WriteString(s2)
		_, _ = str.WriteString(s3)
		_ = str.String()
	}
}

func BenchmarkStringJoinWithStringsBuilderPreAlloc(b *testing.B) {
	for i := 0; i < b.N; i++ {
		var str strings.Builder
		str.Grow(11)
		_, _ = str.WriteString(s1)
		_, _ = str.WriteString(s2)
		_, _ = str.WriteString(s3)
		_ = str.String()
	}
}

func BenchmarkStringJoinWithBytesBuffer(b *testing.B) {
	for i := 0; i < b.N; i++ {
		var buf bytes.Buffer
		_, _ = buf.WriteString(s1)
		_, _ = buf.WriteString(s2)
		_, _ = buf.WriteString(s3)
		_ = buf.String()
	}
}

func BenchmarkStringJoinWithByteSlice(b *testing.B) {
	for i := 0; i < b.N; i++ {
		var bys []byte
		bys = append(bys, s1...)
		bys = append(bys, s2...)
		bys = append(bys, s3...)
		_ = string(bys)
	}
}

func BenchmarkStringJoinWithByteSlicePreAlloc(b *testing.B) {
	for i := 0; i < b.N; i++ {
		bys := make([]byte, 0, 11)
		bys = append(bys, s1...)
		bys = append(bys, s2...)
		_ = append(bys, s3...)
		_ = string(bys)
	}
}

```

运行基准测试，其结果如下：

```go
$ go test -bench .
goos: darwin
goarch: amd64
pkg: gopatterns/string_join
cpu: Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz
BenchmarkStringJoinWithOperator-12                  	58113481	        20.18 ns/op
BenchmarkStringJoinWithStringsJoin-12               	27686020	        65.90 ns/op
BenchmarkStringJoinWithStringsBuilder-12            	21337910	        49.25 ns/op
BenchmarkStringJoinWithStringsBuilderPreAlloc-12    	39148916	        28.72 ns/op
BenchmarkStringJoinWithBytesBuffer-12               	26477316	        42.35 ns/op
BenchmarkStringJoinWithByteSlice-12                 	23214884	        51.21 ns/op
BenchmarkStringJoinWithByteSlicePreAlloc-12         	100000000	        10.73 ns/op
PASS
ok  	gopatterns/string_join	11.076s
```

由此我们可以发现：

- 带有预分配的`byte`切片性能最好
- 其次是操作符+，仅次于byte切片，性能约为前者的一半
- `strings.join` 最差，其他几个都差不多



