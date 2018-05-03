Title: 利用Pelican+Github pages搭建个人博客
Date: 2016-04-24
Category: Tech
Tags: pelican, blog
Slug: pelican-github-chuang-jian-blog
Author: subond
Summary: 本教程基于pelican博客引擎和github page的功能，实现个人博客搭建。

说明：本教程使用的系统平台为ubuntu16.04。

## Github pages

注册Github，并创建一个名为username.github.io的版本库。注意username为自己的用户名。

## 配置本地环境

+ 安装Pelican和Markdown

Pelican是一套开源的使用Python编写的博客静态生成，可以添加文章和创建页面，可使用Markdown，reStructuredText和AsiiDoc的格式来书写，同时使用Disqus评论系统，支持 RSS和Atom输出，插件，主题，代码高亮等功能。

安装Pelican有很多方法，一般采用python的包管理器pip进行安装。

```shell
$ sudo apt-get install python-pip
$ sudo pip install pelican
$ sudo pip install markdow
```

+ 创建博客

创建博客目录，然后使用快速生成，具体如下：

```shell
$ mkdir blog
$ cd blog
$ pelican-quickstart
```

执行pelican-quicstart命令后，会提示博客的配置选项，根据提示操作即可，除必填项之外，其他选择默认即可。如果有需要可以在之后的pelicanconf.py文件进行修改。完成之后，会出现Pelican框架，如下

```shell
bolg
|__content             #存放输入的Markdown文件
|__output              #存放最终生成的静态博客网页文件
|__develop_server.sh   #本地测试服务器文件
|__Makefile            #管理博客的Makefile
|__pelicanconf.py      #博客配置文件
|__publishconf.py      #发布文件，可删除
```

+ 撰写博客

完成博客主题搭建后，使用Markdown语法书写博客，完成后保存在content目录下。

```Markdown
Title: My super title     //文章名字
Date: 2016-04-21
Category: Python          //文章分类
Tags: pelican, publishing //文章标签
Slug: my-super-post       //html文件名
Author: Alexis Metaireau  //作者信息
Summary: Short version for index and feeds  //文章摘要

//文章正文

This is the content of my super blog post.
```

完成之后，在blog目录下，执行如下命令：

```shell
$ make html
$ ./develop_server.sh start 8000
```

之后，在浏览器中输入http://localhost:8000 即可看到博客效果。

+ 发布博客

之前我们已经在Github上创建了仓库，现在我们就将本地文件搬到远程仓库中，进入output目录下，具体指令如下：

```shell
$ git init
$ git add .
$ git remote add origin https://github.com/username/username.github.io
$ git pull origin master
$ git commit -m "First update"
$ git push origin master
```

完成博客发布后，访问http://username.github.io 即可。

## 附：Git简易教程

```shell
$ git init                    #把当前目录变成git可管理的repository
$ git add <files>             #添加文件至缓存区
$ git commit -m "message"     #提交文件
$ git remote add origin <server>       #添加远程服务器
$ git remote set-url origin <server>   #修改远程服务器地址
$ git push origin master      #推送到远程服务器
$ git status    #查看当前各文件状态
```

## Pelican的几点说明

1. 使用`pelican-theme`命令可以安装不同的博客主题风格，`-v`可查看安装路径；使用`pelican-theme`生成主题后，会在博客目录下生成一个`theme`的文件夹(这是依据你所选的主题风格生成的文件，无需修改)。若要修改某个特定主题，需在主题的默认安装路径中进行修改，修改后重新导入主题即可。
