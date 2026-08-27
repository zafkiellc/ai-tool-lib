#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI：联网从 StarRailRes（游戏资源官方镜像）拉取并升级本地 HSR 角色库。

用法:
    python tools/update_hsr_db.py

说明:
    - 数据源: github.com/Mar-7th/StarRailRes（每版本自动更新的官方资源镜像）
    - 策略: 只增不改 + 空字段补齐；网络失败不改动本地数据。
    - 也可在 Web 设置页「角色名单库」点击「在线拉取最新角色名单」完成同样操作。
    - 通用入口: python tools/update_db.py hsr
"""
import os
import runpy
import sys

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.argv = [os.path.join(here, "update_db.py"), "hsr"]
    runpy.run_path(os.path.join(here, "update_db.py"), run_name="__main__")
