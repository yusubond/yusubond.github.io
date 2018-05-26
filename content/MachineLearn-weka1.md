Title: 机器学习之Weka学习-简单分类器
Date: 2016-06-28
Category: TECH
Tags: MachineLearning, AI
Slug: machinelearning-about-weka-classifier
Author: subond
Summary: Weka的全名是怀卡托智能分析环境（Waikato Environment for Knowledge Analysis），是一款免费的，非商业化的，基于JAVA环境下开源的机器学习（machine learning）以及数据挖掘（data mining）工具。 它和它的源代码可在其[官方网站](http://www.cs.waikato.ac.nz/ml/weka/)下载。
WEKA作为一个公开的数据挖掘工作平台，集合了大量能承担数据挖掘任务的机器学习算法，包括对数据进行预处理， 分类，回归、聚类、关联规则以及在新的交互式界面上的可视化。

## 1.Weka介绍

Weka的全名是怀卡托智能分析环境（Waikato Environment for Knowledge Analysis），是一款免费的，非商业化的，基于JAVA环境下开源的机器学习（machine learning）以及数据挖掘（data mining）工具。 它和它的源代码可在其[官方网站](http://www.cs.waikato.ac.nz/ml/weka/)下载。
WEKA作为一个公开的数据挖掘工作平台，集合了大量能承担数据挖掘任务的机器学习算法，包括对数据进行预处理， 分类，回归、聚类、关联规则以及在新的交互式界面上的可视化。

机器学习可以概括为“为使用正确的特征来构建正确的模型，以完成既定的任务”。任务，模型及特征是机器学习的三大”原料“。其工作流程一般如下：

1.学习问题，即由训练数据结合学习算法构建正确的模型  
2.构建特征，即将原始数据根据所需构建特征，形成模型所识别的数据格式  
3.完成任务，即借助正确的模型，对数据进行处理，得到输出。  

## 2.简单分类器实例

该分类器的数据处理过程如下：
1)读入训练数据  
2)初始化分类器  
3)使用训练数据训练分类器  
4)使用测试样本测试分类器的学习效果  
5)打印分类结果  

```java
package weka01;

import java.io.File;

import weka.classifiers.Classifier;
import weka.classifiers.Evaluation;
import weka.core.Instance;
import weka.core.Instances;
import weka.core.converters.ArffLoader;

public class SimpleCluster {

	public static void main(String[] args)
	{
		Instances ins = null;
		Classifier cfs = null;

		try{
      /*
      *读入训练数据
      */
      File file = new File("/home/subond/subond/weka-3-8-0/data/weather.numeric.arff");
			ArffLoader loader = new ArffLoader();
			loader.setFile(file);
			ins = loader.getDataSet();
      /*
      *设置数据集的分类类别，即指定哪一列作为类别
      *注意：本例中设置最后一列作为类别
      */
			ins.setClassIndex(ins.numAttributes()-1);

      /*
      *初始化分类器
      *具体使用哪一种特定的分类器可以在forName函数中指定
      */
			cfs = (Classifier)Class.forName("weka.classifiers.bayes.NaiveBayes").newInstance();
      /*
      *使用训练数据训练分类器
      */
			cfs.buildClassifier(ins);
      /*
      *使用测试样本测试分类器的学习效果
      *注意：本实例中，为了方便将训练数据和测试数据置为同一个
      */
			Instance testInst;
			Evaluation testingEvaluation = new Evaluation(ins);
			int length = ins.numInstances();
			for (int i=0;i < length; i++)
			{
        /*
        *将每个测试样本都用来测试分类器的效果
        */
				testInst = ins.instance(i);
				testingEvaluation.evaluateModelOnceAndRecordPrediction(cfs, testInst);
			}
      /*
      *输出结果
      */
			System.out.println("分类器的正确率：" + (1-testingEvaluation.errorRate()));
		}catch(Exception e){
			e.printStackTrace();
		}
	}

}
```
