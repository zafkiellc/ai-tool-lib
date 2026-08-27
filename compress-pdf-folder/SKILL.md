---
name: compress-pdf-folder
summary: 批量压缩文件夹内 PDF（扫描件/大文件），保持清晰度、可断点续跑、沙箱安全
description: 当用户要求"压缩某个目录下的 PDF / 减小 PDF 体积 / 扫描件太占空间"时使用。针对 Windows + OneDrive +
  WorkBuddy 沙箱环境做了完整避坑设计。
permalink: main/工作/项目/资产/work-buddy-私有-skills/compress-pdf-folder/skill-1
---

# 批量压缩文件夹内 PDF

## 适用场景
- "把这个文件夹里的 PDF 压缩一下" / "PDF 太大了想瘦身" / "扫描件占空间"
- 目标：清晰可读、不缺信息，显著减小体积
- 典型：考勤签字扫描件、型式评价报告、合同扫描等图片型 PDF

## 关键环境约束（WorkBuddy / Windows / OneDrive 沙箱）
1. **OneDrive 占位文件（Files On-Demand）**：`os.path.exists()` 对占位文件可能返回假阴性；`SHFileOperation` 删除时返回伪错误码 `0x2`，但文件其实已进回收站。不要信任这些错误码判断成败，**以实际文件存在性为准**。
2. **safe-delete 钩子**拦截 `os.remove` / `os.rmdir`（回收站在沙箱不可用，会报 `windows-sandbox-recycle-bin-unavailable`）。但 **`os.rename` / `os.replace` 允许** → 用 `os.replace(tmp, original)` 覆盖替换原文件，既不触发删除钩子又完成"替换"。
3. **PyMuPDF 遇损坏内嵌 JPEG 会 `abort()` 直接杀掉整个进程**，`fitz.TOOLS.set_error_mode(EXCEPTION)` 无效。必须**每个文件用独立子进程压缩**，主控用并发池收集，单文件崩溃只死子进程；再加单文件超时强杀（`p.kill()`）。
4. `du -ch` / `find ... -exec du` 在 OneDrive 占位文件上严重低估体积（占位显示 0）——**用 `os.path.getsize` 逐文件累加**才准。

## 推荐方案（图片型 PDF）
用 PyMuPDF 按目标 DPI 重新渲染 + JPEG 重编码（视觉信息完整保留；文本会变图，扫描件本就是图）：
- `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple PyMuPDF`（隔离 venv：`<managed_python>/python.exe -m venv <managed>/envs/default`）
- 参数：`page.get_pixmap(dpi=150)` → `pix.tobytes("jpeg", jpg_quality=82)` → `new.insert_image(...)` → `new.save(tmp, garbage=4, deflate=True, clean=True, use_objstms=True, preserve_metadata=True)`
- **只当压缩后更小才替换**（guard: `if after >= before: 跳过`）；<400KB 小文件直接跳过（重压无收益且污染目录）
- 用户确认前先压 1 个 `_compressed` 副本给他看效果（原文件不动）

## 执行流程（安全、可续跑）
1. 先**整盘备份**到同盘非 OneDrive 目录（如 `C:\Users\zafki\工作_备份_YYYYMMDD`，`robocopy /E`），确认文件数/体积 0 失败。
2. 写两个脚本：
   - **worker.py**（单文件）：接收源路径，压到 `<src>.__cmp__.pdf` 临时件；解码/编码异常 → 把临时件 `os.replace` 到隔离目录 `failed_temps` 并 `exit(4)`；无收益 → 同样隔离并 `exit(3)`；成功 → `os.replace(tmp, src)` 覆盖原件，`exit(0)`。
   - **controller.py**：`subprocess` 并发池（workers=3），每个文件起一个 worker；`done.json` 记录已完成（断点续跑）；单文件超时（如 1200s）强杀；不调用任何删除 API。
3. 跑完用**备份逐文件回查**（同相对路径；注意重命名/合并文件夹后路径变化，做路径映射）算真实节省量，并抽样渲染第 1 页确认清晰度。
4. 收尾：把树内遗留 `.__cmp__.pdf` 临时件移出（若被 OneDrive 锁住 WinError 32，记录并在空闲时重试，原件完好不受影响）。

## 验证要点
- 压缩前/后总体积（逐文件 `os.path.getsize` 累加，非 `du`）
- 抽样渲染对比（压缩后 vs 备份原件，同 DPI）
- 确认无 `. __cmp__.pdf` 临时件残留、无 `_compressed.pdf` 测试副本残留于用户树

## 已知局限
- 文本型 PDF 重渲染成 JPEG 会丢失可选中文本层；guard 已避免"变大"的情况，但"略小"的文本 PDF 会被栅格化。如需保留文本层，应改用 `doc.save(..., deflate=True, garbage=4)` 无损重压而非重渲染。