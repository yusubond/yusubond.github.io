# README

个人博客的所有文档


hugo 的目录说明：

- **archetypes**: 储存`.md`的模板文件，类似于`hexo`的`scaffolds`，该文件夹的优先级高于主题下的`/archetypes`文件夹

- **config.toml**: 配置文件

- **content**: 储存网站的所有内容，类似于`hexo`的`source`

- **data**: 储存数据文件供模板调用，类似于`hexo`的`source/_data`

- **layouts**: 储存`.html`模板，该文件夹的优先级高于主题下的`/layouts`文件夹

- **static**: 储存图片,css,js等静态文件，该目录下的文件会直接拷贝到`/public`，该文件夹的优先级高于主题下的`/static`文件夹

- **themes**: 储存主题

- **public**: 执行`hugo`命令后，储存生成的静态文件
