# 凯文的个人博客

基于 [tailwind-nextjs-starter-blog](https://github.com/timlrx/tailwind-nextjs-starter-blog)（Next.js + Tailwind CSS + Contentlayer）搭建的静态博客站点，通过 GitHub Pages 部署。

## 目录结构

```
├── app/                    # Next.js App Router 页面
│   ├── about/              # 关于页面
│   ├── api/                # API 路由（newsletter 等）
│   ├── blog/               # 博客列表与文章详情页
│   ├── projects/           # 项目展示页
│   ├── reading/            # 阅读页
│   ├── tags/               # 标签聚合页
│   ├── layout.tsx          # 根布局
│   ├── tag-data.json       # 标签统计数据（构建时自动生成）
│   └── siteMetadata.js     # 站点元信息
├── components/             # React 组件（Header、Footer、Card 等）
├── css/                    # 全局样式（Tailwind、Prism 代码高亮）
├── data/
│   ├── blog/               # 博客文章（Markdown，按日期命名）
│   ├── authors/            # 作者信息
│   ├── headerNavLinks.ts   # 导航栏链接配置
│   ├── projectsData.ts     # 项目数据
│   └── references-data.bib # 参考文献（BibTeX）
├── layouts/                # 页面布局模板（PostLayout、ListLayout 等）
├── out/                    # 静态导出输出目录（构建产物）
├── public/                 # 静态资源（CNAME、feed.xml、search.json）
├── scripts/                # 构建后处理脚本（RSS 生成等）
├── static/                 # 原始静态文件（favicon、图片等）
├── contentlayer.config.ts  # Contentlayer 内容处理配置
├── next.config.js          # Next.js 配置
├── postcss.config.js       # PostCSS 配置
├── prettier.config.js      # Prettier 格式化配置
└── eslint.config.mjs       # ESLint 配置
```

## 博客文章格式

文章存放于 `data/blog/` 目录，文件名格式为 `YYYY-MM-DD_英文短名.md`，使用 YAML front matter：

```markdown
---
title: '文章标题'
date: '2026-06-10'
tags: ['标签1', '标签2', '技术']
draft: false
authors: ['default']
layout: PostLayout
---

## 正文标题

正文内容...
```

## 本地开发

```bash
# 安装依赖
npm ci

# 启动开发服务器（http://localhost:3000）
npm start

# 构建静态站点
npm run build

# 代码检查
npm run lint
```

## 构建与发布流程

博客通过 **GitHub Actions** 自动构建和部署到 GitHub Pages：

1. **推送代码**到 `master` 分支
2. GitHub Actions 触发 `.github/workflows/` 中的工作流
3. 工作流执行 `npm ci && npm run build`（设置 `EXPORT=1 UNOPTIMIZED=1` 导出静态 HTML）
4. 构建产物输出到 `out/` 目录
5. 自动部署到 GitHub Pages

发布新文章只需：

1. 在 `data/blog/` 下新建 `.md` 文件
2. 本地 `npm run build` 验证构建无误
3. 提交并推送到 `master` 分支，GitHub Actions 自动完成部署
