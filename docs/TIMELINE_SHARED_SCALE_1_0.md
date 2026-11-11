# 共享尺度实验时间轴 · 数据契约 1.0

2026-11-10。面向本机、结构化、可编辑的实验流程时间轴。Science Farrell 2018 Fig. 1A 区分采样时刻与阶段，Science Hoagland 2025 Fig. 5A 在同一轴表示操作和持续处理，Science Grigoryan 2019 Fig. 4A 把同刻实验组置于同列；来源和图级许可边界见 `docs/CNS_DECADE_REVIEW_LEDGER.md`。只借鉴表达规则，不引入论文图像。

## IllustrationSpec 1.3 的可选字段

`timeline` 缺省表示旧项目或普通图示，保持原有打开和导出行为。若存在，仅用于 `experimental_workflow`，且与 `sections`、`flow_links` 互斥。

```json
{
  "version": "timeline-shared-scale/1.0",
  "unit": "day",
  "ticks": [{"id": "t_0", "day": 0, "label": "第 0 天"}],
  "groups": [{"id": "group_a", "label": "对照组", "sample_days": [0, 2, 9]}],
  "intervals": [{"id": "intervention_1", "group_id": "group_b", "start_day": 2, "end_day": 9, "label": "示例干预"}],
  "stages": [{"id": "stage_0", "start_day": 0, "end_day": 2, "label": "准备阶段"}]
}
```

首个入口支持 2–8 个严格递增的整数天数、两个具名组、每组显式采样时刻、一段具名干预和每对相邻刻度间一条显式阶段说明。所有采样和区间端点须落在刻度上。日期仅代表用户填的数值，不由输入文字推测科学事件。时间轴跨度最大 365 天；相邻刻度在固定版式中需有至少 48 px 距离，否则提示用户缩小范围或减少刻度，避免不可读标签。

坐标由 `(day - firstDay) / (lastDay - firstDay)` 映射到单条水平轴。两个组在同一时刻读取相同 x 坐标；采样标记、干预区间与阶段文字是独立对象。画布与导出 SVG 调用同一几何函数。相邻刻度标签距离较近时上下错行；轴刻度标签、组名、采样与区间仍保留可编辑 SVG 文字。页面可修改上述全部字段并重新应用，项目保存及重开后继续编辑。

合成验收：第 0、2、9 天，第 2–9 天干预；首段与次段像素距离比为 2:7。旧项目的结构、文字与导出不做迁移式修改。
