#!/usr/bin/env bash
# deploy-gitea.sh — 在软路由(iStoreOS)起 Gitea(SQLite 版)
# 用法（路由器 SSH 内执行）：
#   bash /mnt/nvme0n1-1/同步文件/verysyncdown/zafkiel个人知识库/工作/项目/资产/AI工具库/_infra/gitea-deploy.sh
set -e

GITEA_DIR=/mnt/nvme0n1-1/Configs/gitea
DATA_DIR=/mnt/nvme0n1-1/gitea
HOST_PORT=3000

mkdir -p "$GITEA_DIR" "$DATA_DIR"

cat > "$GITEA_DIR/docker-compose.yml" <<'YAML'
version: "3"
services:
  gitea:
    image: gitea/gitea:1.22
    container_name: gitea
    environment:
      - USER_UID=0
      - USER_GID=0
      - GITEA__database__DB_TYPE=sqlite3
      - GITEA__server__ROOT_URL=https://git.zafkiel.com.cn/
      - GITEA__server__SSH_DOMAIN=git.zafkiel.com.cn
      - GITEA__server__PROTOCOL=http
      - GITEA__server__HTTP_PORT=3000
      - GITEA__security__INSTALL_LOCK=false
    volumes:
      - /mnt/nvme0n1-1/gitea:/data
    ports:
      - "3000:3000"
    restart: unless-stopped
YAML

cd "$GITEA_DIR"
docker compose up -d
echo "Gitea 启动中... 稍后访问 http://192.168.100.1:3000 完成初始化(注册管理员 zafkiel, 建空仓 ai-tool-lib)"
echo "注意: 初始化时 基础URL 填 https://git.zafkiel.com.cn/ (反代就绪后)"
