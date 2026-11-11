import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import { useEffect, useRef, useState, type ChangeEvent } from 'react'

type Point = { x: number; y: number }
type Region = { kind?: 'rectangle' | 'ellipse' | 'polygon' | 'full'; x?: number; y?: number; width?: number; height?: number; points?: Point[] }
type Axis = { name: string; length: number; unit: string | null; scale: number | null }
type Source = { sha256: string; bytes: number; axes: Axis[] }
export type RoiCollectionItem = { id: string; name: string; indices: Record<string, number>; roi: Region }
type Item = RoiCollectionItem
type Document = { version: '1.0'; source: Source; items: Item[] }
type MeasureValues = { area: number; area_unit: string; mean: number; min: number; max: number;
  std_dev?: number; median?: number; mode?: number; integrated_density?: number; raw_integrated_density?: number }
type MeasureRow = Item & { sample_count: number; imagej1_analyzer: MeasureValues }
type MeasureResult = { source: Source; rows: MeasureRow[]; extra_measurements: string[];
  method: string; roi_manager_multi_measure_equivalent: false }
type MeasureJob = { id: string; state: string; result: MeasureResult | null; error: string | null }
const measurementOptions = [
  ['std_dev', '标准差'], ['median', '中位数'], ['mode', '众数灰度值'], ['integrated_density', '积分密度'],
] as const

