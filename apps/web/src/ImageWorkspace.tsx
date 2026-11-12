import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ImageResultPreview from './ImageResultPreview'
import ImageSourcePlanePreview from './ImageSourcePlanePreview'
import MeasurementResult, { type MeasurementStatistics } from './MeasurementResult'
import ImageRoiCollection, { type RoiCollectionItem } from './ImageRoiCollection'

import { useMeasurementEditors, selectionFromEditor, defaultMeasurementEditor, type SavedMeasurementSelection } from './measurementEditor'

import ImageMultiMeasureTask from './ImageMultiMeasureTask'
import ImageNativeMeasureTask from './ImageNativeMeasureTask'
import { defaultNativeMeasurementDraft, nativeDraftGeometry, nativeDraftParameters, type NativeMeasurementDraft, type SavedNativeMeasurement } from './nativeMeasurementDraft'
import { draftFromImportedRoi } from './roiFile'

import './ImageWorkspace.css'
import ImageStyleQueue from './ImageStyleQueue'

type CountKey = 'discovered' | 'source_reviewed' | 'runtime_verified' | 'ui_adapted' | 'parity_verified'
type Counts = Record<CountKey, number>
type PluginStatus = Record<CountKey, boolean>
type ImagePlugin = {
  id: string
  label: string
  menu_path: string
  category: string
  kind: string
  source: string
  original_identifier?: string
  adapter_scope?: string
  status: PluginStatus
  parameters: unknown[]
}
type Runtime = {
  state: 'unavailable' | 'inventory_ready' | 'verified'
  snapshot_id: string | null
  message: string
  counts: Counts
}
type PluginInventory = { items: ImagePlugin[]; counts: Counts }
type ImageAsset = { id: string; original_name: string; bytes: number; sha256: string; metadata_status: string;
  pixel_type?: string | null; bit_depth?: number | null; axes?: { name: string; length: number; unit: string | null; scale: number | null }[] | null }
type ImageJob = {
  source_label?: string | null
  id: string; asset_id: string; operation: string; created_at?: number
  selection?: { indices: Record<string, number>; roi: { kind: string; x: number; y: number; width: number; height: number; points?: { x: number; y: number }[] }; sample_count: number; extra_measurements?: string[] } | null
  state: 'queued' | 'running' | 'waiting_for_interaction' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted'
  progress: number | null; error: string | null
  result: { pixel_type?: string; bit_depth?: number; axes?: { name: string; length: number; unit: string | null; scale: number | null }[];
    assets?: ImageAsset[]; result?: ImageResult;
    workspace?: { source_states: Record<string, { native_measurement?: SavedNativeMeasurement | null; collection: { items: RoiCollectionItem[] } | null;
      selection: { indices: Record<string, number>; roi: RoiCollectionItem['roi'] | null; extra_measurements: string[] } | null }>;
      active_asset_id: string | null; selected_asset_ids: string[]; grid: { columns: number; gap_px: number } };
    id?: string; proof?: { width: number; height: number; mode: string; verified_pixels: number; metadata_preserved: boolean };
    sample_count?: number; mean?: number; min?: number; max?: number; sum?: number;
    imagej1_analyzer?: MeasurementStatistics } | null
}
type ImageResult = { id: string; filename: string; bytes: number; sha256: string;
  proof: { width: number; height: number; mode?: string; command?: string; verified_pixels: number; metadata_preserved: boolean;
    grid_recipe?: { columns: number; gap_px: number } | null;
    placements?: { asset_id: string; x: number; y: number; width: number; height: number }[] } }
type AnnotationItem = Record<string, string | number>
type BatchResult = { id: string; filename: string; bytes: number; sha256: string;
  proof: { group_count: number; source_count: number } }

const categories = [
  { id: 'import', label: '导入与浏览', en: 'Import & browse', matches: ['import', 'browse', '导入', '浏览'] },
  { id: 'adjust', label: '调整与通道', en: 'Adjust & channels', matches: ['adjust', 'channel', '调整', '通道'] },
  { id: 'stitch', label: '拼版、拼接与配准', en: 'Montage & registration', matches: ['stitch', 'montage', 'register', '拼版', '拼接', '配准'] },
  { id: 'analysis2d', label: '二维测量与分割', en: '2D analysis', matches: ['analysis2d', '2d', 'measure', 'segment', '二维', '测量', '分割'] },
  { id: 'analysis3d', label: '三维与体数据', en: '3D & volumes', matches: ['analysis3d', '3d', 'volume', '三维', '体数据'] },
  { id: 'tracking', label: '时间与追踪', en: 'Time & tracking', matches: ['tracking', 'time', '时间', '追踪'] },
  { id: 'automation', label: '自动化与任务', en: 'Automation', matches: ['automation', 'batch', 'macro', 'script', '自动化', '批处理', '宏', '脚本'] },
  { id: 'export', label: '导出与核验', en: 'Export & verify', matches: ['export', 'verify', '导出', '核验'] },
  { id: 'environment', label: '组件与环境', en: 'Components', matches: ['environment', 'component', 'plugin', '组件', '环境'] },
] as const

const statusLabels: { key: CountKey; label: string }[] = [
  { key: 'discovered', label: '已发现' },
  { key: 'source_reviewed', label: '源码已审' },
  { key: 'runtime_verified', label: '运行已验' },
  { key: 'ui_adapted', label: '界面已适配' },
  { key: 'parity_verified', label: '功能已核验' },
]
const emptyCounts: Counts = { discovered: 0, source_reviewed: 0, runtime_verified: 0, ui_adapted: 0, parity_verified: 0 }

function categoryId(value: string): string {
  const normalized = value.trim().toLowerCase()
  return categories.find((category) => category.matches.some((match) => normalized.includes(match)))?.id ?? 'other'
}

function isInventory(value: unknown): value is PluginInventory {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<PluginInventory>
  return Array.isArray(candidate.items) && candidate.items.every((item) =>
    item && typeof item.id === 'string' && typeof item.label === 'string' && typeof item.category === 'string',
  )
}

function isRuntime(value: unknown): value is Runtime {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<Runtime>
  return ['unavailable', 'inventory_ready', 'verified'].includes(String(candidate.state))
    && typeof candidate.message === 'string'
}

function friendlyError(error: unknown): string {
  return error instanceof Error ? error.message : '无法读取本机图像服务。'
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const payload = await response.json().catch(() => null) as { detail?: unknown } | null
  return new Error(typeof payload?.detail === 'string' ? payload.detail : fallback)
}

