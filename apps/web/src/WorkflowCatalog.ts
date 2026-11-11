export type OmicsDirection = 'spatial' | 'genome' | 'circos' | 'dna' | 'r'
export type EcologyDirection = 'community' | 'diversity' | 'ordination' | 'environment' | 'time' | 'spatial'

export const omicsDirections: Record<OmicsDirection, { title: string; description: string; formats: string }> = {
  spatial: {
    title: '空间组学',
    description: '已有空间坐标、组织切片和表达结果',
    formats: 'H5AD · 空间坐标 · Feature Plot',
  },
  genome: {
    title: '基因组轨道',
    description: '基因注释、区间和连续信号轨道',
    formats: 'BED · bedGraph · GFF3 · GTF · JSON',
  },
  circos: {
    title: 'Circos 环形图',
    description: '染色体、数值轨道和关系连接',
    formats: '本地 JSON manifest',
  },
  dna: {
    title: 'DNA / 质粒',
    description: '序列特征、方向和注释标签',
    formats: 'GenBank · GBK',
  },
  r: {
    title: 'R 绘图库',
    description: '用已审核的 ggplot2 模板输出静态图',
    formats: 'CSV · XLSX · R 4.6 + ggplot2',
  },
}
export const spatialKinds: Record<string, string> = {
  spatial_categorical: '空间分类',
  spatial_continuous: '空间连续值',
  spatial_feature: '空间 Feature Plot',
}
export const ecologyDirections: Record<EcologyDirection, { title: string; description: string; formats: string }> = {
  community: {
    title: '群落组成',
    description: '物种丰度、相对丰度和样品组成',
    formats: 'CSV · XLSX · 物种矩阵',
  },
  diversity: {
    title: 'α / β 多样性',
    description: '已有 Shannon、Simpson、PCoA 和 NMDS 结果',
    formats: 'CSV · XLSX · 已有指标 · 排序坐标',
  },
  ordination: {
    title: '排序与群落结构',
    description: '已有二维排序坐标与物种向量',
    formats: 'CSV · XLSX · PCoA · NMDS',
  },
  environment: {
    title: '环境梯度',
    description: '已有二维坐标与环境值或环境向量',
    formats: 'CSV · XLSX · 环境字段',
  },
  time: {
    title: '生态时间序列',
    description: '原始观测、独立重复轨迹和已有误差',
    formats: 'CSV · XLSX · 数值时间',
  },
  spatial: {
    title: '空间生态',
    description: '已有采样点的经纬度或平面坐标',
    formats: 'CSV · XLSX · 经纬度 / 平面坐标',
  },
}
