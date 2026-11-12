# Ordered figure workflow delivery / 顺序开发范围

Authorized 2026-11-13: complete 1 → 2 → 3, then stop for user review. A one-time
06:00 Asia/Shanghai continuation is scheduled in this chat. Resume actual unfinished
code; reuse completed checks. Do not expand scope or create recurring follow-ups.

## 1. Consistent figure styling

Use existing figure/chart contracts and rendering engines. Provide shared palette,
font size, line width and author-confirmed category order/color mapping across up
to four existing panels. Preserve data IDs/fields, titles, source values, annotations
and scientific meaning. Preview a bounded change list before apply, reject stale
previews, render changed panels atomically, support undo and project roundtrip.
Keep continuous heatmap colors separate from categorical group palettes.

## 2. Biodot reviewed local editing

Bounded node edits: color, label, move, alignment and display dimensions in the
illustration editor. Target explicit selection, preserve unselected nodes/relations,
source data and evidence. Local structured intent, optional existing reviewed local
model, no external real-data transmission. Show before/after changes and affected
IDs before confirmation; reject stale or out-of-bounds edits and protect verified
objects. Use the existing undo history. Never execute model-generated code.

## 3. Persistent high-throughput image presentation queue

User requirement: submit image processing jobs, unify style in batches, preserve
original data and labels, support retry/resume and isolated derived outputs.
Implement bounded local admission, one bounded worker, durable job state, atomic
outputs, independent failed-item retry, source/output hashes and operation manifest.
Use synthetic tests, including a finite 100-job recovery/failure scenario.

Scientific image pixels, display mapping and presentation are distinct. Default
image beautification means consistent frame, background, margins and separate
caption style; keep embedded source bytes/pixels and existing raster labels intact.
Do not recolor/repaint real microscopy or OCR-rewrite embedded labels. Native pixel
data remains in the original copy; any supported display conversion is recorded
and verified. Unsupported image types/planes are rejected clearly, never silently
flattened. No generative replacement of measured images. Further pixel-level
operations require a separate explicit, reviewable operation.

中文：按图版统一 → Biodot 局部修改 → 图片队列顺序完成。第三项支持提交任务、
统一风格高通量处理、保留原始数据和标签、独立派生结果、失败重试与重启恢复。
默认只美化展示层，不暗中改科研像素或嵌入标签；对不支持的类型明确报错。

All UI is English/简体中文 via Settings, default English. Keep spotlight unchanged.
No dependencies/services/model downloads, system changes, uploads of real data,
paid usage/resets, pushes or publication. User acceptance is never auto-approved.
Each stage ends with actual code, relevant tests and delivery evidence.

## Delivery status / 交付状态

All three bounded source slices are implemented and verified in order. See
FIGURE_WORKFLOW_DELIVERY.md for actual UI evidence, supported formats and limits.
User acceptance and a newly packaged installer remain pending. At the scheduled
06:00 continuation, inspect actual unfinished work; if this delivery has no new
feedback or blockers, stop without repeating passed checks or expanding scope.

三项限定范围已按序完成代码和相关验证，待用户验收。凌晨续接只处理真实剩余事项；
没有新增反馈或阻碍时停止，不重复验证，不自动增加功能。
