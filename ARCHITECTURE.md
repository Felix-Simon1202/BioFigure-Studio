# 架构

```text
React + TypeScript 网页界面
          │ HTTP（仅 127.0.0.1）
FastAPI 接口层
          │
核心服务：数据校验 / ChartSpec 解析 / 任务状态
          │
注册表 → Matplotlib/Seaborn 适配器 → 导出器
```

核心绘图逻辑不依赖网页或 FastAPI 请求对象，以便后续桌面端复用。

建议目录：`apps/web`、`backend/{api,core,data,registry,adapters,themes,exporters}`、`packages/{schemas,color-tools}`、`tests`、`docs`、`examples`。
