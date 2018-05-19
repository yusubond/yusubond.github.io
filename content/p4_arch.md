Title: P4:转发平面的编程语言
Date: 2018-05-05
Category: Tech
Tags: Network, P4lang, L3, L2
Slug: p4_arch
Author: subond
Summary: P4是一种声明性语言，用来表示数据包如何通过网络转发单元的流水线(Pipeline)进行处理，基于抽象转发模型，该模型由解析器(Parser)和一系列匹配+动表(Match+Action Table)组成，分为入口(Ingress)和出口(Egress)两部分。Parser定义了每个传入数据包的包头格式，用于解析数据包。每个Match+Action表对包头字段进行查找和匹配，并在每个表内应用第一个匹配相对应的动作(Action)。

### 1.P4语言介绍

P4是一种 **声明性** 语言，用来表示数据包如何通过网络转发单元的流水线(Pipeline)进行处理，基于抽象转发模型，该模型由解析器(Parser)和一系列匹配+动表(Match+Action Table)组成，分为入口(Ingress)和出口(Egress)两部分。Parser定义了每个传入数据包的包头格式，用于解析数据包。每个Match+Action表对包头字段进行查找和匹配，并在每个表内应用第一个匹配相对应的动作(Action)。如下图所示：

![p4_abstract_forwarding_model](http://on64c9tla.bkt.clouddn.com/subond/p4_1.png)

P4语言本身是协议独立的编程语言，它支持对多种转发平面协议的表达，P4程序为每个转发单元指定以下内容：

  * Header，定义每个数据包包头的格式，包括字段及其大小
  * Parser Graph，定义数据报包包头的解析顺序
  * Table，定义查找类型，匹配字段，应用动作以及表的大小等
  * Action，定义简单动作和复合动作
  * Pipeline and Control Flow，定义流水线中表格的布局以及流水线中数据包的流向

P4通过寻址转发元素的配置，一旦配置完成，就可以利用Table对数据包(Packet)进行处理。

### 2.转发模型的介绍

* 对于每个数据包，Parser都会生成一个Parsed Representation，用于Match + Action表的匹配字段。  
* Ingress中的Macthc + Action表将生成一个出口规范，来确定数据包发送到的端口集合以及每个端口的数据包实例数量等。  
* 队列机制处理此Egress规范，生成数据包的必要实例并将每个实例提交给出口管道。  
* 数据包实例的物理目的地址在进入出口管道之前确定。一旦它在Egress Pipeline中，假定这个目的地不会改变（尽管该分组可能被丢弃或者它的头被进一步修改）。  
* Egress Pipeline完成处理后，数据包实例的包头由Parsed Representation(由Match + Action Table修改)形成，并传输结果数据包。

### 3.P4语言的基本组件

P4语言支持以下声明和定义：首部(Headers)、解析器(Parsers)、表(Tables)、动作(Action)、流控制程序(Control Flow)。

#### 3.1 首部 **Header**

首部类型是由成员字段组成的有序列表，每个字段都有其名称和长度，每一种首部类型都有对应的首部实例来存储具体的数据。首部分为两种，一种是包头（Packet Headers），另一种是元数据（Metadata）。

对于匹配，动作和控制流来说，我们需要引用包头及其字段，而包头正是通过数据包实例来引用。

例如，定义一个ipv4的包头。

```go
header_type ipv4_t {
    fields {
        version : 4;
        ihl : 4;
        typeofserv : 8;
        totalLen : 16;
        identification : 16;
        flags : 3;
        fragOffset : 13;
        ttl : 8;
        protocol : 8;
        hdrChecksum : 16;
        srcAddr : 32;
        dstAddr : 32;
    }
}
```

#### 3.2 解析 **Parser**

Parser可以建模成一种状态机，并根据解析到的有效字节来决定包的处理。它采用状态迁移的方式来表示，如下图所示。

其实就是不断剥离数据包的包头，并判断内部数据是哪一种协议类型，然后进行解析。

一个解析方法/状态可以以下四种方式结束：

    1）return 一个流控制程序名

    2）return一个解析器名

    3）发生显式错误

    4）发生隐式错误

P4语言中流控制程序和解析器的命名空间是共用的，所以在定义解析器和流控制程序的时候需要注意不能重名，否则会导致P4程序错误。

![parser_graph](http://on64c9tla.bkt.clouddn.com/subond/p4_2.png)

例如：定义一个二层数据包的解析。

```go
parser ethernet {
    extract(ethernet);   // Start with the ethernet header
    return select(latest.ethertype) {
        0x8100:     vlan;
        0x0800:     ipv4;
        default:    ingress;
    }
}

parser vlan {
    extract(vlan);
    return select(latest.ethertype) {
        0xaaaa:     mtag;
        0x0800:     ipv4;
        default:    ingress;
    }
}

parser mtag {
    extract(mtag);
    return select(latest.ethertype) {
        0x800:      ipv4;
        default:    ingress;
    }
}
```

#### 3.3 逆解析 **Deparser**

在Egress流水线，转发元素将由解析表示转变成可用于传输的串行字节流，这个过程称为Deparsing(逆解析)。P4语言规定 **任何在出口处应该生成的格式都应该由在入口处使用的解析器来表示**。因此，P4程序中表示的解析图用于确定用于从Parsed Representation生成序列化数据包的算法。Deparing需要注意以下几点：

  * 只有有效的包头格式才能进行逆解析。   
  * 如果解析图是循环的，那么可以生成原始排序（即，尊重解析图的排序的算术平均值），并用它来确定序列化标题的顺序。  
  * 一般来说，在对可选标头进行标签解压缩时，可以使用周期数来标记解析图。这些可以被视为解析图中的单个节点，并作为一个组进行序列化。  
  * 元数据字段不进行序列化，元数据字段一般在Ingress流水线中进行Match + Action表中复制到包头字段中。

#### 3.4 动作 **Action**

P4中动作被认为是功能，这些函数名在运行态时填充表格所应用的功能，分为复合动作和基本动作。

动作函数运行传输参数，这些参数所传递的值可以被编程为运行态(run-time)table实体的API。当一个table实体被匹配到的时候，这个参数的值就会传递给动作函数。P4的table声明可以被编译成运行态API。

例如，对于不确定的数据报，需要上报给cpu，可以定义一下动作。

```go
action copy_to_cpu(cpu_code, bad_pkt) {
  modify_field(local_metadata.copy_to_cpu, 1);
  modify_field(local_metadata.cpu_code, cpu_code);
  modify_field(local_metadata.bad_pkt, bad_pkt);
}
```

下面这张表格包含了一些基本动作和介绍。

![p4_primitive_actions](http://on64c9tla.bkt.clouddn.com/subond/p4_3.png)
![p4_primitive_actions](http://on64c9tla.bkt.clouddn.com/subond/p4_4.png)

#### 3.5 匹配动作表 **Match+Action Table**

Table是声明性结构，指定了匹配和动作，以及其他可能的属性。Table首先指定了用于匹配数据报的字段列表，字段匹配是对包头的引用，对应包头的相应字段。匹配语义上总是所有字段匹配的和，即AND。

例如，定义一个mTag的表，使用精准匹配(exact)。

```
table mTag_table {
    reads {
        ethernet.dst_addr   : exact;
        vlan.vid            : exact;
    }
    actions {
        add_mTag;
        copy_to_cpu;
        no_op;
    }
    max_size                 : 20000;
}
```

其他匹配类型还包括：

  * tenary 三重匹配。

    表中每个条目都提供了一个掩码。 在进行比较之前，该掩码与字段值进行与运算。 字段值和表项值只需要在条目掩码中设置的位相同。 由于重叠匹配的可能性，必须使用三元匹配将优先级与表中的每个条目相关联。

  * lpm 最长掩码匹配

    这是特殊情况下的匹配。由于在高位中的1和在低位中的0之间进行了划分，所以参数的掩码选择可以被修改。该56个1位的数量给出用作条目优先级的前缀的长度。

  * valid 有效性匹配

    只适用于封装头字段和头部实例（非元数据字段）时，只检查是否有效，结果为true/false。

  * rang 范围匹配

    每个条目为条目指定一个低值和高值，只有在该范围内，该字段才匹配。 范围终点包括在内。

#### 3.6 包的处理与控制流

P4语言中匹配-动作表中规定需要匹配的字段和需要执行的操作，流控制程序则用来规定匹配-动作表的执行顺序。

数据包的处理由一系列的匹配动作表执行，在配置时，控制流程序来指定表的执行顺序。表的执行使用`apply`关键字，它有三种操作模式：

1. 顺序：控制无条件的移动到下一语句。  
2. 动作选择：包含了决定要执行的动作集合。  
3. Hit/Miss检查：是否找到匹配项确定要执行的指令块。

例如，Igress的控制流：

```go
control ingress {
    // Verify mTag state and port are consistent
    apply(check_mtag);
    apply(identify_port);
    apply(select_output_port);
}
```

#### 3.7 状态存储

计数器(counter)，仪表(meter)和寄存器(register)保持状态的时间超过一个数据包,被称为有状态存储。 它们需要目标资源，因此由编译器管理。

它们一般用来做QoS保障，通过计算数据报的数量来进行限速处理等操作。

例如，定义一个计数器。

```go
counter ip_pkts_by_dest {
    type : packets;
    direct : ip_host_table;
}
```

定义一个meter。

```
meter customer_meters {
    type : bytes;
    instance_count : 1000;
}
```

### 参考资料

[1].[Ipv4报文格式](http://www.023wg.com/message/message/cd_feature_ip_message_format.html)
[2].[p4.org](https://p4.org/)
[3].[p4-14](https://p4.org/p4-spec/p4-14/v1.0.4/tex/p4.pdf)
