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

const catalogEnglish: Record<string, string> = {
  '空间组学': 'Spatial omics',
  '已有空间坐标、组织切片和表达结果': 'Existing spatial coordinates, tissue sections, and expression results',
  'H5AD · 空间坐标 · Feature Plot': 'H5AD · Spatial coordinates · Feature Plot',
  '基因组轨道': 'Genome tracks',
  '基因注释、区间和连续信号轨道': 'Gene annotations, intervals, and continuous signal tracks',
  'Circos 环形图': 'Circos plots',
  '染色体、数值轨道和关系连接': 'Chromosomes, numeric tracks, and links',
  '本地 JSON manifest': 'Local JSON manifest',
  'DNA / 质粒': 'DNA / plasmids',
  '序列特征、方向和注释标签': 'Sequence features, directions, and annotation labels',
  'R 绘图库': 'R plotting',
  '用已审核的 ggplot2 模板输出静态图': 'Static plots from reviewed ggplot2 templates',
  '空间分类': 'Spatial categories',
  '空间连续值': 'Spatial continuous values',
  '空间 Feature Plot': 'Spatial Feature Plot',
  '群落组成': 'Community composition',
  '物种丰度、相对丰度和样品组成': 'Taxon abundance, relative abundance, and sample composition',
  'CSV · XLSX · 物种矩阵': 'CSV · XLSX · Taxon matrix',
  'α / β 多样性': 'Alpha / beta diversity',
  '已有 Shannon、Simpson、PCoA 和 NMDS 结果': 'Existing Shannon, Simpson, PCoA, and NMDS results',
  'CSV · XLSX · 已有指标 · 排序坐标': 'CSV · XLSX · Existing metrics · Ordination coordinates',
  '排序与群落结构': 'Ordination and community structure',
  '已有二维排序坐标与物种向量': 'Existing 2D ordination coordinates and taxon vectors',
  '环境梯度': 'Environmental gradients',
  '已有二维坐标与环境值或环境向量': 'Existing 2D coordinates and environmental values or vectors',
  'CSV · XLSX · 环境字段': 'CSV · XLSX · Environmental fields',
  '生态时间序列': 'Ecological time series',
  '原始观测、独立重复轨迹和已有误差': 'Observations, independent replicate trajectories, and supplied errors',
  'CSV · XLSX · 数值时间': 'CSV · XLSX · Numeric time',
  '空间生态': 'Spatial ecology',
  '已有采样点的经纬度或平面坐标': 'Existing sample-point geographic or planar coordinates',
  'CSV · XLSX · 经纬度 / 平面坐标': 'CSV · XLSX · Geographic / planar coordinates',
}

/** Localize display labels while retaining original catalog exports and IDs. */
export function getWorkflowCatalog(t: (zh: string, en: string) => string) {
  const fields = <K extends string>(catalog: Record<K, { title: string; description: string; formats: string }>) =>
    Object.fromEntries(Object.entries(catalog).map(([key, raw]) => {
      const entry = raw as { title: string; description: string; formats: string }
      return [key, {
        title: t(entry.title, catalogEnglish[entry.title] ?? entry.title),
        description: t(entry.description, catalogEnglish[entry.description] ?? entry.description),
        formats: t(entry.formats, catalogEnglish[entry.formats] ?? entry.formats),
      }]
    })) as Record<K, { title: string; description: string; formats: string }>
  return {
    omicsDirections: fields(omicsDirections),
    ecologyDirections: fields(ecologyDirections),
    spatialKinds: Object.fromEntries(Object.entries(spatialKinds).map(([key, text]) => [key, t(text, catalogEnglish[text] ?? text)])),
  }
}
