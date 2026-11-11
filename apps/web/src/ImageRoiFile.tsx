import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import { useState } from 'react'
import type { NativeMeasureAsset } from './nativeMeasure'
import { useImageAnalysisJob, type AnalysisJob } from './useImageAnalysisJob'
import { currentRoiForFile, type ImportedRoiItem, type RoiFileResult } from './roiFile'
import { downloadFile } from './downloadFile'

export default function ImageRoiFile({ asset, indices, roi, valid, busy, jobs, onSubmitted, onUse }: {
  asset: NativeMeasureAsset; indices: Record<string, number>; roi: Record<string, unknown> | null
  valid: boolean; busy: boolean; jobs: AnalysisJob[]; onSubmitted: (job: AnalysisJob) => void
  onUse: (item: ImportedRoiItem) => void
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const task = useImageAnalysisJob(asset.id, 'native_roi_exchange', 'roi-exchange', jobs, onSubmitted)
  const [error, setError] = useState('')
  const locked = busy || task.busy
  const result = task.job?.state === 'succeeded' ? task.job.result as RoiFileResult : null
  const current = result?.source.sha256 === asset.sha256 && result.source.bytes === asset.bytes ? result : null
  const imported = current?.operation === 'import_roi' ? current.collection?.items[0] : null
  const nativeRoi = currentRoiForFile(roi)
  async function importFile(file: File) {
    setError('')
    if (!file.name.toLowerCase().endsWith('.roi') || file.size < 64 || file.size > 32768) {
      setError('请选择不超过 32 KiB 的单个 .roi 区域文件。'); return
    }
    try {
      const bytes = new Uint8Array(await file.arrayBuffer())
      await task.submit({ version: '2.0', operation: 'import_roi', file_base64: btoa(String.fromCharCode(...bytes)) })
    } catch (cause) { setError(cause instanceof Error ? cause.message : '无法读取区域文件。') }
  }
  function download() {
    try {
      if (!current?.file_base64 || current.file_base64.length > 44000) throw new Error('区域文件内容无效。')
      const bytes = Uint8Array.from(atob(current.file_base64), (char) => char.charCodeAt(0))
      if (bytes.length !== current.bytes || bytes.length > 32768) throw new Error('区域文件长度不一致。')
      downloadFile('biofigure-region.roi', bytes, 'application/octet-stream')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '无法下载区域文件。') }
  }
  return <div className="iw-roi-file">
    <div className="iw-nm-actions">
      <button type="button" disabled={locked || !valid || !nativeRoi} onClick={() => {
        setError('')
        void task.submit({ version: '2.0', operation: 'export_roi', collection: {
          version: '2.0', source: { sha256: asset.sha256, bytes: asset.bytes, axes: asset.axes },
          items: [{ id: crypto.randomUUID().replaceAll('-', ''), name: 'Current region', indices, roi: nativeRoi }],
        } })
      }}>{tx("保存当前 ROI 文件")}</button>
      <label className="iw-file-picker">{tx("导入 ROI 文件")}<input type="file" accept=".roi" disabled={locked}
        onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; if (file) void importFile(file) }} /></label>
      {task.busy && <button type="button" onClick={() => void task.cancel()}>{tx("取消区域文件任务")}</button>}
      {current?.operation === 'export_roi' && <button type="button" disabled={locked} onClick={download}>{tx("下载 ROI 文件")}</button>}
      {imported && <button type="button" disabled={locked} onClick={() => {
        try { onUse(imported); setError('') }
        catch (cause) { setError(cause instanceof Error ? cause.message : '无法应用区域。') }
      }}>{tx("使用导入的区域")}</button>}
    </div>
    {task.busy && <p role="status">{tx("区域文件正在本机处理…")}</p>}
    {!nativeRoi && <p>{tx("先选择或绘制一个区域，再保存 ROI 文件。")}</p>}
    {nativeRoi?.kind === 'spline_polygon' && <p>{tx("ROI 格式会按 ImageJ 默认方式重新拟合样条；无法保持原曲线时会拒绝保存。")}</p>}
    {imported && <p>{tx("已读取")}{imported.name}{tx("。应用后会切到文件保存的平面；外部 ROI 文件不证明原图来源，请确认适合当前图像。")}</p>}
    {(error || task.error) && <p role="alert">{tx(error || task.error || '')}</p>}
  </div>
}
