#!/usr/bin/env bash
# deploy-gitea.sh — 在软路由(iStoreOS)起 Gitea(rootless 版, SQLite)
# 用法（路由器 SSH 内执行）：
#   bash /mnt/nvme0n1-1/同步文件/verysyncdown/zafkiel个人知识库/工作/项目/资产/AI工具库/_infra/gitea-deploy.sh
# 注意: iStoreOS 无 uid1000 时普通镜像会因 root 检查崩溃, 必须用 rootless 镜像,
# 且数据挂载到 /var/lib/gitea (rootless 镜像内部路径, 非 /data), app.ini 需 bind 到 /etc/gitea/app.ini 并属主 git。
set -e

GITEA_DIR=/mnt/nvme0n1-1/Configs/gitea
DATA_DIR=/mnt/nvme0n1-1/gitea
CONF_DIR=$DATA_DIR/gitea/conf

mkdir -p "$GITEA_DIR" "$DATA_DIR" "$CONF_DIR"

# 1) app.ini: 预置 INSTALL_LOCK=true + 默认管理员, 让 Gitea 以"已安装"模式启动并自动建管理员
cat > "$CONF_DIR/app.ini" <<'INI'
APP_NAME = zafkiel-ai-tools
RUN_USER = git
RUN_MODE = prod
[database]
DB_TYPE = sqlite3
PATH = /var/lib/gitea/gitea.db
[server]
ROOT_URL = https://git.zafkiel.com.cn/
SSH_DOMAIN = git.zafkiel.com.cn
HTTP_PORT = 3000
PROTOCOL = http
[security]
INSTALL_LOCK = true
[admin]
DEFAULT_ADMIN_NAME = zafkiel
DEFAULT_ADMIN_EMAIL = zafkiel@zafkiel.com.cn
DEFAULT_ADMIN_PASSWORD = GiteaInit@2026
INI
chown -R 1000:1000 "$DATA_DIR"

# 2) compose: rootless 镜像, 挂载数据到 /var/lib/gitea, app.ini bind 到 /etc/gitea/app.ini
cat > "$GITEA_DIR/docker-compose.yml" <<'YAML'
version: "3"
services:
  gitea:
    image: gitea/gitea:1.22-rootless
    container_name: gitea
    environment:
      - GITEA__database__DB_TYPE=sqlite3
    volumes:
      - /mnt/nvme0n1-1/gitea:/var/lib/gitea
      - /mnt/nvme0n1-1/gitea/gitea/conf/app.ini:/etc/gitea/app.ini
    ports:
      - "3000:3000"
    restart: unless-stopped
YAML

cd "$GITEA_DIR"
docker compose up -d
echo "Gitea(rootless) 启动中... 访问 http://192.168.100.1:3000 即见已初始化实例(管理员 zafkiel)"
echo "若需改管理员密码: docker exec gitea gitea admin user change-password -u zafkiel -p <新密码>"
