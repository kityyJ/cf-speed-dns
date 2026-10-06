#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
兼容入口。

旧版仓库使用 generate_pages.py 从单个 Cloudflare DNS 记录生成页面。
当前版本已经改为 aggregate_ips.py 多来源聚合；保留本文件是为了避免
旧的手动命令或自动化调用失效。
"""

from aggregate_ips import main


if __name__ == "__main__":
    main()
