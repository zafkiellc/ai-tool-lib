---
name: 迁移回报目录说明
type: note
permalink: main/工作/项目/资产/ai-工具库/迁移回报/README
---

# 迁移回报目录

各端 AI 完成 `各端工具迁移提示词.md` 的迁移后，把回报写进本目录，文件名 `<端名>__<AI名>.md`（如 `desktop__codex.md`、`mac__workbuddy.md`、`dsh__deepseek.md`）。

## 回报格式（直接复制填写）

```markdown
---
name: <端名>__<AI名> 迁移回报
type: note
permalink: main/工作/项目/资产/ai-工具库/迁移回报/<端名>__<AI名>
---

# <端名> / <AI名> 迁移回报

- 迁移端：<端名> / <AI名>
- 本机扫描到的成品工具：<清单>
- 已迁入 AI工具库：
  - <工具名> → AI工具库/<工具名>/（含 scripts：是/否，源码位置：<本机路径>）
- 保持原位 + 双链：<私人向清单>
- 跳过 / 未动：<原因>
- git commit：<hash>
- push：gitea <成功/失败> / github <成功/失败>
- 遗留问题：<如有>

## 确认项
- [ ] 源码已复制进 AI工具库/<工具名>/scripts/（非仅文档入口）
- [ ] 已 `git add <工具目录>`（未用 git add . / -A）
- [ ] 已 claim + release 锁
- [ ] 未替其他端 commit/push
```

路由端（Hermes）会读取本目录各文件，更新 `../迁移状态看板.md` 并逐一确认。
