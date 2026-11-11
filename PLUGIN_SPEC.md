# 插件与适配器规范（草案 v1）

每个图表适配器必须声明：图表类型、数据要求、必填字段、参数模式、主题能力、支持导出格式、版本和审核状态。

统一接口：`validate_input`、`validate_parameters`、`render`、`export`、`warnings`。注册表决定引擎；网页只选择图表类型，不直接指定底层库。

## 阶段 6A 单细胞适配器

`embedding_categorical`、`embedding_continuous`、`feature`、`violin` 和 `dotplot` 接受 AnnData 已有的 `obsm` 坐标与明确选择的 `X`、`raw` 或 `layers` 表达矩阵。适配器只读取和绘制已有结果；缺少坐标、基因、字段或矩阵层时返回可操作错误，不自动降维、标准化、聚类或差异分析。


## 阶段 6B 组学适配器

- `spatial_categorical`、`spatial_continuous`、`spatial_feature`：读取 H5AD 已有 `obsm` 坐标和明确选择的表达矩阵。
- `genome_tracks`：读取 BED、bedGraph、GFF3/GTF、chrom.sizes 或受限 JSON manifest。
- `circos`：读取本地 JSON manifest 的 sectors、tracks 和 links。
- `dna_features`：读取单条 GenBank/GBK 序列和 feature。
- `r_ggplot`：读取 CSV/XLSX 的字段，通过固定 ggplot2 模板输出；不接收任意 R 代码。
- `ecology_composition`：读取 CSV/XLSX 群落组成长表，使用明确的 `sample`、`taxon` 和丰度字段绘制堆叠组成图；支持相对丰度分数或显式选择的原始计数归一化，不自动计算多样性或统计检验。
- `ecology_alpha_diversity`：读取 CSV/XLSX 中已有的样品、指标名和指标值；用户显式选择一个指标，适配器绘制箱线图及样品点，不计算 α 指标。
- `ecology_beta_ordination`：读取 CSV/XLSX 中已有的样品、二维排序坐标和可选分组；适配器绘制带样品标注的排序点图，不计算距离矩阵或排序坐标。
- `ecology_ordination_biplot`：读取已有样品与 taxon 的二维排序坐标，按可选分组绘制样品点，并从原点绘制 taxon 向量和标签；不计算排序、距离或显著性。
- `ecology_environment_gradient`：读取已有二维坐标与环境值或已有环境向量；不计算相关性、envfit、回归或显著性。
- `ecology_time_series`：读取已有原始观测、独立重复轨迹和可选非负对称误差；不聚合、平滑、插值、检验或建模。
- `ecology_spatial_points`：读取 WGS84 经纬度或带用户声明参考/单位的平面点位表，按可选分组着色；不导入底图、不重投影、不计算空间统计。

组学和生态适配器都在本机内存中工作，输入大小、序列长度、区间和 manifest 结构先校验，再调用绘图库。每个适配器当前支持 SVG、PDF、PNG；组学单图暂不进入 FigureSpec 1.0 拼版适配器，生态表格图继续支持最多四图的 FigureSpec 1.0 拼版。

## 阶段 6D 图版导出器

表格与生态拼版升级到向后兼容的 `FigureSpec 2.0`，增加显式边距、间距、标签、共享图例、审核字体、色板版本和通用布局模板。图版导出器支持 PNG、TIFF、SVG、PDF，并在发布缓存前完成尺寸、像素、字体、图例兼容与固定画布边界检查。组学单图仍不自动纳入拼版；TIFF 是普通无损科研栅格，不是 GeoTIFF。详细规范见 `docs/PHASE6D_SCOPE.md`。

## 阶段 7A 图示组件注册表

图示组件不作为 ChartSpec 图表适配器运行，使用独立 `IllustrationSpec 1.0` 与静态审核注册表。注册项必须声明 `component_id`、中英文名称、版本、原创/外部来源、作者、许可证标识、证据说明、科学含义边界、默认尺寸、可覆盖样式和固定锚点。外部素材证据不完整时不得注册。7A 只注册项目原创内联 SVG 几何，不加载远程资源、不接收任意 SVG/HTML 或执行组件代码；详细边界见 `docs/PHASE7A_SCOPE.md`。

## 阶段 7B 图示画布项目

完整画布使用 `IllustrationSpec 1.1`，继续复用 7A 静态注册表；1.0 项目经显式迁移补入网格设置与 `orthogonal` 路由。节点旋转、尺寸和旋转后边界必须由前后端同构校验；连线只保存受控端点与路由枚举，不保存用户 SVG path。视口、选择和撤销历史不属于可移植项目。详细规范见 `docs/PHASE7B_SCOPE.md`。

## 阶段 7C 机制图结构

机制图使用 `IllustrationSpec 1.2`，在八个审核组件上增加用户选择的受控实体类型、六类受控关系和项目级证据记录。结构校验不执行数据库查询、关系推断或科学真实性判断；`verified` 必须引用用户录入的证据。内置模板只展开无关系的示意占位节点，不作为组件、插件或科学来源注册。详细边界见 `docs/PHASE7C_SCOPE.md`。

## 阶段 7D 图形摘要与实验流程

`IllustrationSpec 1.3` 增加文档模式、摘要面板/实验步骤和独立流程顺序箭头。流程箭头只表示用户明确指定的展示顺序，不能作为六类机制科学关系或证据使用；模板只展开原创空白分区。项目迁移、校验、导出和资源上限见 `docs/PHASE7D_SCOPE.md`。
