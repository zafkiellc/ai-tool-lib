#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CLI：联网从官方镜像拉取并升级本地角色库。

用法:
    python tools/update_db.py              # 默认 hsr（崩坏：星穹铁道）
    python tools/update_db.py genshin      # 原神（genshin-db 官方镜像）
    python tools/update_db.py arknights_endfield  # 终末地（BoxCatTeam 元数据）

说明:
    - 只增不改 + 空字段补齐；网络失败不改动本地数据。
    - 绝区零 / 鸣潮 / 异环 暂无可接入的官方镜像名单源，维持精编数据。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from character_refresh import update_db  # noqa: E402


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "hsr"
    print(json.dumps(update_db(game), ensure_ascii=False, indent=2))