export default function ImageWorkspace({ onBack }: { onBack: () => void }) {
  const { locale, t } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const [runtime, setRuntime] = useState<Runtime | null>(null)
  const [inventory, setInventory] = useState<PluginInventory | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCatalog, setShowCatalog] = useState(false)
  const [catalogError, setCatalogError] = useState('')
  const [category, setCategory] = useState('all')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [assets, setAssets] = useState<ImageAsset[]>([])
  const assetRevision = useRef(0)
  const [jobs, setJobs] = useState<ImageJob[]>([])
  const [results, setResults] = useState<ImageResult[]>([])
  const [batchResults, setBatchResults] = useState<BatchResult[]>([])
  const [batchFiles, setBatchFiles] = useState<File[]>([])
  const [batchGroupSize, setBatchGroupSize] = useState(2)
  const [batchColumns, setBatchColumns] = useState(2)
  const [batchGap, setBatchGap] = useState(0)
  const [batchUploading, setBatchUploading] = useState(false)
  const [selectedAssets, setSelectedAssets] = useState<string[]>([])
  const [gridColumns, setGridColumns] = useState(2)
  const [gridGap, setGridGap] = useState(0)
  const [annotationResultId, setAnnotationResultId] = useState<string | null>(null)
  const [annotations, setAnnotations] = useState<AnnotationItem[]>([])
  const [annotationRevision, setAnnotationRevision] = useState(0)
  const [annotationKind, setAnnotationKind] = useState<'text' | 'number' | 'scale_bar'>('text')
  const [annotationText, setAnnotationText] = useState('')
  const [annotationX, setAnnotationX] = useState(10)
  const [annotationY, setAnnotationY] = useState(20)
  const [annotationFont, setAnnotationFont] = useState(16)
  const [annotationColor, setAnnotationColor] = useState('#000000')
  const [barAssetId, setBarAssetId] = useState('')
  const [barLengthUm, setBarLengthUm] = useState(10)
  const [barScaleUm, setBarScaleUm] = useState(0.25)
  const [barCalibrationSource, setBarCalibrationSource] = useState<'user_explicit' | 'fiji_inspected_axes'>('user_explicit')
  const [assetMessage, setAssetMessage] = useState('')
  const [uploading, setUploading] = useState(false)
  const [measureAssetId, setMeasureAssetId] = useState('')
  const measureCandidates = assets.filter((asset) => asset.metadata_status === 'fiji_inspected')
  const selectedMeasureAsset = measureCandidates.find((asset) => asset.id === measureAssetId) ?? measureCandidates[0] ?? null
  const { editor, drafts: measurementDrafts, setters, restoreSelections, removeDraft } = useMeasurementEditors(selectedMeasureAsset?.id ?? null)
  const { indices: measureIndices, useRoi: measureUseRoi, kind: measureRoiKind, rectangle: measureRoi,
    polygonText: measurePolygonText, extras: measureExtras } = editor
  const { indices: setMeasureIndices, useRoi: setMeasureUseRoi, kind: setMeasureRoiKind, rectangle: setMeasureRoi,
    polygonText: setMeasurePolygonText, extras: setMeasureExtras } = setters
  const appliedWorkspaceJobs = useRef(new Set<string>())
  const requestedWorkspaceJobs = useRef(new Set<string>())
  const [nativeDrafts, setNativeDrafts] = useState<Record<string, NativeMeasurementDraft>>({})
  const [workspaceRevision, setWorkspaceRevision] = useState(0)
  const [roiCollectionsByAsset, setRoiCollectionsByAsset] = useState<Record<string, RoiCollectionItem[]>>({})

  const refresh = useCallback(async (signal?: AbortSignal, showLoading = true) => {
    if (showLoading) {
      setLoading(true)
      setError('')
    }
    const revision = assetRevision.current
    try {
      const [runtimeResponse, assetsResponse, jobsResponse, resultsResponse, batchResponse] = await Promise.all([
        fetch('/api/image/runtime', { signal }),
        fetch('/api/image/assets', { signal }),
        fetch('/api/image/jobs', { signal }),
        fetch('/api/image/results', { signal }),
        fetch('/api/image/batch-results', { signal }),
      ])
      if (!runtimeResponse.ok || !assetsResponse.ok || !jobsResponse.ok || !resultsResponse.ok || !batchResponse.ok) {
        throw new Error('图像引擎清单尚未由本机服务提供。')
      }
      const nextRuntime: unknown = await runtimeResponse.json()
      if (!isRuntime(nextRuntime)) throw new Error('本机图像服务返回了无法识别的状态。')
      setRuntime(nextRuntime)
      const loadedAssets = await assetsResponse.json() as { items?: ImageAsset[] }
      if (!signal?.aborted && revision === assetRevision.current) {
        setAssets(Array.isArray(loadedAssets.items) ? loadedAssets.items : [])
      }
      const loadedJobs = await jobsResponse.json() as { items?: ImageJob[] }
      setJobs(Array.isArray(loadedJobs.items) ? loadedJobs.items : [])
      const loadedResults = await resultsResponse.json() as { items?: ImageResult[] }
      setResults(Array.isArray(loadedResults.items) ? loadedResults.items : [])
      const loadedBatchResults = await batchResponse.json() as { items?: BatchResult[] }
      setBatchResults(Array.isArray(loadedBatchResults.items) ? loadedBatchResults.items : [])
    } catch (cause) {
      if (signal?.aborted) return
      setRuntime(null)
      setError(friendlyError(cause))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!showCatalog || inventory) return
    const controller = new AbortController()
    void fetch('/api/image/plugins', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error('无法读取功能目录。')
      const payload: unknown = await response.json()
      if (!isInventory(payload)) throw new Error('功能目录格式无法识别。')
      if (!controller.signal.aborted) setInventory(payload)
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setCatalogError(friendlyError(cause))
    })
    return () => controller.abort()
  }, [showCatalog, inventory])

  const uploadAsset = async (file: File) => {
    if (file.size > 1024 ** 3) { setAssetMessage('单张图像超过 1 GiB 上限。'); return }
    setUploading(true)
    setAssetMessage('正在将图像保存到本机会话…')
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch('/api/image/assets', { method: 'POST', body: form })
      const payload = await response.json() as ImageAsset & { detail?: string }
      if (!response.ok) throw new Error(payload.detail || '图像导入失败。')
      assetRevision.current += 1
      setAssets((current) => [...current.filter((asset) => asset.id !== payload.id), payload])
      setSelectedAssets((current) => [...current, payload.id])
      setAssetMessage('图像已原样存入本机会话；像素、通道和标尺尚未由 Fiji 核验。')
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    } finally {
      setUploading(false)
    }
  }

  const openProject = async (file: File) => {
    const workspace = file.name.toLowerCase().endsWith('.bfswork')
    if (file.size > 2 * 1024 ** 3 + (workspace ? 1114112 : 327680)) {
      setAssetMessage('项目包超过 2 GiB 源图容量上限。'); return
    }
    setUploading(true)
    setAssetMessage('正在将项目包保存到本机，随后重新检查全部源图…')
    try {
      const form = new FormData()
      form.append('file', file)
      const response = await fetch(workspace ? '/api/image/jobs/open-workspace' : '/api/image/jobs/open-project', { method: 'POST', body: form })
      const payload = await response.json() as ImageJob & { detail?: string }
      if (!response.ok) throw new Error(payload.detail || '项目打开失败。')
      if (workspace) requestedWorkspaceJobs.current.add(payload.id)
      setJobs((current) => [payload, ...current.filter((job) => job.id !== payload.id)])
      setAssetMessage(workspace ? '工作台项目已排队；全部原图、ROI 和当前选择核验成功后恢复。'
        : '项目已排队。全部源图重新核验、拼版和标注恢复成功后才加入当前会话。')
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    } finally {
      setUploading(false)
    }
  }

  const removeAsset = async (asset: ImageAsset) => {
    try {
      const response = await fetch(`/api/image/assets/${asset.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error('本机会话图像移除失败。')
      assetRevision.current += 1
      setAssets((current) => current.filter((item) => item.id !== asset.id))
      setSelectedAssets((current) => current.filter((id) => id !== asset.id))
      removeDraft(asset.id)
      setNativeDrafts((current) => { const next = { ...current }; delete next[asset.id]; return next })
      setRoiCollectionsByAsset((current) => { const next = { ...current }; delete next[asset.id]; return next })
      setAssetMessage('图像已从当前本机会话移除。')
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const inspectAsset = async (asset: ImageAsset) => {
    setAssetMessage('已提交给本机 Fiji 检查图像元数据。')
    try {
      const response = await fetch('/api/image/jobs/inspect', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_id: asset.id }),
      })
      const payload = await response.json() as ImageJob & { detail?: string }
      if (!response.ok) throw new Error(payload.detail || '无法开始检查。')
      setJobs((current) => [payload, ...current.filter((job) => job.id !== payload.id)])
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const measureAsset = async (asset: ImageAsset) => {
    const axes = asset.axes ?? []
    const labels: Record<string, string> = { Channel: 'C', Z: 'Z', Time: 'T' }
    const indices: Record<string, number> = {}
    for (const axis of axes) {
      const key = labels[axis.name]
      if (key) indices[key] = measureIndices[key] ?? 0
    }
    setAssetMessage('已提交本机 Fiji 指定平面与区域测量任务。')
    try {
      const response = await fetch('/api/image/jobs/measure-selection', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: '1.0', asset_id: asset.id, indices,
          roi: measureUseRoi ? (measureRoiKind === 'polygon' ? { kind: 'polygon', points: measurePolygonPoints }
            : measureRoiKind === 'ellipse' ? { kind: 'ellipse', ...measureRoi } : measureRoi) : null,
          extra_measurements: measureExtras }),
      })
      const payload = await response.json() as ImageJob & { detail?: string }
      if (!response.ok) throw new Error(payload.detail || 'Fiji 区域测量任务未能开始。')
      setJobs((current) => [payload, ...current.filter((job) => job.id !== payload.id)])
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const invertAsset = async (asset: ImageAsset) => {
    setAssetMessage('已提交本机 Fiji 8 位灰度反相任务。')
    try {
      const response = await fetch('/api/image/jobs/invert-8bit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_id: asset.id }),
      })
      const payload = await response.json() as ImageJob & { detail?: string }
      if (!response.ok) throw new Error(payload.detail || 'Fiji 反相任务未能开始。')
      setJobs((current) => [payload, ...current.filter((job) => job.id !== payload.id)])
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const cancelJob = async (job: ImageJob) => {
    try {
      const response = await fetch(`/api/image/jobs/${job.id}/cancel`, { method: 'POST' })
      if (!response.ok) throw new Error('无法取消本机任务。')
      const payload = await response.json() as ImageJob
      setJobs((current) => current.map((item) => item.id === job.id ? payload : item))
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const createGrid = async () => {
    if (selectedAssets.length === 0) { setAssetMessage('请先选择至少一张源图像。'); return }
    setAssetMessage('已提交原像素网格拼版任务。')
    try {
      const response = await fetch('/api/image/jobs/exact-grid', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: '1.0', asset_ids: selectedAssets,
          columns: Math.min(Math.max(gridColumns, 1), selectedAssets.length), gap_px: gridGap }),
      })
      const payload = await response.json() as ImageJob & { detail?: string }
      if (!response.ok) throw new Error(payload.detail || '原像素网格任务未能开始。')
      setJobs((current) => [payload, ...current.filter((job) => job.id !== payload.id)])
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const createBatch = async () => {
    if (!batchFiles.length || batchFiles.length > 64 || batchFiles.length % batchGroupSize) {
      setAssetMessage('批量文件需 1 至 64 张，并能按每组张数完整分组。')
      return
    }
    if (batchFiles.some((file) => file.size > 1024 ** 3)
        || batchFiles.reduce((total, file) => total + file.size, 0) > 4 * 1024 ** 3) {
      setAssetMessage('批量输入超过单张 1 GiB 或总计 4 GiB 上限。')
      return
    }
    setBatchUploading(true)
    setAssetMessage('正在导入本机批量图像…')
    try {
      const form = new FormData()
      for (const file of batchFiles) form.append('files', file)
      form.append('group_size', String(batchGroupSize))
      form.append('columns', String(Math.min(batchColumns, batchGroupSize)))
      form.append('gap_px', String(batchGap))
      const response = await fetch('/api/image/jobs/batch-grid', { method: 'POST', body: form })
      const payload = await response.json() as ImageJob & { detail?: string }
      if (!response.ok) throw new Error(payload.detail || '批量任务未能开始。')
      setJobs((current) => [payload, ...current.filter((job) => job.id !== payload.id)])
      setBatchFiles([])
      setAssetMessage('批量任务已排队；完成后下载包含每组 TIFF 和核验清单的 ZIP。')
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    } finally {
      setBatchUploading(false)
    }
  }

  const deleteResult = async (result: ImageResult) => {
    try {
      const response = await fetch(`/api/image/results/${result.id}`, { method: 'DELETE' })
      if (!response.ok) throw await responseError(response, '无法移除本机成品。')
      setResults((current) => current.filter((item) => item.id !== result.id))
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const deleteBatchResult = async (result: BatchResult) => {
    try {
      const response = await fetch(`/api/image/batch-results/${result.id}`, { method: 'DELETE' })
      if (!response.ok) throw await responseError(response, '无法移除本机批量成品。')
      setBatchResults((current) => current.filter((item) => item.id !== result.id))
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const gridResults = results.filter((result) => Array.isArray(result.proof.placements))
  const selectedResult = gridResults.find((result) => result.id === annotationResultId) ?? gridResults[0] ?? null
  const polygonLines = measurePolygonText.trim().split(/\r?\n/)
  const measurePolygonPoints = polygonLines.length >= 3 && polygonLines.length <= 32 && polygonLines.every((line) => /^\s*\d+\s*,\s*\d+\s*$/.test(line))
    ? polygonLines.map((line) => { const [x, y] = line.split(',').map(Number); return { x, y } }) : null
  const polygonWidth = selectedMeasureAsset?.axes?.find((axis) => axis.name === 'X')?.length ?? 0
  const polygonHeight = selectedMeasureAsset?.axes?.find((axis) => axis.name === 'Y')?.length ?? 0
  const measurePolygonValid = measurePolygonPoints !== null
    && measurePolygonPoints.every(({ x, y }) => x < polygonWidth && y < polygonHeight)
    && new Set(measurePolygonPoints.map(({ x, y }) => `${x},${y}`)).size === measurePolygonPoints.length
    && measurePolygonPoints.reduce((area, point, index) => {
      const next = measurePolygonPoints[(index + 1) % measurePolygonPoints.length]
      return area + point.x * next.y - next.x * point.y
    }, 0) !== 0
  const measureIndicesValid = (selectedMeasureAsset?.axes ?? []).every((axis) => {
    const key = axis.name === 'Channel' ? 'C' : axis.name === 'Time' ? 'T' : axis.name === 'Z' ? 'Z' : null
    if (!key) return true
    const index = measureIndices[key]
    return Number.isInteger(index) && index >= 0 && index < axis.length
  })
  const measureRoiValid = !measureUseRoi || (measureRoiKind === 'polygon' ? measurePolygonValid
    : Number.isInteger(measureRoi.x) && Number.isInteger(measureRoi.y)
      && Number.isInteger(measureRoi.width) && Number.isInteger(measureRoi.height)
      && measureRoi.x >= 0 && measureRoi.y >= 0 && measureRoi.width > 0 && measureRoi.height > 0
      && measureRoi.x + measureRoi.width <= polygonWidth && measureRoi.y + measureRoi.height <= polygonHeight)
  const measureSelectionIndices: Record<string, number> = {}
  for (const axis of selectedMeasureAsset?.axes ?? []) {
    const key = axis.name === 'Channel' ? 'C' : axis.name === 'Time' ? 'T' : axis.name === 'Z' ? 'Z' : null
    if (key) measureSelectionIndices[key] = measureIndices[key] ?? 0
  }
  const currentCollectionRoi = !measureUseRoi || !measureRoiValid ? null
    : measureRoiKind === 'polygon' ? { kind: 'polygon' as const, points: measurePolygonPoints ?? [] }
      : { kind: measureRoiKind, ...measureRoi }
  const saveWorkspace = () => {
    if (!assets.length || !measureIndicesValid || !measureRoiValid) {
      setAssetMessage('请先修正当前 ROI 与轴位置后保存。'); return
    }
    const sourceStates: Record<string, unknown> = {}
    for (const asset of assets) {
      const items = roiCollectionsByAsset[asset.id]
      const state: Record<string, unknown> = {}
      if (items?.length) state.collection = { version: '1.0', source: {
        sha256: asset.sha256, bytes: asset.bytes, axes: asset.axes }, items }
      const native = nativeDrafts[asset.id]
      const draft = asset.id === selectedMeasureAsset?.id ? editor : measurementDrafts[asset.id] ?? (native ? defaultMeasurementEditor() : null)
      if (draft) {
        try { state.selection = selectionFromEditor(draft, asset.axes ?? []) }
        catch (cause) { setAssetMessage(`${asset.original_name}：${friendlyError(cause)}`); return }
      }
      if (native) {
        try {
          const targets = assets.filter((candidate) => candidate.id !== asset.id).map((candidate) => ({ ...candidate, axes: candidate.axes ?? [] }))
          state.native_measurement = { ...nativeDraftParameters(native, targets), roi: nativeDraftGeometry(native, asset.axes ?? []) }
        } catch (cause) { setAssetMessage(`${asset.original_name}：${friendlyError(cause)}`); return }
      }
      if (Object.keys(state).length) sourceStates[asset.id] = state
    }
    const form = document.createElement('form')
    form.method = 'POST'; form.action = '/api/image/workspace/project'; form.target = '_blank'
    const input = document.createElement('input')
    input.type = 'hidden'; input.name = 'state'; input.value = JSON.stringify({
      asset_ids: assets.map((asset) => asset.id), source_states: sourceStates,
      active_asset_id: selectedMeasureAsset?.id ?? null, selected_asset_ids: selectedAssets,
      grid: { columns: Math.min(gridColumns, assets.length), gap_px: gridGap },
    })
    form.append(input); document.body.append(form); form.submit(); form.remove()
    setAssetMessage('正在保存工作台项目；浏览器将下载原始图像与当前状态。保存失败时会在新标签页显示原因。')
  }

  const restoreWorkspaceState = useCallback((job: ImageJob) => {
      const state = job.result?.workspace
      if (job.operation !== 'open_workspace_project' || job.state !== 'succeeded' || !state
          || !requestedWorkspaceJobs.current.has(job.id) || appliedWorkspaceJobs.current.has(job.id)) return
      appliedWorkspaceJobs.current.add(job.id)
      setWorkspaceRevision((value) => value + 1)
      setRoiCollectionsByAsset((current) => ({ ...current, ...Object.fromEntries(
        Object.entries(state.source_states).map(([id, value]) => [id, value.collection?.items ?? []])) }))
      setNativeDrafts((current) => {
        const next = { ...current }
        for (const asset of job.result?.assets ?? []) delete next[asset.id]
        for (const [id, value] of Object.entries(state.source_states)) {
          const native = value.native_measurement
          if (!native) continue
          const { measurements, decimal_places, threshold } = native.settings
          const draft = { ...defaultNativeMeasurementDraft(), selected: measurements, decimalPlaces: decimal_places,
            thresholdEnabled: threshold !== null, thresholdMin: threshold ? String(threshold.min) : '',
            thresholdMax: threshold ? String(threshold.max) : '', redirectId: native.redirect_source ?? '',
            redirectIndices: Object.fromEntries(Object.entries(native.redirect_plane ?? {}).map(([key, index]) => [key, String(index)])) }
          next[id] = native.roi ? draftFromImportedRoi(draft, native.roi) : draft
        }
        return next
      })
      setSelectedAssets(state.selected_asset_ids)
      setGridColumns(state.grid.columns); setGridGap(state.grid.gap_px)
      restoreSelections(Object.fromEntries(Object.entries(state.source_states)
        .map(([id, value]) => [id, value.selection as SavedMeasurementSelection | null])))
      if (state.active_asset_id) setMeasureAssetId(state.active_asset_id)
      setAssetMessage('工作台项目已恢复：原图、ROI 集合、当前平面和选择均已重新核验。')
  }, [restoreSelections])

  const selectedResultId = selectedResult?.id

  const saveAnnotations = async (items: AnnotationItem[]) => {
    if (!selectedResult) return
    try {
      const response = await fetch(`/api/image/results/${selectedResult.id}/annotations`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: '1.0', items }),
      })
      const payload = await response.json() as { items?: AnnotationItem[]; detail?: string }
      if (!response.ok) throw new Error(payload.detail || '保存标注失败。')
      setAnnotations(payload.items ?? [])
      setAnnotationRevision((current) => current + 1)
      setAssetMessage('标注层已单独保存，原像素 TIFF 未修改。')
    } catch (cause) {
      setAssetMessage(friendlyError(cause))
    }
  }

  const addAnnotation = () => {
    if (!selectedResult) return
    const item: AnnotationItem = annotationKind === 'scale_bar' ? {
      kind: 'scale_bar', asset_id: barAssetId || selectedResult.proof.placements?.[0]?.asset_id || '',
      offset_x: annotationX, offset_y: annotationY, length_um: barLengthUm,
      calibration_source: barCalibrationSource,
      ...(barCalibrationSource === 'user_explicit' ? { x_um_per_pixel: barScaleUm } : {}), color: annotationColor,
    } : { kind: annotationKind, text: annotationText, x: annotationX, y: annotationY,
      font_px: annotationFont, color: annotationColor }
    void saveAnnotations([...annotations, item])
  }

  useEffect(() => {
    const controller = new AbortController()
    queueMicrotask(() => {
      if (!controller.signal.aborted) void refresh(controller.signal, false)
    })
    return () => controller.abort()
  }, [refresh])

  useEffect(() => {
    if (!jobs.some((job) => job.state === 'queued' || job.state === 'running')) return
    const controller = new AbortController()
    const options = { signal: controller.signal }
    let polling = false
    const timer = window.setInterval(() => {
      if (polling) return
      polling = true
      const revision = assetRevision.current
      void Promise.all([fetch('/api/image/jobs?include_results=false', options), fetch('/api/image/results', options),
        fetch('/api/image/assets', options), fetch('/api/image/batch-results', options)]).then(async ([jobsResponse, resultsResponse, assetsResponse, batchResponse]) => {
        if (![jobsResponse, resultsResponse, assetsResponse, batchResponse].every((response) => response.ok))
          throw new Error('本机状态响应失败。')
        const payload = await jobsResponse.json() as { items?: ImageJob[] }
        const resultPayload = await resultsResponse.json() as { items?: ImageResult[] }
        const assetsPayload = await assetsResponse.json() as { items?: ImageAsset[] }
        const batchPayload = await batchResponse.json() as { items?: BatchResult[] }
        if (Array.isArray(payload.items)) {
          const hydrated = await Promise.all(payload.items.map(async (summary) => {
            if (summary.state !== 'succeeded') return summary
            const cached = jobs.find((old) => old.id === summary.id && old.state === 'succeeded' && old.result)
            if (cached) return { ...summary, result: cached.result }
            const detail = await fetch(`/api/image/jobs/${summary.id}`, options)
            if (!detail.ok) throw new Error('本机结果暂不可用。')
            return await detail.json() as ImageJob
          }))
          if (controller.signal.aborted) return
          setJobs(hydrated)
          for (const job of hydrated) restoreWorkspaceState(job)
        }
        if (controller.signal.aborted) return
        if (Array.isArray(resultPayload.items)) setResults(resultPayload.items)
        if (revision === assetRevision.current && Array.isArray(assetsPayload.items)) setAssets(assetsPayload.items)
        if (Array.isArray(batchPayload.items)) setBatchResults(batchPayload.items)
      }).catch(() => {
        if (!controller.signal.aborted) setAssetMessage('本机任务状态暂时无法刷新。')
      }).finally(() => { polling = false })
    }, 1000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [jobs, restoreWorkspaceState])

  useEffect(() => {
    if (!selectedResultId) return
    const controller = new AbortController()
    void fetch(`/api/image/results/${selectedResultId}/annotations`, { signal: controller.signal })
      .then((response) => response.json()).then((payload: { items?: AnnotationItem[] }) => {
        if (!controller.signal.aborted) setAnnotations(Array.isArray(payload.items) ? payload.items : [])
      }).catch(() => {})
    return () => controller.abort()
  }, [selectedResultId])

  const items = useMemo(() => inventory?.items ?? [], [inventory])
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const item of items) {
      const key = categoryId(item.category)
      counts[key] = (counts[key] ?? 0) + 1
    }
    return counts
  }, [items])
  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase()
    return items.filter((item) => (category === 'all' || categoryId(item.category) === category)
      && (!term || [item.label, item.id, item.menu_path, item.source].some((part) => String(part ?? '').toLocaleLowerCase().includes(term))))
  }, [items, category, query])
  const visible = filtered.slice(0, 250)
  const selected = visible.find((item) => item.id === selectedId) ?? visible[0] ?? null
  const counts = inventory?.counts ?? runtime?.counts ?? emptyCounts
  const runtimeLabel = runtime?.state === 'verified' ? '已完成运行核验' : runtime?.state === 'inventory_ready' ? '清单可浏览' : '引擎未就绪'
  const jobLabel = (job: ImageJob) => job.source_label ?? (job.operation === 'exact_grid_batch' ? tx('批量原像素网格')
    : job.operation === 'open_grid_project' ? tx('重开图像项目')
    : job.operation === 'open_workspace_project' ? tx('恢复工作台项目')
    : job.operation === 'invert_8bit' ? tx('Fiji 8 位灰度反相')
      : job.operation === 'measure_selection' ? tx('Fiji 指定区域测量')
      : job.operation === 'measure_roi_collection' ? tx('命名 ROI 集合逐项测量')
      : job.operation === 'native_multi_measure' ? tx('原生 ROI Manager Multi Measure')
    : job.operation === 'exact_grid' ? tx('原像素网格')
      : assets.find((asset) => asset.id === job.asset_id)?.original_name || job.asset_id.slice(0, 8))
  const jobDetails = (job: ImageJob) => {
    if (!job.result) return null
    if (job.operation === 'open_workspace_project' && job.result?.workspace) {
      return <button type="button" disabled={!job.result.assets?.every((source) => assets.some((asset) => asset.id === source.id))} onClick={() => {
        requestedWorkspaceJobs.current.add(job.id); appliedWorkspaceJobs.current.delete(job.id)
        restoreWorkspaceState(job)
      }}>{tx("恢复此项目状态")}</button>
    }
    if (job.operation === 'open_grid_project') {
      return <p>{tx("已重新检查")}{job.result.assets?.length} {tx("张源图并恢复拼版与独立标注。原图和成品已加入下方列表。")}</p>
    }
    if (job.operation === 'exact_grid_batch') {
      return <p>{tx("批量任务已完成；请在下方下载 ZIP 成品。")}</p>
    }
    if (job.operation === 'exact_grid') {
      return <p>{job.result.proof?.mode} · {job.result.proof?.width} × {job.result.proof?.height} {tx("· 已逐区域核验")}{job.result.proof?.verified_pixels} {tx("个源像素")}</p>
    }
    if (job.operation === 'invert_8bit') {
      return <p>{job.result.proof?.width} × {job.result.proof?.height} {tx("· 已逐像素核验")}{job.result.proof?.verified_pixels} {tx("个像素")}</p>
    }
    if (job.operation === 'measure_selection') {
      return <MeasurementResult jobId={job.id} selection={job.selection}
        sampleCount={job.result.sample_count} statistics={job.result.imagej1_analyzer} />
    }
    if (job.operation === 'measure_roi_collection') {
      return <p>{tx("按每项保存的 C/Z/T 平面使用原生 ImageJ1 Analyzer；结果请在上方命名 ROI 集合中查看与下载。")}</p>
    }
    return <p>{job.result.pixel_type || tx('像素类型未知')} · {job.result.bit_depth ?? '?'} {tx("位 ·")}{job.result.axes?.map((axis) => `${axis.name} ${axis.length}${axis.unit ? ` ${axis.unit}` : ''}`).join(' × ') || tx('轴信息未知')}</p>
  }

  const [styleQueueOpen,setStyleQueueOpen]=useState(false)
  return (
    <section className="iw" aria-label={tx("图像工作台")}>
      <div className="iw-heading">
        <div>
          <span className="wf-overline">{tx("IMAGE WORKSPACE / FIJI 插件")}</span>
          <h1>{tx("图像工作台")}</h1>
          <p>{tx("导入图像、选择区域、测量或拼版，文件与处理都留在本机。功能目录可按需展开查看。")}</p>
        </div>
        <button type="button" onClick={onBack}>{tx("← 返回作品类型")}</button>
      </div>

      <details open={styleQueueOpen} onToggle={event=>setStyleQueueOpen(event.currentTarget.open)}>
        <summary>{t('统一风格处理队列','Unified image presentation queue')}</summary>
        {styleQueueOpen&&<ImageStyleQueue/>}
      </details>

      <div className="iw-runtime" role="status">
        <div className="iw-runtime-title"><span className={`iw-state-dot iw-state-${runtime?.state ?? 'unavailable'}`} />
          <strong>{loading ? tx('正在读取本机图像清单') : error ? tx('本机图像清单不可用') : tx(runtimeLabel)}</strong>
          <button type="button" onClick={() => void refresh()} disabled={loading || uploading}>{tx("刷新状态")}</button>
        </div>
        <p>{tx(error || runtime?.message || '正在连接本机服务。')}</p>
        {runtime?.snapshot_id && <small>{tx("发行快照：")}{runtime.snapshot_id}</small>}
      </div>

      <div className="iw-assets">
        <div><h2>{tx("图像资源")}<span>Local assets</span></h2><p>{tx("保留源文件字节与摘要。可用本机 Fiji 检查格式、位深、轴和标尺。")}</p></div>
        <label className="iw-file-picker">{uploading ? tx('正在导入…') : tx('选择本机图像')}<input type="file" disabled={loading || uploading} onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) void uploadAsset(file)
          event.target.value = ''
        }} /></label>
        <label className="iw-file-picker">{tx("打开图像项目")}<input type="file" accept=".bfsimg,.bfswork" disabled={loading || uploading} onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) void openProject(file)
          event.target.value = ''
        }} /></label>
        <button type="button" disabled={uploading || assets.length === 0} onClick={saveWorkspace}>{tx("保存工作台项目")}</button>
        {assetMessage && <p className="iw-asset-message" role="status">{tx(assetMessage)}</p>}
        {assets.length > 0 && <ul>{assets.map((asset) => <li key={asset.id}><label className="iw-asset-select"><input type="checkbox" checked={selectedAssets.includes(asset.id)} onChange={(event) => setSelectedAssets((current) => event.target.checked ? [...current, asset.id] : current.filter((id) => id !== asset.id))} /><strong>{asset.original_name}</strong></label><span>{(asset.bytes / 1024 ** 2).toFixed(1)} MiB · SHA-256 {asset.sha256.slice(0, 12)}… · {asset.metadata_status === 'fiji_inspected' ? tx(`Fiji 已检 ${asset.bit_depth ?? '?'} 位`) : tx('元数据待检')}</span><div className="iw-asset-actions"><button type="button" onClick={() => void inspectAsset(asset)}>{tx("Fiji 检查")}</button><button type="button" onClick={() => void invertAsset(asset)}>{tx("Fiji 反相（8 位灰度）")}</button><button type="button" onClick={() => void removeAsset(asset)}>{tx("移除")}</button></div></li>)}</ul>}
        {selectedMeasureAsset && <div className="iw-grid-controls">
          <strong>{tx("区域与基础测量")}</strong>
          <label>{tx("已检查图像")}<select value={selectedMeasureAsset.id} onChange={(event) => {
            setMeasureAssetId(event.target.value)
          }}>
            {measureCandidates.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_name}</option>)}
          </select></label>
          {selectedMeasureAsset.axes?.filter((axis) => ['Channel', 'Z', 'Time'].includes(axis.name)).map((axis) => {
            const key = axis.name === 'Channel' ? 'C' : axis.name === 'Time' ? 'T' : 'Z'
            return <label key={key}>{key} {tx("索引（0–")}{axis.length - 1}）<input type="number" min="0" max={axis.length - 1}
              value={measureIndices[key] ?? 0}
              onChange={(event) => setMeasureIndices((current) => ({ ...current, [key]: Number(event.target.value) }))} /></label>
          })}
          <label><input type="checkbox" checked={measureUseRoi} onChange={(event) => setMeasureUseRoi(event.target.checked)} />{tx("使用 ROI")}</label>
          {measureUseRoi && <>
            <label>{tx("形状")}<select value={measureRoiKind} onChange={(event) => setMeasureRoiKind(event.target.value as 'rectangle' | 'ellipse' | 'polygon')}>
              <option value="rectangle">{tx("矩形")}</option><option value="ellipse">{tx("椭圆")}</option><option value="polygon">{tx("多边形")}</option></select></label>
            {measureRoiKind === 'polygon' ? <label>{tx("顶点（每行 x,y）")}<textarea value={measurePolygonText}
              onChange={(event) => setMeasurePolygonText(event.target.value)} rows={4} /></label>
              : (['x', 'y', 'width', 'height'] as const).map((key) => <label key={key}>{key}<input type="number" min={key === 'x' || key === 'y' ? 0 : 1}
              value={measureRoi[key]} onChange={(event) => setMeasureRoi((current) => ({ ...current, [key]: Number(event.target.value) }))} /></label>)}
          </>}
          {([['std_dev', tx('标准差')], ['median', tx('中位数')], ['mode', tx('众数灰度值')], ['integrated_density', tx('积分密度')]] as const).map(([key, label]) =>
            <label key={key}><input type="checkbox" checked={measureExtras.includes(key)}
              onChange={(event) => setMeasureExtras((current) => event.target.checked
                ? [...current, key] : current.filter((item) => item !== key))} />{label}</label>)}
          <button type="button" disabled={!measureIndicesValid || !measureRoiValid} onClick={() => void measureAsset(selectedMeasureAsset)}>{tx("测量所选区域")}</button>
          {!measureIndicesValid && <p role="status">{tx("轴索引超出已检查的范围；请修正后再测量。")}</p>}
          {!measureRoiValid && <p role="status">{tx("ROI 超出已检查图像边界，或顶点未围成有效多边形。")}</p>}
          <p>{tx("选定平面后，可在预览上圈出区域。基础测量包含面积、均值和极值。")}</p>
          <ImageSourcePlanePreview key={`${selectedMeasureAsset.id}:${measureIndices.C}:${measureIndices.Z}:${measureIndices.T}`}
            assetId={selectedMeasureAsset.id} axes={selectedMeasureAsset.axes ?? []}
            bytes={selectedMeasureAsset.bytes} bitDepth={selectedMeasureAsset.bit_depth} indices={measureIndices}
            roi={measureRoi} roiKind={measureRoiKind} polygonPoints={measurePolygonValid ? measurePolygonPoints : null} useRoi={measureUseRoi}
            onRoiChange={(next) => { setMeasureRoi(next); setMeasureUseRoi(true) }}
            onPointAdd={(point) => setMeasurePolygonText((current) => `${current.trim()}\n${point.x},${point.y}`)} />
          <details className="iw-measure-more">
            <summary>{tx("区域集合")}</summary>
            <ImageRoiCollection key={`${selectedMeasureAsset.id}:${workspaceRevision}`} assetId={selectedMeasureAsset.id}
            indices={measureSelectionIndices} roi={measureIndicesValid ? currentCollectionRoi : null}
            initialItems={roiCollectionsByAsset[selectedMeasureAsset.id] ?? []}
            onItemsChange={(next) => setRoiCollectionsByAsset((current) => ({ ...current, [selectedMeasureAsset.id]: next }))}
            onSelect={(item) => {
              setMeasureIndices({ C: item.indices.C ?? 0, Z: item.indices.Z ?? 0, T: item.indices.T ?? 0 })
              if (item.roi.kind === 'full') { setMeasureUseRoi(false); return }
              setMeasureUseRoi(true)
              if (item.roi.kind === 'polygon') {
                setMeasureRoiKind('polygon')
                setMeasurePolygonText((item.roi.points ?? []).map((point) => `${point.x},${point.y}`).join('\n'))
              } else {
                setMeasureRoiKind(item.roi.kind === 'ellipse' ? 'ellipse' : 'rectangle')
                setMeasureRoi({ x: item.roi.x ?? 0, y: item.roi.y ?? 0,
                  width: item.roi.width ?? 1, height: item.roi.height ?? 1 })
              }
            }} />

          </details>
          <details className="iw-measure-more">
            <summary>{tx("高级测量与 ROI 文件")}</summary>
            <ImageNativeMeasureTask key={`native-${selectedMeasureAsset.id}:${workspaceRevision}`}
            asset={{ ...selectedMeasureAsset, axes: selectedMeasureAsset.axes ?? [] }}
            availableAssets={measureCandidates.map((asset) => ({ ...asset, axes: asset.axes ?? [] }))}
            indices={measureSelectionIndices} roi={currentCollectionRoi} validSelection={measureIndicesValid && measureRoiValid}
            draft={nativeDrafts[selectedMeasureAsset.id] ?? defaultNativeMeasurementDraft()}
            onDraftChange={(update) => setNativeDrafts((current) => ({ ...current, [selectedMeasureAsset.id]:
              typeof update === 'function' ? update(current[selectedMeasureAsset.id] ?? defaultNativeMeasurementDraft()) : update }))}
            onPlaneChange={setMeasureIndices}
            validPlane={measureIndicesValid}
            jobs={jobs} onSubmitted={(job) => setJobs((current) => [job as ImageJob, ...current.filter((old) => old.id !== job.id)])} />

          </details>
          <details className="iw-measure-more">
            <summary>{tx("多区域与多平面测量")}</summary>
            <ImageMultiMeasureTask key={`multi-${selectedMeasureAsset.id}:${workspaceRevision}`}
            assetId={selectedMeasureAsset.id} currentPlane={measureSelectionIndices} validPlane={measureIndicesValid}
            collection={{ version: '1.0', source: { sha256: selectedMeasureAsset.sha256,
              bytes: selectedMeasureAsset.bytes, axes: selectedMeasureAsset.axes ?? [] },
              items: roiCollectionsByAsset[selectedMeasureAsset.id] ?? [] }} jobs={jobs}
            onSubmitted={(job) => setJobs((current) => [job as ImageJob, ...current.filter((old) => old.id !== job.id)])} />

          </details>
        </div>}
        {assets.length > 0 && <div className="iw-grid-controls"><strong>{tx("原像素网格拼版")}</strong><label>{tx("列数")}<input type="number" min="1" max={Math.max(1, selectedAssets.length)} value={Math.min(gridColumns, Math.max(1, selectedAssets.length))} onChange={(event) => setGridColumns(Number(event.target.value))} /></label><label>{tx("间距 px")}<input type="number" min="0" max="1000" value={gridGap} onChange={(event) => setGridGap(Number(event.target.value))} /></label><button type="button" onClick={() => void createGrid()} disabled={selectedAssets.length === 0}>{tx("生成并核验 TIFF")}</button><p>{tx("仅支持相同像素模式的单帧图像；不缩放、不插值。一致且已核验的 X/Y 标定会写入 TIFF；混合或缺失标定时不设置统一标尺。完整元数据往返仍待核验。")}</p></div>}
        {jobs.length > 0 && <div className="iw-jobs"><h3>{tx("本机任务")}</h3>{jobs.map((job) => <div key={job.id} className="iw-job"><strong>{jobLabel(job)}</strong><span>{job.state === 'queued' ? tx('排队中') : job.state === 'running' ? tx('运行中') : job.state === 'succeeded' ? tx('已完成') : job.state === 'cancelled' ? tx('已取消') : job.state === 'failed' ? tx('失败') : job.state === 'waiting_for_interaction' ? tx('等待交互') : tx('已中断')}{job.progress != null ? ` · ${Math.round(job.progress * 100)}%` : ''}</span>{(job.state === 'queued' || job.state === 'running') && <button type="button" onClick={() => void cancelJob(job)}>{tx("取消")}</button>}{job.error && <p>{tx(job.error)}</p>}{jobDetails(job)}</div>)}</div>}
        {results.length > 0 && <div className="iw-results-download"><h3>{tx("成品 TIFF")}</h3>{results.map((result) => <div key={result.id}><span>{result.proof.command ? tx('Fiji 反相 · 8 位灰度') : result.proof.mode} · {result.proof.width} × {result.proof.height} · SHA-256 {result.sha256.slice(0, 12)}…</span><a href={`/api/image/results/${result.id}/file`} download={result.filename}>{tx("下载")}</a>{result.proof.grid_recipe && <a href={`/api/image/results/${result.id}/project`} download={`biofigure-grid-${result.id.slice(0, 8)}.bfsimg`}>{tx("保存项目包")}</a>}<button type="button" onClick={() => void deleteResult(result)}>{tx("移除")}</button></div>)}</div>}
        {selectedResult && <ImageResultPreview key={selectedResult.id} id={selectedResult.id} width={selectedResult.proof.width} height={selectedResult.proof.height} hasAnnotations={annotations.length > 0} revision={annotationRevision} />}
        {selectedResult && <div className="iw-annotations"><div><h3>{tx("独立标注层")}</h3><p>{tx("文字、编号与比例尺作为透明 SVG 保存；下载原像素 TIFF 时不写入标注。")}</p></div><label>{tx("成品")}<select value={selectedResult.id} onChange={(event) => setAnnotationResultId(event.target.value)}>{gridResults.map((result) => <option key={result.id} value={result.id}>{result.filename}</option>)}</select></label><label>{tx("类型")}<select value={annotationKind} onChange={(event) => setAnnotationKind(event.target.value as 'text' | 'number' | 'scale_bar')}><option value="text">{tx("文字")}</option><option value="number">{tx("编号")}</option><option value="scale_bar">{tx("比例尺")}</option></select></label>{annotationKind === 'scale_bar' ? <><label>{tx("图块")}<select value={barAssetId || selectedResult.proof.placements?.[0]?.asset_id || ''} onChange={(event) => setBarAssetId(event.target.value)}>{selectedResult.proof.placements?.map((placement) => <option key={placement.asset_id} value={placement.asset_id}>{assets.find((asset) => asset.id === placement.asset_id)?.original_name || placement.asset_id.slice(0, 8)}</option>)}</select></label><label>{tx("标尺长度 µm")}<input type="number" min="0.001" step="any" value={barLengthUm} onChange={(event) => setBarLengthUm(Number(event.target.value))} /></label><label>{tx("标定来源")}<select value={barCalibrationSource} onChange={(event) => setBarCalibrationSource(event.target.value as 'user_explicit' | 'fiji_inspected_axes')}><option value="user_explicit">{tx("手动填写")}</option><option value="fiji_inspected_axes">{tx("使用已核验图块标定")}</option></select></label>{barCalibrationSource === 'user_explicit' && <label>{tx("X 轴 µm/px")}<input type="number" min="0.000001" step="any" value={barScaleUm} onChange={(event) => setBarScaleUm(Number(event.target.value))} /></label>}</> : <><label>{annotationKind === 'number' ? tx('编号') : tx('文字')} <input value={annotationText} maxLength={80} onChange={(event) => setAnnotationText(event.target.value)} /></label><label>{tx("字号 px")}<input type="number" min="8" max="96" value={annotationFont} onChange={(event) => setAnnotationFont(Number(event.target.value))} /></label></>}<label>{annotationKind === 'scale_bar' ? tx('图块内 X') : 'X'} <input type="number" min="0" value={annotationX} onChange={(event) => setAnnotationX(Number(event.target.value))} /></label><label>{annotationKind === 'scale_bar' ? tx('图块内 Y') : 'Y'} <input type="number" min="0" value={annotationY} onChange={(event) => setAnnotationY(Number(event.target.value))} /></label><label>{tx("颜色")}<input type="color" value={annotationColor} onChange={(event) => setAnnotationColor(event.target.value)} /></label><div className="iw-annotation-actions"><button type="button" onClick={addAnnotation}>{tx("添加标注")}</button><button type="button" onClick={() => void saveAnnotations([])} disabled={annotations.length === 0}>{tx("清空标注")}</button>{annotations.length > 0 && <><a href={`/api/image/results/${selectedResult.id}/annotations.svg`} download={`biofigure-annotations-${selectedResult.id.slice(0, 8)}.svg`}>{tx("下载 SVG（")}{annotations.length} {tx("项）")}</a><a href={`/api/image/results/${selectedResult.id}/annotations.json`} download={`biofigure-annotations-${selectedResult.id.slice(0, 8)}.json`}>{tx("下载参数 JSON")}</a></>}</div>{annotationKind === 'scale_bar' && <p className="iw-annotation-note">{tx("可使用所选图块已核验的 X 轴物理标定；缺少标定时请手动填写真实 µm/px。系统不从 DPI 推测科研尺度。")}</p>}</div>}
      </div>

      <div className="iw-batch">
        <div><h2>{tx("批量原像素网格")}</h2><p>{tx("按文件选择顺序分组；每组独立生成 TIFF，最终 ZIP 含逐组核验清单。批量输入使用独立的容量限额；上方交互资源仍限 8 张。")}</p></div>
        <label className="iw-file-picker">{batchUploading ? tx('正在导入…') : tx('选择批量图像')}<input type="file" multiple disabled={batchUploading} onChange={(event) => {
          setBatchFiles(Array.from(event.target.files ?? []))
          event.target.value = ''
        }} /></label>
        <div className="iw-batch-controls"><span>{batchFiles.length} {tx("张已选择")}</span><label>{tx("每组张数")}<input type="number" min="1" max="8" value={batchGroupSize} onChange={(event) => setBatchGroupSize(Math.max(1, Math.min(8, Number(event.target.value) || 1)))} /></label><label>{tx("列数")}<input type="number" min="1" max={batchGroupSize} value={Math.min(batchColumns, batchGroupSize)} onChange={(event) => setBatchColumns(Math.max(1, Math.min(batchGroupSize, Number(event.target.value) || 1)))} /></label><label>{tx("间距 px")}<input type="number" min="0" max="1000" value={batchGap} onChange={(event) => setBatchGap(Number(event.target.value))} /></label><button type="button" disabled={batchUploading || batchFiles.length === 0} onClick={() => void createBatch()}>{tx("开始批量拼版")}</button></div>
        {batchFiles.length > 0 && <p className="iw-batch-file-list">{batchFiles.slice(0, 12).map((file) => file.name).join(' · ')}{batchFiles.length > 12 ? tx(` · 等 ${batchFiles.length} 张`) : ''}</p>}
        {batchResults.length > 0 && <div className="iw-results-download"><h3>{tx("批量 ZIP 成品")}</h3>{batchResults.map((result) => <div key={result.id}><span>{result.proof.group_count} {tx("组 /")}{result.proof.source_count} {tx("张 · SHA-256")}{result.sha256.slice(0, 12)}…</span><a href={`/api/image/batch-results/${result.id}/file`} download={result.filename}>{tx("下载 ZIP")}</a><button type="button" onClick={() => void deleteBatchResult(result)}>{tx("移除")}</button></div>)}</div>}
      </div>

      <button type="button" aria-expanded={showCatalog} onClick={() => { setCatalogError(''); setShowCatalog((shown) => !shown) }}>{showCatalog ? tx('收起功能目录') : tx('浏览功能目录与接入进度')}</button>
      {showCatalog && !inventory && <p role="status">{tx(catalogError || '正在读取功能目录…')}</p>}
      {showCatalog && inventory && <>
      <div className="iw-counts" aria-label={tx("插件接入进度")}>
        {statusLabels.map(({ key, label }) => <div key={key}><strong>{counts[key] ?? 0}</strong><span>{tx(label)}</span></div>)}
      </div>

      <div className="iw-browser">
        <aside className="iw-categories" aria-label={tx("图像功能分类")}>
          <h2>{tx("功能分类")}<span>Categories</span></h2>
          <button className={category === 'all' ? 'active' : ''} onClick={() => setCategory('all')}>{tx("全部命令")}<span>{items.length}</span></button>
          {categories.map((entry) => <button key={entry.id} className={category === entry.id ? 'active' : ''} onClick={() => setCategory(entry.id)}>
            <span>{tx(entry.label)}{locale === 'zh-CN' && <small>{entry.en}</small>}</span><span>{categoryCounts[entry.id] ?? 0}</span>
          </button>)}
          {(categoryCounts.other ?? 0) > 0 && <button className={category === 'other' ? 'active' : ''} onClick={() => setCategory('other')}>{tx("待归类")}<span>{categoryCounts.other}</span></button>}
        </aside>

        <div className="iw-results">
          <div className="iw-search">
            <label htmlFor="iw-command-search">{tx("检索原命令、菜单或来源")}</label>
            <input id="iw-command-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search commands / menus" />
            <span>{filtered.length} {tx("项")}</span>
          </div>
          <div className="iw-command-layout">
            <div className="iw-command-list" aria-label={tx("命令清单")}>
              {visible.map((item) => <button key={item.id} className={selected?.id === item.id ? 'active' : ''} onClick={() => setSelectedId(item.id)}>
                <strong>{item.label}</strong><small>{item.menu_path || item.id}</small>
                <span>{item.status?.parity_verified ? tx('功能已核验') : item.status?.ui_adapted ? tx('界面已适配') : item.status?.runtime_verified ? tx('运行已验') : tx('盘点中')}</span>
              </button>)}
              {filtered.length > 250 && <p className="iw-empty">{tx("仅显示前 250 项；可用搜索和分类缩小范围，完整清单仍保存在本机。")}</p>}
              {!loading && filtered.length === 0 && <p className="iw-empty">{items.length === 0 ? tx('尚无已盘点的运行时命令。') : tx('没有符合当前筛选条件的命令。')}</p>}
            </div>
            <div className="iw-detail">
              {selected ? <>
                <span className="wf-overline">ORIGINAL COMMAND</span>
                <h2>{selected.label}</h2>
                <dl>
                  <div><dt>{tx("原命令 ID")}</dt><dd>{selected.original_identifier || tx('尚未记录')}</dd></div>
                  <div><dt>{tx("清单记录 ID")}</dt><dd>{selected.id}</dd></div>
                  <div><dt>{tx("原菜单位置")}</dt><dd>{selected.menu_path || tx('未记录')}</dd></div>
                  <div><dt>{tx("命令类型")}</dt><dd>{selected.kind || tx('未记录')}</dd></div>
                  <div><dt>{tx("来源")}</dt><dd>{selected.source || tx('未记录')}</dd></div>
                  <div><dt>{tx("参数")}</dt><dd>{Array.isArray(selected.parameters) ? tx(`${selected.parameters.length} 项已发现`) : tx('尚未盘点')}</dd></div>
                  {selected.adapter_scope && <div><dt>{tx("已接入范围")}</dt><dd>{selected.adapter_scope}</dd></div>}
                </dl>
                <div className="iw-checklist" aria-label={tx("命令核验状态")}>
                  {statusLabels.map(({ key, label }) => <span key={key} className={selected.status?.[key] ? 'done' : ''}>{selected.status?.[key] ? '✓' : '○'} {tx(label)}</span>)}
                </div>
                <p className="iw-detail-note">{tx("当前页面显示命令清单与核验状态。执行入口需在参数、交互和产物核验接通后逐项开放。")}</p>
              </> : <div className="iw-empty">{tx("选择命令后查看其来源和核验状态。")}</div>}
            </div>
          </div>
        </div>
      </div>
      </>}
    </section>
  )
}
