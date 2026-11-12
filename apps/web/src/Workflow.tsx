import WorkspaceModeSwitch from './WorkspaceModeSwitch'
import NavigationGroup from './NavigationGroup'
import { useEffect, useRef, useState } from 'react'
import { FolderIcon, SampleChart } from './WorkflowPrototype'
import IllustrationStudio from './IllustrationStudio'
import ImageWorkspace from './ImageWorkspace'
import DrawingWorkbench, { type ExternalDraft, type WorkbenchConnection, type WorkbenchProposal, type WorkbenchProvider } from './DrawingWorkbench'
import type { DocumentKind, IllustrationSpec } from './illustration'
import { EcologyPreview, OmicsPreview } from './WorkflowPreviews'
import { getWorkflowCatalog, type EcologyDirection, type OmicsDirection } from './WorkflowCatalog'
import './WorkflowPrototype.css'
import { useI18n, translate } from './i18n'
import LanguageSettings from './LanguageSettings'
import ChartStyleChoices from './ChartStyleChoices'
import { isPairedPalette, paletteChoices, scientificPaletteColors, scientificPalettes } from './chartPalettes'

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



const palettes: Record<string, string[]> = {
  ...scientificPaletteColors,
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
    throw new Error(typeof error.detail === 'string' ? error.detail : translate('en', `请求失败（${response.status}），请检查文件、字段和参数。`, `Request failed (${response.status}). Check the file, fields, and settings.`))
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
  const { t } = useI18n()
  return (
    <label>
      {t("SVG 文字", "SVG text")}<select value={value ?? 'outline'} onChange={(event) => onChange(event.target.value === 'editable' ? 'editable' : 'outline')}>
        <option value="outline">{t("转为路径（保持外观）", "Convert to paths (preserve appearance)")}</option>
        <option value="editable">{t("保留文字（便于外部编辑）", "Keep editable text")}</option>
      </select>
    </label>
  )
}
function FormatPicker({ value, onChange, tiff = false }: { value: string; onChange: (v: string) => void; tiff?: boolean }) {
  const { t } = useI18n()
  return (
    <label>
      {t("导出格式", "Export format")}<select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="pdf">PDF</option>
        <option value="svg">SVG</option>
        <option value="png">PNG</option>
        {tiff && <option value="tiff">{t("TIFF（无损栅格）", "TIFF (lossless raster)")}</option>}
      </select>
    </label>
  )
}

export default function Workflow() {
  const { locale, t } = useI18n()
  const { ecologyDirections, omicsDirections, spatialKinds } = getWorkflowCatalog(t)
  const [languageSettingsOpen, setLanguageSettingsOpen] = useState(false)
  const languageDialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = languageDialog.current
    if (languageSettingsOpen && dialog && !dialog.open) dialog.showModal()
    else if (!languageSettingsOpen && dialog?.open) dialog.close()
  }, [languageSettingsOpen])
