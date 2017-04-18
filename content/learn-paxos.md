Title: 深入理解Paxos算法
Date: 2017-03-21
Category: Tech
Tags: Algorithm, Distributed Systems
Slug: learn-paxos-in-distributed-system
Author: subond
Summary: Paxos算法是Leslie Lanmport(2013年获图灵奖)在1990年提出的一种基于消息传递的共识算法(也称为，一致性算法)，由于算法难以理解并没有被ACM TOCS发表。直到1998年，才引起人们的注意，Lanmport重新发表文章。为了便于人们通俗地理解Paxos算法，Lanmport于2001年简化原来的文章，发表了[Paxos Made Simple](http://on64c9tla.bkt.clouddn.com/2017A/paxos-simple-Copy.pdf)，文章循序渐进地推导出了Paxos算法，并用数学归纳法进行了证明。在此基础上，本文结合Paxos Made Simple，与其他优秀的Paxos算法解读，重新描述Paxos协议，希望可以深入理解基本的Paxos算法理论。

## 1.Paxos算法

Paxos算法是Leslie Lanmport(2013年获图灵奖)在1990年提出的一种基于消息传递的共识算法(也称为，一致性算法)，由于算法难以理解并没有被ACM TOCS发表。直到1998年，才引起人们的注意，Lanmport重新发表文章。为了便于人们通俗地理解Paxos算法，Lanmport于2001年简化原来的文章，发表了[Paxos Made Simple](http://on64c9tla.bkt.clouddn.com/2017A/paxos-simple-Copy.pdf)，文章循序渐进地推导出了Paxos算法，并用数学归纳法进行了证明。在此基础上，本文结合Paxos Made Simple，与其他优秀的Paxos算法解读，重新描述Paxos协议，希望可以深入理解基本的Paxos算法理论。

Paxos算法解决的问题是一个分布式系统中如何就某个值(或协议)达成一致。在一个分布式系统中，如果各节点的初始状态一致，每个节点都执行相同的操作，那么他们最后的得到的也是一个一致的状态。一个分布式系统中，通常包含一个主节点和多个备节点。为了保证每个节点执行相同的操作指令，需要每一条执行执行一个“一致性算法”来选举出主节点，进而保证每个节点得到的指令一致。这是一个分布式系统中的重要问题。

## 2.基本概念

Paxos算法中有三种角色：*Proposer*, *Acceptor*, *Learner*。每个节点需要同时扮演 **两种或两种以上的角色**。

+ Proposal Value: 提议的值　　
+ Proposal Number: 提议编号，并且要求提议编号不能冲突　　
+ Proposal: 提议　=　提议编号 + 提议的值　　
+ Proposer: 提议发起者　　
+ Acceptors: 提议接受者　　
+ Learners: 提议学习者　　

需要说明的是，Proposer有两种行为，一个是向Acceptors发起Prepare请求，另一个是向Acceptors发起Accept请求。Acceptors则根据协议规则或(自身状态)对Proposers的请求做出应答。Learners根据Acceptors的状态，学习最终被确定的值。

## 3.两个原则

**1安全原则**

1. 只能(而且必须)允许一个值被选定；

2. 每个节点只能学习已经被选定的值；

**2存活原则**

只要多数节点存活，并且彼此可以通信，则会达成以下两件事：

1. 最终会选定某个提议的值　　
2. 一个被选定的值，其他节点最终会学习到这个值　　

## 4.算法过程

**第一阶段A**，即Prepare阶段

Proposer选择一个提议编号n，向所有的Acceptors发送(广播)Prepare(n)请求。

**第一阶段B**，即Prepare阶段

Acceptor接收到Prepare(n)请求后，若提议编号比之前接收的Prepare提议编号都要大，则做出如下承诺：即不会在接收比n小的提议，并携带之前Accept的提议中编号小于n的最大值的提议，否则不予理会。

**第二阶段A**，即Accept阶段

Proposer接收到多数Acceptors的承诺后，如果没有一个Acceptor接受过这个值，则向所有的Acceptors的发起自己的值和提议编号，否则从接受过的值中选择对应的提议编号最大的那个值，作为提议的值，提议编号仍为n。

**第二阶段B**，即Accept阶段

Acceptor接收到Accept请求后，如果该提议编号不违反自己的做过的承诺，则接受提议。

![paxos-protocolflow](http://on64c9tla.bkt.clouddn.com/2017A/paxos.png)

需要说明是，Proposer发出Prepare请求后，得到多数派的应答，然后再选择一个多数派广播Accept请求，而不一定是将Accept请求发给有应答的Acceptor。这样做的原因是，Prepare阶段得到只是Proposal number 和 Proposal value，而一个值最终是否被选定，还需要Accept阶段的验证。

当一个提议被多数接受后，这个提议的值就被选定choesn，一旦有一个值被选定，那么只有按协议的规则继续演进，后续被选定的值也是同一个值。这就是chosen的一致性问题。

## 5.算法证明

其实，Paxos算法是一个非常确定的数学问题，可以用数学语言表达，进而用严谨的数学逻辑进行证明。

**Paxso算法原命题**

如果一个提议{n0,v0}被多数Acceptors所接受，那么不存在提议{n1,v1}被多数Acceptors接受，其中n0 < n1,v1 != v0。

**Paxso算法原命题加强**

如果一个提议{n0,v0}被多数Acceptors所接受，那么不存在Acceptors接受提议{n1,v1}，其中n0 < n1, v1 != v0。

**Paxso算法原命题进一步加强**

如果一个提议{n0,v0}被多数Acceptors所接受，那么不存在Proposer发出提议{n1,v1}，其中n0 < n1, v1 != v0。

**归纳法证明**

假设，提议{m, v}(简称m)被多数派接受，那么提议m到n(n >= m)，对应的值也是v。对n进行归纳假设。

1. n = m时，显然结论成立。

2. 设n = k时，结论成立，即如果提议(m, v)被多数派接受，则提议m到k对应的值为v。

3. 当n = k + 1时，若提议k+1不存在，则结论成立。

接下来，证明提议提议k+1不存问题。

假设，提议k+1存在，对应的值为v1。因为提议m被多数派接受，又因为提议k+1的Prepare请求被承诺并返回结果。**两个多数派必有交集**，那么提议k+1的第一阶段B必有提议带回来，那么v1就是从返回的提议中选择出来的，设v1对应的提议编号为t。根据第二阶段B可知，t是返回的提议编号最大的一个，因此t>=m。又因为第一阶段A，t<n。根据假设,t对应的值也是v，即v1 = v。所以，n=k成立时，n=k+1也成立。

## 6.示例演示

为了便于理解，记(n,v)为提议编号为n,提议的值为v的提议，(m,(n,v))为承诺了Prepare(m)请求，并接受了提议(n,v)。

![simple-paxos](http://on64c9tla.bkt.clouddn.com/2017A/simple-paxos.png)

## 7.小结

通过前面的讨论和学习，我们可以回顾一下协议的细节：

1. 为什么要被大多数接受？因为两个多数派必有交集，所以一般是奇数个(2n+1)Acceptors，然后允许最多n个Acceptors宕机，而保证算法仍然可以正常运行，最终得到一个确定的chosen值。

2. 为什么需要做一个承诺？首先，可以保证第二阶段A的Proposer的选择不受未来某个值的影响(因为对方已经给出了承诺)；其次，对于每一个Acceptors而言，承诺决定了它回应提议编号较大的Prepare请求，和接受提议编号较小的Accept请求的先后顺序。

3. 为什么第二阶段A要从返回的提议编号中选取最大的一个？这样选出来的提议编号一定不小于已经被多数派接受的提议编号，进而可以保证该提议编号对应的那个值是chosen的那个值。

**"与其预测未来，不如限制未来"**,应该是Paxos协议的核心思想。——郑建军(微信工程师)

**参考资料**

Leslie Lanmport:[Paxos Made Simple](http://on64c9tla.bkt.clouddn.com/2017A/paxos-simple-Copy.pdf)

Info架构师2017年1月刊:[微信PaxsoStore:深入浅出Paxos算法协议](http://www.infoq.com/cn/minibooks/architect-201701)

[一步一步理解Paxos算法](http://www.cnblogs.com/zhengran/p/4212502.html)
