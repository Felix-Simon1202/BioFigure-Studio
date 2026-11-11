# 阶段 4 配色审核（2026-09-13）

| 资源 / 版本 | 证据与再分发事项 | 本次决定 |
| --- | --- | --- |
| Clay / Lagoon 1.0 | backend/themes/palettes.py 固定 RGB 表，本项目新编配色，未采样画作、论文图或图片，随项目授权；项目尚未确定对外发布许可证 | 本机启用，不宣称期刊官方或色盲认证 |
| Matplotlib 3.11.2 内置 Viridis / Coolwarm | 已安装发行物元数据与 LICENSE 实物；https://matplotlib.org/stable/project/license.html 作为官方说明。再分发保留许可证和版权声明，修改其代码时记录变更 | 沿用已锁定依赖，不下载新引擎；相关性范围 -1 至 1、中心 0；Viridis 连续、Coolwarm 发散 |
| d3-scale-chromatic v3.1.0 | https://github.com/d3/d3-scale-chromatic/blob/v3.1.0/LICENSE ，ISC，要求保留版权和许可声明 | 不引入：现有渲染需求不需要额外 JS 色板依赖；未下载运行其代码 |
| pals 候选（main，未固定发布版） | https://github.com/kwstat/pals/blob/main/LICENSE.note 表明集合内不同色板有独立许可证 | 不引入：未完成逐色板、固定发布版审核，不能用整体 MIT 代替资源审查 |

## 本地证据

- licenses/matplotlib-3.11.2-LICENSE.txt：从已安装 3.11.2 发行物复制，SHA256 `822e8e528147569a41975592aee19c11992ab667ba50451cd929031d5fc74491`。
- licenses/DejaVu-LICENSE.txt：默认字体随 Matplotlib 提供，保留完整声明，SHA256 `d75938dec098f06f0ac3c00853065d94f020be1c3c62ef1dc2975ba15b4d9b0e`。
- 没有新增运行时依赖、字体文件或图片素材。此审核不代替未来完整发行包的传递依赖/字体审核。

## 语义与已知限制

分类色用于类别区分。相关性热图禁止 Clay/Lagoon，网页选择分类色时热图明确回退到 Coolwarm。分类图可将 Viridis/Coolwarm 等间隔采样为分类色，不暗示类别间连续数值关系。
同一拼版、同一分组字段和同色板的散点/折线共享保存的类别顺序；不同色板的子图有意使用不同配色。箱线/柱状按 X 轴分组，未实现任意自定义类别映射编辑器。
现有默认 DejaVu 不覆盖所有中文字符；中文图内文字还需经审核的 CJK 字体方案，当前不宣称完整支持。网页中文不受影响。