function download(name: string, body: BlobPart, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function csvCell(value: unknown) {
  const text = typeof value === 'string' ? value : value == null ? '' : String(value)
  const safe = typeof value === 'string' && /^\s*[=+@-]/.test(text) ? `'${text}` : text
  return `"${safe.replaceAll('"', '""')}"`
}

export default function ImageRoiCollection({ assetId, indices, roi, initialItems, onItemsChange, onSelect }: {
  assetId: string
  indices: Record<string, number>
  roi: Region | null
  initialItems: Item[]
  onItemsChange: (items: Item[]) => void
  onSelect: (item: Item) => void
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const measureRequest = useRef<AbortController | null>(null)
  useEffect(() => () => measureRequest.current?.abort(), [])
  const [source, setSource] = useState<Source | null>(null)
  const [items, setItems] = useState<Item[]>(initialItems)
  const [selectedId, setSelectedId] = useState('')
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [sourceAttempt, setSourceAttempt] = useState(0)
  const [sourceLoading, setSourceLoading] = useState(true)
  const [measureExtras, setMeasureExtras] = useState<string[]>([])
  const [measureJobId, setMeasureJobId] = useState('')
  const [measureResult, setMeasureResult] = useState<MeasureResult | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void fetch(`/api/image/assets/${assetId}/roi-collection/source`, { signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json() as Source & { detail?: string }
        if (!response.ok) throw new Error(payload.detail || '无法核对源图。')
        setSource(payload)
      }).catch((error: unknown) => { if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : '无法核对源图。') })
      .finally(() => { if (!controller.signal.aborted) setSourceLoading(false) })
    return () => controller.abort()
  }, [assetId, sourceAttempt])

  async function verify(next: Item[], importedSource = source): Promise<Document> {
    if (!importedSource) throw new Error('源图摘要尚未核对。')
    const response = await fetch(`/api/image/assets/${assetId}/roi-collection/validate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: '1.0', source: importedSource, items: next }),
    })
    const payload = await response.json() as Document & { detail?: string }
    if (!response.ok) throw new Error(payload.detail || 'ROI 集合校验失败。')
    return payload
  }

  async function apply(next: Item[], notice: string) {
    setBusy(true)
    try {
      const checked = await verify(next)
      setItems(checked.items)
      onItemsChange(checked.items)
      setMeasureResult(null)
      setMessage(notice)
    } catch (error) { setMessage(error instanceof Error ? error.message : 'ROI 操作失败。') }
    finally { setBusy(false) }
  }

  async function add() {
    if (!roi) { setMessage('请先启用并编辑 ROI。'); return }
    const label = name.trim()
    if (!label) { setMessage('请先填写 ROI 名称。'); return }
    const item: Item = { id: crypto.randomUUID().replaceAll('-', ''), name: label, indices, roi }
    await apply([...items, item], `已加入「${label}」。`)
  }

  async function rename() {
    const label = name.trim()
    if (!selectedId || !label) { setMessage('请先选择 ROI 并填写名称。'); return }
    await apply(items.map((item) => item.id === selectedId ? { ...item, name: label } : item), `已重命名为「${label}」。`)
  }

  async function remove() {
    if (!selectedId) return
    await apply(items.filter((item) => item.id !== selectedId), '已移除所选 ROI。')
    setSelectedId('')
  }

  async function save() {
    setBusy(true)
    try {
      const checked = await verify(items)
      const blob = new Blob([JSON.stringify(checked, null, 2) + '\n'], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `biofigure-rois-${checked.source.sha256.slice(0, 12)}.json`
      document.body.append(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMessage(`已保存 ${checked.items.length} 个 ROI 的本机集合文件。`)
    } catch (error) { setMessage(error instanceof Error ? error.message : '保存失败。') }
    finally { setBusy(false) }
  }

  async function load(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 128 * 1024) { setMessage('ROI 集合文件超过 128 KiB。'); return }
    setBusy(true)
    try {
      const parsed = JSON.parse(await file.text()) as Document
      if (!parsed || !parsed.source || !Array.isArray(parsed.items)) throw new Error('ROI 集合缺少来源或项目。')
      const checked = await verify(parsed.items, parsed.source)
      setItems(checked.items)
      onItemsChange(checked.items)
      setMeasureResult(null)
      setSelectedId('')
      setMessage(`已重开 ${checked.items.length} 个 ROI；源图摘要与轴信息匹配。`)
    } catch (error) { setMessage(error instanceof Error ? error.message : 'ROI 集合文件无效。') }
    finally { setBusy(false) }
  }

  async function exportNative() {
    setBusy(true)
    try {
      const checked = await verify(items)
      const response = await fetch(`/api/image/assets/${assetId}/roi-collection/native-export`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(checked),
      })
      const payload = await response.json() as { archive_base64?: string; count?: number; detail?: string }
      if (!response.ok || !payload.archive_base64) throw new Error(payload.detail || '原生 ROI ZIP 导出失败。')
      const binary = atob(payload.archive_base64)
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0))
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `biofigure-rois-${checked.source.sha256.slice(0, 12)}.zip`
      document.body.append(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setMessage(`已导出 ${payload.count ?? checked.items.length} 个 ImageJ ROI；ZIP 附有源图摘要。`)
    } catch (error) { setMessage(error instanceof Error ? error.message : '原生 ROI ZIP 导出失败。') }
    finally { setBusy(false) }
  }

  async function importNative(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 512 * 1024) { setMessage('原生 ROI ZIP 超过 512 KiB。'); return }
    setBusy(true)
    try {
      const bytes = new Uint8Array(await file.arrayBuffer())
      let binary = ''
      for (let offset = 0; offset < bytes.length; offset += 8192)
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192))
      const response = await fetch(`/api/image/assets/${assetId}/roi-collection/native-import`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archive_base64: btoa(binary) }),
      })
      const payload = await response.json() as { document?: Document; source_bound?: boolean; detail?: string }
      if (!response.ok || !payload.document) throw new Error(payload.detail || '原生 ROI ZIP 导入失败。')
      setItems(payload.document.items)
      onItemsChange(payload.document.items)
      setMeasureResult(null)
      setSelectedId('')
      setMessage(payload.source_bound
        ? `已导入 ${payload.document.items.length} 个 ImageJ ROI；源图摘要与轴信息匹配。`
        : `已导入 ${payload.document.items.length} 个 ImageJ ROI；此 ZIP 无源图摘要，已按当前图像校验形状与 C/Z/T 位置。`)
    } catch (error) { setMessage(error instanceof Error ? error.message : '原生 ROI ZIP 导入失败。') }
    finally { setBusy(false) }
  }

  async function measureCollection() {
    setBusy(true)
    setMeasureResult(null)
    const controller = new AbortController()
    measureRequest.current = controller
    try {
      const checked = await verify(items)
      if (controller.signal.aborted) return
      const response = await fetch(`/api/image/assets/${assetId}/roi-collection/measure`, {
        signal: controller.signal,
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collection: checked, extra_measurements: measureExtras }),
      })
      let job = await response.json() as MeasureJob & { detail?: string }
      if (!response.ok) throw new Error(job.detail || '集合测量提交失败。')
      setMeasureJobId(job.id)
      setMessage(`已提交 ${checked.items.length} 个 ROI 的逐项测量。`)
      while (!controller.signal.aborted && ['queued', 'running'].includes(job.state)) {
        await new Promise((resolve) => setTimeout(resolve, 800))
        const progress = await fetch(`/api/image/jobs/${job.id}`, { signal: controller.signal })
        job = await progress.json() as MeasureJob & { detail?: string }
        if (!progress.ok) throw new Error(job.detail || '无法读取集合测量状态。')
      }
      if (job.state !== 'succeeded' || !job.result) throw new Error(job.error || `集合测量${job.state === 'cancelled' ? '已取消' : '未完成'}。`)
      setMeasureResult(job.result)
      setMessage(`已完成 ${job.result.rows.length} 个 ROI 的原生 ImageJ1 Analyzer 逐项测量。`)
    } catch (error) {
      if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : '集合测量失败。')
    } finally {
      if (!controller.signal.aborted) { setBusy(false); setMeasureJobId('') }
      if (measureRequest.current === controller) measureRequest.current = null
    }
  }

  async function cancelMeasure() {
    if (!measureJobId) return
    try {
      const response = await fetch(`/api/image/jobs/${measureJobId}/cancel`, { method: 'POST' })
      if (!response.ok) throw new Error('无法取消集合测量，请等待任务结束。')
      setMessage('已请求取消集合测量；正在等待本机任务结束。')
    } catch (error) { setMessage(error instanceof Error ? error.message : '无法取消集合测量。') }
  }

  function saveMeasurements(format: 'json' | 'csv') {
    if (!measureResult) return
    const prefix = `biofigure-roi-measure-${measureResult.source.sha256.slice(0, 12)}`
    if (format === 'json') {
      download(`${prefix}.json`, JSON.stringify({ version: '1.0', ...measureResult }, null, 2) + '\n', 'application/json')
      return
    }
    const columns = ['source_sha256', 'id', 'name', 'C', 'Z', 'T', 'kind', 'roi_json', 'sample_count',
      'area', 'area_unit', 'mean', 'min', 'max', 'std_dev', 'median', 'mode',
      'integrated_density', 'raw_integrated_density']
    const rows = measureResult.rows.map((row) => {
      const values = row.imagej1_analyzer
      return [measureResult.source.sha256, row.id, row.name, row.indices.C ?? '', row.indices.Z ?? '',
        row.indices.T ?? '', row.roi.kind, JSON.stringify(row.roi), row.sample_count, values.area,
        values.area_unit, values.mean, values.min, values.max, values.std_dev, values.median,
        values.mode, values.integrated_density, values.raw_integrated_density].map(csvCell).join(',')
    })
    download(`${prefix}.csv`, '\ufeff' + [columns.join(','), ...rows].join('\r\n') + '\r\n', 'text/csv;charset=utf-8')
  }

  return <div className="iw-roi-collection">
{!source && <button type="button" disabled={sourceLoading}
      onClick={() => { setSourceLoading(true); setSourceAttempt((attempt) => attempt + 1) }}>{sourceLoading ? tx('正在核验源图…') : tx('重新核验源图')}</button>}
<div><strong>{tx("命名 ROI 集合")}</strong><p>{tx("每项保留形状与 C/Z/T 位置；可保存本机 JSON，或与 ImageJ ROI Manager 交换 ZIP。")}</p></div>

    <div className="iw-roi-actions">
      <label>{tx("名称")}<input value={name} maxLength={80} onChange={(event) => setName(event.target.value)} /></label>
      <button type="button" disabled={busy || !source || !roi || items.length >= 64} onClick={() => void add()}>{tx("加入当前 ROI")}</button>
      <button type="button" disabled={busy || !selectedId} onClick={() => void rename()}>{tx("重命名")}</button>
      <button type="button" disabled={busy || !selectedId} onClick={() => void remove()}>{tx("移除")}</button>
      <button type="button" disabled={busy || !source} onClick={() => void save()}>{tx("保存集合 JSON")}</button>
      <label className="iw-file-picker">{tx("重新载入集合")}<input type="file" accept="application/json,.json" disabled={busy || !source}
        onChange={(event) => void load(event)} /></label>
      <button type="button" disabled={busy || !source || items.length === 0} onClick={() => void exportNative()}>{tx("导出 ImageJ ROI ZIP")}</button>
      <label className="iw-file-picker">{tx("导入 ImageJ ROI ZIP")}<input type="file" accept="application/zip,.zip" disabled={busy || !source}
        onChange={(event) => void importNative(event)} /></label>
    </div>
    <div className="iw-roi-actions">
      {measurementOptions.map(([key, label]) => <label key={key}><input type="checkbox" checked={measureExtras.includes(key)}
        disabled={busy} onChange={(event) => setMeasureExtras((current) => event.target.checked
          ? [...current, key] : current.filter((value) => value !== key))} />{tx(label)}</label>)}
      <button type="button" disabled={busy || !source || items.length === 0} onClick={() => void measureCollection()}>{tx("按集合逐 ROI 测量")}</button>
      {measureJobId && <button type="button" onClick={() => void cancelMeasure()}>{tx("取消测量")}</button>}
    </div>
    <p>{tx("逐条在保存的 C/Z/T 平面用原生 ImageJ1 Analyzer 测量；与 ROI Manager 的跨切片 Multi Measure 表格不同。")}</p>
    {items.length > 0 && <ul>{items.map((item) => <li key={item.id}>
      <button type="button" className={selectedId === item.id ? 'active' : ''} onClick={() => {
        setSelectedId(item.id); setName(item.name); onSelect(item)
      }}>{item.name} · {item.roi.kind === 'ellipse' ? tx('椭圆') : item.roi.kind === 'polygon' ? tx('多边形') : item.roi.kind === 'full' ? tx('全平面') : tx('矩形')} · {JSON.stringify(item.indices)}</button>
    </li>)}</ul>}
    {measureResult && <div className="iw-roi-measure-results">
      <strong>{tx("逐 ROI 测量结果")}</strong>
      <div className="iw-roi-actions"><button type="button" onClick={() => saveMeasurements('json')}>{tx("下载结果 JSON")}</button>
        <button type="button" onClick={() => saveMeasurements('csv')}>{tx("下载结果 CSV")}</button></div>
      <div style={{ overflowX: 'auto' }}><table><thead><tr><th>{tx("名称")}</th><th>C/Z/T</th><th>{tx("形状")}</th><th>{tx("像素数")}</th>
        <th>{tx("面积")}</th><th>{tx("均值")}</th><th>{tx("最小")}</th><th>{tx("最大")}</th><th>{tx("标准差")}</th><th>{tx("中位数")}</th><th>{tx("众数")}</th><th>IntDen</th><th>RawIntDen</th>
      </tr></thead><tbody>{measureResult.rows.map((row) => { const values = row.imagej1_analyzer; return <tr key={row.id}>
        <td>{row.name}</td><td>{JSON.stringify(row.indices)}</td><td>{row.roi.kind}</td><td>{row.sample_count}</td>
        <td>{values.area} {values.area_unit}</td><td>{values.mean}</td><td>{values.min}</td><td>{values.max}</td>
        <td>{values.std_dev ?? '—'}</td><td>{values.median ?? '—'}</td><td>{values.mode ?? '—'}</td>
        <td>{values.integrated_density ?? '—'}</td><td>{values.raw_integrated_density ?? '—'}</td>
      </tr> })}</tbody></table></div>
    </div>}
    {message && <p role="status">{tx(message)}</p>}
  </div>
}
