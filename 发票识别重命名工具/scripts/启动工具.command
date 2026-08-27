#!/bin/bash
cd "$(dirname "$0")"

NODE_BIN="./runtime/mac/node"
if [ "$(uname -m)" = "x86_64" ]; then
  NODE_BIN="./runtime/mac-x64/node"
fi

if [ ! -x "$NODE_BIN" ]; then
  echo "缺少 Mac 运行环境，请检查文件夹是否完整。"
  read -r -p "按回车键关闭窗口..."
  exit 1
fi

PORT="${PORT:-27180}"
URL="http://127.0.0.1:${PORT}/"

open_page() {
  if command -v open >/dev/null 2>&1 && open "$URL" 2>/dev/null; then
    return 0
  fi
  if osascript -e "open location \"$URL\"" >/dev/null 2>&1; then
    return 0
  fi
  echo "未能自动打开浏览器，请手动访问：$URL"
  return 1
}

if curl -s --max-time 1 "${URL}api/ping" >/dev/null 2>&1; then
  echo "工具已在运行，正在打开页面..."
  echo "$URL"
  open_page
  read -r -p "按回车键关闭窗口..."
  exit 0
fi

SKIP_AUTO_OPEN=1 "$NODE_BIN" "app/server.js" "$PORT" &
SERVER_PID=$!

STARTED=0
for i in $(seq 1 50); do
  if curl -s --max-time 1 "${URL}api/ping" >/dev/null 2>&1; then
    STARTED=1
    break
  fi
  sleep 0.2
done

if [ "$STARTED" = "1" ]; then
  echo "工具已启动，正在打开页面：$URL"
  open_page
else
  echo "服务启动失败，请查看上方错误信息；也可以手动访问：$URL"
fi

wait "$SERVER_PID"
echo
read -r -p "工具已退出，按回车键关闭窗口..."
