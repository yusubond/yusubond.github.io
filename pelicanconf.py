#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals
# import sitemap

AUTHOR = u'subond'
SITENAME = u'Subond'
SITEURL = 'www.subond.com'

PATH = 'content'

TIMEZONE = 'Asia/Shanghai'

RELATIVE_URLS = True
DEFAULT_DATE_FORMAT = '%Y-%m-%d'
DEFAULT_LANG = u'zh'
ARCHIVES_URL = 'archives.html'
ARTICLE_URL = 'pages/{date:%Y}/{date:%m}/{date:%d}/{slug}.html'
ARTICLE_SAVE_AS = 'pages/{date:%Y}/{date:%m}/{date:%d}/{slug}.html'

THEME = 'tuxlite_tbs'
GOOGLE_ANALYTICS = 'UA-45955656-1'
GOOGLE_CUSTOM_SEARCH_SIDEBAR = '007073422838042852012:lysvmhlibk8'

# PLUGINS = [sitemap]
PLUGIN_PATHS = ['pelican-plugins']
PLUGINS = ['sitemap']
SITEMAP = {
    "format":"xml",
    "priorities":{
        "articles":0.7,
        "indexes":0.5,
        "pages":0.3,
    },
    "changefreqs":{
        "articles":"monthly",
        "indexes":"daily",
        "pages":"monthly",
    }
}

# Feed generation is usually not desired when developing
FEED_DOMAIN = '.'
FEED_ALL_ATOM = 'feeds/all.atom.xml'
FEED_ALL_RSS = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None

# Blogroll
LINKS = (('UCloud', 'https://www.ucloud.cn'),
         ('InfoQ', 'http://www.infoq.com/cn/'),
         ('SDNLAB', 'http://www.sdnlab.com/'),
         ('BYR', 'https://bbs.byr.cn/'))

# Social widget
SOCIAL = (('Github', 'https://github.com/yusubond'),
          ('LinkedIn', 'https://www.linkedin.com/in/subond-yu-523281146/'),
          ('Weibo', 'http://weibo.com/ybconly'),
          ('Lofter', 'http://subond.lofter.com/'))

DEFAULT_PAGINATION = 10
