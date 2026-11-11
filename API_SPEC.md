# API 规范（阶段 2，v1）

- `GET /api/health`：返回本地服务状态与版本，不含设备或路径信息。
- `POST /api/datasets`：接收单个、最多 5 MB 的 CSV/XLSX 文件；数据只保留于本机服务会话内存。
- `GET /api/datasets/simulated.csv`：下载项目内置的模拟 CSV。
- `GET /api/datasets/simulated/preview`：返回受限行数的模拟数据预览与字段类型。
- `POST /api/renders`：接收已校验的 `ChartSpec`，由注册表选择已审核的散点、柱状、折线、箱线、热图或 `ecology_environment_gradient` 引擎；环境图只展示已有二维坐标、环境值或环境向量，不运行统计分析。
- `GET /api/renders/{id}.{svg|pdf|png}`：按已验证的 ChartSpec 导出本机内存中的图表。
- `POST /api/configs`、`GET /api/configs/{name}`：保存及加载版本化配置；仅保留至本机服务停止。

客户端不得传递任意服务器路径、命令或可执行代码。

## 阶段 4 增量（冻结 v1）

- POST /api/figures：FigureSpec 1.0，1–4 个 panels、1–2 columns、upper/lower/none 标签、统一主题与毫米尺寸/DPI。成功前完成三种格式渲染；错误返回 422/404。
- GET /api/figures/{id}.{svg|pdf|png}：下载已生成字节，PNG 预览使用同一路径。仅保留最近 8 次拼版。
- POST /api/figure-configs 与 GET /api/figure-configs/{name}：会话内保存/读取，记录 palette_version 与 category_order。

## 阶段 4A 增量（保持配置 v1）
- GET /api/datasets/{dataset_id}/preview：会话内数据预览，缺失返回 404，供配置恢复。
- POST /api/renders：全部三格式绘制完成才返回 201；数据/字段/绘图错误在创建时返回，不再推迟到下载时。
- GET /api/renders/{id}.{svg|pdf|png}：返回已缓存字节，不重新绘制；最近 8 次，过期返回 404。
- 新网页通过 Vite 同源 /api 代理连接固定 127.0.0.1:8000；代理开发与生产预览均只监听回环地址。

## 阶段 6C-6 增量（ChartSpec 1.2）

- `GET /api/datasets/simulated-ecology-spatial/preview`：返回原创合成空间点位表，不包含真实地点或底图。
- `POST /api/renders` 的 `ecology_spatial_points`：接收唯一点位标识、数值 X/Y、可选分组、明确的 WGS84 或平面坐标语义；只绘制已有点位，不重投影、不联网取图、不执行空间统计。
- WGS84 模式固定 `EPSG:4326`/`degrees` 并校验经纬度范围；平面模式要求非空坐标参考说明及 `m`、`km` 或 `arbitrary` 单位。
- `.bfsproj` 继续嵌入单个 CSV/XLSX 副本和完整 ChartSpec；栅格/矢量底图与多文件项目包不属于 1.2。
