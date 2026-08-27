# -*- coding: utf-8 -*-
"""抽卡建议分析器 · 系统托盘启动器（无控制台窗口）。

将后端 HTTP 服务运行于后台线程，并在 Windows 系统托盘显示图标：
  - 「打开主页」：浏览器打开 http://localhost:<PORT>
  - 「退出」：优雅关闭后端服务并退出

要点：
  - 显式 UTF-8 编码，避免中文 Windows 环境启动失败。
  - 直接运行 backend/server.py 源码（不走打包 exe，避免旧 exe 的逻辑错误）。
  - 若系统未安装 pystray，则自动降级为「后台运行服务 + 自动打开主页」
    （无托盘图标，但服务照常可用，便于排查/验证）。

依赖（托盘版，可选）：
  pip install pystray pillow pywin32
若未安装，仅托盘不可用，不影响服务本身。
"""
import os
import sys
import threading
import webbrowser
import time
import traceback

# ---- 编码修复（中文 Windows 环境）----
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

PORT = 8787
APP_NAME = "抽卡建议分析器"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "backend"))

IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# 后端服务引用（用于退出时优雅关闭）
_srv = None
_server_ready = threading.Event()


def _log_error(msg):
    """把启动错误写到项目根目录的 startup_error.log，便于排查。"""
    try:
        with open(os.path.join(HERE, "startup_error.log"), "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


# 顶层 import（失败要能定位原因，而不是静默崩溃）
try:
    import server  # noqa: E402
except Exception as e:
    _log_error("import server 失败：\n" + traceback.format_exc())
    raise


def _start_server():
    """在后台线程启动后端 HTTP 服务。"""
    global _srv
    try:
        _srv = server.ThreadingHTTPServer(("0.0.0.0", PORT), server.Handler)
    except OSError:
        # 端口被占用：可能已有实例在运行，直接打开主页即可
        _server_ready.set()
        try:
            webbrowser.open("http://localhost:%d" % PORT)
        except Exception:
            pass
        return
    t = threading.Thread(target=_srv.serve_forever, daemon=True)
    t.start()
    time.sleep(1.0)
    _server_ready.set()
    try:
        webbrowser.open("http://localhost:%d" % PORT)
    except Exception:
        pass


def _stop_server():
    global _srv
    if _srv is not None:
        try:
            _srv.shutdown()
            _srv.server_close()
        except Exception:
            pass


def _build_icon():
    """生成一个简单的托盘图标（金底圆角方块，避免依赖中文字体）。"""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (64, 64), (24, 28, 36))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([8, 8, 56, 56], radius=16, fill=(230, 195, 74))
        d.rounded_rectangle([22, 22, 42, 42], radius=8, fill=(24, 28, 36))
        return img
    except Exception:
        from PIL import Image
        return Image.new("RGB", (64, 64), (230, 195, 74))


def _ensure_tray_deps():
    """确保 pystray/pillow 可用；Windows 额外需要 pywin32。

    首次运行（联网）自动安装一次；非 Windows 不自动安装 pywin32
    （macOS 上 pystray 会随 pip 自动带上所需的 pyobjc 依赖）。
    """
    try:
        import pystray  # noqa: F401
        return True
    except Exception:
        pass
    try:
        import subprocess
        _log_error("未检测到 pystray，尝试自动安装托盘依赖（需联网）…")
        pkgs = ["pystray", "pillow"]
        if IS_WINDOWS:
            pkgs.append("pywin32")
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet"] + pkgs,
                       check=False, timeout=600)
        import pystray  # noqa: F401
        _log_error("托盘依赖安装成功。")
        return True
    except Exception as e:
        _log_error("自动安装托盘依赖失败，降级为无托盘模式：%s" % e)
        return False


def _run_tray():
    """托盘模式（需要 pystray）。失败则降级到无托盘模式。"""
    if not _ensure_tray_deps():
        return False
    try:
        import pystray
        from pystray import Menu, MenuItem
    except Exception as e:
        _log_error("pystray 不可用，降级为无托盘模式：%s" % e)
        return False

    def on_open(icon, item):
        try:
            webbrowser.open("http://localhost:%d" % PORT)
        except Exception:
            pass

    def on_exit(icon, item):
        _stop_server()
        icon.stop()

    try:
        icon = pystray.Icon(
            APP_NAME,
            icon=_build_icon(),
            title=APP_NAME,
            menu=Menu(
                MenuItem("打开主页", on_open, default=True),
                Menu.SEPARATOR,
                MenuItem("退出", on_exit),
            ),
        )
        icon.run()
    except Exception as e:
        _log_error("托盘启动失败，降级为无托盘模式：%s" % e)
        return False
    return True


def main():
    # 先启动后端（后台线程）
    threading.Thread(target=_start_server, daemon=True).start()

    # macOS / Linux 无 pythonw：pystray 可用则用菜单栏/托盘，
    # 否则自动降级为「后台服务 + 自动打开主页」。
    used_tray = _run_tray()
    if not used_tray:
        # 无托盘降级：服务已在后台运行，主页已打开；主线程保持存活。
        # Windows：可在「任务管理器」结束 pythonw 进程退出；
        # macOS：可在「活动监视器」结束 python3 进程，或安装 pystray 后即有菜单栏图标。
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            _stop_server()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _log_error("启动器异常退出：\n" + traceback.format_exc())
        raise
