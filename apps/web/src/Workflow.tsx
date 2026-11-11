import { useEffect, useRef, useState } from 'react'
import { FolderIcon, SampleChart } from './WorkflowPrototype'
import IllustrationStudio from './IllustrationStudio'
import ImageWorkspace from './ImageWorkspace'
import DrawingWorkbench, { type ExternalDraft, type WorkbenchConnection, type WorkbenchProposal, type WorkbenchProvider } from './DrawingWorkbench'
import type { DocumentKind, IllustrationSpec } from './illustration'
import { EcologyPreview, OmicsPreview } from './WorkflowPreviews'
import { ecologyDirections, omicsDirections, spatialKinds, type EcologyDirection, type OmicsDirection } from './WorkflowCatalog'
import './WorkflowPrototype.css'

type SvgTextMode = 'outline' | 'editable'
type Mode = 'table' | 'single_cell' | 'omics' | 'ecology'
export type Chart = {
  spec_version: string
  dataset_id: string
  chart_type: string
  x_column: string
  y_column: string
  group_column: string | null
  coordinate_key: string
  color_field: string | null
  genes: string[]
  expression_source: string
  expression_layer: string | null
  transform: string
  ecology_value_mode: 'relative_fraction' | 'count'
  ecology_sample_column: string
  ecology_metric_column: string
  ecology_metric: string
  ecology_entity_type_column: string
  ecology_environment_mode: 'continuous_value' | 'existing_vector'
  ecology_environment_column: string
  ecology_time_column: string
  ecology_value_column: string
  ecology_replicate_column: string
  ecology_error_column: string
  ecology_spatial_coordinate_mode: 'geographic_wgs84' | 'planar'
  ecology_spatial_reference: string
  ecology_spatial_unit: 'degrees' | 'm' | 'km' | 'arbitrary'
  point_size: number
  title: string
  theme_id: string
  palette_id: string
  palette_version: string
  category_order: string[]
  width_mm: number
  height_mm: number
  dpi: number
  font_size: number
  line_width: number
  show_legend: boolean
  svg_text_mode?: SvgTextMode
}
type Column = { name: string; dtype: string; missing_count?: number }
type Preview = {
  dataset_id: string
  kind: string
  row_count?: number
  cell_count?: number
  gene_count?: number
  source_name?: string
  sha256?: string
  matrix_format?: string
  has_raw?: boolean
  columns: Column[]
  rows: Record<string, unknown>[]
  coordinates?: { key: string; dimensions: number }[]
  layers?: string[]
  gene_names?: string[]
  summary?: string
  sequence_id?: string
  sequence_length?: number
  feature_count?: number
  feature_types?: string[]
  manifest_version?: string
}
type ImageCrop = { x: number; y: number; width: number; height: number }
type FigureImage = {
  asset_id: string
  crop: ImageCrop | null
  x_um_per_pixel: number
  scale_bar_um: number
  scale_bar_color: 'white' | 'black'
}
type ImageCheck = {
  source_pixels: [number, number]
  placed_pixels: [number, number]
  effective_dpi: number
  output_dpi: number
  below_output_dpi: boolean
}
type Snapshot = { chart: Chart; image: string }
type Figure = {
  spec_version: string
  panels: Chart[]
  columns: number
  labels: string
  theme_id: string
  template_id: string
  width_mm: number
  height_mm: number
  margin_top_mm: number
  margin_right_mm: number
  margin_bottom_mm: number
  margin_left_mm: number
  panel_gap_mm: number
  label_position: string
  label_font_size: number
  legend_mode: string
  legend_position: string
  font_family: string
  font_embedding: string
  svg_text_mode?: SvgTextMode
  palette_version: string
  dpi: number
}
type RenderArtifact = { type: 'renders' | 'figures'; id: string; formats: string[] }
const tableKinds: Record<string, string> = {
  scatter: '散点图',
  bar: '柱状图',
  line: '折线图',
  box: '箱线图',
  heatmap: '热图',
}
const singleKinds: Record<string, string> = {
  embedding_categorical: 'UMAP / t-SNE 分类',
  embedding_continuous: 'UMAP / t-SNE 连续值',
  feature: 'Feature Plot',
  violin: '小提琴图',
  dotplot: 'Dot Plot',
}
const themes: Record<string, string> = {
  scientific_clear: '科研清晰',
  modern_soft: '现代柔和',
  high_contrast: '高对比',
}
const palettes: Record<string, string[]> = {
  scientific_clear: ['#2374ab', '#d05a3b', '#3e8e72'],
  modern_soft: ['#5f8f9b', '#d6806c', '#9eae79'],
  high_contrast: ['#0072b2', '#d55e00', '#009e73'],
  clay: ['#A34F3E', '#D3A45B', '#527C78'],
  lagoon: ['#246B78', '#5F9E91', '#CA8755'],
  colorblind: ['#0072b2', '#e69f00', '#009e73'],
  viridis: ['#440154', '#21918c', '#fde725'],
  cividis: ['#00224e', '#7d7c78', '#fee838'],
  magma: ['#000004', '#b73779', '#fcfdbf'],
  coolwarm: ['#3b4cc0', '#dddcdc', '#b40426'],
}
const paletteLabels: Record<string, string> = {
  theme: '跟随主题', colorblind: '高辨识分类色', viridis: 'Viridis 连续色', cividis: 'Cividis 连续色',
  magma: 'Magma 连续色', coolwarm: 'Coolwarm 发散色', clay: '陶土 / Clay', lagoon: '湖湾 / Lagoon',
}
const chartMeasureLabels: Record<string, string> = {
  width_mm: '图表宽度（mm）', height_mm: '图表高度（mm）', dpi: '分辨率（DPI）',
  font_size: '字体大小（pt）', line_width: '线条宽度（pt）',
}
const figureMeasureLabels: Record<string, string> = {
  width_mm: '图版宽度（mm）', height_mm: '图版高度（mm）',
  margin_top_mm: '上边距（mm）', margin_right_mm: '右边距（mm）', margin_bottom_mm: '下边距（mm）', margin_left_mm: '左边距（mm）',
  panel_gap_mm: '子图间距（mm）', label_font_size: '标签字号（pt）', dpi: '分辨率（DPI）',
}
const initial: Chart = {
  spec_version: '1.2',
  dataset_id: '',
  chart_type: 'scatter',
  x_column: '',
  y_column: '',
  group_column: null,
  coordinate_key: 'X_umap',
  color_field: null,
  genes: [],
  expression_source: 'X',
  expression_layer: null,
  transform: 'none',
  ecology_value_mode: 'relative_fraction',
  ecology_sample_column: 'sample',
  ecology_metric_column: 'metric',
  ecology_metric: '',
  ecology_entity_type_column: 'entity_type',
  ecology_environment_mode: 'continuous_value',
  ecology_environment_column: '',
  ecology_time_column: 'time',
  ecology_value_column: 'value',
  ecology_replicate_column: '',
  ecology_error_column: '',
  ecology_spatial_coordinate_mode: 'geographic_wgs84',
  ecology_spatial_reference: 'EPSG:4326',
  ecology_spatial_unit: 'degrees',
  point_size: 8,
  title: 'Cell response',
  theme_id: 'scientific_clear',
  palette_id: 'theme',
  palette_version: '1.0',
  category_order: [],
  width_mm: 180,
  height_mm: 120,
  dpi: 300,
  font_size: 10,
  line_width: 1.2,
  show_legend: true,
}
const desktop = '__BIOFIGURE_DESKTOP__' in window

