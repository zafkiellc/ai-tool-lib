#!/bin/bash
# ============================================================
# 抽卡建议分析器 · macOS 启动器（双击即可运行）
#   - 自动定位 python3（系统自带 / PATH 中的均可）
#   - 后台运行 launcher.py（隐藏控制台，启动后自动打开浏览器）
#   - 若未安装 Python 3，请先安装: https://www.python.org/downloads/
# ============================================================
cd "$(dirname "$0")" || exit 1

PY=""
if [ -x "runtime/python/bin/python3" ]; then
  PY="$(pwd)/runtime/python/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "未找到 Python 3，请先安装（https://www.python.org/downloads/）或将其加入 PATH。"
  read -r -p "按回车键退出…" _x
  exit 1
fi

# 后台启动（无控制台窗口），随后关闭本终端窗口
nohup "$PY" "$(pwd)/launcher.py" >/dev/null 2>&1 &
sleep 1
osascript -e 'tell application "Terminal" to close (every window whose name contains "start.command")' >/dev/null 2>&1 &
exit 0
