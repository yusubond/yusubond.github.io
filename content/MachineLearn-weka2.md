Title: 机器学习之Weka学习-Instances类介绍
Date: 2016-06-29
Category: TECH
Tags: MachineLearning, AI
Slug: machinelearning-about-weka-instances
Author: subond
Summary: Instances类是Weka中进行数据操作的对象，即需将所要处理的数据先存入并转化为Instances类的对象，然后进行其他操作。也就是说Instances类是继承AbstractList类而来，并实了Serializable,RevisionHandler接口。

## 1.Intances类介绍

Instances类是Weka中进行数据操作的对象，即需将所要处理的数据先存入并转化为Instances类的对象，然后进行其他操作。

```
public class Instances
extends java.util.AbstractList<Instace>
implemensts java.io.Serializable, RevisionHandler
```

也就是说Instances类是继承AbstractList类而来，并实现了Serializable,RevisionHandler接口。

## 2.构造函数

![weka-instances](http://on64c9tla.bkt.clouddn.com/2016B/20160629instances-gouzao.jpg)

其构造函数可以实现实例的完整或部分拷贝，也可以创建新的实例，值得注意的是，其读入的数据格式为arff。关于arff的数据格式后续会有介绍。

**主要成员变量**

+ numAttributes():返回属性总量

+ setClassIndex(int):设置用于分类的属性

+ instance(int):返回具体的实例

+ firstInstance():返回第一个实例

## 3.应用实例

1.导入数据，设置分类属性，输出实例

```
import java.lang.String;
import weka.core.converters.ConverterUtils.DataSource;

DataSource source = new DataSource("filename");
Instances ins = source.getDataSet();

System.out.println(ins)
```
2.示例程序 程序源码地址：[Instances小实例](https://github.com/yusubond/Machine-Learning/blob/master/Instances/Demo_Instances.java)

```java
package weka01;

import java.lang.String;
import weka.core.converters.ConverterUtils.DataSource;
import weka.core.Instances;

public class Demo_Instances {
	public void testInstances()
	{
		try{
			DataSource source = new DataSource("/home/subond/subond/weka-3-8-0/data/weather.numeric.arff");
			Instances ins = source.getDataSet();

			ins.setClassIndex(ins.numAttributes()-1);

			//System.out.println(ins);
			System.out.println("the number of attributes:" + ins.numAttributes());
			System.out.println("the number of instances:" + ins.numInstances());
			System.out.println("the first instance:" + ins.firstInstance());
			System.out.println("the 3rd instance:" + ins.instance(3));
			System.out.println("the last instances:" + ins.lastInstance());
			System.out.println("the name of relation:" + ins.relationName());
			//将第一个实例加入到总实例的最后
			ins.add(ins.firstInstance());
			System.out.println(ins);



		}catch(Exception e){
			e.printStackTrace();
		}
	}
	public static void main(String[] args)
	{
		Demo_Instances testIns = new Demo_Instances();
		testIns.testInstances();
	}

}
```

**参考资料**

官网资料：[Intances类](http://10.103.14.28/weka-3-8-0/doc/)
