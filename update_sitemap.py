#!/usr/bin/env python3
"""update_sitemap.py — updates lastmod dates in sitemap.xml to today"""
import re, datetime

today = datetime.date.today().isoformat()
with open('sitemap.xml') as f:
    s = f.read()
s = re.sub(r'<lastmod>[0-9-]+</lastmod>', f'<lastmod>{today}</lastmod>', s)
with open('sitemap.xml', 'w') as f:
    f.write(s)
print(f'sitemap.xml lastmod updated to {today}')
