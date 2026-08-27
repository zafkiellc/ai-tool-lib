#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加油站强检证书下载工具 - 网页版启动器
========================================
启动本地 HTTP 服务，自动打开浏览器操作界面。
界面功能：选择账号密码本、勾选站点、一键下载、实时日志、断点续传。

运行：python web_launcher.py  或双击 启动工具.vbs（隐藏窗口）
"""
import json
import sys
import threading
import webbrowser
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# ---- pythonw 无控制台环境兜底：stdout/stderr 重定向到日志文件 ----
def _ensure_std():
    if sys.stdout is None:
        try:
            sys.stdout = open(BASE_DIR / "web_launcher.log", "a", encoding="utf-8")
        except Exception:
            import io
            sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = sys.stdout

_ensure_std()

# 记录"原始" stdout（console 或日志文件），log() 用它打印避免被 Tee 递归拦截
_ORIG_STDOUT = sys.stdout

import download_certs as dc

PORT = 8766
STATIC_DIR = BASE_DIR / "static"

# 全局状态
STATE = {
    "running": False,
    "stop": False,
    "log_lines": [],
    "stations": [],
    "checked": [],
    "output_dir": str(Path("D:/加油机强检证书")),
    "excel": str(Path("C:/Users/zafki/OneDrive/工作/安数/账号/加油站强制检定申报信息统计表.xlsx")),
    "progress": {},
}

# 当前活动的浏览器实例（供"停止"时强制关闭，立即中断下载）
ACTIVE_BROWSER = None
ACTIVE_LOCK = threading.Lock()


def log(msg):
    STATE["log_lines"].append(f"[{time_str()}] {msg}")
    if len(STATE["log_lines"]) > 2000:
        STATE["log_lines"] = STATE["log_lines"][-2000:]
    # 用原始 stdout 打印（console 或 pythonw 日志文件），避免被 Tee 递归拦截
    try:
        if _ORIG_STDOUT is not None:
            _ORIG_STDOUT.write(msg + "\n")
            _ORIG_STDOUT.flush()
    except Exception:
        pass


def time_str():
    import time
    return time.strftime("%H:%M:%S")


def load_stations():
    try:
        STATE["stations"] = dc.read_stations(Path(STATE["excel"]))
        STATE["checked"] = [True] * len(STATE["stations"])
        log(f"已加载 {len(STATE['stations'])} 个站点")
    except Exception as e:
        log(f"读取 Excel 失败: {e}")
        STATE["stations"] = []
        STATE["checked"] = []


def run_download():
    """后台下载线程。将 process_station 的全部 print 转发到页面日志。"""
    import sys as _sys
    import time as _time

    # ---- stdout 管道：把下载脚本的所有 print 实时转发到页面日志 ----
    class _Tee:
        def __init__(self, stream):
            self.stream = stream
        def write(self, data):
            try:
                self.stream.write(data)
                self.stream.flush()
            except Exception:
                pass
            text = data.rstrip()
            if text:
                log(text)
        def flush(self):
            try:
                self.stream.flush()
            except Exception:
                pass

    _orig_stdout = _sys.stdout
    _sys.stdout = _Tee(_orig_stdout)
    # 开始前重置停止标志
    STATE["stop"] = False
    dc.STOP_REQUESTED = False
    try:
        from playwright.sync_api import sync_playwright

        selected = [s for s, c in zip(STATE["stations"], STATE["checked"]) if c]
        if not selected:
            log("未选择任何站点")
            STATE["running"] = False
            return

        out_dir = Path(STATE["output_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        log_path = out_dir / "download_log.json"
        logbook = {}
        if log_path.exists():
            try:
                logbook = json.loads(log_path.read_text(encoding="utf-8"))
            except Exception:
                logbook = {}

        log(f"开始下载 {len(selected)} 个站点，输出到 {out_dir}")
        STATE["progress"] = {"total": len(selected), "done": 0, "current": "", "downloaded": 0}

        done_count = 0
        total_pdf = 0
        with sync_playwright() as p:
            # 每个站点使用全新浏览器实例（绕开 WAF 实例级限流）
            for station in selected:
                if STATE["stop"] or dc.stop_check():
                    log("已停止。")
                    break
                STATE["progress"]["current"] = station["name"]
                log(f"══════ 开始站点 [{done_count+1}/{len(selected)}] {station['name']} ══════")
                browser = dc.launch_browser(p)
                with ACTIVE_LOCK:
                    ACTIVE_BROWSER = browser  # 记录当前浏览器，供停止时强制关闭
                try:
                    context = browser.new_context(
                        viewport={"width": 1366, "height": 900},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        accept_downloads=True,
                    )
                    page = context.new_page()
                    page.set_default_timeout(30000)
                    dc.process_station(page, context, station, out_dir, logbook)
                except Exception as e:
                    import traceback
                    log(f"站点 {station['name']} 异常: {e}")
                    traceback.print_exc()
                    logbook[station["name"]] = {"status": "error", "error": str(e), "time": _time.strftime("%Y-%m-%d %H:%M:%S")}
                finally:
                    with ACTIVE_LOCK:
                        ACTIVE_BROWSER = None
                    try:
                        browser.close()
                    except Exception:
                        pass
                try:
                    log_path.write_text(json.dumps(logbook, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
                done_count += 1
                total_pdf += logbook.get(station["name"], {}).get("downloaded", 0)
                STATE["progress"] = {"total": len(selected), "done": done_count, "current": station["name"], "downloaded": total_pdf}

        log(f"全部完成！共下载 {total_pdf} 份证书")
        STATE["running"] = False
    except Exception as e:
        import traceback
        log(f"运行异常: {e}")
        traceback.print_exc()
        STATE["running"] = False
    finally:
        # 兜底清理：确保浏览器进程被释放
        with ACTIVE_LOCK:
            ACTIVE_BROWSER = None
        _sys.stdout = _orig_stdout


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # 关闭默认访问日志

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        if path == "/" or path == "/index.html":
            html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
            self._send(200, html, "text/html; charset=utf-8")
            return

        if path == "/api/status":
            self._send(200, json.dumps({
                "running": STATE["running"],
                "stations": STATE["stations"],
                "checked": STATE["checked"],
                "output_dir": STATE["output_dir"],
                "excel": STATE["excel"],
                "logs": STATE["log_lines"][-100:],
                "progress": STATE["progress"],
            }, ensure_ascii=False))
            return

        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/load":
            excel = data.get("excel")
            if excel:
                STATE["excel"] = excel
            load_stations()
            self._send(200, json.dumps({"ok": True, "stations": STATE["stations"]}, ensure_ascii=False))
            return

        if path == "/api/set":
            if "checked" in data:
                STATE["checked"] = data["checked"]
            if "output_dir" in data:
                STATE["output_dir"] = data["output_dir"]
            self._send(200, json.dumps({"ok": True}))
            return

        if path == "/api/start":
            if STATE["running"]:
                self._send(200, json.dumps({"ok": False, "msg": "已有任务在运行"}))
                return
            STATE["running"] = True
            STATE["stop"] = False
            STATE["log_lines"] = []
            threading.Thread(target=run_download, daemon=True).start()
            self._send(200, json.dumps({"ok": True}))
            return

        if path == "/api/stop":
            STATE["stop"] = True
            dc.STOP_REQUESTED = True
            log("正在停止任务，强制关闭浏览器进程...")
            # 强制关闭当前浏览器，立即中断阻塞中的 playwright 操作
            with ACTIVE_LOCK:
                br = ACTIVE_BROWSER
            if br is not None:
                def _kill():
                    try:
                        br.close()
                    except Exception:
                        pass
                threading.Thread(target=_kill, daemon=True).start()
            self._send(200, json.dumps({"ok": True}))
            return

        if path == "/api/upload_excel":
            # 接收前端上传的账号密码本（multipart/form-data），保存并加载
            try:
                ctype = self.headers.get("Content-Type", "")
                boundary = None
                if "boundary=" in ctype:
                    boundary = ctype.split("boundary=", 1)[1].strip().strip('"')
                raw = self.rfile.read(length) if length else b""
                filename = "上传的密码本.xlsx"
                if boundary:
                    # 简单 multipart 解析：取第一个文件块的 content
                    parts = raw.split(("--" + boundary).encode())
                    for part in parts:
                        if b"filename=" in part.split(b"\r\n\r\n", 1)[0] if b"\r\n\r\n" in part else False:
                            head, _, content = part.partition(b"\r\n\r\n")
                            # 提取原始文件名
                            import re as _re
                            m = _re.search(rb'filename="([^"]+)"', head)
                            if m:
                                try:
                                    filename = m.group(1).decode("utf-8")
                                except Exception:
                                    filename = "上传的密码本.xlsx"
                            # 去掉尾部 boundary 的 \r\n
                            content = content.rstrip(b"\r\n")
                            save_path = BASE_DIR / "上传的密码本.xlsx"
                            save_path.write_bytes(content)
                            break
                else:
                    (BASE_DIR / "上传的密码本.xlsx").write_bytes(raw)
                STATE["excel"] = str(BASE_DIR / "上传的密码本.xlsx")
                load_stations()
                self._send(200, json.dumps({
                    "ok": True,
                    "filename": filename,
                    "stations": STATE["stations"],
                    "excel": STATE["excel"],
                }, ensure_ascii=False))
            except Exception as e:
                self._send(200, json.dumps({"ok": False, "msg": f"上传失败: {e}"}, ensure_ascii=False))
            return

        self._send(404, json.dumps({"error": "not found"}))


def main():
    # 确保输出目录存在
    try:
        Path(STATE["output_dir"]).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # 端口占用检测：已有实例在运行则直接打开浏览器访问
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", PORT))
        sock.close()
    except OSError:
        print(f"端口 {PORT} 已被占用，工具可能已在运行，直接打开浏览器...")
        webbrowser.open(f"http://127.0.0.1:{PORT}")
        return

    load_stations()

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"服务已启动: http://127.0.0.1:{PORT}")
    print("将自动打开浏览器...")

    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
