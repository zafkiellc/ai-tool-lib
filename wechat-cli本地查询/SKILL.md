---
name: wechat-cli 本地微信数据查询
description: macOS 上查询本地微信数据（聊天记录/联系人/会话/收藏/未读等）的 CLI 工具，用于工作核查。直接读本地微信数据库，无需联网/登录态。
agent_created: true
created_by: WorkBuddy(吕晨) / 收口 Hermes(软路由) / 源码迁入 mac/WorkBuddy
created_at: 2026-08-27
permalink: main/工作/项目/资产/ai-工具库/wechat-cli本地查询/skill
---

# wechat-cli 本地微信数据查询

> 注：`references/原笔记.md` 为早期基于 "pip 第三方包" 的误记，本文件为唯一准确来源。

## Overview
macOS 上查询**本地微信数据**（聊天记录、联系人、会话、收藏、未读等）的 CLI 工具，用于工作核查。
- **真实实现**：Node 版 `@canghe_ai/wechat-cli` v0.2.4（日常用的就是它，**不是** pip 那个 Python 包 `wechat_cli`）。
- 上游仓库：`https://github.com/freestylefly/wechat-cli`（Apache-2.0，公开）。
- 运行机制：JS 入口 `bin/wechat-cli.js` 按平台解析**原生二进制** `@canghe_ai/wechat-cli-<platform>` 并 `execFileSync` 调用；真正读写微信数据的是那个原生二进制。
- 直接读本地微信数据，**无需联网 / 登录态**。已在多次核查任务中复用（如「厕所水枪安装核实」）。
- 平台：macOS Apple Silicon / arm64。Windows / Linux 也有对应原生二进制包（npm 安装时自动拉取）。

## 用法
### A. 库内离线运行（Mac，推荐，无需 npm 安装）
原生二进制已固化进库，直接指定即可：
```bash
export WECHAT_CLI_BINARY="$LIB/wechat-cli本地查询/scripts/wechat-cli/node_modules/@canghe_ai/wechat-cli-darwin-arm64/bin/wechat-cli"
node "$LIB/wechat-cli本地查询/scripts/wechat-cli/bin/wechat-cli.js" <子命令> [参数]
```
> `$LIB` = vault 内 `工作/项目/资产/AI工具库`。
> 首次使用需 `init` 提取密钥（见下）。

### B. 本机日常入口（Mac，已配置）
日常直接敲 `wechat-cli <子命令>` 即可——Mac 端 venv 的 `bin/wechat-cli` 是个重定向，调用 WorkBuddy node workspace 里装的 Node 版。
- 运行实例路径：`~/.workbuddy/binaries/node/workspace/node_modules/@canghe_ai/wechat-cli`（**日常依赖，勿删**；库内 `scripts/` 副本为版本化真源）。

### C. 其他端安装
```bash
npm install -g @canghe_ai/wechat-cli   # 自动拉取对应平台原生二进制（win32-x64 / linux-x64 / darwin-x64 ...）
```

## 子命令速查
| 子命令 | 说明 |
|--------|------|
| `init` | 首次使用：提取微信密钥并生成 config.json |
| `sessions` | 最近会话列表（`--limit N`） |
| `history "张三"` | 指定聊天的消息记录（`--limit` / `--start-time`） |
| `search "关键词"` | 搜索消息（`--chat 群名` 限定范围 / `--limit`） |
| `contacts --query "李"` | 搜索 / 列出联系人 |
| `members` | 查询群聊成员列表 |
| `new-messages` | 获取自上次调用以来的增量新消息 |
| `unread` | 查看未读会话 |
| `favorites` | 查看微信收藏 |
| `export` | 导出聊天记录为 markdown / 纯文本 |
| `stats` | 聊天统计分析 |

## 依赖
- Node.js >= 14（Mac 端用 WorkBuddy 管理的 Node 22）。
- 平台原生二进制 `@canghe_ai/wechat-cli-darwin-arm64`（**已固化在 `scripts/wechat-cli/node_modules/@canghe_ai/`**，离线可用；也可 `npm install` 重新拉取）。
- macOS 需授予**完全磁盘访问权限**（Full Disk Access）以读取微信本地数据库——WorkBuddy 终端已获此权限。

## 注意事项 / 坑
- **源码真相**：本工具是公开 npm 包（非私有），库内 `scripts/wechat-cli/` 是其镜像 + 固化原生二进制，构成自包含可运行副本（任何 Mac 端离线即可跑）。
- `WECHAT_CLI_BINARY` 环境变量可覆盖二进制路径（调试 / 换平台时用）。
- 首次必须 `init` 提取密钥；机器未授权全盘访问会读不到数据。
- **不要删除** Mac 本机 WorkBuddy node workspace 里的运行实例（日常 `wechat-cli` 命令依赖它）。

## 改造记录
见 `MANIFEST.json` 的 `changelog`。