async function request(path: string, signal: AbortSignal, body?: unknown, file?: File) {
  const form = file ? new FormData() : undefined
  if (file) form!.append('file', file)
  const response = await fetch(path, {
    signal,
    ...(form
      ? { method: 'POST', body: form }
      : body !== undefined
        ? {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          }
        : {}),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(typeof error.detail === 'string' ? error.detail : `请求失败（${response.status}），请检查文件、字段和参数。`)
  }
  return response
}
async function json(path: string, signal: AbortSignal, body?: unknown, file?: File) {
  return (await request(path, signal, body, file)).json()
}
async function artifactBlob(artifact: RenderArtifact, format: string, signal: AbortSignal): Promise<Blob> {
  return (await request(`/api/${artifact.type}/${artifact.id}.${format}`, signal)).blob()
}
function dataImage(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}
function SvgTextPicker({ value, onChange }: { value?: SvgTextMode; onChange: (value: SvgTextMode) => void }) {
  return (
    <label>
      SVG 文字
      <select value={value ?? 'outline'} onChange={(event) => onChange(event.target.value === 'editable' ? 'editable' : 'outline')}>
        <option value="outline">转为路径（保持外观）</option>
        <option value="editable">保留文字（便于外部编辑）</option>
      </select>
    </label>
  )
}
function FormatPicker({ value, onChange, tiff = false }: { value: string; onChange: (v: string) => void; tiff?: boolean }) {
  return (
    <label>
      导出格式
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="pdf">PDF</option>
        <option value="svg">SVG</option>
        <option value="png">PNG</option>
        {tiff && <option value="tiff">TIFF（无损栅格）</option>}
      </select>
    </label>
  )
}

export default function Workflow() {
  const [page, setPage] = useState(0),
    [mode, setMode] = useState<Mode>('table'),
    [omicsDirection, setOmicsDirection] = useState<OmicsDirection | null>(null),
    [ecologyDirection, setEcologyDirection] = useState<EcologyDirection | null>(null),
    [draft, setDraft] = useState<Chart>(initial),
    [preview, setPreview] = useState<Preview | null>(null),
    [result, setResult] = useState<(Snapshot & { artifact: RenderArtifact }) | null>(null),
    [panels, setPanels] = useState<Snapshot[]>([])
  const [assemblyIntent, setAssemblyIntent] = useState(false)
  const [figureImage, setFigureImage] = useState<{ name: string; panel: FigureImage } | null>(null)
  const [showFileGuide, setShowFileGuide] = useState(false)
  const [illustrationKind, setIllustrationKind] = useState<DocumentKind>('mechanism')
  const [illustrationFile, setIllustrationFile] = useState<File | null>(null)
  const [illustrationSkillDraft, setIllustrationSkillDraft] = useState<IllustrationSpec | null>(null)
  const [illustrationSkillRevision, setIllustrationSkillRevision] = useState(0)
  const projectInputRef = useRef<HTMLInputElement>(null)
  const [layout, setLayout] = useState<Omit<Figure, 'panels'>>({
      spec_version: '2.0',
      columns: 2,
      labels: 'upper',
      theme_id: 'scientific_clear',
      template_id: 'double_column',
      width_mm: 180,
      height_mm: 120,
      margin_top_mm: 10,
      margin_right_mm: 10,
      margin_bottom_mm: 12,
      margin_left_mm: 16,
      panel_gap_mm: 7,
      label_position: 'inside',
      label_font_size: 11,
      legend_mode: 'per_panel',
      legend_position: 'right',
      font_family: 'noto_sans_sc',
      font_embedding: 'required',
      palette_version: '1.0',
      dpi: 300,
    }),
    [assembly, setAssembly] = useState<{
      image: string
      artifact: RenderArtifact
      imageCheck?: ImageCheck
    } | null>(null),
    [review, setReview] = useState(false),
    [format, setFormat] = useState('pdf'),
    [name, setName] = useState('current-project'),
    [notice, setNotice] = useState(''),
    [busy, setBusy] = useState('')
  const [aiMode, setAiMode] = useState(false)
  const [visitedAI, setVisitedAI] = useState(false)
  const [recentProjects, setRecentProjects] = useState<File[]>([])
  const active = useRef<AbortController | null>(null)
  const canApplyWorkbenchDraft = (!preview || draft.dataset_id === 'simulated-cell-response-v1') && !figureImage && !panels.length && page !== 6 && page !== 10
  const updateLayout = (patch: Partial<Omit<Figure, 'panels'>>) => {
    setLayout((current) => ({ ...current, ...patch }))
    setAssembly(null)
  }
  const applyTemplate = (template: string) => {
    const templates: Record<string, Partial<Omit<Figure, 'panels'>>> = {
      single_column: { template_id: 'single_column', columns: 1, width_mm: 90, height_mm: 120, margin_top_mm: 9, margin_right_mm: 8, margin_bottom_mm: 11, margin_left_mm: 13, panel_gap_mm: 6 },
      double_column: { template_id: 'double_column', columns: 2, width_mm: 180, height_mm: 120, margin_top_mm: 10, margin_right_mm: 10, margin_bottom_mm: 12, margin_left_mm: 16, panel_gap_mm: 7 },
      square_grid: { template_id: 'square_grid', columns: 2, width_mm: 180, height_mm: 180, margin_top_mm: 10, margin_right_mm: 10, margin_bottom_mm: 12, margin_left_mm: 16, panel_gap_mm: 8 },
      custom: { template_id: 'custom' },
    }
    updateLayout(templates[template] ?? templates.custom)
  }
  useEffect(() => () => active.current?.abort(), [])
  useEffect(() => {
    const root = document.documentElement
    if (page !== 0 || aiMode) {
      root.classList.remove('wf-fossil-relief-active')
      return
    }
    root.classList.add('wf-fossil-relief-active')
    let frame = 0
    let visible = false
    let targetX = window.innerWidth * 0.5
    let targetY = window.innerHeight * 0.42
    let x = targetX
    let y = targetY
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const textLayers = Array.from(document.querySelectorAll<HTMLElement>('.wf-spotlight-title > span, .wf-spotlight-subtitle > span'))
    const tick = () => {
      if (reduced) {
        x = targetX
        y = targetY
      } else {
        x += (targetX - x) * 0.16
        y += (targetY - y) * 0.16
      }
      root.style.setProperty('--wf-cursor-x', `${x}px`)
      root.style.setProperty('--wf-cursor-y', `${y}px`)
      // Translate the same viewport circle, without scaling its radius.
      // Reading each frame also tracks scrolling, resizing and font layout changes.
      for (const layer of textLayers) {
        const rect = layer.getBoundingClientRect()
        layer.style.setProperty('--wf-text-x', `${x - rect.left}px`)
        layer.style.setProperty('--wf-text-y', `${y - rect.top}px`)
      }
      if (visible) frame = requestAnimationFrame(tick)
    }
    const move = (event: PointerEvent) => {
      if (event.pointerType === 'touch') return
      targetX = event.clientX
      targetY = event.clientY
      if (!visible) {
        visible = true
        root.classList.add('wf-fossil-relief-visible')
        frame = requestAnimationFrame(tick)
      }
    }
    const leave = () => {
      visible = false
      root.classList.remove('wf-fossil-relief-visible')
      cancelAnimationFrame(frame)
    }
    window.addEventListener('pointermove', move, { passive: true })
    window.addEventListener('pointerleave', leave)
    document.documentElement.addEventListener('pointerleave', leave)
    window.addEventListener('blur', leave)
    return () => {
      visible = false
      root.classList.remove('wf-fossil-relief-active', 'wf-fossil-relief-visible')
      cancelAnimationFrame(frame)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerleave', leave)
      document.documentElement.removeEventListener('pointerleave', leave)
      window.removeEventListener('blur', leave)
      root.style.removeProperty('--wf-cursor-x')
      root.style.removeProperty('--wf-cursor-y')
      for (const layer of textLayers) {
        layer.style.removeProperty('--wf-text-x')
        layer.style.removeProperty('--wf-text-y')
      }
    }
  }, [page, aiMode])
  const kinds =
    mode === 'table'
      ? tableKinds
      : mode === 'single_cell'
        ? singleKinds
        : mode === 'ecology'
          ? ecologyDirection === 'diversity'
            ? {
                ecology_alpha_diversity: 'α 多样性箱线图',
                ecology_beta_ordination: 'β 多样性排序图',
              }
            : ecologyDirection === 'ordination'
              ? { ecology_ordination_biplot: '排序双图（样品 + taxon）' }
              : ecologyDirection === 'environment'
                ? { ecology_environment_gradient: '环境梯度（已有值 / 向量）' }
                : ecologyDirection === 'time'
                  ? { ecology_time_series: '生态时间序列（原始观测）' }
                  : ecologyDirection === 'spatial'
                    ? { ecology_spatial_points: '空间生态点位图' }
                    : { ecology_composition: '群落组成堆叠图' }
          : omicsDirection === 'spatial'
            ? spatialKinds
            : omicsDirection === 'r'
              ? { r_ggplot: 'R ggplot2 散点图' }
              : omicsDirection === 'genome'
                ? { genome_tracks: '基因组多轨道' }
                : omicsDirection === 'circos'
                  ? { circos: 'Circos 轨道与链接' }
                  : { dna_features: 'DNA 特征图' }
  const change = (patch: Partial<Chart>) => {
    setDraft((current) => ({ ...current, ...patch }))
    setResult(null)
  }
  const run = async (kind: string, action: (signal: AbortSignal) => Promise<void>) => {
    if (active.current) return
    const controller = new AbortController()
    active.current = controller
    setBusy(kind)
    setNotice('')
    try {
      await action(controller.signal)
    } catch (error) {
      if (!controller.signal.aborted) setNotice(error instanceof Error ? error.message : '操作失败，请重试。')
    } finally {
      if (active.current === controller) {
        active.current = null
        setBusy('')
      }
    }
  }
  const loadData = (file?: File) =>
    run('data', async (signal) => {
      const isSpatial = mode === 'omics' && omicsDirection === 'spatial'
      const accept = mode === 'table' || mode === 'ecology' ? /\.(csv|xlsx)$/i : mode === 'single_cell' || isSpatial ? /\.h5ad$/i : omicsDirection === 'dna' ? /\.(gb|gbk|genbank)$/i : omicsDirection === 'circos' ? /\.json$/i : omicsDirection === 'genome' ? /\.json$|\.(bed|bedgraph|gff|gff3|gtf|chrom\.sizes)$/i : /\.(csv|xlsx)$/i
      const sizeLimit = mode === 'table' || mode === 'ecology' || omicsDirection === 'r' ? 5 * 1024 * 1024 : mode === 'single_cell' || isSpatial ? 200 * 1024 * 1024 : 50 * 1024 * 1024
      if (file && (file.size > sizeLimit || !accept.test(file.name))) throw new Error(`请选择符合当前方向的文件，大小不超过 ${Math.round(sizeLimit / 1024 / 1024)} MB。`)
      const endpoint = file ? '/api/datasets' : mode === 'single_cell' ? '/api/datasets/simulated-single-cell/preview' : mode === 'ecology' ? (ecologyDirection === 'spatial' ? '/api/datasets/simulated-ecology-spatial/preview' : ecologyDirection === 'time' ? '/api/datasets/simulated-ecology-time/preview' : ecologyDirection === 'environment' ? '/api/datasets/simulated-ecology-environment/preview' : ecologyDirection === 'ordination' ? '/api/datasets/simulated-ecology-ordination/preview' : ecologyDirection === 'diversity' && draft.chart_type === 'ecology_beta_ordination' ? '/api/datasets/simulated-ecology-beta/preview' : ecologyDirection === 'diversity' ? '/api/datasets/simulated-ecology-alpha/preview' : '/api/datasets/simulated-ecology/preview') : '/api/datasets/simulated/preview'
      const data: Preview = await json(endpoint, signal, undefined, file)
      setPreview(data)
      if (data.kind === 'single_cell') {
        const coordinate = data.coordinates?.find((c) => /umap|spatial/i.test(c.key))?.key ?? data.coordinates?.[0]?.key ?? 'X_umap'
        const spatial = isSpatial
        change({
          dataset_id: data.dataset_id,
          coordinate_key: coordinate,
          chart_type: spatial ? 'spatial_categorical' : 'embedding_categorical',
          color_field: data.columns[0]?.name ?? null,
          group_column: data.columns[0]?.name ?? null,
        })
      } else if (data.kind === 'dna') {
        change({
          dataset_id: data.dataset_id,
          chart_type: 'dna_features',
          title: data.sequence_id ? `${data.sequence_id} features` : 'DNA features',
        })
      } else if (data.kind === 'circos') {
        change({
          dataset_id: data.dataset_id,
          chart_type: 'circos',
          title: 'Circos overview',
        })
      } else if (data.kind === 'genome_tracks') {
        change({
          dataset_id: data.dataset_id,
          chart_type: 'genome_tracks',
          title: 'Genome tracks',
        })
      } else {
        const numbers = data.columns.filter((c) => /int|float|double/i.test(c.dtype))
        const ecologyChart = mode === 'ecology' ? draft.chart_type : ''
        const alpha = ecologyChart === 'ecology_alpha_diversity'
        const beta = ecologyChart === 'ecology_beta_ordination'
        const biplot = ecologyChart === 'ecology_ordination_biplot'
        const environment = ecologyChart === 'ecology_environment_gradient'
        const timeSeries = ecologyChart === 'ecology_time_series'
        const spatialEcology = ecologyChart === 'ecology_spatial_points'
        const column = (name: string, fallback: string) => data.columns.find((item) => item.name === name)?.name ?? fallback
        change({
          dataset_id: data.dataset_id,
          chart_type: mode === 'ecology' ? ecologyChart : omicsDirection === 'r' ? 'r_ggplot' : 'scatter',
          x_column: alpha ? column('group', 'sample') : beta ? column('PCoA1', numbers[0]?.name ?? '') : biplot || environment ? column('axis_1', numbers[0]?.name ?? '') : timeSeries ? column('time', numbers[0]?.name ?? '') : spatialEcology ? column('longitude', numbers[0]?.name ?? '') : mode === 'ecology' ? 'sample' : (numbers[0]?.name ?? data.columns[0]?.name ?? ''),
          y_column: alpha ? column('value', numbers[0]?.name ?? '') : beta ? column('PCoA2', numbers[1]?.name ?? numbers[0]?.name ?? '') : biplot || environment ? column('axis_2', numbers[1]?.name ?? numbers[0]?.name ?? '') : timeSeries ? column('value', numbers[1]?.name ?? numbers[0]?.name ?? '') : spatialEcology ? column('latitude', numbers[1]?.name ?? numbers[0]?.name ?? '') : mode === 'ecology' ? 'abundance' : (numbers[1]?.name ?? numbers[0]?.name ?? ''),
          group_column: alpha || beta || biplot || environment || timeSeries || spatialEcology ? (data.columns.some((item) => item.name === 'group') ? 'group' : null) : null,
          color_field: mode === 'ecology' && !alpha && !beta && !biplot && !environment && !timeSeries && !spatialEcology ? 'taxon' : null,
          ecology_value_mode: mode === 'ecology' && !alpha && !beta ? 'relative_fraction' : 'relative_fraction',
          ecology_sample_column: mode === 'ecology' ? column(environment || biplot ? 'entity' : 'sample', data.columns[0]?.name ?? 'sample') : 'sample',
          ecology_metric_column: alpha ? column('metric', 'metric') : 'metric',
          ecology_metric: alpha ? String(data.rows.find((row) => row.metric != null)?.metric ?? '') : '',
          ecology_entity_type_column: biplot || environment ? column('entity_type', 'entity_type') : 'entity_type',
          ecology_environment_column: environment ? column('nitrate', numbers[2]?.name ?? numbers[0]?.name ?? '') : '',
          ecology_time_column: timeSeries ? column('time', numbers[0]?.name ?? '') : 'time',
          ecology_value_column: timeSeries ? column('value', numbers[1]?.name ?? numbers[0]?.name ?? '') : 'value',
          ecology_replicate_column: timeSeries && data.columns.some((item) => item.name === 'replicate') ? 'replicate' : '',
          ecology_error_column: timeSeries && data.columns.some((item) => item.name === 'error') ? 'error' : '',
        })
      }
      setNotice('数据已在本机读取，请检查预览与字段后确认。')
    })
  const renderChart = async (chart: Chart, signal: AbortSignal) => {
    const data = await json('/api/renders', signal, { chart })
    const artifact: RenderArtifact = { type: 'renders', id: data.render_id, formats: data.formats }
    setResult({
      chart: structuredClone(chart),
      image: await dataImage(await artifactBlob(artifact, 'png', signal)),
      artifact,
    })
    setPage(3)
  }
  const render = () => run('chart', (signal) => renderChart(draft, signal))
  const showMode = (enableAI: boolean) => {
    if (enableAI) setVisitedAI(true)
    else if (busy === 'workbench-draft') active.current?.abort()
    setAiMode(enableAI)
  }
  const proposeWorkbenchDraft = (provider: WorkbenchProvider, prompt: string, receive: (proposal: WorkbenchProposal) => void, external?: ExternalDraft) =>
    void run('workbench-draft', async (signal) => {
      const proposal = external
        ? await json('/api/workbench/v1/external-drafts', signal, external)
        : await json('/api/workbench/v1/drafts', signal, { provider, prompt })
      if (!signal.aborted) receive(proposal)
    })
  const proposeIllustrationDraft = (receive: (value: unknown) => void, fail: (message: string) => void) =>
    void run('workbench-draft', async (signal) => {
      try {
        const result = await json('/api/workbench/v1/illustration-draft', signal, { sample_id: 'synthetic-branch-v1' })
        if (!signal.aborted) receive(result)
      } catch (error) {
        if (!signal.aborted) fail(error instanceof Error ? error.message : '本机模型提取失败，请手动填写。')
      }
    })
  const inspectWorkbenchSample = () =>
    void run('workbench', async (signal) => {
      await json('/api/workbench/v1/fiji-sample', signal, {})
      setPage(10)
      setAiMode(false)
    })
  const connectWorkbench = (receive: (connection: WorkbenchConnection) => void) =>
    void run('workbench', async (signal) => {
      receive(await json('/api/workbench/v1/connection', signal, {}))
    })
  const disconnectWorkbench = (done: () => void) =>
    void run('workbench', async (signal) => {
      const response = await fetch('/api/workbench/v1/connection', { method: 'DELETE', signal })
      if (!response.ok) throw new Error('撤销连接失败，请从本机启动窗口重新打开软件。')
      done()
    })
  const applyWorkbenchDraft = (chart: Chart, generate: boolean) =>
    void run('workbench', async (signal) => {
      if (!canApplyWorkbenchDraft) return
      const dataset = await json('/api/datasets/simulated/preview', signal)
      setAiMode(false)
      setMode('table')
      setPreview(dataset)
      setDraft(chart)
      setResult(null)
      setAssemblyIntent(false)
      setFormat('pdf')
      setPage(2)
      if (generate) await renderChart(chart, signal)
    })
  const figurePayload = () => ({
    ...layout,
    spec_version: figureImage ? '2.1' : '2.0',
    panels: panels.map((p) => p.chart),
    ...(figureImage ? { image_panel: figureImage.panel } : {}),
  })
  const importFigureImage = (file: File) =>
    run('image', async (signal) => {
      if (file.size > 64 * 1024 * 1024) throw new Error('请选择不超过 64 MiB 的图像。')
      const asset = await json('/api/image/assets', signal, undefined, file)
      setFigureImage({ name: asset.original_name, panel: { asset_id: asset.id, crop: null, x_um_per_pixel: 0, scale_bar_um: 0, scale_bar_color: 'white' } })
      setAssembly(null)
    })
  const updateFigureImage = (patch: Partial<FigureImage>) => {
    setFigureImage((image) => image ? { ...image, panel: { ...image.panel, ...patch } } : null)
    setAssembly(null)
  }
  const removeFigureImage = () => {
    if (!figureImage) return
    void run('image', async (signal) => {
      const response = await fetch(`/api/image/assets/${figureImage.panel.asset_id}`, { method: 'DELETE', signal })
      if (!response.ok && response.status !== 404) throw new Error('图像正在使用，请稍后再移除。')
      setFigureImage(null)
      setAssembly(null)
    })
  }
  const renderAssembly = () =>
    run('assembly', async (signal) => {
      const data = await json('/api/figures', signal, figurePayload())
      const artifact: RenderArtifact = { type: 'figures', id: data.render_id, formats: data.formats }
      setAssembly({ artifact, image: await dataImage(await artifactBlob(artifact, 'png', signal)), imageCheck: data.image_check })
      setReview(true)
    })
  const download = (artifact: RenderArtifact) =>
    run('export', async (signal) => {
      if (!artifact.formats.includes(format)) throw new Error('当前结果不包含所选导出格式，请重新生成图版。')
      const file = await artifactBlob(artifact, format, signal)
      const url = URL.createObjectURL(file)
      const link = document.createElement('a')
      link.href = url
      link.download = `biofigure.${format}`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      if (!signal.aborted) setNotice(desktop ? '请在系统保存窗口确认位置。' : '已交给浏览器下载。')
    })
  const saveProject = () =>
    run('project', async (signal) => {
      const projectChart = figureImage ? panels[0]?.chart : draft
      if (!projectChart?.dataset_id) throw new Error('请先添加统计图。')
      if (panels.some((panel) => panel.chart.dataset_id !== projectChart.dataset_id)) throw new Error('当前项目格式只支持保存同一数据集的图表和图版。请改用同一数据集制作子图。')
      const response = await request('/api/projects', signal, {
        name,
        chart: projectChart,
        figure: panels.length ? figurePayload() : null,
      })
      const blob = await response.blob()
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `${name || 'biofigure-project'}.bfsproj`
      link.click()
      setTimeout(() => URL.revokeObjectURL(link.href), 60000)
      setNotice(desktop ? '请在系统保存窗口确认项目位置。' : '项目文件已交给浏览器下载；请确认保存位置。')
    })
  const openProject = (file: File) =>
    run('project', async (signal) => {
      const data = await json('/api/projects/open', signal, undefined, file)
      const project = data.project
      setName(project.name)
      setDraft(project.chart)
      setPreview(data.preview)
      setResult(null)
      setPanels([])
      setFigureImage(project.figure?.image_panel ? { name: project.image_filename, panel: project.figure.image_panel } : null)
      setAssembly(null)
      setReview(false)
      const projectMode: Mode = ['ecology_composition', 'ecology_alpha_diversity', 'ecology_beta_ordination', 'ecology_ordination_biplot', 'ecology_environment_gradient', 'ecology_time_series', 'ecology_spatial_points'].includes(project.chart.chart_type) ? 'ecology' : project.chart.chart_type.startsWith('spatial_') || ['genome_tracks', 'circos', 'dna_features', 'r_ggplot'].includes(project.chart.chart_type) ? 'omics' : data.preview.kind === 'single_cell' ? 'single_cell' : 'table'
      setMode(projectMode)
      if (projectMode === 'ecology') setEcologyDirection(project.chart.chart_type === 'ecology_composition' ? 'community' : project.chart.chart_type === 'ecology_ordination_biplot' ? 'ordination' : project.chart.chart_type === 'ecology_environment_gradient' ? 'environment' : project.chart.chart_type === 'ecology_time_series' ? 'time' : project.chart.chart_type === 'ecology_spatial_points' ? 'spatial' : 'diversity')
      if (projectMode === 'omics') setOmicsDirection(project.chart.chart_type.startsWith('spatial_') ? 'spatial' : project.chart.chart_type === 'genome_tracks' ? 'genome' : project.chart.chart_type === 'circos' ? 'circos' : project.chart.chart_type === 'dna_features' ? 'dna' : 'r')
      if (project.figure) {
        const { panels: projectPanels, image_panel: _imagePanel, ...projectLayout } = project.figure
        setLayout(projectLayout)
        const next: Snapshot[] = []
        for (const chart of projectPanels) {
          const renderData = await json('/api/renders', signal, { chart })
          const image = await dataImage(await (await request(`/api/renders/${renderData.render_id}.png`, signal)).blob())
          next.push({ chart, image })
        }
        setPanels(next)
      }
      setAssemblyIntent(!!project.figure)
      setPage(project.figure ? 8 : 1)
      setAiMode(false)
      setRecentProjects((items) => [file, ...items.filter((item) => item.name !== file.name)].slice(0, 3))
      setNotice('项目已打开；请检查恢复的数据、图表配置和图版。')
    })
  const numeric = preview?.columns.filter((c) => /int|float|double/i.test(c.dtype)) ?? [],
    tableValid = !!preview && (draft.chart_type === 'heatmap' ? numeric.length >= 2 : !!draft.x_column && !!draft.y_column && numeric.some((c) => c.name === draft.y_column)),
    singleValid = !!preview && !!preview.coordinates?.length && ((draft.chart_type === 'embedding_categorical' && !!draft.color_field) || (draft.chart_type === 'embedding_continuous' && !!draft.color_field) || (draft.chart_type === 'feature' && draft.genes.length === 1) || (['violin', 'dotplot'].includes(draft.chart_type) && !!draft.group_column && draft.genes.length > 0)),
    ecologyValid = !!preview && (draft.chart_type === 'ecology_composition' ? !!draft.x_column && !!draft.y_column && !!draft.color_field && numeric.some((c) => c.name === draft.y_column) : draft.chart_type === 'ecology_alpha_diversity' ? !!draft.ecology_sample_column && !!draft.ecology_metric_column && !!draft.ecology_metric.trim() && numeric.some((c) => c.name === draft.y_column) : draft.chart_type === 'ecology_beta_ordination' ? !!draft.ecology_sample_column && !!draft.x_column && !!draft.y_column && draft.x_column !== draft.y_column && numeric.some((c) => c.name === draft.x_column) && numeric.some((c) => c.name === draft.y_column) : draft.chart_type === 'ecology_ordination_biplot' ? !!draft.ecology_sample_column && !!draft.ecology_entity_type_column && draft.x_column !== draft.y_column && numeric.some((c) => c.name === draft.x_column) && numeric.some((c) => c.name === draft.y_column) && preview.columns.some((c) => c.name === draft.ecology_sample_column) && preview.columns.some((c) => c.name === draft.ecology_entity_type_column) : draft.chart_type === 'ecology_environment_gradient' ? !!draft.ecology_sample_column && !!draft.x_column && !!draft.y_column && draft.x_column !== draft.y_column && numeric.some((c) => c.name === draft.x_column) && numeric.some((c) => c.name === draft.y_column) && (draft.ecology_environment_mode === 'existing_vector' ? !!draft.ecology_entity_type_column : !!draft.ecology_environment_column && numeric.some((c) => c.name === draft.ecology_environment_column)) : draft.chart_type === 'ecology_time_series' ? !!draft.ecology_sample_column && !!draft.ecology_time_column && !!draft.ecology_value_column && numeric.some((c) => c.name === draft.ecology_time_column) && numeric.some((c) => c.name === draft.ecology_value_column) && (!draft.ecology_error_column || numeric.some((c) => c.name === draft.ecology_error_column)) : draft.chart_type === 'ecology_spatial_points' ? !!draft.ecology_sample_column && !!draft.x_column && !!draft.y_column && draft.x_column !== draft.y_column && numeric.some((c) => c.name === draft.x_column) && numeric.some((c) => c.name === draft.y_column) && (draft.ecology_spatial_coordinate_mode === 'geographic_wgs84' || (!!draft.ecology_spatial_reference.trim() && draft.ecology_spatial_unit !== 'degrees')) : false),
    omicsValid = !!preview && (draft.chart_type.startsWith('spatial_') ? !!preview.coordinates?.length : ['genome_tracks', 'circos', 'dna_features'].includes(draft.chart_type) ? true : draft.chart_type === 'r_ggplot' ? !!draft.x_column && !!draft.y_column : false),
    valid = mode === 'table' ? tableValid : mode === 'single_cell' ? singleValid : mode === 'ecology' ? ecologyValid : omicsValid
  const sameDatasetPanels = Boolean(figureImage) || panels.every((panel) => panel.chart.dataset_id === draft.dataset_id)
  const figureChartLimit = figureImage ? 1 : 4
  const canAddFigureChart = panels.length < figureChartLimit && mode !== 'omics' && (!figureImage || mode === 'table')
  const figureReady = panels.length > 0 && (!figureImage || (
    panels.length === 1 && figureImage.panel.x_um_per_pixel > 0 && figureImage.panel.scale_bar_um > 0
  ))
  const fieldOptions = preview?.columns ?? []
  const chooseOmics = (direction: OmicsDirection) => {
    setMode('omics')
    setFormat('pdf')
    setOmicsDirection(direction)
    setPreview(null)
    setResult(null)
    const chartType = direction === 'spatial' ? 'spatial_categorical' : direction === 'genome' ? 'genome_tracks' : direction === 'circos' ? 'circos' : direction === 'dna' ? 'dna_features' : 'r_ggplot'
    setDraft({
      ...initial,
      chart_type: chartType,
      title: omicsDirections[direction].title,
    })
    setPage(1)
  }
  const chooseTable = () => {
    setMode('table')
    setFormat('pdf')
    setPreview(null)
    setResult(null)
    setDraft({ ...initial, chart_type: 'scatter', title: 'Cell response' })
    setPage(1)
  }
  const chooseSingleCell = () => {
    setMode('single_cell')
    setFormat('pdf')
    setPreview(null)
    setResult(null)
    setDraft({ ...initial, chart_type: 'embedding_categorical', title: 'Single-cell map' })
    setPage(1)
  }
  const chooseIllustration = (kind: DocumentKind) => {
    setIllustrationKind(kind)
    setIllustrationFile(null)
    setIllustrationSkillDraft(null)
    setPage(6)
  }
  const addResultToFigure = () => {
    if (!result || !canAddFigureChart) return
    setPanels([...panels, { chart: structuredClone(result.chart), image: result.image }])
    setAssembly(null)
    if (assemblyIntent) setPage(8)
  }
  const openSavedFile = (file: File) => {
    if (file.name.toLowerCase().endsWith('.bfsillustration.json')) {
      setIllustrationFile(file)
      setIllustrationSkillDraft(null)
      setPage(6)
      setAiMode(false)
    } else if (file.name.toLowerCase().endsWith('.bfsproj')) {
      void openProject(file)
    } else {
      setNotice('请选择 .bfsproj 图表/图版项目或 .bfsillustration.json 生物图示项目。')
    }
  }
  const chooseEcology = (direction: EcologyDirection) => {
    setMode('ecology')
    setFormat('pdf')
    setEcologyDirection(direction)
    setPreview(null)
    setResult(null)
    const chartType = direction === 'community' ? 'ecology_composition' : direction === 'diversity' ? 'ecology_alpha_diversity' : direction === 'ordination' ? 'ecology_ordination_biplot' : direction === 'environment' ? 'ecology_environment_gradient' : direction === 'time' ? 'ecology_time_series' : 'ecology_spatial_points'
    setDraft({
      ...initial,
      chart_type: chartType,
      title: ecologyDirections[direction].title,
      x_column: direction === 'diversity' ? 'group' : direction === 'community' ? 'sample' : direction === 'time' ? 'time' : direction === 'spatial' ? 'longitude' : 'axis_1',
      y_column: direction === 'diversity' ? 'value' : direction === 'community' ? 'abundance' : direction === 'time' ? 'value' : direction === 'spatial' ? 'latitude' : 'axis_2',
      color_field: direction === 'community' ? 'taxon' : null,
      group_column: direction === 'time' || direction === 'spatial' ? 'group' : null,
      ecology_sample_column: direction === 'ordination' || direction === 'environment' ? 'entity' : 'sample',
      ecology_metric: direction === 'diversity' ? 'Shannon' : '',
      ecology_value_mode: 'relative_fraction',
      ecology_environment_column: direction === 'environment' ? 'nitrate' : '',
    })
    setPage(1)
  }
  const omicsForm =
    mode === 'omics' ? (
      <div className="wf-form">
        <p className="wf-form-note">{omicsDirection ? `${omicsDirections[omicsDirection].title} · ${omicsDirections[omicsDirection].formats}` : '请选择组学方向'}</p>
        {omicsDirection === 'spatial' && (
          <>
            <label>
              空间坐标
              <select value={draft.coordinate_key} onChange={(e) => change({ coordinate_key: e.target.value })}>
                {preview?.coordinates?.map((c) => (
                  <option key={c.key}>{c.key}</option>
                ))}
              </select>
            </label>
            {['spatial_categorical', 'spatial_continuous'].includes(draft.chart_type) && (
              <label>
                颜色字段
                <select value={draft.color_field ?? ''} onChange={(e) => change({ color_field: e.target.value || null })}>
                  <option value="">请选择</option>
                  {fieldOptions.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
            )}
            {draft.chart_type === 'spatial_feature' && (
              <label>
                基因
                <input
                  value={draft.genes.join(', ')}
                  onChange={(e) =>
                    change({
                      genes: e.target.value
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </label>
            )}
            <label>
              表达来源
              <select value={draft.expression_source} onChange={(e) => change({ expression_source: e.target.value })}>
                <option value="X">X</option>
                {preview?.has_raw && <option value="raw">raw</option>}
                {preview?.layers?.map((layer) => (
                  <option key={layer} value="layer">
                    layer: {layer}
                  </option>
                ))}
              </select>
            </label>
            {draft.expression_source === 'layer' && (
              <label>
                Layer 名称
                <input value={draft.expression_layer ?? ''} onChange={(e) => change({ expression_layer: e.target.value })} />
              </label>
            )}
          </>
        )}
        {omicsDirection === 'r' && (
          <>
            <label>
              X 轴
              <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
                <option value="">请选择</option>
                {fieldOptions.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
            <label>
              Y 轴
              <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                <option value="">请选择</option>
                {numeric.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
            <label>
              颜色分组
              <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
                <option value="">不分组</option>
                {fieldOptions.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
            <p className="wf-form-note">R 仅执行内置 ggplot2 模板，不接收任意 R 代码。</p>
          </>
        )}
        {['genome', 'circos', 'dna'].includes(omicsDirection ?? '') && <p className="wf-form-note">文件已校验。字段和区间由本地适配器读取；下一步可调整标题、主题、色板和导出尺寸。</p>}
      </div>
    ) : null
  const ecologyForm =
    mode === 'ecology' ? (
      draft.chart_type === 'ecology_composition' ? (
        <div className="wf-form">
          <p className="wf-form-note">群落组成首版使用长表：每行一个样品 × 分类单元记录；不自动合并重复键或补齐缺失值。</p>
          <label>
            样品字段
            <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            丰度字段
            <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            分类单元字段
            <select value={draft.color_field ?? ''} onChange={(e) => change({ color_field: e.target.value || null })}>
              <option value="">请选择</option>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            丰度语义
            <select
              value={draft.ecology_value_mode}
              onChange={(e) =>
                change({
                  ecology_value_mode: e.target.value as Chart['ecology_value_mode'],
                })
              }
            >
              <option value="relative_fraction">相对丰度分数（0–1）</option>
              <option value="count">原始计数（本机归一化为比例）</option>
            </select>
          </label>
          <p className="wf-form-note">最多 60 个样品；分类单元上限由所选色板容量决定，默认主题为 3 个。导出图中的百分比来自明确选择的丰度语义。</p>
        </div>
      ) : draft.chart_type === 'ecology_ordination_biplot' ? (
        <div className="wf-form">
          <p className="wf-form-note">只展示已有二维排序坐标；sample 为点，taxon 为从原点出发的向量。</p>
          <label>
            实体名称
            <select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            实体类型
            <select value={draft.ecology_entity_type_column} onChange={(e) => change({ ecology_entity_type_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            第一轴
            <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            第二轴
            <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            样品分组
            <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">不分组</option>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
        </div>
      ) : draft.chart_type === 'ecology_environment_gradient' ? (
        <div className="wf-form">
          <p className="wf-form-note">仅展示已有二维坐标与环境字段；不计算相关性、envfit、回归或显著性。</p>
          <label>
            环境模式
            <select
              value={draft.ecology_environment_mode}
              onChange={(e) =>
                change({
                  ecology_environment_mode: e.target.value as Chart['ecology_environment_mode'],
                })
              }
            >
              <option value="continuous_value">连续环境值着色</option>
              <option value="existing_vector">已有环境向量</option>
            </select>
          </label>
          <label>
            样品/实体字段
            <select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            实体类型字段
            <select value={draft.ecology_entity_type_column} onChange={(e) => change({ ecology_entity_type_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            第一轴
            <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            第二轴
            <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          {draft.ecology_environment_mode === 'continuous_value' && (
            <label>
              环境值字段
              <select value={draft.ecology_environment_column} onChange={(e) => change({ ecology_environment_column: e.target.value })}>
                {numeric.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            样品分组
            <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">不分组</option>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
        </div>
      ) : draft.chart_type === 'ecology_time_series' ? (
        <div className="wf-form">
          <p className="wf-form-note">每条线只连接同一个重复测量轨迹；分组仅控制颜色。系统不聚合、平滑、插值或计算显著性。</p>
          <label>
            样品 / 监测对象
            <select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            数值时间
            <select value={draft.ecology_time_column} onChange={(e) => change({ ecology_time_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            观测值
            <select value={draft.ecology_value_column} onChange={(e) => change({ ecology_value_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            显示分组
            <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">不分组</option>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            重复测量轨迹
            <select value={draft.ecology_replicate_column} onChange={(e) => change({ ecology_replicate_column: e.target.value })}>
              <option value="">未提供（按样品连接）</option>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            对称误差大小
            <select value={draft.ecology_error_column} onChange={(e) => change({ ecology_error_column: e.target.value })}>
              <option value="">不显示</option>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <p className="wf-form-note">误差必须非负，仅按原值显示；不推断 SD、SE 或置信区间。</p>
        </div>
      ) : draft.chart_type === 'ecology_spatial_points' ? (
        <div className="wf-form">
          <p className="wf-form-note">只绘制已有点位；不加载底图、不重投影，也不计算距离、热点、插值或其他空间统计。</p>
          <label>
            坐标模式
            <select
              value={draft.ecology_spatial_coordinate_mode}
              onChange={(e) => {
                const next = e.target.value as Chart['ecology_spatial_coordinate_mode']
                change(
                  next === 'geographic_wgs84'
                    ? { ecology_spatial_coordinate_mode: next, ecology_spatial_reference: 'EPSG:4326', ecology_spatial_unit: 'degrees' }
                    : { ecology_spatial_coordinate_mode: next, ecology_spatial_reference: '', ecology_spatial_unit: 'm' },
                )
              }}
            >
              <option value="geographic_wgs84">WGS84 经度 / 纬度</option>
              <option value="planar">平面 X / Y 坐标</option>
            </select>
          </label>
          <label>
            样品 / 点位标识
            <select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {draft.ecology_spatial_coordinate_mode === 'geographic_wgs84' ? '经度字段' : 'X 坐标字段'}
            <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {draft.ecology_spatial_coordinate_mode === 'geographic_wgs84' ? '纬度字段' : 'Y 坐标字段'}
            <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            显示分组
            <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">不分组</option>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          {draft.ecology_spatial_coordinate_mode === 'planar' ? (
            <>
              <label>
                坐标参考说明
                <input value={draft.ecology_spatial_reference} onChange={(e) => change({ ecology_spatial_reference: e.target.value })} placeholder="例如 EPSG:32650 或样地局部坐标" />
              </label>
              <label>
                坐标单位
                <select value={draft.ecology_spatial_unit} onChange={(e) => change({ ecology_spatial_unit: e.target.value as Chart['ecology_spatial_unit'] })}>
                  <option value="m">米</option>
                  <option value="km">千米</option>
                  <option value="arbitrary">任意单位</option>
                </select>
              </label>
            </>
          ) : (
            <p className="wf-form-note">固定为 EPSG:4326；经度范围 -180–180，纬度范围 -90–90。图上角度距离不是地表距离。</p>
          )}
          <p className="wf-form-note">最多 5000 个唯一点位；同坐标的不同点位会原样重叠，不自动合并或抖动。</p>
        </div>
      ) : (
        <div className="wf-form">
          <p className="wf-form-note">本阶段只展示已有 α 指标或 β 排序坐标，不在本机计算多样性或距离矩阵。</p>
          <label>
            样品字段
            <select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          {draft.chart_type === 'ecology_alpha_diversity' ? (
            <>
              <label>
                指标字段
                <select value={draft.ecology_metric_column} onChange={(e) => change({ ecology_metric_column: e.target.value })}>
                  {fieldOptions.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                已有指标名称
                <input value={draft.ecology_metric} onChange={(e) => change({ ecology_metric: e.target.value })} placeholder="例如 Shannon" />
              </label>
              <label>
                指标值
                <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                  {numeric.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <>
              <label>
                第一轴
                <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
                  {numeric.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                第二轴
                <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                  {numeric.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
            </>
          )}
          <label>
            分组字段
            <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">不分组</option>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
        </div>
      )
    ) : null
  const homeView = (
    <>
      <div className="wf-intro">
        <span className="wf-overline">YOUR RESEARCH, CLEARLY DRAWN</span>
        <h1 className="wf-spotlight-title" aria-label="从想完成的作品开始。">
          <span className="wf-title-zh" aria-hidden="true">
            从想完成的作品开始。
          </span>
          <span className="wf-title-en" lang="en" aria-hidden="true">
            Start with what you want to make.
          </span>
        </h1>
        <p className="wf-spotlight-subtitle" aria-label="选择图表、图版、生物图示或图像工作台，再进入对应的任务。">
          <span className="wf-subtitle-zh" aria-hidden="true">
            选择图表、图版、生物图示或图像工作台，再进入对应的任务。
          </span>
          <span className="wf-subtitle-en" lang="en" aria-hidden="true">
            Choose a chart, figure, illustration, or image workspace.
          </span>
        </p>
        <button className="primary wf-workbench-entry" onClick={() => showMode(true)}>打开绘图工作台 <span lang="en">/ Drawing workbench</span></button>
      </div>
      <div className="wf-categories wf-product-categories">
        <button className="wf-category" onClick={() => { setAssemblyIntent(false); setPage(7) }}>
          <span className="wf-category-icon">▦</span>
          <strong>制作数据图表 <span>↗</span></strong>
          <p lang="en">Create a data chart</p>
          <small>基础表格、单细胞、空间组学、基因组、生态与 R 绘图</small>
        </button>
        <button className="wf-category" onClick={() => { setAssemblyIntent(true); setPage(8) }}>
          <span className="wf-category-icon">▤</span>
          <strong>排版多图图版 <span>↗</span></strong>
          <p lang="en">Arrange a multi-panel figure</p>
          <small>把已生成的图表加入工作栏，统一标签、图例与尺寸</small>
        </button>
        <button className="wf-category" onClick={() => setPage(9)}>
          <span className="wf-category-icon">✦</span>
          <strong>绘制生物图示 <span>↗</span></strong>
          <p lang="en">Draw a biological illustration</p>
          <small>机制图、实验流程图与图形摘要</small>
        </button>
        <button className="wf-category" onClick={() => setPage(10)}>
          <span className="wf-category-icon">◫</span>
          <strong>处理科研图像 <span>↗</span></strong>
          <p lang="en">Explore the image workspace</p>
          <small>Fiji 原命令清单、来源与逐项核验状态</small>
        </button>
      </div>
      <div className="wf-home-utilities">
        <button className="wf-open-project" onClick={() => projectInputRef.current?.click()}><FolderIcon />打开已有项目 <span lang="en">/ Open a project</span></button>
        <button className="wf-file-guide-toggle" aria-expanded={showFileGuide} onClick={() => setShowFileGuide(!showFileGuide)}>我有一个文件，先看从哪里开始 {showFileGuide ? '↑' : '↓'}</button>
      </div>
      {showFileGuide && <div className="wf-file-guide">
        <p>按文件内容和想做的作品选择；原始文件会在下一步由你亲自选择。</p>
        <button onClick={() => { setAssemblyIntent(false); setPage(7) }}>CSV / XLSX、H5AD、GenBank 或轨道文件 → 制作数据图表</button>
        <button onClick={() => setPage(10)}>显微图像或图像栈 → 查看图像工作台</button>
        <button onClick={() => projectInputRef.current?.click()}>.bfsproj / .bfsillustration.json → 打开已有项目</button>
      </div>}
      <p className="wf-home-note">从选任务、确认数据、调整图形到检查导出。真实数据只在本机处理；软件不自动给出统计或科学结论。</p>
    </>
  )
  const chartCatalog = (
    <>
      <div className="wf-title wf-catalog-title">
        <span className="wf-overline">DATA CHARTS / 选择来源</span>
        <h1>你要制作哪类数据图表？</h1>
        <p>先选数据类型或绘图方式，再确认文件和字段。所有图表只展示输入中已有的数据或结果。</p>
      </div>
      <div className="wf-catalog-grid">
        <button className="wf-category" onClick={chooseTable}><span className="wf-category-icon">▦</span><strong>基础表格图表 ↗</strong><p>CSV / XLSX</p><small>散点 · 柱状 · 折线 · 箱线 · 热图</small></button>
        <button className="wf-category" onClick={chooseSingleCell}><span className="wf-category-icon">◉</span><strong>单细胞图表 ↗</strong><p>已有分析结果的 H5AD</p><small>UMAP / t-SNE · Feature · Violin · Dot Plot</small></button>
        <button className="wf-category" onClick={() => chooseOmics('spatial')}><span className="wf-category-icon">⌖</span><strong>空间组学图表 ↗</strong><p>已有空间坐标的 H5AD</p><small>空间分类 · 连续值 · Feature Plot</small></button>
        <button className="wf-category" onClick={() => setPage(4)}><span className="wf-category-icon">≋</span><strong>基因组与序列图表 ↗</strong><p>选择轨道、Circos 或 DNA 特征</p><small>基因组文本轨道 · JSON manifest · GenBank</small></button>
        <button className="wf-category" onClick={() => { setEcologyDirection(null); setPage(5) }}><span className="wf-category-icon">∿</span><strong>生态学图表 ↗</strong><p>群落、多样性与环境数据</p><small>组成 · 排序 · 时间序列 · 空间点位</small></button>
        <button className="wf-category" onClick={() => chooseOmics('r')}><span className="wf-category-icon">R</span><strong>R 绘图 ↗</strong><p>已审核的 ggplot2 静态散点模板</p><small>需要本机已安装的 R；不运行任意 R 代码</small></button>
      </div>
      <div className="wf-bottom"><button onClick={() => setPage(0)}>← 返回作品类型</button></div>
    </>
  )
  const illustrationCatalog = (
    <>
      <div className="wf-title wf-catalog-title">
        <span className="wf-overline">BIOLOGICAL ILLUSTRATIONS / 选择用途</span>
        <h1>你要绘制哪种生物图示？</h1>
        <p>使用本机原创组件与空白布局，科学关系、流程和证据由你编辑与核实。</p>
      </div>
      <div className="wf-catalog-grid wf-illustration-grid">
        <button className="wf-category" onClick={() => chooseIllustration('mechanism')}><span className="wf-category-icon">◎</span><strong>机制图 ↗</strong><p>组织实体与关系</p><small>Mechanism diagram · 空白画布与机制布局</small></button>
        <button className="wf-category" onClick={() => chooseIllustration('experimental_workflow')}><span className="wf-category-icon">⇢</span><strong>实验流程图 ↗</strong><p>编排步骤与流向</p><small>Experimental workflow · 手动填写方法内容</small></button>
        <button className="wf-category" onClick={() => chooseIllustration('graphical_abstract')}><span className="wf-category-icon">▧</span><strong>图形摘要 ↗</strong><p>编排摘要面板</p><small>Graphical abstract · 手动组织研究叙事</small></button>
      </div>
      <div className="wf-bottom"><button onClick={() => setPage(0)}>← 返回作品类型</button></div>
    </>
  )
  const figureWorkspace = (
    <>
      <div className="wf-title">
        <span className="wf-overline">MULTI-PANEL FIGURE / 图版工作栏</span>
        <h1>排版多图图版</h1>
        <p>制作图表后加入右侧工作栏。可以排最多 4 张图表，也可以把一张科研图像与一张统计图排成 A/B 图版。</p>
      </div>
      <div className="wf-figure-guide">
        <div><b>1</b><strong>加入图表</strong><p>使用当前本机数据生成图表，然后点“加入图版”。</p></div>
        <div><b>2</b><strong>调整版面</strong><p>在右侧选择模板、排列、尺寸和标签。</p></div>
        <div><b>3</b><strong>检查并导出</strong><p>生成实际图版预览，检查后导出成品。</p></div>
      </div>
      <div className="wf-bottom"><button onClick={() => setPage(0)}>← 返回作品类型</button><button className="primary" onClick={() => setPage(7)}>{panels.length ? '继续添加图表 →' : '制作第一张图表 →'}</button></div>
      <section className="wf-config">
        <h2>加入科研图像</h2>
        <p>混合图版中，科研图像放在 A，统计图放在 B。请选择单平面 PNG 或 TIFF，并使用你已确认的标定。</p>
        {!figureImage ? (
          <label>选择源图<input type="file" accept=".png,.tif,.tiff" disabled={panels.length > 1 || panels.some((item) => !['scatter', 'bar', 'line', 'box', 'heatmap'].includes(item.chart.chart_type))} onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void importFigureImage(file)
          }} /></label>
        ) : (
          <>
            <p>A · {figureImage.name}</p>
            <label>横向标定（µm/像素）<input type="number" min="0" step="any" value={figureImage.panel.x_um_per_pixel || ''} onChange={(e) => updateFigureImage({ x_um_per_pixel: Number(e.target.value) })} /></label>
            <label>比例尺长度（µm）<input type="number" min="0" step="any" value={figureImage.panel.scale_bar_um || ''} onChange={(e) => updateFigureImage({ scale_bar_um: Number(e.target.value) })} /></label>
            <label>比例尺颜色<select value={figureImage.panel.scale_bar_color} onChange={(e) => updateFigureImage({ scale_bar_color: e.target.value === 'black' ? 'black' : 'white' })}>
              <option value="white">白色</option><option value="black">黑色</option>
            </select></label>
            <details>
              <summary>裁切选项</summary>
              <p>从源图左上角以像素计。裁切只用于图版，项目保留原图。</p>
              {figureImage.panel.crop ? (
                <>
                  {([['x', '起点 X'], ['y', '起点 Y'], ['width', '宽'], ['height', '高']] as const).map(([key, title]) => (
                    <label key={key}>{title}<input type="number" min={key === 'x' || key === 'y' ? 0 : 1} step="1" value={figureImage.panel.crop?.[key]} onChange={(e) => {
                      const crop = figureImage.panel.crop
                      if (crop) updateFigureImage({ crop: { ...crop, [key]: Number(e.target.value) } })
                    }} /></label>
                  ))}
                  <button onClick={() => updateFigureImage({ crop: null })}>恢复整图</button>
                </>
              ) : assembly?.imageCheck ? <button onClick={() => {
                const [width, height] = assembly.imageCheck!.source_pixels
                updateFigureImage({ crop: { x: 0, y: 0, width, height } })
              }}>设置裁切</button> : <p>先生成一次整图预览，即可按原图尺寸设置裁切。</p>}
            </details>
            <button onClick={removeFigureImage}>移除科研图像</button>
          </>
        )}
        {panels.length > 1 && <p>先把图表减至一张，再加入科研图像。</p>}
        {panels.length === 1 && !['scatter', 'bar', 'line', 'box', 'heatmap'].includes(panels[0].chart.chart_type) && <p>混合图版首版支持五类基础统计图。请先移除当前图表。</p>}
      </section>
      <section className="wf-config"><h2>保存可编辑项目</h2><p>.bfsproj 会保存图表配置、图版布局及源数据副本，方便下次继续编辑；PDF、SVG、PNG 或 TIFF 是导出的成品文件。当前项目格式只支持来自同一数据集的子图。</p><label>项目名称<input value={name} onChange={(e) => setName(e.target.value)} /></label><div className="wf-actions"><button disabled={!figureReady || !sameDatasetPanels || (!figureImage && !draft.dataset_id)} onClick={saveProject}>保存 .bfsproj 项目</button><button onClick={() => projectInputRef.current?.click()}>打开已有项目</button></div>{!sameDatasetPanels && <p role="status">这些子图来自不同数据集，可以导出图版，但暂不能保存为同一个可编辑项目。</p>}</section>
    </>
  )
  const ecologyCard = (direction: EcologyDirection) => {
    const content = (
      <>
        <EcologyPreview direction={direction} compact />
        <div className="wf-ecology-meta">
          <span>虚拟数据示意</span>
        </div>
        <strong>
          {ecologyDirections[direction].title} ↗
        </strong>
        <p>{ecologyDirections[direction].description}</p>
        <small>{ecologyDirections[direction].formats}</small>
      </>
    )
    return (
      <button className="wf-ecology-card wf-ecology-card-active" key={direction} onClick={() => chooseEcology(direction)}>
        {content}
      </button>
    )
  }
  const ecologyView = (
    <>
      <div className="wf-title">
        <span className="wf-overline">ECOLOGY / 02</span>
        <h1>先选择你的生态学任务。</h1>
        <p>群落组成、多样性、排序、环境梯度、生态时间序列与空间点位均可进入本机绘图流程。</p>
      </div>
      <div className="wf-ecology-grid">{(Object.keys(ecologyDirections) as EcologyDirection[]).map(ecologyCard)}</div>
      <p className="wf-form-note wf-ecology-note">空间生态首版只接受已有点位表，不含在线地图、底图导入、重投影或空间统计；所有方向的真实数据均只在本机处理。</p>
      <div className="wf-bottom">
        <button onClick={() => setPage(7)}>← 返回数据图表</button>
      </div>
    </>
  )
  const modeSwitch = (
    <div className="dw-switch dw-mode-switch" role="group" aria-label="工作模式">
      <button type="button" aria-pressed={!aiMode} onClick={() => showMode(false)}>本地模式</button>
      <button type="button" aria-pressed={aiMode} onClick={() => showMode(true)}>AI 模式</button>
    </div>
  )
  return (
    <div className={aiMode ? 'wf wf-ai' : 'wf'}>
      {visitedAI && <DrawingWorkbench visible={aiMode} modeSwitch={modeSwitch} busy={!!busy}
        canApply={canApplyWorkbenchDraft} recent={recentProjects}
        onOpenProject={(file) => { if (file) openSavedFile(file); else projectInputRef.current?.click() }}
        onOpen={(destination) => {
          const target = { chart: 7, figure: 8, image: 10, illustration: 9 }[destination]
          const editingHere = (destination === 'chart' && [1, 2, 3, 4, 5, 7].includes(page)) || (destination === 'illustration' && page === 6)
          if (!editingHere) setPage(target)
          setAiMode(false)
        }}
        onDraft={proposeWorkbenchDraft} onApply={applyWorkbenchDraft} onInspect={inspectWorkbenchSample}
        onConnect={connectWorkbench} onDisconnect={disconnectWorkbench}
        onDraftIllustration={proposeIllustrationDraft}
        onApplyIllustration={(document) => { if (!canApplyWorkbenchDraft) return; setIllustrationSkillDraft(document); setIllustrationSkillRevision((value) => value + 1); setIllustrationKind('experimental_workflow'); setIllustrationFile(null); setPage(6); setAiMode(false) }} />}
      <input ref={projectInputRef} className="wf-hidden-input" type="file" accept=".bfsproj,.bfsillustration.json" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) openSavedFile(file) }} />
      <div hidden={aiMode}>
      {page === 6 ? <>
        <div className="dw-illustration-mode">{modeSwitch}</div>
        <IllustrationStudio key={illustrationFile ? `${illustrationFile.name}-${illustrationFile.lastModified}` : illustrationSkillDraft ? `skill-${illustrationSkillRevision}` : illustrationKind} initialKind={illustrationKind} initialProject={illustrationFile} initialDocument={illustrationSkillDraft} onBack={() => { setIllustrationFile(null); setIllustrationSkillDraft(null); setPage(9) }} />
      </> : <>
      <header className="wf-header">
        <button className="wf-brand" onClick={() => setPage(0)}>
          <span className="wf-logo">✳</span>BioFigure <span>Studio</span>
        </button>
        <div className="wf-header-tools"><span className="wf-badge">● 本机优先</span><button onClick={() => projectInputRef.current?.click()}>打开已有项目</button>{modeSwitch}</div>
      </header>
      <div className="wf-notice">数据与项目只在本机处理；绘图使用输入中已有的值和分析结果，不自动计算统计结论。本机绘图助手按需运行。</div>
      <div className={`wf-layout ${[0, 4, 5, 7, 9, 10].includes(page) ? 'wf-home-layout' : ''}`}>
        <main className="wf-main">
          {page === 0 ? (
            homeView
          ) : page === 7 ? (
            chartCatalog
          ) : page === 8 ? (
            figureWorkspace
          ) : page === 9 ? (
            illustrationCatalog
          ) : page === 10 ? (
            <ImageWorkspace onBack={() => setPage(0)} />

          ) : page === 5 ? (
            ecologyView
          ) : page === 4 ? (
            <>
              <div className="wf-title">
                <span className="wf-overline">GENOME & SEQUENCE CHARTS / 选择类型</span>
                <h1>选择基因组或序列图表。</h1>
                <p>选择现有文件对应的图表类型，再检查输入内容。</p>
              </div>
              <div className="wf-omics-grid">
                {(['genome', 'circos', 'dna'] as OmicsDirection[]).map((direction) => (
                  <button className="wf-omics-card" key={direction} onClick={() => chooseOmics(direction)}>
                    <OmicsPreview direction={direction} compact />
                    <strong>{omicsDirections[direction].title} ↗</strong>
                    <p>{omicsDirections[direction].description}</p>
                    <small>{omicsDirections[direction].formats}</small>
                  </button>
                ))}
              </div>
              <div className="wf-bottom">
                <button onClick={() => setPage(7)}>← 返回数据图表</button>
              </div>
            </>
          ) : (
            <>
              <nav className="wf-steps" aria-label="绘图步骤">
                {['确认数据', '调整图表', '检查并导出'].map((t, i) => (
                  <span key={t} aria-current={page === i + 1 ? 'step' : undefined} className={page === i + 1 ? 'active' : ''}>
                    <b>{i + 1}</b>
                    {t}
                  </span>
                ))}
              </nav>
              <div className="wf-title">
                <span className="wf-overline">
                  {mode === 'single_cell' ? 'SINGLE CELL / 0' : mode === 'omics' ? `OMICS / ${omicsDirection?.toUpperCase() ?? ''}` : mode === 'ecology' ? `ECOLOGY / ${(ecologyDirection ?? 'community').toUpperCase()}` : 'DATA TABLE / 0'}
                  {page}
                </span>
                <h1>{['', '先确认你的数据。', '调整图表的表达。', '检查图表并导出。'][page]}</h1>
              </div>
              {page === 1 && (
                <>
                  <div className="wf-field">
                    <span>图表类型 / Chart type</span>
                    <div className="wf-chips">
                      {Object.entries(kinds).map(([key, title]) => (
                        <button
                          key={key}
                          aria-pressed={draft.chart_type === key}
                          className={draft.chart_type === key ? 'selected' : ''}
                          onClick={() => {
                            if (mode === 'ecology' && ecologyDirection === 'diversity' && key !== draft.chart_type) {
                              setPreview(null)
                              setResult(null)
                              setDraft({
                                ...initial,
                                chart_type: key,
                                title: title,
                                x_column: key === 'ecology_beta_ordination' ? 'PCoA1' : 'group',
                                y_column: key === 'ecology_beta_ordination' ? 'PCoA2' : 'value',
                                group_column: 'group',
                                ecology_metric: key === 'ecology_alpha_diversity' ? 'Shannon' : '',
                              })
                            } else change({ chart_type: key })
                          }}
                        >
                          {title}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="wf-upload">
                    <h3>{mode === 'single_cell' ? '提交 H5AD' : mode === 'omics' ? `提交 ${omicsDirection ? omicsDirections[omicsDirection].title : '组学数据'}` : mode === 'ecology' ? (ecologyDirection === 'diversity' ? '提交已有多样性结果' : ecologyDirection === 'time' ? '提交生态时间序列' : ecologyDirection === 'spatial' ? '提交空间点位表' : '提交群落组成数据') : '提交数据表格'}</h3>
                    <p>{mode === 'single_cell' ? 'H5AD · 最多 200 MB · 只读取已有结果' : mode === 'omics' ? (omicsDirection ? omicsDirections[omicsDirection].formats : '先选择组学方向') : mode === 'ecology' ? (ecologyDirection === 'diversity' ? 'CSV、XLSX · 已有指标或排序坐标 · 最多 5 MB' : ecologyDirection === 'time' ? 'CSV、XLSX · 数值时间 · 最多 5000 行 / 5 MB' : ecologyDirection === 'spatial' ? 'CSV、XLSX · 经纬度或平面坐标 · 最多 5000 行 / 5 MB' : 'CSV、XLSX · 长表 · 最多 5 MB') : 'CSV、XLSX · 最多 5 MB'}</p>
                    <label>
                      选择文件
                      <input
                        type="file"
                        accept={mode === 'single_cell' || (mode === 'omics' && omicsDirection === 'spatial') ? '.h5ad' : mode === 'omics' && omicsDirection === 'dna' ? '.gb,.gbk,.genbank' : mode === 'omics' && omicsDirection === 'circos' ? '.json' : mode === 'omics' && omicsDirection === 'genome' ? '.json,.bed,.bedgraph,.gff,.gff3,.gtf,.chrom.sizes' : '.csv,.xlsx'}
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          e.target.value = ''
                          if (file) void loadData(file)
                        }}
                      />
                    </label>
                    {(mode === 'table' || mode === 'ecology') && <button onClick={() => loadData()}>使用内置模拟数据</button>}
                  </div>
                  {preview && (
                    <div className="wf-data">
                      <h3>{preview.kind === 'single_cell' ? `H5AD 预览 · ${preview.cell_count} 个细胞 · ${preview.gene_count} 个基因` : preview.kind === 'dna' ? `GenBank 预览 · ${preview.sequence_length ?? 0} bp · ${preview.feature_count ?? 0} 个特征` : preview.kind === 'omics_manifest' ? `组学清单 · ${preview.summary ?? '本地 manifest'}` : preview.kind === 'genome_tracks' ? `基因组轨道 · ${preview.row_count ?? 0} 个区间` : `数据预览 · ${preview.row_count ?? 0} 行`}</h3>
                      <p>{preview.source_name ?? '内置模拟数据'} · {preview.matrix_format ?? '表格'}{preview.sha256 ? ` · SHA256 ${preview.sha256.slice(0, 12)}` : ''}</p>
                      <table>
                        <thead>
                          <tr>
                            {preview.columns.map((c) => (
                              <th key={c.name}>
                                {c.name}
                                <small>
                                  {' '}
                                  {c.dtype} · 缺失 {c.missing_count ?? 0}
                                </small>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {preview.rows.map((row, i) => (
                            <tr key={i}>
                              {preview.columns.map((c) => (
                                <td key={c.name}>{row[c.name] == null ? '缺失' : String(row[c.name])}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  {mode === 'table' ? (
                    <div className="wf-form">
                      <label>
                        X 轴
                        <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
                          <option value="">请选择</option>
                          {(draft.chart_type === 'heatmap' ? (preview?.columns ?? []) : numeric).map((c) => (
                            <option key={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Y 数值轴
                        <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                          <option value="">请选择</option>
                          {numeric.map((c) => (
                            <option key={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        颜色分组
                        <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
                          <option value="">不分组</option>
                          {fieldOptions.map((c) => (
                            <option key={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                  ) : mode === 'ecology' ? (
                    ecologyForm
                  ) : mode === 'omics' ? (
                    omicsForm
                  ) : (
                    <div className="wf-form">
                      <label>
                        坐标
                        <select value={draft.coordinate_key} onChange={(e) => change({ coordinate_key: e.target.value })}>
                          {preview?.coordinates?.map((c) => (
                            <option key={c.key}>{c.key}</option>
                          ))}
                        </select>
                      </label>
                      {['embedding_categorical', 'embedding_continuous'].includes(draft.chart_type) && (
                        <label>
                          颜色字段
                          <select value={draft.color_field ?? ''} onChange={(e) => change({ color_field: e.target.value || null })}>
                            <option value="">请选择</option>
                            {fieldOptions.map((c) => (
                              <option key={c.name}>{c.name}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      {['violin', 'dotplot'].includes(draft.chart_type) && (
                        <label>
                          分组字段
                          <select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
                            <option value="">请选择</option>
                            {fieldOptions.map((c) => (
                              <option key={c.name}>{c.name}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      {['feature', 'violin', 'dotplot'].includes(draft.chart_type) && (
                        <label>
                          基因（逗号分隔）
                          <input
                            value={draft.genes.join(', ')}
                            onChange={(e) =>
                              change({
                                genes: e.target.value
                                  .split(',')
                                  .map((s) => s.trim())
                                  .filter(Boolean),
                              })
                            }
                          />
                        </label>
                      )}
                      <label>
                        表达来源
                        <select value={draft.expression_source} onChange={(e) => change({ expression_source: e.target.value })}>
                          <option value="X">X</option>
                          {preview?.has_raw && <option value="raw">raw</option>}
                          {preview?.layers?.map((layer) => (
                            <option key={layer} value="layer">
                              layer: {layer}
                            </option>
                          ))}
                        </select>
                      </label>
                      {draft.expression_source === 'layer' && (
                        <label>
                          Layer 名称
                          <input value={draft.expression_layer ?? ''} onChange={(e) => change({ expression_layer: e.target.value })} />
                        </label>
                      )}
                      <label>
                        展示转换
                        <select value={draft.transform} onChange={(e) => change({ transform: e.target.value })}>
                          <option value="none">不转换</option>
                          <option value="log1p">log1p（写入配置）</option>
                        </select>
                      </label>
                    </div>
                  )}
                  <div className="wf-bottom">
                    <button onClick={() => setPage(7)}>← 返回数据图表</button>
                    <button className="primary" disabled={!valid} onClick={() => setPage(2)}>
                      确认数据，下一步 →
                    </button>
                  </div>
                </>
              )}
              {page === 2 && (
                <>
                  <div className="wf-form">
                    <label>
                      图表标题
                      <input value={draft.title} onChange={(e) => change({ title: e.target.value })} />
                    </label>
                    <label>
                      基础主题
                      <select value={draft.theme_id} onChange={(e) => change({ theme_id: e.target.value })}>
                        {Object.entries(themes).map(([key, title]) => (
                          <option key={key} value={key}>
                            {title}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      色板
                      <select value={draft.palette_id} onChange={(e) => change({ palette_id: e.target.value })}>
                        {['theme', 'colorblind', 'viridis', 'cividis', 'magma', 'coolwarm', 'clay', 'lagoon'].map((key) => (
                          <option key={key} value={key}>{paletteLabels[key]}</option>
                        ))}
                      </select>
                    </label>
                    {(['width_mm', 'height_mm', 'dpi', 'font_size', 'line_width'] as const).map((key) => (
                      <label key={key}>
                        {chartMeasureLabels[key]}
                        <input type="number" value={draft[key]} onChange={(e) => change({ [key]: Number(e.target.value) })} />
                      </label>
                    ))}
                    {draft.chart_type !== 'r_ggplot' && <SvgTextPicker value={draft.svg_text_mode} onChange={(svg_text_mode) => change({ svg_text_mode })} />}
                    <label>
                      显示图例
                      <input type="checkbox" checked={draft.show_legend} onChange={(e) => change({ show_legend: e.target.checked })} />
                    </label>
                  </div>
                  <div className="wf-live-preview">
                    <div className="wf-preview-stage">
                      <div className="wf-preview-paper">
                        {mode === 'omics' && omicsDirection ? (
                          <OmicsPreview direction={omicsDirection} colors={palettes[draft.palette_id === 'theme' ? draft.theme_id : draft.palette_id]} />
                        ) : mode === 'ecology' ? (
                          <EcologyPreview direction={ecologyDirection ?? 'community'} variant={draft.chart_type === 'ecology_alpha_diversity' ? 'alpha' : 'beta'} colors={palettes[draft.palette_id === 'theme' ? draft.theme_id : draft.palette_id]} />
                        ) : (
                          <SampleChart
                            draft={{
                              kind: kinds[draft.chart_type],
                              theme: themes[draft.theme_id],
                              ratio: '3 / 2',
                              format,
                              title: draft.title,
                            }}
                            palette={palettes[draft.palette_id === 'theme' ? draft.theme_id : draft.palette_id]}
                          />
                        )}
                      </div>
                    </div>
                    <p>此处是虚拟数据示意；下一步会用当前数据生成实际图表。</p>
                  </div>
                  <div className="wf-bottom">
                    <button onClick={() => setPage(1)}>← 返回数据确认</button>
                    <button className="primary" disabled={!valid} onClick={render}>
                      生成图表并检查 →
                    </button>
                  </div>
                </>
              )}
              {page === 3 && result && (
                <>
                  <div className="wf-result">
                    <img className="wf-real-image" src={result.image} alt="实际数据图表" />
                  </div>
                  <div className="wf-result-meta">
                    <span>
                      {kinds[result.chart.chart_type]} · {themes[result.chart.theme_id]}
                    </span>
                    <span>
                      {result.chart.width_mm} × {result.chart.height_mm} mm · {result.chart.dpi} DPI
                    </span>
                  </div>
                  <div className="wf-bottom">
                    <button onClick={() => setPage(2)}>← 调整图表</button>
                    <FormatPicker value={format} onChange={setFormat} />
                    <button onClick={() => download(result.artifact)}>
                      <FolderIcon />
                      导出 {format.toUpperCase()}
                    </button>
                    <button className="primary" disabled={!canAddFigureChart} onClick={addResultToFigure}>
                      {(mode === 'omics' || (figureImage && mode !== 'table')) ? '此类图表暂不支持当前图版' : `＋ 加入图版 ${panels.length}/${figureChartLimit}`}
                    </button>
                  </div>
                </>
              )}
              {page > 0 && page !== 4 && page !== 5 && (
                <section className="wf-config">
                  <label>
                    项目名称
                    <input value={name} onChange={(e) => setName(e.target.value)} />
                  </label>
                  <div className="wf-actions">
                    <button disabled={!draft.dataset_id || !sameDatasetPanels || (Boolean(figureImage) && !figureReady)} onClick={saveProject}>保存 .bfsproj 项目</button>
                    <label>
                      打开项目
                      <input
                        type="file"
                        accept=".bfsproj"
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          e.target.value = ''
                          if (file) void openProject(file)
                        }}
                      />
                    </label>
                  </div>
                  <p>.bfsproj 保存可编辑的图表配置与源数据副本，下次可重新打开。PDF、SVG、PNG 是当前图表的导出成品。图版项目仅支持同一数据集的子图。</p>
                  {!sameDatasetPanels && <p role="status">当前图版包含不同数据集，可导出图版成品，但暂不能保存为同一个项目。</p>}
                </section>
              )}
            </>
          )}
        </main>
        {[1, 2, 3, 8].includes(page) && (
          <aside className="wf-sidebar">
            <div className="wf-section-head">
              <h2>图版工作栏</h2>
              <span>{figureImage ? `${panels.length + 1}/2` : `${panels.length}/4`}</span>
            </div>
            {!panels.length && <div className="wf-empty"><span>▤</span><strong>还没有子图</strong><p>生成数据图表后点“加入图版”。</p></div>}
            <div className="wf-queue">
              {panels.map((p, i) => (
                <div className="wf-panel" key={i}>
                  <div className="wf-thumb">
                    <img className="wf-real-image" src={p.image} alt={`子图 ${i + 1}`} />
                  </div>
                  <div>
                    <strong>
                      {String.fromCharCode(65 + i + Number(Boolean(figureImage)))} · {kinds[p.chart.chart_type]}
                    </strong>
                    <small>{p.chart.title}</small>
                    <button onClick={() => { setPanels(panels.filter((_, j) => i !== j)); setAssembly(null) }}>移除</button>
                  </div>
                </div>
              ))}
            </div>
            <div className="wf-console">
              <h3>布局控制台</h3>
              <label>
                通用模板（非期刊官方）
                <select value={layout.template_id} onChange={(e) => applyTemplate(e.target.value)}>
                  <option value="single_column">单栏 90 × 120 mm</option>
                  <option value="double_column">双栏 180 × 120 mm</option>
                  <option value="square_grid">方形网格 180 × 180 mm</option>
                  <option value="custom">自定义</option>
                </select>
              </label>
              <label>
                排列
                <select value={layout.columns} onChange={(e) => updateLayout({ columns: Number(e.target.value), template_id: 'custom' })}>
                  <option value={1}>单列</option>
                  <option value={2}>双列</option>
                </select>
              </label>
              <label>
                子图标签
                <select value={layout.labels} onChange={(e) => updateLayout({ labels: e.target.value })}>
                  <option value="upper">A, B, C…</option>
                  <option value="lower">a, b, c…</option>
                  <option value="none">不显示</option>
                </select>
              </label>
              <label>
                标签位置
                <select value={layout.label_position} onChange={(e) => updateLayout({ label_position: e.target.value })}>
                  <option value="inside">图内左上</option>
                  <option value="outside">图外左上</option>
                </select>
              </label>
              <label>
                图例布局
                <select value={layout.legend_mode} onChange={(e) => updateLayout({ legend_mode: e.target.value })}>
                  <option value="per_panel">逐图图例</option>
                  <option value="shared">{figureImage ? '统计图内统一图例' : '共享图例'}</option>
                  <option value="none">不显示图例</option>
                </select>
              </label>
              {layout.legend_mode === 'shared' && (
                <label>
                  共享图例位置
                  <select value={layout.legend_position} onChange={(e) => updateLayout({ legend_position: e.target.value })}>
                    <option value="right">右侧</option>
                    <option value="bottom">底部</option>
                  </select>
                </label>
              )}
              {(['width_mm', 'height_mm', 'margin_top_mm', 'margin_right_mm', 'margin_bottom_mm', 'margin_left_mm', 'panel_gap_mm', 'label_font_size', 'dpi'] as const).map((key) => (
                <label key={key}>
                  {figureMeasureLabels[key]}
                  <input type="number" value={layout[key]} onChange={(e) => updateLayout({ [key]: Number(e.target.value), template_id: key === 'width_mm' || key === 'height_mm' || key.startsWith('margin_') || key === 'panel_gap_mm' ? 'custom' : layout.template_id })} />
                </label>
              ))}
              <SvgTextPicker value={layout.svg_text_mode} onChange={(svg_text_mode) => updateLayout({ svg_text_mode })} />
              <p>Noto Sans SC（OFL-1.1）固定审核字体。PDF 嵌入字体，保留可编辑 SVG 文字时请在目标编辑器安装对应字体。</p>
            </div>
            <button className="primary" disabled={!figureReady} onClick={assembly ? () => setReview(true) : renderAssembly}>
              <FolderIcon />
              {assembly ? '检查图版预览与导出 →' : '生成图版预览 →'}
            </button>
            <p>图版成品：PDF / SVG / PNG / TIFF。可编辑项目请另存为 .bfsproj。</p>
          </aside>
        )}
      </div>
      {review && assembly && (
        <div className="wf-overlay">
          <section className="wf-dialog" role="dialog" aria-modal="true">
            <div className="wf-section-head">
              <h2>最终图版 · 实际预览</h2>
              <button onClick={() => setReview(false)}>关闭</button>
            </div>
            <div className="wf-dialog-body">
              <img className="wf-real-image" src={assembly.image} alt="实际拼版预览" />
              {assembly.imageCheck && <p role="status">
                图像有效分辨率 {assembly.imageCheck.effective_dpi} DPI，导出 {assembly.imageCheck.output_dpi} DPI。
                源图 {assembly.imageCheck.source_pixels.join(' × ')} 像素，排版使用 {assembly.imageCheck.placed_pixels.join(' × ')} 像素。
                {assembly.imageCheck.below_output_dpi && '图像有效分辨率低于导出设置，请核对投稿要求。'}
              </p>}
            </div>
            <div className="wf-dialog-footer">
              <FormatPicker value={format} onChange={setFormat} tiff />
              <button className="primary" onClick={() => download(assembly.artifact)}>
                确认下载 {format.toUpperCase()}
              </button>
            </div>
          </section>
        </div>
      )}
      </>}
      </div>
      {busy && (
        <div className="wf-overlay wf-working-overlay">
          <div className="wf-working-card">
            <h2>biofigure 工作中</h2>
            <p>正在本机处理，请稍候…</p>
            <button onClick={() => active.current?.abort()}>取消等待</button>
            {busy === 'workbench-draft' && <button onClick={() => showMode(false)}>返回本地模式</button>}
          </div>
        </div>
      )}
      {notice && (
        <div className="wf-export-toast" role="status">
          {notice}
          <button onClick={() => setNotice('')}>×</button>
        </div>
      )}
    </div>
  )
}
