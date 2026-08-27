#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""便携打包脚本：应用 + 免安装 Python 运行时 → 可直接拷贝分发的目录（Windows / macOS）。

本项目后端仅使用 Python 标准库（http.server / urllib 等），因此无需 pip 安装任何依赖；
打包后对方不需要安装 Python，双击启动器即可运行。

用法:
    python tools/package.py                    # 按当前系统打包
    python tools/package.py --platform win     # 强制打 Windows 包
    python tools/package.py --platform mac --arch aarch64   # macOS (Apple Silicon)
    python tools/package.py --platform mac --arch x86_64    # macOS (Intel)

产物:
    dist/GachaAdvisor-win/   ← Windows：双击 start.bat（无控制台窗口）
    dist/GachaAdvisor-mac/   ← macOS：双击 start.command（首次需 chmod +x start.command）
把整个目录拷贝/压缩给他人即可使用。
"""

import argparse
import io
import json
import os
import shutil
import sys
import tarfile
import urllib.request


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_TAG = "20260728"
RUNTIME_PY = "3.13.14"
RUNTIME_URL = ("https://github.com/astral-sh/python-build-standalone/releases/download/"
               "%s/cpython-%s+%s-%s-install_only_stripped.tar.gz")

PLATFORM_TARGETS = {
    "win": {"arch": "x86_64-pc-windows-msvc", "label": "Windows"},
    "mac": {"arch": "aarch64-apple-darwin", "label": "macOS"},
}


def _log(msg):
    print("[package] " + msg, flush=True)


def _resolve_platform(platform):
    if platform:
        return platform
    return "win" if os.name == "nt" else ("mac" if sys.platform == "darwin" else "linux")


def _runtime_tar(platform, arch):
    return "cpython-%s+%s-%s-install_only_stripped.tar.gz" % (RUNTIME_PY, RUNTIME_TAG, arch)


def _download(url, dest):
    _log("下载运行时（%d MB 左右，首次打包需要）…" % (45 if "windows" in url else 24))
    req = urllib.request.Request(url, headers={"User-Agent": "gacha-advisor-packager"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f, length=1024 * 256)
    _log("下载完成：%s" % dest)


def _ensure_runtime(platform, arch, runtime_dir, keep_cache):
    """确保目标目录内存在可用运行时；返回 python 可执行文件路径（或 None）。"""
    cache_dir = os.path.join(BASE, "tools", "_py_runtime")
    os.makedirs(cache_dir, exist_ok=True)
    tar_path = os.path.join(cache_dir, _runtime_tar(platform, arch))
    if not os.path.exists(tar_path):
        url = RUNTIME_URL % (RUNTIME_TAG, RUNTIME_PY, RUNTIME_TAG, arch)
        _download(url, tar_path)
    _log("解压运行时到 %s …" % runtime_dir)
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(runtime_dir, filter="data")
    if not keep_cache:
        try:
            os.remove(tar_path)
        except Exception:
            pass
    # 定位 python
    python_root = os.path.join(runtime_dir, "python")
    if platform == "win":
        py = os.path.join(python_root, "python.exe")
        pyw = os.path.join(python_root, "pythonw.exe")
    else:
        py = os.path.join(python_root, "bin", "python3")
        pyw = py
    if not os.path.exists(py):
        _log("错误：未找到运行时 python（%s）" % py)
        return None
    return py


def _sanitize_config():
    """生成分发版 config.json：清空敏感信息（SESSDATA / AI Key），默认示例模式。"""
    src = os.path.join(BASE, "config.json")
    cfg = json.load(open(src, encoding="utf-8"))
    cookie = cfg.get("cookie") or {}
    if isinstance(cookie, dict) and cookie.get("SESSDATA"):
        cookie["SESSDATA"] = ""
    ai = cfg.get("ai") or {}
    for k in ("online", "local"):
        if isinstance(ai.get(k), dict) and ai[k].get("api_key"):
            ai[k]["api_key"] = ""
    ai["enabled"] = False
    cfg["demo_mode"] = True
    return cfg


def _copy_tree(src, dst, exclude=()):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in exclude]
        rel = os.path.relpath(root, src)
        target = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target, exist_ok=True)
        for fn in files:
            if ".bak." in fn:
                continue
            shutil.copy2(os.path.join(root, fn), os.path.join(target, fn))


def _write_launcher_win(dist):
    content = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM ===== 抽卡建议分析器 · Windows 启动器（使用内置 Python 运行时）=====
set "PYW=runtime\\python\\pythonw.exe"
set "PY=runtime\\python\\python.exe"
if exist "%PYW%" (
  start "" "%PYW%" launcher.py
) else if exist "%PY%" (
  start "" "%PY%" launcher.py
) else (
  echo 未找到内置 Python 运行时，尝试使用系统 python...
  python launcher.py
)
"""
    with open(os.path.join(dist, "start.bat"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)


def _write_launcher_mac(dist):
    content = """#!/bin/bash
# ===== 抽卡建议分析器 · macOS 启动器（使用内置 Python 运行时）=====
cd "$(dirname "$0")" || exit 1
PY="runtime/python/bin/python3"
if [ ! -x "$PY" ]; then
  PY="python3"
fi
nohup "$PY" "$(pwd)/launcher.py" >/dev/null 2>&1 &
sleep 1
osascript -e 'tell application "Terminal" to close (every window whose name contains "start.command")' >/dev/null 2>&1 &
exit 0
"""
    with open(os.path.join(dist, "start.command"), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.chmod(os.path.join(dist, "start.command"), 0o755)


def _write_readme(dist, platform):
    lines = [
        "抽卡建议分析器（便携版）使用说明",
        "=" * 40,
        "",
        "本目录已内置 Python 运行时，无需安装 Python，直接启动即可。",
        "",
        "【启动】",
        "- Windows：双击 start.bat（后台运行，自动打开浏览器 http://localhost:8787）",
        "- macOS：双击 start.command（首次运行如被系统拦截：右键→打开；",
        "  或在终端执行 chmod +x start.command 后双击）",
        "",
        "【首次使用】",
        "1. 打开右上「⚙ 设置」：",
        "   - AI 分析：填入你的 API（OpenAI 兼容服务）base_url / key / 模型名",
        "   - 真实 B站 数据：关闭示例模式，填入 SESSDATA（家庭宽带本机运行）",
        "2. 数据更新：设置 → 数据来源 →「在线拉取最新角色名单」",
        "   （原神/星铁/绝区零/鸣潮/终末地/异环，自动备份、只增不改）",
        "",
        "【数据位置】",
        "- 角色库/官方数值/头像：data/ 目录（可整体备份）",
        "- AI 结果缓存：data/.ai_cache/（设置页可一键清空）",
        "- 配置文件：config.json（含你的 AI Key / SESSDATA，请勿外传）",
        "",
        "【退出】",
        "- Windows：托盘图标右键 → 退出；或任务管理器结束 pythonw",
        "- macOS：活动监视器结束 python3；或安装 pystray 后菜单栏退出",
        "",
        "【备注】",
        "- 无第三方 Python 依赖（纯标准库），内置运行时为 python-build-standalone 3.13",
        "- 已分析角色复用本地 AI 缓存，只有手动点「AI 分析」才消耗 token",
    ]
    with open(os.path.join(dist, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build(platform, arch, keep_cache):
    if platform not in PLATFORM_TARGETS:
        print("不支持的平台：%s（仅支持 win / mac）" % platform)
        return 1
    if arch:
        PLATFORM_TARGETS["mac"]["arch"] = arch if "darwin" in arch else arch + "-apple-darwin"
    arch = PLATFORM_TARGETS[platform]["arch"]
    dist = os.path.join(BASE, "dist", "GachaAdvisor-" + platform)
    if os.path.exists(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)

    _log("拷贝应用文件…")
    _copy_tree(os.path.join(BASE, "backend"), os.path.join(dist, "backend"),
               exclude=("__pycache__",))
    os.makedirs(os.path.join(dist, "frontend"), exist_ok=True)
    shutil.copy2(os.path.join(BASE, "frontend", "index.html"),
                 os.path.join(dist, "frontend", "index.html"))
    _copy_tree(os.path.join(BASE, "data"), os.path.join(dist, "data"),
               exclude=("__pycache__", ".cache", ".ai_cache"))
    shutil.copy2(os.path.join(BASE, "launcher.py"), os.path.join(dist, "launcher.py"))
    with open(os.path.join(dist, "config.json"), "w", encoding="utf-8") as f:
        json.dump(_sanitize_config(), f, ensure_ascii=False, indent=2)

    _log("准备内置 Python 运行时…")
    runtime_dir = os.path.join(dist, "runtime")
    py = _ensure_runtime(platform, arch, runtime_dir, keep_cache)
    if not py:
        return 1
    _log("内置 Python：%s" % py)

    if platform == "win":
        _write_launcher_win(dist)
    else:
        _write_launcher_mac(dist)
    _write_readme(dist, platform)
    _log("完成：%s（可直接拷贝分发）" % dist)
    return 0


def main():
    ap = argparse.ArgumentParser(description="便携打包（Windows / macOS）")
    ap.add_argument("--platform", choices=["win", "mac"], default=None)
    ap.add_argument("--arch", default=None, help="macOS 架构：aarch64 / x86_64")
    ap.add_argument("--keep-runtime", action="store_true",
                    help="保留已下载的运行时缓存（tools/_py_runtime/），加速重复打包")
    args = ap.parse_args()
    platform = _resolve_platform(args.platform)
    return build(platform, args.arch, args.keep_runtime)


if __name__ == "__main__":
    sys.exit(main())
