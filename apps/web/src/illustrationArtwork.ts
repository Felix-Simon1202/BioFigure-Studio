/** Original textbook-informed schematic vectors, not reproduced textbook figures. */
import type { ComponentDefinition, ComponentId } from './illustration'

export const COMPONENT_ARTWORK_VERSION = '2.0'
type Primitive = { tag: 'path' | 'ellipse' | 'circle' | 'rect' | 'line'; attrs: Record<string, string | number> }
const ink = '#4b5563'
const path = (d: string, fill = 'none', stroke = ink, strokeWidth = 2): Primitive =>
  ({ tag: 'path', attrs: { d, fill, stroke, strokeWidth, strokeLinecap: 'round', strokeLinejoin: 'round' } })
const ellipse = (cx: number, cy: number, rx: number, ry: number, fill: string, stroke = ink, strokeWidth = 2): Primitive =>
  ({ tag: 'ellipse', attrs: { cx, cy, rx, ry, fill, stroke, strokeWidth } })
const circle = (cx: number, cy: number, r: number, fill: string, stroke = ink, strokeWidth = 1.5): Primitive =>
  ({ tag: 'circle', attrs: { cx, cy, r, fill, stroke, strokeWidth } })
const rect = (x: number, y: number, width: number, height: number, rx: number, fill: string, stroke = ink): Primitive =>
  ({ tag: 'rect', attrs: { x, y, width, height, rx, fill, stroke, strokeWidth: 2 } })
const tint = (hex: string, white: number) => '#' + [1, 3, 5].map(i =>
  Math.round(parseInt(hex.slice(i, i + 2), 16) * (1 - white) + 255 * white).toString(16).padStart(2, '0')).join('')
const dots = (points: number[][], fill: string, r = 2) => points.map(([x, y]) => circle(x, y, r, fill, 'none'))
const nucleus = (x: number, y: number, rx = 23, ry = 18) => [
  ellipse(x, y, rx, ry, '#e8e1f4', '#8e80a9', 1.6),
  ellipse(x, y, rx - 3, ry - 3, 'none', '#b9add0', 1),
  circle(x + 6, y - 2, 5, '#a891c4', 'none'),
  path(`M${x - 12} ${y - 5} q8 -7 12 3 t9 1 M${x - 9} ${y + 7} q7 -5 12 0`, 'none', '#b9add0', 1.2),
]
const mito = (x: number, y: number, w = 38, h = 20) => [
  ellipse(x, y, w / 2, h / 2, '#f7ded1', '#b67c65', 1.3),
  path(`M${x - w / 3} ${y} q4 -7 8 0 t8 0 t8 0`, 'none', '#b67c65', 1.3),
]
const membrane = (width: number, y: number) => Array.from({ length: Math.floor((width - 12) / 10) }, (_, i) => {
  const x = 10 + i * 10
  return [path(`M${x - 2} ${y + 4} v8 M${x + 2} ${y + 4} v8 M${x - 2} ${y + 24} v-8 M${x + 2} ${y + 24} v-8`, 'none', '#a2aeb9', 1),
    circle(x, y, 3.6, '#d9e2eb', '#7a8b9d', 1), circle(x, y + 28, 3.6, '#d9e2eb', '#7a8b9d', 1)]
}).flat()

const entry = (id: ComponentId, name: string, english: string, meaning: string, meaning_en: string,
  category: 'cells' | 'organelles' | 'molecules', width: number, height: number, fill: string): ComponentDefinition =>
  ({ id, name, english, meaning, meaning_en, category, width, height, fill, version: '1.0', source: 'BioFigure Studio 原创', license: '项目许可证' })

