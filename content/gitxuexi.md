Title: Git学习手记
Date: 2016-04-29
Category: Note
Tags: git, gitbook
Slug: git-xue-xi-shou-ji
Author: subond
Summary: Git版本控制功能很强大，作为程序猿必修掌握。

## 一、基础篇

### 指令介绍

```shell
git config --global user.name "username"   	#配置仓库参数，作为一个标志
git config --global user.email "useremail"	#配置仓库参数，作为一个标志
git init                      #把当前目录变成git可管理的仓库
git add files          #添加文件到暂存区
git diff file          #查看文件的修改内容
git commit -m "提交说明信息"   #提交文件到仓库
git status                    #获取当前仓库中文档的状态
git log                       #查看历史记录
git log -pretty=oneline       #单行显示历史信息
git reflog                    #显示版本号
git checkout -- file          #取出文件
git remote add origin <仓库地址>    #添加远程仓库地址
git push origin <分支名1>          #推送本地内容到远程仓库分支1
git pull origin <远程主机名> <远程分支名>:<本地分支名>
                                  #取回远程主机某个分支，并与本地指定分支合并
git clone <仓库地址>               #克隆远程仓库到本地仓库
git remote            #查看远程仓库信息
git remote -v         #查看远程仓库详细信息
```

### 版本回退

git reset --hard 版本号(即commit_id)

```shell
git reset --hard HEAD^      #回退至上一版本
git reset --hard HEAD^^     #回退至上上版本
git reset --hard HEAD~10    #回退至前10个版本
git reset --hard commit_id  #结合git reflog;git log使用
                            #git log可以查看提交历史，以便确定回退到哪个版本;
                            #git reflog可以查看命令历史，以便确定回到未来的哪个版本
```

### 分支操作

```shell
git branch                #查看分支
git checkout <分支名1>       #切换至分支名1
git checkout -b <分支名1>  #创建并切换至分支名1
git merge <分支名1>        #合并分支名1至当前分支
```

### 提交文件步骤

第一步：`git add file_name`,提交文件到暂存区(Index)

第二步：`git commit -m "message about file"`,提交文件到本地仓库(Repository)

第三步：`git push origin master`,提交文件到远程仓库master分支(Remote)

**注意：** 第一次推送至master分支，需要使用-u参数，即`git push -u origin master`。

![git-mechism](http://on64c9tla.bkt.clouddn.com/20160429gitcaozuo.jpg)

图1 Git基本操作示意图

几个名词解释：

Workspace:工作区  
Index：暂存区  
Repository：仓库区(本地仓库)  
Remote：远程仓库  

## 二、进阶篇

### 分支管理

一般而言，主分支master分支是非常稳定的版本，可以用来直接发布，一般情况下不允许直接在上面进行修改。一般都是新建一个dev分支，在dev分支上进行修改操作，工作完成后可合并到主分支master上。其流程一般如下：
1.创建一个dev分支；  
2.修改文件内容；  
3.添加到暂存区；  
4.切换至主分支(msater)；   
5.合并dev分支；  
6.查看历史记录。  

注意:合并分支时，git一般使用“Fast Forward”模式，在这种模式下，删除分支后，会丢掉分支信息。为了保证可以随时查看分支信息，合并时可使用命令git merge -no-ff -m "注释信息" dev


### Stach功能介绍

+ 使用场景

工作过程中，我们一般在自己的分支上修改和调试代码，如果临时接到通知需要修改某个BUG问题，而且自己的工作还需要一段时间才能完成， 而修复BUG问题可能只需要一点时间，此时我们就需要使stash功能。”git stash“通俗地讲就是把当前的工作现场”隐藏起来“，待现场回复后可继续 工作。具体来说就是先使用’git stash'将当前未提交到本地（或服务器）的代码推入git的栈中，这时我们的工作区和上一次提交的内容是一样，所以可以放心的修复BUG问题，等到 修复完成并提交到服务器之后，再使用'git stash apply'将以前的工作应用回来

+ 指令介绍

```shell
git stash       #备份当前分支的工作区内容，保证工作区内容和上一次提交的内容一致，同时，将当前的工作内容压入git栈中
git pop         #从git栈中读取最近一次保存的内容，恢复工作区的相关内容
git stash list  #显示git栈中所有备份，可以利用列表选择从哪恢复内容
git stash apply <版本号>   #将制定版本号的内容恢复至当前工作区，配合git stash list使用
git stash clear           #清空git栈
```

## 三、gitbook使用指南

gitbook的使用方法和git基本类似，其修改记录，发布版本等相关操作均可参考上面的git指令，略有不同，下面详细介绍：

```shell
# 初始化书记目录
gitbook init
# 编译图书，可在本地查看
gitbook serve
# 克隆远程图书到本地
git clone https://git.gitbook.com/user_name/book_name.git
# 添加文件
git add file_name
# 提交修改记录
git commit -m "sth about your changes"
# 添加图书的远程地址
git remote add gitbook https://git.gitbook.com/user_name/book_name.git
# 发布图书至远程仓库
git push -u gitbook master  #第一次使用-u参数，之后可以不用加-u参数
```
