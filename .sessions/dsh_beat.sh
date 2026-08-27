#!/usr/bin/env bash
# dsh_beat.sh — 让 DeepSeek Harness (dsh) 侧一键注册共享会话索引
#
# 用法（在 DSH 运行环境内执行）：
#   bash /workspace/同步文件/verysyncdown/zafkiel个人知识库/工作/项目/资产/AI工具库/.sessions/dsh_beat.sh "当前任务描述"
#
# 说明：
# - DSH 容器内 vault 挂载点是 /workspace/同步文件/verysyncdown/zafkiel个人知识库/...
#   （与 Hermes 软路由容器同挂载；底层是同一份磁盘，verysync 同步后 .sessions/ 同一份）。
# - 脚本调用同目录的 sessionctl.py，写出 dsh__deepseek.json（只写自己、只读别人）。
# - 改造工具前：python3 .sessions/sessionctl.py who-has --tool <工具名>
#   被锁则停下等释放；FREE 则 claim；改完 release。
set -e
TASK="${1:-DSH 开工心跳}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."   # 切到 AI工具库 根，sessionctl.py 依赖此相对位置
python3 .sessions/sessionctl.py beat --endpoint dsh --ai deepseek --session "${DSH_SESSION_ID:-dsh-online}" --task "$TASK"
echo "DSH 会话已注册。其他端可用 view 看到本条目。"