export const additionalComponents: ComponentDefinition[] = [
  entry('cell_animal', '动物细胞', 'Animal cell', '教学式动物细胞剖面；内部结构不按比例', 'Schematic animal cell cutaway; structures are not to scale.', 'cells', 190, 130, '#b9d8e5'),
  entry('cell_plant', '光合植物细胞', 'Photosynthetic plant cell', '示意细胞壁、中央液泡和叶绿体；并非所有植物细胞均有叶绿体', 'Cell wall, central vacuole and chloroplasts; not every plant cell has chloroplasts.', 'cells', 190, 130, '#bdd6a8'),
  entry('cell_bacterium', '杆状细菌', 'Rod-shaped bacterium', '无膜包裹细胞核；鞭毛为部分细菌具有的示意结构', 'Nucleoid without a membrane-bound nucleus; the illustrated flagellum is not universal.', 'cells', 190, 130, '#d7bf91'),
  entry('cell_neuron', '神经元', 'Neuron', '示意胞体、树突与轴突，不指定神经元亚型', 'Soma, branched dendrites and an axon; no neuronal subtype is specified.', 'cells', 190, 130, '#d3c3e8'),
  entry('cell_erythrocyte', '成熟哺乳动物红细胞', 'Mature mammalian erythrocyte', '双凹圆盘示意，无细胞核；不适用于所有脊椎动物红细胞', 'Biconcave disc without a nucleus; not representative of all vertebrate erythrocytes.', 'cells', 160, 110, '#d77e88'),
  entry('cell_lymphocyte', '淋巴细胞', 'Lymphocyte', '大核、较少胞质的通用示意；不区分 T、B 或 NK 细胞', 'Large nucleus and narrow cytoplasm; does not distinguish T, B or NK cells.', 'cells', 150, 130, '#a9c9e4'),
  entry('cell_macrophage', '巨噬细胞', 'Macrophage', '不规则轮廓和胞内囊泡的通用示意，不表示极化状态', 'Irregular contour with intracellular vesicles; no polarization state is implied.', 'cells', 190, 130, '#d7b5c5'),
  entry('cell_epithelial', '柱状上皮细胞', 'Columnar epithelial cell', '示意顶端与基底端、细胞核；不指定组织来源', 'Apical/basal orientation and nucleus; no tissue of origin is assigned.', 'cells', 130, 150, '#c2d9db'),
  entry('mitochondrion', '线粒体', 'Mitochondrion', '双膜与内膜嵴示意，不表示能量状态', 'Double membrane and inner membrane cristae; no energetic state is implied.', 'organelles', 150, 90, '#e6ac8f'),
  entry('chloroplast', '叶绿体', 'Chloroplast', '双膜、类囊体堆叠和基质片层的教学示意', 'Double envelope, stacked thylakoids and connecting lamellae.', 'organelles', 150, 90, '#a6c990'),
  entry('rough_er', '粗面内质网', 'Rough endoplasmic reticulum', '膜囊及附着于胞质侧的核糖体示意', 'Membrane cisternae with ribosomes on the cytosolic surface.', 'organelles', 150, 100, '#adbcd8'),
  entry('smooth_er', '滑面内质网', 'Smooth endoplasmic reticulum', '不附着核糖体的管状膜网络示意', 'Tubular membrane network without attached ribosomes.', 'organelles', 150, 100, '#b7c9d9'),
  entry('golgi', '高尔基体', 'Golgi apparatus', '扁平膜囊堆叠与周围囊泡示意', 'Stacked flattened cisternae and surrounding vesicles.', 'organelles', 150, 100, '#d9afba'),
  entry('lysosome', '溶酶体', 'Lysosome', '单膜及内部颗粒的通用示意，不指定底物', 'Single membrane with schematic luminal granules; no substrate is specified.', 'organelles', 100, 90, '#d6b177'),
  entry('peroxisome', '过氧化物酶体', 'Peroxisome', '单膜细胞器示意，颜色不表示酶活性', 'Single-membrane organelle; colors do not encode enzyme activity.', 'organelles', 100, 90, '#a7c6b5'),
  entry('ribosome', '核糖体', 'Ribosome', '大小亚基示意；不描绘膜，不指定物种', 'Large and small subunits; no surrounding membrane or species assignment.', 'organelles', 110, 85, '#c7add3'),
  entry('vesicle', '运输囊泡', 'Transport vesicle', '膜包裹囊泡的通用示意，不指定运输方向或货物', 'Membrane-bound vesicle; no trafficking direction or cargo is assigned.', 'organelles', 100, 90, '#a4c9df'),
  entry('membrane_bilayer', '磷脂双分子层', 'Phospholipid bilayer', '亲水头朝外、疏水尾朝内的局部示意', 'Hydrophilic heads face outward; hydrophobic tails face inward.', 'molecules', 180, 70, '#9bb4cb'),
  entry('ion_channel', '膜通道', 'Membrane channel', '跨膜孔道示意，不指定离子选择性或开放状态', 'Transmembrane pore; no ion selectivity or gating state is assigned.', 'molecules', 110, 120, '#8aaabb'),
  entry('antibody', '抗体', 'Antibody', 'Y 形通用免疫球蛋白符号，不指定同型或结合靶点', 'Generic Y-shaped immunoglobulin symbol; no isotype or target is assigned.', 'molecules', 110, 110, '#b5a3ce'),
]

