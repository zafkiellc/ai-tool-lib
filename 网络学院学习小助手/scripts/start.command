#!/bin/bash
cd "$(dirname "$0")"

if ! command -v node >/dev/null 2>&1; then
  echo "未找到 Node.js，请先安装 Node.js 20 或更高版本：https://nodejs.org/"
  read -r -p "按回车键退出..." _
  exit 1
fi

if [ ! -d node_modules ]; then
  echo "首次运行，正在安装依赖..."
  npm install || {
    echo "依赖安装失败"
    read -r -p "按回车键退出..." _
    exit 1
  }
fi

if [ ! -d "$HOME/Library/Caches/ms-playwright/chromium-1234" ] || \
   [ ! -d "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1234" ]; then
  echo "首次运行，正在下载 Chromium..."
  npx playwright install chromium || {
    echo "Chromium 下载失败"
    read -r -p "按回车键退出..." _
    exit 1
  }
fi

if curl -fsS --max-time 2 http://127.0.0.1:3000/api/health >/dev/null 2>&1; then
  echo "服务已在运行：http://127.0.0.1:3000"
  open "http://127.0.0.1:3000"
  exit 0
fi

[ -f data/port.txt ] && rm -f data/port.txt

echo "正在启动 网络学院学习小助手..."
node server.js &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null' EXIT

PORT=3000
for _ in $(seq 1 40); do
  if [ -f data/port.txt ]; then
    PORT=$(cat data/port.txt)
    break
  fi
  sleep 0.5
done

for _ in $(seq 1 20); do
  if curl -fsS --max-time 1 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "服务已启动：http://127.0.0.1:$PORT"
open "http://127.0.0.1:$PORT"
echo "停止方式：关闭本窗口，或按 Ctrl+C"
wait "$SERVER_PID"