const tableKinds: Record<string, string> = {
  scatter: t("散点图", "Scatter plot"),
  bar: t("柱状图", "Bar chart"),
  line: t("折线图", "Line chart"),
  box: t("箱线图", "Box plot"),
  heatmap: t("热图", "Heatmap"),
}
const singleKinds: Record<string, string> = {
  embedding_categorical: t("UMAP / t-SNE 分类", "UMAP / t-SNE categories"),
  embedding_continuous: t("UMAP / t-SNE 连续值", "UMAP / t-SNE continuous values"),
  feature: 'Feature Plot',
  violin: t("小提琴图", "Violin plot"),
  dotplot: 'Dot Plot',
}
const themes: Record<string, string> = {
  scientific_clear: t("科研清晰", "Scientific Clear"),
  modern_soft: t("现代柔和", "Modern Soft"),
  high_contrast: t("高对比", "High Contrast"),
}
const paletteLabels: Record<string, string> = {
  ...Object.fromEntries(scientificPalettes.map(item => [item.id, item.name[locale]])),
  theme: t("跟随主题", "Use theme colors"), colorblind: t("高辨识分类色", "Distinct categorical colors"), viridis: t("Viridis 连续色", "Viridis sequential"), cividis: t("Cividis 连续色", "Cividis sequential"),
  magma: t("Magma 连续色", "Magma sequential"), coolwarm: t("Coolwarm 发散色", "Coolwarm diverging"), clay: t("陶土 / Clay", "Clay"), lagoon: t("湖湾 / Lagoon", "Lagoon"),
}
const chartMeasureLabels: Record<string, string> = {
  width_mm: t("图表宽度（mm）", "Chart width (mm)"), height_mm: t("图表高度（mm）", "Chart height (mm)"), dpi: t("分辨率（DPI）", "Resolution (DPI)"),
  font_size: t("字体大小（pt）", "Font size (pt)"), line_width: t("线条宽度（pt）", "Line width (pt)"),
}
const figureMeasureLabels: Record<string, string> = {
  width_mm: t("图版宽度（mm）", "Figure width (mm)"), height_mm: t("图版高度（mm）", "Figure height (mm)"),
  margin_top_mm: t("上边距（mm）", "Top margin (mm)"), margin_right_mm: t("右边距（mm）", "Right margin (mm)"), margin_bottom_mm: t("下边距（mm）", "Bottom margin (mm)"), margin_left_mm: t("左边距（mm）", "Left margin (mm)"),
  panel_gap_mm: t("子图间距（mm）", "Panel spacing (mm)"), label_font_size: t("标签字号（pt）", "Panel label size (pt)"), dpi: t("分辨率（DPI）", "Resolution (DPI)"),
}

  const [page, updatePage] = useState(0),
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
    [noticeText, updateNotice] = useState({ zh: '', en: '' }),
    [busy, setBusy] = useState('')
  const notice = t(noticeText.zh, noticeText.en)
  const setNotice = (zh: string, en = zh) => updateNotice({ zh, en })
  const [retainedEditors, setRetainedEditors] = useState({ illustration: false, image: false })
  const [illustrationRevision, setIllustrationRevision] = useState(0)
  const setPage = (next: number) => {
    if (next === 6 || next === 10) setRetainedEditors(previous => {
      const key = next === 6 ? 'illustration' : 'image'
      return previous[key] ? previous : { ...previous, [key]: true }
    })
    updatePage(next)
  }
  const [aiMode, setAiMode] = useState(true)
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
                ecology_alpha_diversity: t("α 多样性箱线图", "Alpha-diversity box plot"),
                ecology_beta_ordination: t("β 多样性排序图", "Beta-diversity ordination"),
              }
            : ecologyDirection === 'ordination'
              ? { ecology_ordination_biplot: t("排序双图（样品 + taxon）", "Ordination biplot (samples + taxa)") }
              : ecologyDirection === 'environment'
                ? { ecology_environment_gradient: t("环境梯度（已有值 / 向量）", "Environmental gradient (existing values / vectors)") }
                : ecologyDirection === 'time'
                  ? { ecology_time_series: t("生态时间序列（原始观测）", "Ecological time series (observations)") }
                  : ecologyDirection === 'spatial'
                    ? { ecology_spatial_points: t("空间生态点位图", "Spatial ecology point map") }
                    : { ecology_composition: t("群落组成堆叠图", "Stacked community composition") }
          : omicsDirection === 'spatial'
            ? spatialKinds
            : omicsDirection === 'r'
              ? { r_ggplot: t("R ggplot2 散点图", "R ggplot2 scatter plot") }
              : omicsDirection === 'genome'
                ? { genome_tracks: t("基因组多轨道", "Genome tracks") }
                : omicsDirection === 'circos'
                  ? { circos: t("Circos 轨道与链接", "Circos tracks and links") }
                  : { dna_features: t("DNA 特征图", "DNA feature map") }
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
      if (!controller.signal.aborted) setNotice(error instanceof Error ? error.message : t("操作失败，请重试。", "The operation failed. Please try again."))
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
      if (file && (file.size > sizeLimit || !accept.test(file.name))) throw new Error(t(`请选择符合当前方向的文件，大小不超过 ${Math.round(sizeLimit / 1024 / 1024)} MB。`, `Choose a supported file for this workflow, no larger than ${Math.round(sizeLimit / 1024 / 1024)} MB.`))
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
      setNotice("数据已在本机读取，请检查预览与字段后确认。", "Data loaded locally. Review the preview and fields before continuing.")
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
    if (!enableAI) { if (busy === 'workbench-draft') active.current?.abort(); setPage(0) }
    setAiMode(enableAI)
  }
  const proposeWorkbenchDraft = (provider: WorkbenchProvider, prompt: string, receive: (proposal: WorkbenchProposal) => void, external?: ExternalDraft) =>
    void run('workbench-draft', async (signal) => {
      const proposal = external
        ? await json('/api/workbench/v1/external-drafts', signal, external)
        : await json('/api/workbench/v1/drafts', signal, { provider, prompt, locale })
      if (!signal.aborted) receive(proposal)
    })
  const proposeIllustrationDraft = (receive: (value: unknown) => void, fail: (message: string) => void) =>
    void run('workbench-draft', async (signal) => {
      try {
        const result = await json('/api/workbench/v1/illustration-draft', signal, { sample_id: 'synthetic-branch-v1' })
        if (!signal.aborted) receive(result)
      } catch (error) {
        if (!signal.aborted) fail(error instanceof Error ? error.message : t("本机模型提取失败，请手动填写。", "Local model extraction failed. Enter the fields manually."))
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
      if (!response.ok) throw new Error(t("撤销连接失败，请从本机启动窗口重新打开软件。", "Could not revoke the connection. Reopen the application from its local launcher."))
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
      if (file.size > 64 * 1024 * 1024) throw new Error(t("请选择不超过 64 MiB 的图像。", "Choose an image no larger than 64 MiB."))
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
      if (!response.ok && response.status !== 404) throw new Error(t("图像正在使用，请稍后再移除。", "The image is in use. Wait before removing it."))
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
      if (!artifact.formats.includes(format)) throw new Error(t("当前结果不包含所选导出格式，请重新生成图版。", "This result does not include the selected format. Generate the figure again."))
      const file = await artifactBlob(artifact, format, signal)
      const url = URL.createObjectURL(file)
      const link = document.createElement('a')
      link.href = url
      link.download = `biofigure.${format}`
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 60000)
      if (!signal.aborted) setNotice(desktop ? '请在系统保存窗口确认位置。' : '已交给浏览器下载。', desktop ? 'Choose a location in the system save dialog.' : 'The download has been sent to your browser.')
    })
  const saveProject = () =>
    run('project', async (signal) => {
      const projectChart = figureImage ? panels[0]?.chart : draft
      if (!projectChart?.dataset_id) throw new Error(t("请先添加统计图。", "Add a data plot first."))
      if (panels.some((panel) => panel.chart.dataset_id !== projectChart.dataset_id)) throw new Error(t("当前项目格式只支持保存同一数据集的图表和图版。请改用同一数据集制作子图。", "This project format supports plots and figures from one dataset. Use the same dataset for all panels."))
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
      setNotice(desktop ? '请在系统保存窗口确认项目位置。' : '项目文件已交给浏览器下载；请确认保存位置。', desktop ? 'Choose the project location in the system save dialog.' : 'The project download has started. Confirm its save location.')
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
      setNotice("项目已打开；请检查恢复的数据、图表配置和图版。", "Project opened. Review the restored data, plot settings, and figure layout.")
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
    setIllustrationRevision(value => value + 1)
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
      setNotice("请选择 .bfsproj 图表/图版项目或 .bfsillustration.json 生物图示项目。", "Choose a .bfsproj plot/figure project or a .bfsillustration.json illustration project.")
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
        <p className="wf-form-note">{omicsDirection ? `${omicsDirections[omicsDirection].title} · ${omicsDirections[omicsDirection].formats}` : t("请选择组学方向", "Choose an omics workflow")}</p>
        {omicsDirection === 'spatial' && (
          <>
            <label>
              {t("空间坐标", "Spatial coordinates")}<select value={draft.coordinate_key} onChange={(e) => change({ coordinate_key: e.target.value })}>
                {preview?.coordinates?.map((c) => (
                  <option key={c.key}>{c.key}</option>
                ))}
              </select>
            </label>
            {['spatial_categorical', 'spatial_continuous'].includes(draft.chart_type) && (
              <label>
                {t("颜色字段", "Color field")}<select value={draft.color_field ?? ''} onChange={(e) => change({ color_field: e.target.value || null })}>
                  <option value="">{t("请选择", "Choose an option")}</option>
                  {fieldOptions.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
            )}
            {draft.chart_type === 'spatial_feature' && (
              <label>
                {t("基因", "Genes")}<input
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
              {t("表达来源", "Expression source")}<select value={draft.expression_source} onChange={(e) => change({ expression_source: e.target.value })}>
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
                {t("Layer 名称", "Layer name")}<input value={draft.expression_layer ?? ''} onChange={(e) => change({ expression_layer: e.target.value })} />
              </label>
            )}
          </>
        )}
        {omicsDirection === 'r' && (
          <>
            <label>
              {t("X 轴", "X axis")}<select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
                <option value="">{t("请选择", "Choose an option")}</option>
                {fieldOptions.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
            <label>
              {t("Y 轴", "Y axis")}<select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                <option value="">{t("请选择", "Choose an option")}</option>
                {numeric.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
            <label>
              {t("颜色分组", "Color grouping")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
                <option value="">{t("不分组", "No grouping")}</option>
                {fieldOptions.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
            <p className="wf-form-note">{t("R 仅执行内置 ggplot2 模板，不接收任意 R 代码。", "R runs only the built-in ggplot2 template. Arbitrary R code is not accepted.")}</p>
          </>
        )}
        {['genome', 'circos', 'dna'].includes(omicsDirection ?? '') && <p className="wf-form-note">{t("文件已校验。字段和区间由本地适配器读取；下一步可调整标题、主题、色板和导出尺寸。", "File validated. A local adapter reads the fields and intervals. Next, adjust the title, theme, palette, and export size.")}</p>}
      </div>
    ) : null
  const ecologyForm =
    mode === 'ecology' ? (
      draft.chart_type === 'ecology_composition' ? (
        <div className="wf-form">
          <p className="wf-form-note">{t("群落组成首版使用长表：每行一个样品 × 分类单元记录；不自动合并重复键或补齐缺失值。", "Community composition uses a long table: one sample–taxon record per row. Duplicate keys and missing values are not filled automatically.")}</p>
          <label>
            {t("样品字段", "Sample field")}<select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("丰度字段", "Abundance field")}<select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("分类单元字段", "Taxon field")}<select value={draft.color_field ?? ''} onChange={(e) => change({ color_field: e.target.value || null })}>
              <option value="">{t("请选择", "Choose an option")}</option>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("丰度语义", "Abundance interpretation")}<select
              value={draft.ecology_value_mode}
              onChange={(e) =>
                change({
                  ecology_value_mode: e.target.value as Chart['ecology_value_mode'],
                })
              }
            >
              <option value="relative_fraction">{t("相对丰度分数（0–1）", "Relative abundance fraction (0–1)")}</option>
              <option value="count">{t("原始计数（本机归一化为比例）", "Raw counts (normalize locally to fractions)")}</option>
            </select>
          </label>
          <p className="wf-form-note">{t("最多 60 个样品；分类单元上限由所选色板容量决定，默认主题为 3 个。导出图中的百分比来自明确选择的丰度语义。", "Up to 60 samples. Taxon capacity follows the palette; the default theme supports three. Exported percentages follow the selected abundance interpretation.")}</p>
        </div>
      ) : draft.chart_type === 'ecology_ordination_biplot' ? (
        <div className="wf-form">
          <p className="wf-form-note">{t("只展示已有二维排序坐标；sample 为点，taxon 为从原点出发的向量。", "Displays existing two-dimensional ordination coordinates. Samples are points; taxa are vectors from the origin.")}</p>
          <label>
            {t("实体名称", "Entity name")}<select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("实体类型", "Entity type")}<select value={draft.ecology_entity_type_column} onChange={(e) => change({ ecology_entity_type_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("第一轴", "First axis")}<select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("第二轴", "Second axis")}<select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("样品分组", "Sample grouping")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">{t("不分组", "No grouping")}</option>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
        </div>
      ) : draft.chart_type === 'ecology_environment_gradient' ? (
        <div className="wf-form">
          <p className="wf-form-note">{t("仅展示已有二维坐标与环境字段；不计算相关性、envfit、回归或显著性。", "Displays existing 2D coordinates and environmental fields. It does not calculate correlations, envfit, regression, or significance.")}</p>
          <label>
            {t("环境模式", "Environmental mode")}<select
              value={draft.ecology_environment_mode}
              onChange={(e) =>
                change({
                  ecology_environment_mode: e.target.value as Chart['ecology_environment_mode'],
                })
              }
            >
              <option value="continuous_value">{t("连续环境值着色", "Color by continuous environmental values")}</option>
              <option value="existing_vector">{t("已有环境向量", "Existing environmental vectors")}</option>
            </select>
          </label>
          <label>
            {t("样品/实体字段", "Sample / entity field")}<select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("实体类型字段", "Entity type field")}<select value={draft.ecology_entity_type_column} onChange={(e) => change({ ecology_entity_type_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("第一轴", "First axis")}<select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            {t("第二轴", "Second axis")}<select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          {draft.ecology_environment_mode === 'continuous_value' && (
            <label>
              {t("环境值字段", "Environmental value field")}<select value={draft.ecology_environment_column} onChange={(e) => change({ ecology_environment_column: e.target.value })}>
                {numeric.map((c) => (
                  <option key={c.name}>{c.name}</option>
                ))}
              </select>
            </label>
          )}
          <label>
            {t("样品分组", "Sample grouping")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">{t("不分组", "No grouping")}</option>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
        </div>
      ) : draft.chart_type === 'ecology_time_series' ? (
        <div className="wf-form">
          <p className="wf-form-note">{t("每条线只连接同一个重复测量轨迹；分组仅控制颜色。系统不聚合、平滑、插值或计算显著性。", "Each line connects one repeated-measure trajectory; grouping controls color only. No aggregation, smoothing, interpolation, or significance calculation is performed.")}</p>
          <label>
            {t("样品 / 监测对象", "Sample / monitored entity")}<select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("数值时间", "Numeric time")}<select value={draft.ecology_time_column} onChange={(e) => change({ ecology_time_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("观测值", "Observed value")}<select value={draft.ecology_value_column} onChange={(e) => change({ ecology_value_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("显示分组", "Display grouping")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">{t("不分组", "No grouping")}</option>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("重复测量轨迹", "Repeated-measure trajectory")}<select value={draft.ecology_replicate_column} onChange={(e) => change({ ecology_replicate_column: e.target.value })}>
              <option value="">{t("未提供（按样品连接）", "Not supplied (connect by sample)")}</option>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("对称误差大小", "Symmetric error magnitude")}<select value={draft.ecology_error_column} onChange={(e) => change({ ecology_error_column: e.target.value })}>
              <option value="">{t("不显示", "Hide")}</option>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <p className="wf-form-note">{t("误差必须非负，仅按原值显示；不推断 SD、SE 或置信区间。", "Errors must be nonnegative and are displayed as supplied. SD, SE, and confidence intervals are not inferred.")}</p>
        </div>
      ) : draft.chart_type === 'ecology_spatial_points' ? (
        <div className="wf-form">
          <p className="wf-form-note">{t("只绘制已有点位；不加载底图、不重投影，也不计算距离、热点、插值或其他空间统计。", "Plots existing points only. No basemap, reprojection, distance, hotspot, interpolation, or other spatial statistics are applied.")}</p>
          <label>
            {t("坐标模式", "Coordinate mode")}<select
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
              <option value="geographic_wgs84">{t("WGS84 经度 / 纬度", "WGS84 longitude / latitude")}</option>
              <option value="planar">{t("平面 X / Y 坐标", "Planar X / Y coordinates")}</option>
            </select>
          </label>
          <label>
            {t("样品 / 点位标识", "Sample / point identifier")}<select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {draft.ecology_spatial_coordinate_mode === 'geographic_wgs84' ? t("经度字段", "Longitude field") : t("X 坐标字段", "X coordinate field")}
            <select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {draft.ecology_spatial_coordinate_mode === 'geographic_wgs84' ? t("纬度字段", "Latitude field") : t("Y 坐标字段", "Y coordinate field")}
            <select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
              {numeric.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("显示分组", "Display grouping")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">{t("不分组", "No grouping")}</option>
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
                {t("坐标参考说明", "Coordinate reference")}<input value={draft.ecology_spatial_reference} onChange={(e) => change({ ecology_spatial_reference: e.target.value })} placeholder={t("例如 EPSG:32650 或样地局部坐标", "For example, EPSG:32650 or site-local coordinates")} />
              </label>
              <label>
                {t("坐标单位", "Coordinate unit")}<select value={draft.ecology_spatial_unit} onChange={(e) => change({ ecology_spatial_unit: e.target.value as Chart['ecology_spatial_unit'] })}>
                  <option value="m">{t("米", "Meters")}</option>
                  <option value="km">{t("千米", "Kilometers")}</option>
                  <option value="arbitrary">{t("任意单位", "Arbitrary units")}</option>
                </select>
              </label>
            </>
          ) : (
            <p className="wf-form-note">{t("固定为 EPSG:4326；经度范围 -180–180，纬度范围 -90–90。图上角度距离不是地表距离。", "Uses EPSG:4326: longitude −180–180 and latitude −90–90. Angular separation on the plot is not ground distance.")}</p>
          )}
          <p className="wf-form-note">{t("最多 5000 个唯一点位；同坐标的不同点位会原样重叠，不自动合并或抖动。", "Up to 5,000 unique points. Distinct points at identical coordinates overlap; they are not merged or jittered.")}</p>
        </div>
      ) : (
        <div className="wf-form">
          <p className="wf-form-note">{t("本阶段只展示已有 α 指标或 β 排序坐标，不在本机计算多样性或距离矩阵。", "Displays existing alpha-diversity metrics or beta-ordination coordinates. Diversity and distance matrices are not calculated locally.")}</p>
          <label>
            {t("样品字段", "Sample field")}<select value={draft.ecology_sample_column} onChange={(e) => change({ ecology_sample_column: e.target.value })}>
              {fieldOptions.map((c) => (
                <option key={c.name}>{c.name}</option>
              ))}
            </select>
          </label>
          {draft.chart_type === 'ecology_alpha_diversity' ? (
            <>
              <label>
                {t("指标字段", "Metric field")}<select value={draft.ecology_metric_column} onChange={(e) => change({ ecology_metric_column: e.target.value })}>
                  {fieldOptions.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("已有指标名称", "Existing metric name")}<input value={draft.ecology_metric} onChange={(e) => change({ ecology_metric: e.target.value })} placeholder={t("例如 Shannon", "For example, Shannon")} />
              </label>
              <label>
                {t("指标值", "Metric value")}<select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                  {numeric.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <>
              <label>
                {t("第一轴", "First axis")}<select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
                  {numeric.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
              <label>
                {t("第二轴", "Second axis")}<select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                  {numeric.map((c) => (
                    <option key={c.name}>{c.name}</option>
                  ))}
                </select>
              </label>
            </>
          )}
          <label>
            {t("分组字段", "Grouping field")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
              <option value="">{t("不分组", "No grouping")}</option>
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
      <nav className="workspace-home-nav" aria-label={t('本地创作导航', 'Local creation navigation')}>
        <NavigationGroup direction="above" icon="▦" label={t('数据图表', 'Data plots')}
          description={t('按数据类型选择绘图方式。', 'Choose a workflow for your data.')} items={[
            ...(preview?[{label:t('继续当前图表', 'Resume current plot'),onSelect:()=>setPage(result?3:2)}]:[]),
            {label:t('表格图表', 'Tabular plots'),description:'CSV / XLSX',onSelect:chooseTable},
            {label:t('单细胞与空间', 'Single-cell and spatial'),description:'H5AD',onSelect:()=>setPage(7)},
            {label:t('组学、生态与 R', 'Omics, ecology and R'),onSelect:()=>setPage(7)},
          ]}/>
        <NavigationGroup direction="above" icon="▤" label={t('论文图版', 'Figure assembly')}
          description={t('统一子图、标签和导出尺寸。', 'Unify panels, labels and export dimensions.')} items={[
            {label:t('打开图版工作栏', 'Open figure assembly'),onSelect:()=>{setAssemblyIntent(true);setPage(8)}},
            {label:t('打开已有项目', 'Open project'),onSelect:()=>projectInputRef.current?.click()},
          ]}/>
        <NavigationGroup direction="above" icon="◇" label={t('科研图示', 'Illustrations')}
          description={t('从原创矢量组件组织科研故事。', 'Build a scientific story with original vector components.')} items={[
            ...(retainedEditors.illustration?[{label:t('继续上次编辑', 'Resume illustration'),onSelect:()=>setPage(6)}]:[]),
            {label:t('机制图', 'Mechanism diagram'),onSelect:()=>chooseIllustration('mechanism')},
            {label:t('实验流程图', 'Experimental workflow'),onSelect:()=>chooseIllustration('experimental_workflow')},
            {label:t('图形摘要', 'Graphical abstract'),onSelect:()=>chooseIllustration('graphical_abstract')},
          ]}/>
        <NavigationGroup direction="above" icon="◫" label={t('科研图像', 'Scientific images')}
          description={t('本地图像、测量、拼接与批量处理。', 'Local images, measurement, assembly and batch processing.')} items={[
            {label:t('打开图像工作台', 'Open image workspace'),onSelect:()=>setPage(10)},
          ]}/>
      </nav>
      <div className="wf-home-utilities">
        <button className="wf-open-project" onClick={() => projectInputRef.current?.click()}><FolderIcon />{t("打开已有项目", "Open project")}<span lang="en">/ Open a project</span></button>
        <button className="wf-file-guide-toggle" aria-expanded={showFileGuide} onClick={() => setShowFileGuide(!showFileGuide)}>{t("我有一个文件，先看从哪里开始", "I have a file. Where should I start?")}{showFileGuide ? '↑' : '↓'}</button>
      </div>
      {showFileGuide && <div className="wf-file-guide">
        <p>{t("按文件内容和想做的作品选择；原始文件会在下一步由你亲自选择。", "Choose by file contents and intended output. You will select the original file in the next step.")}</p>
        <button onClick={() => { setAssemblyIntent(false); setPage(7) }}>{t("CSV / XLSX、H5AD、GenBank 或轨道文件 → 制作数据图表", "CSV / XLSX, H5AD, GenBank, or track files → Data plots")}</button>
        <button onClick={() => setPage(10)}>{t("显微图像或图像栈 → 查看图像工作台", "Microscopy images or stacks → Image workspace")}</button>
        <button onClick={() => projectInputRef.current?.click()}>{t(".bfsproj / .bfsillustration.json → 打开已有项目", ".bfsproj / .bfsillustration.json → Open project")}</button>
      </div>}
      <p className="wf-home-note">{t("从选任务、确认数据、调整图形到检查导出。真实数据只在本机处理；软件不自动给出统计或科学结论。", "Choose a task, review data, refine the figure, and check the export. Real data stays local; statistical and scientific conclusions require your review.")}</p>
    </>
  )
  const chartCatalog = (
    <>
      <div className="wf-title wf-catalog-title">
        <span className="wf-overline">{t("DATA CHARTS / 选择来源", "DATA CHARTS / CHOOSE A SOURCE")}</span>
        <h1>{t("你要制作哪类数据图表？", "What kind of data plot do you need?")}</h1>
        <p>{t("先选数据类型或绘图方式，再确认文件和字段。所有图表只展示输入中已有的数据或结果。", "Choose a data type or plotting workflow, then review the file and fields. Plots display data or results already present in the input.")}</p>
      </div>
      <div className="wf-catalog-grid">
        <button className="wf-category" onClick={chooseTable}><span className="wf-category-icon">▦</span><strong>{t("基础表格图表 ↗", "Tabular plots ↗")}</strong><p>CSV / XLSX</p><small>{t("散点 · 柱状 · 折线 · 箱线 · 热图", "Scatter · Bar · Line · Box · Heatmap")}</small></button>
        <button className="wf-category" onClick={chooseSingleCell}><span className="wf-category-icon">◉</span><strong>{t("单细胞图表 ↗", "Single-cell plots ↗")}</strong><p>{t("已有分析结果的 H5AD", "H5AD with existing analysis results")}</p><small>UMAP / t-SNE · Feature · Violin · Dot Plot</small></button>
        <button className="wf-category" onClick={() => chooseOmics('spatial')}><span className="wf-category-icon">⌖</span><strong>{t("空间组学图表 ↗", "Spatial omics plots ↗")}</strong><p>{t("已有空间坐标的 H5AD", "H5AD with existing spatial coordinates")}</p><small>{t("空间分类 · 连续值 · Feature Plot", "Spatial categories · Continuous values · Feature Plot")}</small></button>
        <button className="wf-category" onClick={() => setPage(4)}><span className="wf-category-icon">≋</span><strong>{t("基因组与序列图表 ↗", "Genome and sequence plots ↗")}</strong><p>{t("选择轨道、Circos 或 DNA 特征", "Choose tracks, Circos, or DNA features")}</p><small>{t("基因组文本轨道 · JSON manifest · GenBank", "Genome text tracks · JSON manifest · GenBank")}</small></button>
        <button className="wf-category" onClick={() => { setEcologyDirection(null); setPage(5) }}><span className="wf-category-icon">∿</span><strong>{t("生态学图表 ↗", "Ecological plots ↗")}</strong><p>{t("群落、多样性与环境数据", "Community, diversity, and environmental data")}</p><small>{t("组成 · 排序 · 时间序列 · 空间点位", "Composition · Ordination · Time series · Spatial points")}</small></button>
        <button className="wf-category" onClick={() => chooseOmics('r')}><span className="wf-category-icon">R</span><strong>{t("R 绘图 ↗", "R plotting ↗")}</strong><p>{t("已审核的 ggplot2 静态散点模板", "Reviewed ggplot2 static scatter template")}</p><small>{t("需要本机已安装的 R；不运行任意 R 代码", "Requires a local R installation; arbitrary R code is not run")}</small></button>
      </div>
      <div className="wf-bottom"><button onClick={() => setPage(0)}>{t("← 返回作品类型", "← Back to figure types")}</button></div>
    </>
  )
  const illustrationCatalog = (
    <>
      <div className="wf-title wf-catalog-title">
        <span className="wf-overline">{t("BIOLOGICAL ILLUSTRATIONS / 选择用途", "SCIENTIFIC ILLUSTRATIONS / CHOOSE A PURPOSE")}</span>
        <h1>{t("你要绘制哪种生物图示？", "What kind of scientific illustration do you need?")}</h1>
        <p>{t("使用本机原创组件与空白布局，科学关系、流程和证据由你编辑与核实。", "Start with local original components and blank layouts. Edit and verify scientific relationships, steps, and evidence yourself.")}</p>
      </div>
      <div className="wf-catalog-grid wf-illustration-grid">
        <button className="wf-category" onClick={() => chooseIllustration('mechanism')}><span className="wf-category-icon">◎</span><strong>{t("机制图 ↗", "Mechanism diagram ↗")}</strong><p>{t("组织实体与关系", "Arrange entities and relationships")}</p><small>{t("Mechanism diagram · 空白画布与机制布局", "Mechanism diagram · Blank canvas and mechanism layouts")}</small></button>
        <button className="wf-category" onClick={() => chooseIllustration('experimental_workflow')}><span className="wf-category-icon">⇢</span><strong>{t("实验流程图 ↗", "Experimental workflow ↗")}</strong><p>{t("编排步骤与流向", "Arrange steps and flow")}</p><small>{t("Experimental workflow · 手动填写方法内容", "Experimental workflow · Enter method details manually")}</small></button>
        <button className="wf-category" onClick={() => chooseIllustration('graphical_abstract')}><span className="wf-category-icon">▧</span><strong>{t("图形摘要 ↗", "Graphical abstract ↗")}</strong><p>{t("编排摘要面板", "Arrange abstract panels")}</p><small>{t("Graphical abstract · 手动组织研究叙事", "Graphical abstract · Organize the research narrative manually")}</small></button>
      </div>
      <div className="wf-bottom"><button onClick={() => setPage(0)}>{t("← 返回作品类型", "← Back to figure types")}</button></div>
    </>
  )
  const figureWorkspace = (
    <>
      <div className="wf-title">
        <span className="wf-overline">{t("MULTI-PANEL FIGURE / 图版工作栏", "MULTI-PANEL FIGURE / ASSEMBLY")}</span>
        <h1>{t("排版多图图版", "Assemble a multi-panel figure")}</h1>
        <p>{t("制作图表后加入右侧工作栏。可以排最多 4 张图表，也可以把一张科研图像与一张统计图排成 A/B 图版。", "Collect plots in the sidebar. Arrange up to four plots, or combine one scientific image and one data plot as an A/B figure.")}</p>
      </div>
      <div className="wf-figure-guide">
        <div><b>1</b><strong>{t("加入图表", "Add a plot")}</strong><p>{t("使用当前本机数据生成图表，然后点“加入图版”。", "Generate a plot from the current local dataset, then select Add to figure.")}</p></div>
        <div><b>2</b><strong>{t("调整版面", "Adjust the layout")}</strong><p>{t("在右侧选择模板、排列、尺寸和标签。", "Choose a template, arrangement, dimensions, and labels in the sidebar.")}</p></div>
        <div><b>3</b><strong>{t("检查并导出", "Review and export")}</strong><p>{t("生成实际图版预览，检查后导出成品。", "Generate the actual figure preview, review it, then export.")}</p></div>
      </div>
      <div className="wf-bottom"><button onClick={() => setPage(0)}>{t("← 返回作品类型", "← Back to figure types")}</button><button className="primary" onClick={() => setPage(7)}>{panels.length ? t("继续添加图表 →", "Add another plot →") : t("制作第一张图表 →", "Create the first plot →")}</button></div>
      <section className="wf-config">
        <h2>{t("加入科研图像", "Add a scientific image")}</h2>
        <p>{t("混合图版中，科研图像放在 A，统计图放在 B。请选择单平面 PNG 或 TIFF，并使用你已确认的标定。", "Mixed figures place the image in panel A and the plot in panel B. Choose a single-plane PNG or TIFF and supply a verified calibration.")}</p>
        {!figureImage ? (
          <label>{t("选择源图", "Choose source image")}<input type="file" accept=".png,.tif,.tiff" disabled={panels.length > 1 || panels.some((item) => !['scatter', 'bar', 'line', 'box', 'heatmap'].includes(item.chart.chart_type))} onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) void importFigureImage(file)
          }} /></label>
        ) : (
          <>
            <p>A · {figureImage.name}</p>
            <label>{t("横向标定（µm/像素）", "Horizontal calibration (µm/pixel)")}<input type="number" min="0" step="any" value={figureImage.panel.x_um_per_pixel || ''} onChange={(e) => updateFigureImage({ x_um_per_pixel: Number(e.target.value) })} /></label>
            <label>{t("比例尺长度（µm）", "Scale bar length (µm)")}<input type="number" min="0" step="any" value={figureImage.panel.scale_bar_um || ''} onChange={(e) => updateFigureImage({ scale_bar_um: Number(e.target.value) })} /></label>
            <label>{t("比例尺颜色", "Scale bar color")}<select value={figureImage.panel.scale_bar_color} onChange={(e) => updateFigureImage({ scale_bar_color: e.target.value === 'black' ? 'black' : 'white' })}>
              <option value="white">{t("白色", "White")}</option><option value="black">{t("黑色", "Black")}</option>
            </select></label>
            <details>
              <summary>{t("裁切选项", "Crop options")}</summary>
              <p>{t("从源图左上角以像素计。裁切只用于图版，项目保留原图。", "Pixel coordinates start at the source image’s upper-left corner. Cropping applies only to the figure; the project retains the original image.")}</p>
              {figureImage.panel.crop ? (
                <>
                  {([['x', t("起点 X", "Start X")], ['y', t("起点 Y", "Start Y")], ['width', t("宽", "Width")], ['height', t("高", "Height")]] as const).map(([key, title]) => (
                    <label key={key}>{title}<input type="number" min={key === 'x' || key === 'y' ? 0 : 1} step="1" value={figureImage.panel.crop?.[key]} onChange={(e) => {
                      const crop = figureImage.panel.crop
                      if (crop) updateFigureImage({ crop: { ...crop, [key]: Number(e.target.value) } })
                    }} /></label>
                  ))}
                  <button onClick={() => updateFigureImage({ crop: null })}>{t("恢复整图", "Restore full image")}</button>
                </>
              ) : assembly?.imageCheck ? <button onClick={() => {
                const [width, height] = assembly.imageCheck!.source_pixels
                updateFigureImage({ crop: { x: 0, y: 0, width, height } })
              }}>{t("设置裁切", "Apply crop")}</button> : <p>{t("先生成一次整图预览，即可按原图尺寸设置裁切。", "Generate a full-image preview before defining a crop in source-image pixels.")}</p>}
            </details>
            <button onClick={removeFigureImage}>{t("移除科研图像", "Remove scientific image")}</button>
          </>
        )}
        {panels.length > 1 && <p>{t("先把图表减至一张，再加入科研图像。", "Keep one data plot before adding a scientific image.")}</p>}
        {panels.length === 1 && !['scatter', 'bar', 'line', 'box', 'heatmap'].includes(panels[0].chart.chart_type) && <p>{t("混合图版首版支持五类基础统计图。请先移除当前图表。", "Mixed figures currently support the five standard chart types. Remove the current plot first.")}</p>}
      </section>
      <section className="wf-config"><h2>{t("保存可编辑项目", "Save an editable project")}</h2><p>{t(".bfsproj 会保存图表配置、图版布局及源数据副本，方便下次继续编辑；PDF、SVG、PNG 或 TIFF 是导出的成品文件。当前项目格式只支持来自同一数据集的子图。", "A .bfsproj stores plot settings, figure layout, and source-data copies for later editing. PDF, SVG, PNG, and TIFF are exported outputs. This project format supports panels from one dataset.")}</p><label>{t("项目名称", "Project name")}<input value={name} onChange={(e) => setName(e.target.value)} /></label><div className="wf-actions"><button disabled={!figureReady || !sameDatasetPanels || (!figureImage && !draft.dataset_id)} onClick={saveProject}>{t("保存 .bfsproj 项目", "Save .bfsproj project")}</button><button onClick={() => projectInputRef.current?.click()}>{t("打开已有项目", "Open project")}</button></div>{!sameDatasetPanels && <p role="status">{t("这些子图来自不同数据集，可以导出图版，但暂不能保存为同一个可编辑项目。", "These panels use different datasets. You can export the figure, but cannot save them as one editable project yet.")}</p>}</section>
    </>
  )
  const ecologyCard = (direction: EcologyDirection) => {
    const content = (
      <>
        <EcologyPreview direction={direction} compact />
        <div className="wf-ecology-meta">
          <span>{t("虚拟数据示意", "Synthetic preview")}</span>
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
        <h1>{t("先选择你的生态学任务。", "Choose your ecological task.")}</h1>
        <p>{t("群落组成、多样性、排序、环境梯度、生态时间序列与空间点位均可进入本机绘图流程。", "Local workflows cover community composition, diversity, ordination, environmental gradients, ecological time series, and spatial points.")}</p>
      </div>
      <div className="wf-ecology-grid">{(Object.keys(ecologyDirections) as EcologyDirection[]).map(ecologyCard)}</div>
      <p className="wf-form-note wf-ecology-note">{t("空间生态首版只接受已有点位表，不含在线地图、底图导入、重投影或空间统计；所有方向的真实数据均只在本机处理。", "Spatial ecology accepts existing point tables. Online maps, imported basemaps, reprojection, and spatial statistics are not included. Real data is processed locally in all workflows.")}</p>
      <div className="wf-bottom">
        <button onClick={() => setPage(7)}>{t("← 返回数据图表", "← Back to data plots")}</button>
      </div>
    </>
  )
  const modeSwitch = <WorkspaceModeSwitch ai={aiMode} onChange={showMode} />
  const languageSettingsButton = <button type="button" onClick={() => setLanguageSettingsOpen(true)}>{t('设置', 'Settings')}</button>
  return (
    <div className={aiMode ? 'wf wf-ai' : 'wf'}>
      <DrawingWorkbench visible={aiMode} modeSwitch={modeSwitch} busy={!!busy}
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
        onApplyIllustration={(document) => { if (!canApplyWorkbenchDraft) return; setIllustrationSkillDraft(document); setIllustrationSkillRevision((value) => value + 1); setIllustrationKind('experimental_workflow'); setIllustrationFile(null); setPage(6); setAiMode(false) }} />
      <input ref={projectInputRef} className="wf-hidden-input" type="file" accept=".bfsproj,.bfsillustration.json" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) openSavedFile(file) }} />
      <div hidden={aiMode}>
      <div hidden={page !== 6}>
        <div className="dw-illustration-mode">{languageSettingsButton}{modeSwitch}</div>
        {(retainedEditors.illustration || page === 6) && <IllustrationStudio active={!aiMode && page === 6} key={illustrationFile ? `${illustrationFile.name}-${illustrationFile.lastModified}` : illustrationSkillDraft ? `skill-${illustrationSkillRevision}` : illustrationKind+'-'+illustrationRevision} initialKind={illustrationKind} initialProject={illustrationFile} initialDocument={illustrationSkillDraft} onBack={() => { setIllustrationFile(null); setIllustrationSkillDraft(null); setPage(9) }} />}
      </div><div hidden={page === 6}>
      <header className="wf-header">
        <button className="wf-brand" onClick={() => setPage(0)}>
          <span className="wf-logo">✳</span>BioFigure <span>Studio</span>
        </button>
        <div className="wf-header-tools"><span className="wf-badge">{t("● 本机优先", "● Local first")}</span><button onClick={() => projectInputRef.current?.click()}>{t("打开已有项目", "Open project")}</button>{languageSettingsButton}{modeSwitch}</div>
      </header>
      <div className="wf-notice">{t("数据与项目只在本机处理；绘图使用输入中已有的值和分析结果，不自动计算统计结论。本机绘图助手按需运行。", "Data and projects are processed locally. Plots use supplied values and analysis results; statistical conclusions are not calculated automatically. The local drawing assistant runs on request.")}</div>
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
            null

          ) : page === 5 ? (
            ecologyView
          ) : page === 4 ? (
            <>
              <div className="wf-title">
                <span className="wf-overline">{t("GENOME & SEQUENCE CHARTS / 选择类型", "GENOME & SEQUENCE CHARTS / CHOOSE A TYPE")}</span>
                <h1>{t("选择基因组或序列图表。", "Choose a genome or sequence plot.")}</h1>
                <p>{t("选择现有文件对应的图表类型，再检查输入内容。", "Choose a plot type for your existing file, then review the input.")}</p>
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
                <button onClick={() => setPage(7)}>{t("← 返回数据图表", "← Back to data plots")}</button>
              </div>
            </>
          ) : (
            <>
              <nav className="wf-steps" aria-label={t("绘图步骤", "Plotting steps")}>
                {[t("确认数据", "Review data"), t("调整图表", "Refine plot"), t("检查并导出", "Review and export")].map((t, i) => (
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
                <h1>{['', t("先确认你的数据。", "Review your data first."), t("调整图表的表达。", "Refine how the data is presented."), t("检查图表并导出。", "Review the plot and export.")][page]}</h1>
              </div>
              {page === 1 && (
                <>
                  <div className="wf-field">
                    <span>{t("图表类型 / Chart type", "Chart type")}</span>
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
                    <h3>{mode === 'single_cell' ? t("提交 H5AD", "Load H5AD") : mode === 'omics' ? t(`提交 ${omicsDirection ? omicsDirections[omicsDirection].title : t("组学数据", "Omics data")}`, `Load ${omicsDirection ? omicsDirections[omicsDirection].title : t("组学数据", "Omics data")}`) : mode === 'ecology' ? (ecologyDirection === 'diversity' ? t("提交已有多样性结果", "Load existing diversity results") : ecologyDirection === 'time' ? t("提交生态时间序列", "Load ecological time series") : ecologyDirection === 'spatial' ? t("提交空间点位表", "Load spatial point table") : t("提交群落组成数据", "Load community composition data")) : t("提交数据表格", "Load data table")}</h3>
                    <p>{mode === 'single_cell' ? t("H5AD · 最多 200 MB · 只读取已有结果", "H5AD · Up to 200 MB · Existing results only") : mode === 'omics' ? (omicsDirection ? omicsDirections[omicsDirection].formats : t("先选择组学方向", "Choose an omics workflow first")) : mode === 'ecology' ? (ecologyDirection === 'diversity' ? t("CSV、XLSX · 已有指标或排序坐标 · 最多 5 MB", "CSV, XLSX · Existing metrics or ordination coordinates · Up to 5 MB") : ecologyDirection === 'time' ? t("CSV、XLSX · 数值时间 · 最多 5000 行 / 5 MB", "CSV, XLSX · Numeric time · Up to 5,000 rows / 5 MB") : ecologyDirection === 'spatial' ? t("CSV、XLSX · 经纬度或平面坐标 · 最多 5000 行 / 5 MB", "CSV, XLSX · Geographic or planar coordinates · Up to 5,000 rows / 5 MB") : t("CSV、XLSX · 长表 · 最多 5 MB", "CSV, XLSX · Long table · Up to 5 MB")) : t("CSV、XLSX · 最多 5 MB", "CSV, XLSX · Up to 5 MB")}</p>
                    <label>
                      {t("选择文件", "Choose file")}<input
                        type="file"
                        accept={mode === 'single_cell' || (mode === 'omics' && omicsDirection === 'spatial') ? '.h5ad' : mode === 'omics' && omicsDirection === 'dna' ? '.gb,.gbk,.genbank' : mode === 'omics' && omicsDirection === 'circos' ? '.json' : mode === 'omics' && omicsDirection === 'genome' ? '.json,.bed,.bedgraph,.gff,.gff3,.gtf,.chrom.sizes' : '.csv,.xlsx'}
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          e.target.value = ''
                          if (file) void loadData(file)
                        }}
                      />
                    </label>
                    {(mode === 'table' || mode === 'ecology') && <button onClick={() => loadData()}>{t("使用内置模拟数据", "Use synthetic example")}</button>}
                  </div>
                  {preview && (
                    <div className="wf-data">
                      <h3>{preview.kind === 'single_cell' ? t(`H5AD 预览 · ${preview.cell_count} 个细胞 · ${preview.gene_count} 个基因`, `H5AD preview · ${preview.cell_count} cells · ${preview.gene_count} genes`) : preview.kind === 'dna' ? t(`GenBank 预览 · ${preview.sequence_length ?? 0} bp · ${preview.feature_count ?? 0} 个特征`, `GenBank preview · ${preview.sequence_length ?? 0} bp · ${preview.feature_count ?? 0} features`) : preview.kind === 'omics_manifest' ? t(`组学清单 · ${preview.summary ?? t("本地 manifest", "Local manifest")}`, `Omics manifest · ${preview.summary ?? t("本地 manifest", "Local manifest")}`) : preview.kind === 'genome_tracks' ? t(`基因组轨道 · ${preview.row_count ?? 0} 个区间`, `Genome tracks · ${preview.row_count ?? 0} intervals`) : t(`数据预览 · ${preview.row_count ?? 0} 行`, `Data preview · ${preview.row_count ?? 0} rows`)}</h3>
                      <p>{preview.source_name ?? t("内置模拟数据", "Synthetic example")} · {preview.matrix_format ?? t("表格", "Table")}{preview.sha256 ? ` · SHA256 ${preview.sha256.slice(0, 12)}` : ''}</p>
                      <table>
                        <thead>
                          <tr>
                            {preview.columns.map((c) => (
                              <th key={c.name}>
                                {c.name}
                                <small>
                                  {' '}
                                  {c.dtype} {t("· 缺失", " · Missing")}{c.missing_count ?? 0}
                                </small>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {preview.rows.map((row, i) => (
                            <tr key={i}>
                              {preview.columns.map((c) => (
                                <td key={c.name}>{row[c.name] == null ? t("缺失", "Missing") : String(row[c.name])}</td>
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
                        {t("X 轴", "X axis")}<select value={draft.x_column} onChange={(e) => change({ x_column: e.target.value })}>
                          <option value="">{t("请选择", "Choose an option")}</option>
                          {(draft.chart_type === 'heatmap' ? (preview?.columns ?? []) : numeric).map((c) => (
                            <option key={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        {t("Y 数值轴", "Numeric Y axis")}<select value={draft.y_column} onChange={(e) => change({ y_column: e.target.value })}>
                          <option value="">{t("请选择", "Choose an option")}</option>
                          {numeric.map((c) => (
                            <option key={c.name}>{c.name}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        {t("颜色分组", "Color grouping")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
                          <option value="">{t("不分组", "No grouping")}</option>
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
                        {t("坐标", "Coordinates")}<select value={draft.coordinate_key} onChange={(e) => change({ coordinate_key: e.target.value })}>
                          {preview?.coordinates?.map((c) => (
                            <option key={c.key}>{c.key}</option>
                          ))}
                        </select>
                      </label>
                      {['embedding_categorical', 'embedding_continuous'].includes(draft.chart_type) && (
                        <label>
                          {t("颜色字段", "Color field")}<select value={draft.color_field ?? ''} onChange={(e) => change({ color_field: e.target.value || null })}>
                            <option value="">{t("请选择", "Choose an option")}</option>
                            {fieldOptions.map((c) => (
                              <option key={c.name}>{c.name}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      {['violin', 'dotplot'].includes(draft.chart_type) && (
                        <label>
                          {t("分组字段", "Grouping field")}<select value={draft.group_column ?? ''} onChange={(e) => change({ group_column: e.target.value || null })}>
                            <option value="">{t("请选择", "Choose an option")}</option>
                            {fieldOptions.map((c) => (
                              <option key={c.name}>{c.name}</option>
                            ))}
                          </select>
                        </label>
                      )}
                      {['feature', 'violin', 'dotplot'].includes(draft.chart_type) && (
                        <label>
                          {t("基因（逗号分隔）", "Genes (comma-separated)")}<input
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
                        {t("表达来源", "Expression source")}<select value={draft.expression_source} onChange={(e) => change({ expression_source: e.target.value })}>
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
                          {t("Layer 名称", "Layer name")}<input value={draft.expression_layer ?? ''} onChange={(e) => change({ expression_layer: e.target.value })} />
                        </label>
                      )}
                      <label>
                        {t("展示转换", "Display transform")}<select value={draft.transform} onChange={(e) => change({ transform: e.target.value })}>
                          <option value="none">{t("不转换", "No transform")}</option>
                          <option value="log1p">{t("log1p（写入配置）", "log1p (recorded in settings)")}</option>
                        </select>
                      </label>
                    </div>
                  )}
                  <div className="wf-bottom">
                    <button onClick={() => setPage(7)}>{t("← 返回数据图表", "← Back to data plots")}</button>
                    <button className="primary" disabled={!valid} onClick={() => setPage(2)}>
                      {t("确认数据，下一步 →", "Confirm data and continue →")}</button>
                  </div>
                </>
              )}
              {page === 2 && (
                <>
                  <div className="wf-form">
                    <label>
                      {t("图表标题", "Plot title")}<input value={draft.title} onChange={(e) => change({ title: e.target.value })} />
                    </label>
                    <label>
                      {t("基础主题", "Base theme")}<select value={draft.theme_id} onChange={(e) => change({ theme_id: e.target.value })}>
                        {Object.entries(themes).map(([key, title]) => (
                          <option key={key} value={key}>
                            {title}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      {t("色板", "Palette")}<select value={draft.palette_id} onChange={(e) => change({ palette_id: e.target.value })}>
                        {Object.keys(paletteLabels).filter(key => !scientificPalettes.some(item => item.id === key) || key === draft.palette_id || paletteChoices(draft.chart_type).some(item => item.id === key)).map((key) => (
                          <option key={key} value={key}>{paletteLabels[key]}</option>
                        ))}
                      </select>
                    </label>
                    <ChartStyleChoices chartType={draft.chart_type} paletteId={draft.palette_id} onChange={change} />
                    {isPairedPalette(draft.palette_id) && ['scatter', 'line', 'embedding_categorical', 'spatial_categorical', 'ecology_composition'].includes(draft.chart_type) && <label>
                      {t('类别顺序（每行一个，依次对应色样）', 'Category order (one per line, matching swatch order)')}
                      <textarea key={`${draft.dataset_id}:${draft.palette_id}`} defaultValue={draft.category_order.join('\n')} rows={4}
                        placeholder={t('请原样填写数据中的类别名称', 'Enter exact category names from your data')}
                        onBlur={event => change({ category_order: event.target.value.split('\n').filter(Boolean) })} />
                    </label>}
                    {(['width_mm', 'height_mm', 'dpi', 'font_size', 'line_width'] as const).map((key) => (
                      <label key={key}>
                        {chartMeasureLabels[key]}
                        <input type="number" value={draft[key]} onChange={(e) => change({ [key]: Number(e.target.value) })} />
                      </label>
                    ))}
                    {draft.chart_type !== 'r_ggplot' && <SvgTextPicker value={draft.svg_text_mode} onChange={(svg_text_mode) => change({ svg_text_mode })} />}
                    <label>
                      {t("显示图例", "Show legend")}<input type="checkbox" checked={draft.show_legend} onChange={(e) => change({ show_legend: e.target.checked })} />
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
                    <p>{t("此处是虚拟数据示意；下一步会用当前数据生成实际图表。", "This is a synthetic preview. The next step generates the actual plot from your current data.")}</p>
                  </div>
                  <div className="wf-bottom">
                    <button onClick={() => setPage(1)}>{t("← 返回数据确认", "← Back to data review")}</button>
                    <button className="primary" disabled={!valid} onClick={render}>
                      {t("生成图表并检查 →", "Generate and review plot →")}</button>
                  </div>
                </>
              )}
              {page === 3 && result && (
                <>
                  <div className="wf-result">
                    <img className="wf-real-image" src={result.image} alt={t("实际数据图表", "Actual data plot")} />
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
                    <button onClick={() => setPage(2)}>{t("← 调整图表", "← Refine plot")}</button>
                    <FormatPicker value={format} onChange={setFormat} />
                    <button onClick={() => download(result.artifact)}>
                      <FolderIcon />
                      {t("导出", "Export")}{format.toUpperCase()}
                    </button>
                    <button className="primary" disabled={!canAddFigureChart} onClick={addResultToFigure}>
                      {(mode === 'omics' || (figureImage && mode !== 'table')) ? t("此类图表暂不支持当前图版", "This chart type is not supported in the current figure") : t(`＋ 加入图版 ${panels.length}/${figureChartLimit}`, `＋ Add to figure ${panels.length}/${figureChartLimit}`)}
                    </button>
                  </div>
                </>
              )}
              {page > 0 && page !== 4 && page !== 5 && (
                <section className="wf-config">
                  <label>
                    {t("项目名称", "Project name")}<input value={name} onChange={(e) => setName(e.target.value)} />
                  </label>
                  <div className="wf-actions">
                    <button disabled={!draft.dataset_id || !sameDatasetPanels || (Boolean(figureImage) && !figureReady)} onClick={saveProject}>{t("保存 .bfsproj 项目", "Save .bfsproj project")}</button>
                    <label>
                      {t("打开项目", "Open project")}<input
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
                  <p>{t(".bfsproj 保存可编辑的图表配置与源数据副本，下次可重新打开。PDF、SVG、PNG 是当前图表的导出成品。图版项目仅支持同一数据集的子图。", "A .bfsproj stores editable plot settings and source-data copies for reopening. PDF, SVG, and PNG are exported plots. Figure projects support panels from one dataset.")}</p>
                  {!sameDatasetPanels && <p role="status">{t("当前图版包含不同数据集，可导出图版成品，但暂不能保存为同一个项目。", "The current figure contains different datasets. Export is available, but saving as a single project is not supported yet.")}</p>}
                </section>
              )}
            </>
          )}
          <div hidden={page !== 10}>{(retainedEditors.image || page === 10) && <ImageWorkspace onBack={() => setPage(0)} />}</div>
        </main>
        {[1, 2, 3, 8].includes(page) && (
          <aside className="wf-sidebar">
            <div className="wf-section-head">
              <h2>{t("图版工作栏", "Figure assembly")}</h2>
              <span>{figureImage ? `${panels.length + 1}/2` : `${panels.length}/4`}</span>
            </div>
            {!panels.length && <div className="wf-empty"><span>▤</span><strong>{t("还没有子图", "No panels yet")}</strong><p>{t("生成数据图表后点“加入图版”。", "Generate a data plot, then select Add to figure.")}</p></div>}
            <div className="wf-queue">
              {panels.map((p, i) => (
                <div className="wf-panel" key={i}>
                  <div className="wf-thumb">
                    <img className="wf-real-image" src={p.image} alt={t(`子图 ${i + 1}`, `Panel ${i + 1}`)} />
                  </div>
                  <div>
                    <strong>
                      {String.fromCharCode(65 + i + Number(Boolean(figureImage)))} · {kinds[p.chart.chart_type]}
                    </strong>
                    <small>{p.chart.title}</small>
                    <button onClick={() => { setPanels(panels.filter((_, j) => i !== j)); setAssembly(null) }}>{t("移除", "Remove")}</button>
                  </div>
                </div>
              ))}
            </div>
            <div className="wf-console">
              <h3>{t("布局控制台", "Layout controls")}</h3>
              <label>
                {t("通用模板（非期刊官方）", "General template (not journal-endorsed)")}<select value={layout.template_id} onChange={(e) => applyTemplate(e.target.value)}>
                  <option value="single_column">{t("单栏 90 × 120 mm", "Single column · 90 × 120 mm")}</option>
                  <option value="double_column">{t("双栏 180 × 120 mm", "Double column · 180 × 120 mm")}</option>
                  <option value="square_grid">{t("方形网格 180 × 180 mm", "Square grid · 180 × 180 mm")}</option>
                  <option value="custom">{t("自定义", "Custom")}</option>
                </select>
              </label>
              <label>
                {t("排列", "Arrangement")}<select value={layout.columns} onChange={(e) => updateLayout({ columns: Number(e.target.value), template_id: 'custom' })}>
                  <option value={1}>{t("单列", "One column")}</option>
                  <option value={2}>{t("双列", "Two columns")}</option>
                </select>
              </label>
              <label>
                {t("子图标签", "Panel labels")}<select value={layout.labels} onChange={(e) => updateLayout({ labels: e.target.value })}>
                  <option value="upper">A, B, C…</option>
                  <option value="lower">a, b, c…</option>
                  <option value="none">{t("不显示", "Hide")}</option>
                </select>
              </label>
              <label>
                {t("标签位置", "Label position")}<select value={layout.label_position} onChange={(e) => updateLayout({ label_position: e.target.value })}>
                  <option value="inside">{t("图内左上", "Inside, upper left")}</option>
                  <option value="outside">{t("图外左上", "Outside, upper left")}</option>
                </select>
              </label>
              <label>
                {t("图例布局", "Legend layout")}<select value={layout.legend_mode} onChange={(e) => updateLayout({ legend_mode: e.target.value })}>
                  <option value="per_panel">{t("逐图图例", "Per-panel legends")}</option>
                  <option value="shared">{figureImage ? t("统计图内统一图例", "Unified legend within the data plot") : t("共享图例", "Shared legend")}</option>
                  <option value="none">{t("不显示图例", "No legends")}</option>
                </select>
              </label>
              {layout.legend_mode === 'shared' && (
                <label>
                  {t("共享图例位置", "Shared legend position")}<select value={layout.legend_position} onChange={(e) => updateLayout({ legend_position: e.target.value })}>
                    <option value="right">{t("右侧", "Right")}</option>
                    <option value="bottom">{t("底部", "Bottom")}</option>
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
              <p>{t("Noto Sans SC（OFL-1.1）固定审核字体。PDF 嵌入字体，保留可编辑 SVG 文字时请在目标编辑器安装对应字体。", "Uses the reviewed Noto Sans SC font (OFL-1.1). PDF embeds fonts. Install the same font in your editor when using editable SVG text.")}</p>
            </div>
            <button className="primary" disabled={!figureReady} onClick={assembly ? () => setReview(true) : renderAssembly}>
              <FolderIcon />
              {assembly ? t("检查图版预览与导出 →", "Review figure preview and export →") : t("生成图版预览 →", "Generate figure preview →")}
            </button>
            <p>{t("图版成品：PDF / SVG / PNG / TIFF。可编辑项目请另存为 .bfsproj。", "Figure outputs: PDF / SVG / PNG / TIFF. Save a separate .bfsproj for editing.")}</p>
          </aside>
        )}
      </div>
      {review && assembly && (
        <div className="wf-overlay">
          <section className="wf-dialog" role="dialog" aria-modal="true">
            <div className="wf-section-head">
              <h2>{t("最终图版 · 实际预览", "Final figure · Actual preview")}</h2>
              <button onClick={() => setReview(false)}>{t("关闭", "Close")}</button>
            </div>
            <div className="wf-dialog-body">
              <img className="wf-real-image" src={assembly.image} alt={t("实际拼版预览", "Actual figure preview")} />
              {assembly.imageCheck && <p role="status">
                {t("图像有效分辨率", "Effective image resolution")}{assembly.imageCheck.effective_dpi} {t("DPI，导出", " DPI; export ")}{assembly.imageCheck.output_dpi} {t("DPI。 源图", " DPI. Source image ")}{assembly.imageCheck.source_pixels.join(' × ')} {t("像素，排版使用", " pixels; placed at ")}{assembly.imageCheck.placed_pixels.join(' × ')} {t("像素。", " pixels.")}{assembly.imageCheck.below_output_dpi && t("图像有效分辨率低于导出设置，请核对投稿要求。", "Effective image resolution is lower than the export setting. Check your submission requirements.")}
              </p>}
            </div>
            <div className="wf-dialog-footer">
              <FormatPicker value={format} onChange={setFormat} tiff />
              <button className="primary" onClick={() => download(assembly.artifact)}>
                {t("确认下载", "Confirm download")}{format.toUpperCase()}
              </button>
            </div>
          </section>
        </div>
      )}
      </div>
      </div>
      <dialog ref={languageDialog} className="wf-dialog" aria-label={t('设置', 'Settings')}
        onCancel={() => setLanguageSettingsOpen(false)} onClose={() => setLanguageSettingsOpen(false)}
        style={{ display: languageSettingsOpen ? 'block' : 'none', maxWidth: 520, width: 'min(90vw, 520px)', border: '1px solid #d7d7d7', borderRadius: 12, padding: 24, color: '#252525', background: '#fff' }}>
        <div className="wf-section-head"><h2>{t('设置', 'Settings')}</h2><button type="button" autoFocus onClick={() => setLanguageSettingsOpen(false)}>{t('关闭', 'Close')}</button></div>
        <LanguageSettings />
      </dialog>
      {busy && (
        <div className="wf-overlay wf-working-overlay">
          <div className="wf-working-card">
            <h2>{t("biofigure 工作中", "BioFigure is working")}</h2>
            <p>{t("正在本机处理，请稍候…", "Processing locally. Please wait…")}</p>
            <button onClick={() => active.current?.abort()}>{t("取消等待", "Cancel")}</button>
            {busy === 'workbench-draft' && <button onClick={() => showMode(false)}>{t("返回本地模式", "Return to Local mode")}</button>}
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
