## Atom的个性化配置

### Packages

推荐几个好用的packages.

1. **Minimap**

Minimap是Atom最流行好用的几个packages之一，它可以提供源码的全局视图。

[https://atom.io/packages/minimap](https://atom.io/packages/minimap)

![picture](http://dab1nmslvvntp.cloudfront.net/wp-content/uploads/2015/08/1438675653mini-map.png)

2. **Highlight Selected**

无需多说，代码高亮也是必备。

[https://atom.io/packages/highlight-selected](https://atom.io/packages/highlight-selected)

![picture](http://dab1nmslvvntp.cloudfront.net/wp-content/uploads/2015/08/1438675732highlight-selected.png)

3. **Linter**

[https://atom.io/packages/linter](https://atom.io/packages/linter)

![picture](http://dab1nmslvvntp.cloudfront.net/wp-content/uploads/2015/08/1438675975linter.gif)

4. **atom-beautify**

[https://atom.io/packages/atom-beautify](https://atom.io/packages/atom-beautify)

5. **file-icons**

[https://atom.io/packages/file-icons](https://atom.io/packages/file-icons)

![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/file-icons.png)

6. **todo-show**

[https://atom.io/packages/todo-show](https://atom.io/packages/todo-show)

![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/todo-show.png)

### Theme

个人比较喜欢的几个theme.

1. **Dracula**

[https://atom.io/themes/dracula-ui](https://atom.io/themes/dracula-ui)
// TODO
![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/dracula-ui.png)

[https://atom.io/themes/dracula-syntax](https://atom.io/themes/dracula-syntax)
// TODO
![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/dracula-syntax.png)

2. **Material**

[https://atom.io/themes/atom-material-ui](https://atom.io/themes/atom-material-ui)
// TODO
![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/material-ui.png)

[https://atom.io/themes/atom-material-syntax](https://atom.io/themes/atom-material-syntax)
// TODO
![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/material-syntax.png)

3. **City-Light**

[https://atom.io/themes/city-lights-ui](https://atom.io/themes/city-lights-ui)
// TODO
![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/city-light-ui.png)

[https://atom.io/themes/city-lights-syntax](https://atom.io/themes/city-lights-syntax)
// TODO
![picture](http://on64c9tla.bkt.clouddn.com/www.subond.com/city-light-syntax.png)

### 再高效一些

1.快速跳出成对出现符号

当我们使用atom编辑器时，括号、引号等符号往往是成对出现的。而且，当我们打出成对的符号，光标相应的移动到符号中间，方面书写。但是写完后再跳出右边的符号需要使用`->`这个键，移动距离过大，不是很方便。为了快速跳出，可进行如下设置：

在`init.coffee`中添加如下代码：

```
# move cursor across the ending symbols...
EndingSymbolRegex = /\s*[)}>\]/'";:=-]/
atom.commands.add 'atom-text-editor', 'custom:jump-over-symbol': (event) ->
  editor = atom.workspace.getActiveTextEditor()
  cursorMoved = false
  for cursor in editor.getCursors()
    range = cursor.getCurrentWordBufferRange(wordRegex: EndingSymbolRegex)
    unless range.isEmpty()
      cursor.setBufferPosition(range.end)
      cursorMoved = true
  event.abortKeyBinding() unless cursorMoved
```

然后在`config.cson`中添加如下代码：

```
"atom-text-editor:not([mini])":
  "enter": "custom:jump-over-symbol"
```

### 参考资料

[1].[10 Essential Atom Add-ons](https://www.sitepoint.com/10-essential-atom-add-ons/)

[2].[10 Best Atom themes of 2017](https://blog.duojam.com/10-best-atom-themes-of-2017/)

[3].[The best Atom packages and themes](https://medium.com/@Dannypaton/the-best-packages-and-themes-for-atom-fee4860a7955)

[4].[用TAB在原子编辑器中跳过括号/括号/引号](http://stackoverflow.org.cn/front/ask/view?ask_id=607299)
