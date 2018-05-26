Title: 工作中遇到的小技巧
Date: 2016-07-12
Category: NOTE
Tags: tools
Slug: tip-tools
Author: subond

### Ubuntu彻底删除Mysql,重装Mysql

```shell
# 删除MySQL
sudo apt-get autoremove --purge mysql-server-5.0
sudo apt-get remove mysql-server
sudo apt-get autoremove mysql-server
sudo apt-get remove mysql-common  #很重要

# 清理残留数据
dpkg -l | grep ^rc | awk '{print $2}' | sudo xargs dpkg -P
# 安装mysql
sudo apt-get install mysql-server mysql-client php5-mysql
# 启动mysql
# sudo /etc/init.d/mysql restart
# 安装phpmyadmin
sudo apt-get install phpmyadmin
sudo ln -s /etc/phpmyadmin/apache.conf /etc/apache2.conf-available/phpmyadmin.conf
sudo a2enconf phpmyadmin
sudo /etc/init.d/apache2 reload
```

### Ubuntu启动问题以及Grub Rescue修复方法

在安装双系统时，或者不小心删除了启动引导项时，启动时系统将进入Grub Rescue模式。在rescue模式下，只用少量的命令可以使用，但是通过一定的操作可以让系统加载正常模块，然后进入正常启动模式，启动后修复grub启动项即可。

rescue模式下可使用的命令有：set,ls(列出文件),insmod(插入启动模块),root(设置启动分区),prefix(设置启动路径)。

解决方法如下：

<pre>
# 查看系统分区情况
grub rescue>ls
# 罗列出所有的磁盘分区信息，比如说：
(hd0,msdos6) (hd0,msdos5) (hd0,msdos4) (hd0,msdos3)(hd0,msdos2)
# 查找曾经安装系统的磁盘分区，找到相应的grub
grub rescue>ls (hd0,X)/        # 查看X磁盘分区/根路径的文件信息
grub rescue>ls (hd0,X)/boot    # 查看X磁盘分区/boot路径的文件信息
grub rescue>ls (hd0,X)/grub    # 查看X磁盘分区/grub路径的文件信息
# 假设找的(hd0,msdos3)时，显示了文件信息，则表明系统安装在这个分区，并记住相应的grub路径
# 接下来，设置系统的启动项，调用如下命令
grub rescue>set root=(hd0,msdos3)
grub rescue>set prefix=(hd0,msdos3)/grub  #这个路径为之前找到的启动项路径
grub rescue>insmod normal
# 设置完成后，进行启动即可
grub rescue>normal</pre>

经过以上操作，就可以显示丢失的grub菜单，然后进入自己想进入的系统即可。

**注意**：如果进行重启，问题依旧存在。所以最关键的一步就是对grub进行修复。</b>进入系统后，使用以下命令对grub进行修复。

<pre>
sudo update-grub
sudo grub-install /dev/sda
# sda是磁盘号码，不是分区号码</pre>

grub修复成功后，重启测试即可。*说明一下，grub修复成功后，其启动项是由当前系统去引导另一系统启动。*你也可以进入另一系统进行grub修复，修改启动引导顺序，或者修改文件/etc/default/grub设定默认启动项(GRUB_DEFAULT从0开始计算)。