export function componentArtwork(id: ComponentId, fill: string): Primitive[] {
  if (!/^#[0-9a-f]{6}$/i.test(fill)) throw new Error('Invalid component color')
  const pale = tint(fill, .72), light = tint(fill, .4)
  switch (id) {
    case 'cell_generic': return [
      path('M9 56 C15 23 48 9 85 14 C115 3 160 15 176 43 C193 73 178 107 148 117 C110 132 76 118 45 119 C15 116 1 89 9 56Z', pale, fill, 2.5),
      path('M18 57 C24 28 53 19 86 23 C118 13 155 24 166 48 C180 75 166 101 143 108 C111 120 78 110 48 110 C23 106 10 84 18 57Z', 'none', light, 1.5),
    ]
    case 'cell_animal': return [
      ...componentArtwork('cell_generic', fill), ...nucleus(87, 64), ...mito(137, 44), ...mito(40, 87),
      path('M52 35 q-15 5 -7 14 M48 29 q-24 10 -11 25 M120 79 q22 4 17 12 M116 86 q25 6 14 13', 'none', '#9aaac6', 3),
      ...dots([[40, 42], [46, 35], [52, 30], [128, 100], [144, 83], [61, 96]], '#8793a6'),
    ]
    case 'cell_plant': return [rect(5, 5, 180, 120, 22, light, '#6f895f'), rect(12, 12, 166, 106, 17, pale, '#9ab08a'),
      rect(58, 28, 95, 74, 22, '#edf5fb', '#afc8d9'), ...nucleus(36, 67, 17, 21),
      ...mito(106, 111, 26, 12),
      ...[[41, 27], [166, 45], [163, 98], [53, 109]].flatMap(([x, y]) => [ellipse(x, y, 12, 6, '#b4ce9b', '#6d915b', 1), path(`M${x - 6} ${y - 2} h12 M${x - 6} ${y + 2} h12`, 'none', '#6d915b', 1)]),
    ]
    case 'cell_bacterium': return [
      path('M145 68 C168 50 164 97 181 79 C190 67 177 52 187 44', 'none', '#b59a70', 2),
      rect(9, 31, 146, 68, 34, pale, '#9b8663'), rect(16, 38, 132, 54, 27, light, '#baa57f'),
      path('M45 62 c9 -22 39 23 47 0 s-32 -16 -28 7 s31 5 37 -8', 'none', '#8e78a8', 2),
      ...dots([[28, 61], [39, 81], [54, 44], [102, 78], [126, 57], [122, 84], [88, 45]], '#8b816f'),
      ...[28, 49, 110, 132].flatMap(x => [path(`M${x} 33 l-4 -9 M${x} 97 l4 9`, 'none', '#b59a70', 1.5)]),
    ]
    case 'cell_neuron': return [
      path('M62 53 L44 22 M47 29 L29 24 M46 29 L47 10 M57 61 L23 61 M30 61 L17 44 M32 61 L18 77 M64 74 L43 108 M49 98 L31 99 M50 96 L53 120 M87 66 C116 54 144 80 167 65 L183 53 M167 65 L182 75', 'none', fill, 6),
      path('M49 50 Q58 37 72 40 L86 49 L98 64 L87 77 Q69 89 54 76 L44 64Z', light, ink, 1.8), ...nucleus(70, 62, 13, 12),
      ...[111, 133].map(x => path(`M${x} 65 l13 1`, 'none', '#e7dff0', 10)),
    ]
    case 'cell_erythrocyte': return [ellipse(80, 55, 69, 43, fill, '#a65d6b', 2), ellipse(80, 55, 42, 23, light, '#c7828c', 1.5), ellipse(80, 54, 29, 13, pale, 'none'), path('M28 40 Q79 6 129 39', 'none', tint(fill, .55), 3)]
    case 'cell_lymphocyte': return [ellipse(75, 65, 62, 57, pale, fill, 2.5), ...nucleus(72, 65, 46, 43), ...mito(119, 83, 18, 10)]
    case 'cell_macrophage': return [path('M9 53 L24 45 L19 23 L43 29 Q57 8 83 23 L108 11 L119 30 L147 24 L151 45 L181 60 L164 77 L174 100 L146 102 Q116 128 90 111 L61 124 L45 103 L18 102 L24 80 L5 72Z', pale, fill, 2),
      path('M65 52 C48 39 38 64 51 80 C68 101 99 88 94 72 C72 86 81 62 65 52Z', '#dfd4eb', '#9c88b2', 1.5),
      ...[[117, 54, 9], [143, 77, 8], [111, 94, 6], [42, 40, 4]].map(([x, y, r]) => circle(x, y, r, light, fill, 1.2)),
    ]
    case 'cell_epithelial': return [path('M20 27 Q64 35 111 27 L109 130 Q65 141 20 130Z', pale, fill, 2),
      ...Array.from({ length: 10 }, (_, i) => path(`M${24 + i * 9} 27 v-14`, 'none', fill, 3)), ...nucleus(65, 101, 23, 21),
      path('M19 135 H111', 'none', '#aaa3b9', 3), ...mito(66, 57, 31, 16),
    ]
    case 'nucleus_generic': return [ellipse(55, 41, 49, 35, pale, '#9b86b4'), ellipse(55, 41, 44, 30, 'none', '#c2b1d7', 1.4), circle(68, 36, 10, fill, 'none'),
      path('M25 30 q16 -14 22 4 t22 14 M22 50 q14 -9 23 4 t30 -6', 'none', '#b7a3cb', 2), ...dots([[23, 15], [96, 43], [40, 73]], '#fff', 2.5)]
    case 'mitochondrion': return [ellipse(75, 45, 69, 37, pale, '#b5826b'), ellipse(75, 45, 61, 29, light, '#c79982', 1.5),
      path('M24 43 C32 23 38 20 42 42 S53 73 57 43 S68 18 73 44 S85 75 90 45 S104 20 109 43 S120 66 126 44', 'none', '#ad755c', 2)]
    case 'chloroplast': return [ellipse(75, 45, 69, 37, pale, '#72975d'), ellipse(75, 45, 62, 30, 'none', '#a0ba8e', 1.4),
      path('M32 47 H116 M42 55 H103', 'none', '#7d9b68', 2),
      ...[35, 72, 108].flatMap(x => [29, 36, 43, 50].map(y => rect(x - 11, y, 23, 5, 2, light, '#789b61'))),
    ]
    case 'rough_er': return [
      ...[20, 42, 64].map(y => path(`M12 ${y} C48 ${y - 13} 74 ${y + 12} 132 ${y - 3} L135 ${y + 7} C81 ${y + 23} 47 ${y - 1} 12 ${y + 12}Z`, light, '#8394b0', 1.6)),
      ...dots([[18, 15], [39, 11], [61, 14], [86, 15], [117, 11], [28, 37], [57, 36], [99, 37], [125, 32], [19, 58], [55, 57], [91, 59], [121, 54]], '#6e7890', 2.4),
    ]
    case 'smooth_er': return [
      path('M15 20 C55 1 38 76 78 64 S96 92 135 73 M13 54 C49 82 65 5 92 29 S113 61 137 39 M42 46 Q74 41 79 64 M92 29 Q105 12 128 17', 'none', '#8ba0b2', 10),
      path('M15 20 C55 1 38 76 78 64 S96 92 135 73 M13 54 C49 82 65 5 92 29 S113 61 137 39 M42 46 Q74 41 79 64 M92 29 Q105 12 128 17', 'none', light, 6),
    ]
    case 'golgi': return [
      ...[22, 39, 56, 73].map((y, i) => path(`M${26 + i * 4} ${y} Q76 ${y + 22} ${124 - i * 4} ${y} Q${126 - i * 4} ${y + 9} ${120 - i * 4} ${y + 11} Q75 ${y + 30} ${29 + i * 4} ${y + 11}Z`, i % 2 ? pale : light, '#ad8093', 1.5)),
      circle(15, 35, 6, light, '#ad8093', 1.3), circle(137, 52, 7, pale, '#ad8093', 1.3), circle(123, 86, 4, fill, 'none'),
    ]
    case 'lysosome': return [ellipse(50, 45, 40, 35, pale, fill), ...dots([[30, 38], [50, 26], [67, 41], [41, 56], [63, 61], [26, 55]], fill, 3), path('M46 40 l7 5 -5 7 M63 23 l6 3', 'none', '#b89b68', 2)]
    case 'peroxisome': return [ellipse(50, 45, 40, 35, pale, fill), ...dots([[26, 35], [42, 27], [63, 31], [72, 49], [56, 61], [31, 59], [47, 46]], fill, 2.8)]
    case 'ribosome': return [path('M12 43 Q9 15 33 12 Q43 1 57 12 Q91 8 98 40 Q88 55 66 52 L46 49 Q24 57 12 43Z', light, '#9780aa', 1.8),
      path('M24 59 Q53 49 85 60 Q90 78 62 80 Q29 83 24 59Z', pale, '#9780aa', 1.8)]
    case 'vesicle': return [ellipse(50, 45, 39, 35, pale, fill), ellipse(50, 45, 34, 30, 'none', light, 1.5), ...dots([[38, 38], [61, 49], [45, 59]], light, 4)]
    case 'membrane_bilayer': return membrane(180, 20)
    case 'receptor_membrane': return [...membrane(105, 67),
      path('M48 110 V55 Q30 45 25 20 L36 14 L51 38 L66 14 L78 20 Q73 45 56 55 V110Z', light, ink, 1.8),
      path('M47 68 V94 M57 68 V94', 'none', fill, 2)]
    case 'ion_channel': return [...membrane(110, 50), rect(27, 21, 21, 82, 9, light), rect(63, 21, 21, 82, 9, light), path('M52 28 V95 M59 28 V95', 'none', '#b5c6d2', 1.4)]
    case 'antibody': return [path('M49 99 V58 L15 24 L22 14 L55 46 L88 14 L96 24 L62 58 V99Z', light, '#87739c', 1.8),
      path('M34 47 L9 22 M76 47 L102 22', 'none', fill, 6), path('M49 64 H62 M49 72 H62', 'none', '#87739c', 1.3)]
    case 'dna_helix': {
      const samples = Array.from({ length: 41 }, (_, i) => ({
        y: +(8 + 68 * i / 40).toFixed(2), x: +(42 * Math.cos(2 * Math.PI * i / 40)).toFixed(2),
      }))
      const strand = (sign: number) => samples.map(({ x, y }, i) => `${i ? 'L' : 'M'}${65 + sign * x} ${y}`).join(' ')
      return [...samples.filter((point, i) => i % 4 === 0 && Math.abs(point.x) > 3).map(({ x, y }, i) =>
        path(`M${65 - x} ${y} H${65 + x}`, 'none', i % 2 ? '#c1b3cf' : '#a5bdcb', 2)),
      path(strand(1), 'none', fill, 4), path(strand(-1), 'none', fill, 4)]
    }
    case 'rna_single': return [path('M8 44 C20 13 37 11 49 37 S78 65 91 34 S116 15 123 38', 'none', fill, 5),
      ...[ [19, 25], [37, 24], [57, 49], [78, 51], [99, 23], [115, 23] ].map(([x, y], i) => path(`M${x} ${y} l${i % 2 ? 5 : -5} -8`, 'none', '#9a7a76', 2))]
    case 'protein_generic': return [path('M12 40 C4 21 24 8 41 17 C51 3 77 9 81 26 C108 21 111 49 95 59 C93 81 67 83 55 68 C31 83 9 63 12 40Z', pale, '#a78b5c', 2),
      path('M26 32 q15 -16 22 2 t22 2 t20 6 M24 51 q14 13 23 -2 t25 4', 'none', fill, 5)]
    case 'ligand_generic': return [path('M14 12 Q32 0 49 10 L62 25 L57 44 L36 53 L14 43 L6 26Z', light, '#976185', 1.8), path('M18 18 Q30 9 44 16', 'none', pale, 3), circle(42, 33, 4, fill, 'none')]
    case 'drug_tablet': return [rect(4, 6, 84, 42, 21, light, '#b77970'), path('M46 7 V47', 'none', '#b77970', 1.6), path('M18 17 H36', 'none', pale, 4)]
  }
}

export function componentSvg(id: ComponentId, fill: string): string {
  return componentArtwork(id, fill).map(({ tag, attrs }) => `<${tag} ${Object.entries(attrs).map(([key, value]) =>
    `${key.replace(/[A-Z]/g, letter => '-' + letter.toLowerCase())}="${String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[char]!))}"`).join(' ')}/>`).join('')
}
