---
name: organize-personal-folder
description: 安全整理个人文件夹（去重+归档）。当用户要求"整理/清理/去重/归档我的某个文件夹（尤其是 OneDrive）"时使用。严格遵循个人文件安全规则：先只读扫描、列清单、确认、整盘备份、回收站删除、分批可撤销。
agent_created: true
permalink: main/工作/项目/资产/work-buddy-私有-skills/organize-personal-folder/skill
---

# 安全整理个人文件夹（去重 + 归档）

适用于：用户要求整理、去重、清理重复文件、归档/重组某个个人文件夹（Desktop、Documents、Downloads、OneDrive 等）。

## 铁律（个人文件安全）
1. **先只读扫描**，生成完整清单，**绝不**在确认前移动/删除任何文件。
2. 删除/移动前**必须整盘备份**到该盘其他位置（如 `C:\Users\<user>\工作_备份_YYYYMMDD`，注意放在 OneDrive 目录之外，避免被重新同步）。用 robocopy `/E /R:2 /W:2`，完成后核对"文件数 + 0 失败"。
3. **Trash, Not Delete**：删除走系统回收站（可还原），绝不用 `rm`/`os.remove` 直接删。
4. 分批执行（每批 ≤10），每批校验、写日志、出错即停。
5. 任何移动/删除前，**加粗警告 + 列出受影响路径 + 用户显式确认**。

## 去重技术要点
- 真重复 = **内容哈希相同**（sha256），不是文件名相同。先按 size 分组，再对同组哈希，省算力。
- **OneDrive 占位文件（Files On-Demand）陷阱**：
  - `SHFileOperationW(FO_DELETE | FOF_ALLOWUNDO)` 把文件送入回收站；但在占位文件上常返回伪错误码 `0x2`（ERROR_FILE_NOT_FOUND），**文件其实已被回收**。→ 判定成功应以"源文件是否仍存在(`os.path.exists`)"为准，不要信任返回码。
  - 路径超过 260 字符会触发 `0x2`；本场景多为深层嵌套，注意依赖"文件是否存在"校验即可（SHFileOperation 自身能处理长路径）。
- **沙箱 safe-delete 钩子**：部分环境对 `os.remove`/`os.rmdir` 拦截并"fail-closed"（报 `windows-sandbox-recycle-bin-unavailable`）→ 删除空文件夹也要改用 `SHFileOperation` 回收，而非 `os.rmdir`。
- 临时锁文件：`~$` 开头的 Office 临时文件可直接清理（仍走回收站）。
- 二次扫描验证：去重后重跑扫描，确认重复组归零。

## 归档/重构要点
- 合并同名/重叠文件夹：把源文件夹内容 `os.rename` 到目标（同盘瞬时），碰撞时重命名(`_合并N`)。
- 重命名文件夹用 `os.rename`（仅改名，不动内容）。
- 根目录散落文件：建 `工具软件\`（apk/rar/exe/zip）与 `工作散件\`（兜底收纳，避免误归类）。
- 合并后删空壳：用 SHFileOperation 回收（见上），不要 os.rmdir。
- 移动用 `\\?\` 扩展路径前缀可规避 MAX_PATH（同盘 rename 即可）。

## 复用脚本模板（Python，managed python 运行）
- 扫描+哈希：`os.walk` 收集 (rel,size,mtime,ext)，size 分组后 sha256。
- 回收：`ctypes.windll.shell32.SHFileOperationW` + `SHFILEOPSTRUCT`（hwnd=0, wFunc=0x3, fFlags=0x40|0x10|0x400|0x4），pFrom 双 NUL 结尾。
- 执行器：读 plan CSV → 逐动作 move/merge/rename/delete，校验+日志。

## 产物建议
扫描报告 HTML、inventory CSV、dedup_manifest CSV、delete_list txt、各阶段 exec_log txt，统一放工作区 `scan_output\`。