Title: 机器学习之Weka学习-Evaluation类介绍
Date: 2016-07-03
Category: Tech
Tags: MachineLearning, AI
Slug: machinelearning-about-weka-evaluation
Author: subond
Summary: Evaluation类顾名思义，用来评价各种分类器（包括机器学习模型）的性能。Weka中有两个Evaluation类，分别位于weka.classifiers.evaluation.Evaluation和weka.classifiers.Evaluation 而且这两个类定义了同样的接口，其中evaluation包下的Evaluation类就是把所有的操作交给classifier包下的Evalution类来完成，也许为了能够适配旧版本已经编写的代码，就保留了classifier包下的 Evalution类，我们暂且不需要即可。下面我们就介绍weka.classifier.Evaluation类。

## 1.Evalution类介绍

Evaluation类顾名思义，用来评价各种分类器（包括机器学习模型）的性能。Weka中有两个Evaluation类，分别位于weka.classifiers.evaluation.Evaluation和weka.classifiers.Evaluation 而且这两个类定义了同样的接口，其中evaluation包下的Evaluation类就是把所有的操作交给classifier包下的Evalution类来完成，也许为了能够适配旧版本已经编写的代码，就保留了classifier包下的 Evalution类，我们暂且不需要即可。下面我们就介绍weka.classifier.Evaluation类。

```
public class　Evaluation
extends java.lang.Object
implemensts java.io.Serializable, Summarizable, RevisionHandler
```

## 2.构造函数

Evaluation类没有无参的构造函数，一般用Instances对象作为构造函数的参数。例如：

```
Evaluation eval = new Evaluation(data)
```

data是训练集的数据，用来获取一些信息，并不用来评价分类器。

![evaluation-weka](http://on64c9tla.bkt.clouddn.com/2016C/Evaluation.jpg)

## 3.主要成员变量

+ evaluationModel(Classifier classifier, Instances data)

如果训练集和测试集是分开的，可以使用evaluationModel方法，方法中的参数为：第一个参数是训练过的分类器，第二个参数是测试集的数据。

+ crossValidationModel()

crossValidationModel方法的四个参数为：第一个参数是分类器，第二个参数是测试集的数据，第三个参数是交叉检验的次数（比较常见的是10），第四个参数是一个随机数对象。

## 4.应用示例

下面这个小程序用同一数据测试了两类方法的评价结果，源码地址如下[Demo](https://github.com/yusubond/Machine-Learning/blob/master/Evaluation/Demo_evaluation.java)

结果如下：

![result-evaluationModel](http://on64c9tla.bkt.clouddn.com/2016C/evaluationModel.jpg)

![result-crossvalidateModel](http://on64c9tla.bkt.clouddn.com/2016C/crossvalidateModel.jpg)

**参考资料**

官网资料：[Instances类](http://10.103.14.28/weka-3-8-0/doc/)  
Weka开发[3]-Evaluation类：[http://quweiprotoss.blog.163.com/blog/static/408828832008103042734622/](http://quweiprotoss.blog.163.com/blog/static/408828832008103042734622/)
