import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'
import type { NativeMeasurementDraft } from './nativeMeasurementDraft'
import ImageNativeMeasurements from './ImageNativeMeasurements'
import ImageRoiFile from './ImageRoiFile'
import { draftFromImportedRoi } from './roiFile'
import type { NativeMeasureAsset, NativeMeasureResult } from './nativeMeasure'
import { useImageAnalysisJob, type AnalysisJob } from './useImageAnalysisJob'

export default function ImageNativeMeasureTask({ asset, availableAssets, indices, roi, validSelection, validPlane, jobs, draft, onDraftChange, onPlaneChange, onSubmitted }: {
  draft: NativeMeasurementDraft; onDraftChange: Dispatch<SetStateAction<NativeMeasurementDraft>>
  asset: NativeMeasureAsset; availableAssets: NativeMeasureAsset[]; indices: Record<string, number>
  roi: Record<string, unknown> | null; validSelection: boolean; validPlane: boolean; jobs: AnalysisJob[]
  onPlaneChange: (indices: Record<string, number>) => void
  onSubmitted: (job: AnalysisJob) => void
}) {
  const [capability, setCapability] = useState<unknown>(null)
  const [capabilityError, setCapabilityError] = useState('')
  const task = useImageAnalysisJob(asset.id, 'native_set_measurements', 'native-measure', jobs, onSubmitted)
  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/image/measurement-settings', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error('无法读取本机测量设置。')
      const payload: unknown = await response.json()
      if (!controller.signal.aborted) setCapability(payload)
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setCapabilityError(cause instanceof Error ? cause.message : '无法读取本机测量设置。')
    })
    return () => controller.abort()
  }, [])
  return <>
    {task.job && <p role="status">原生测量：{task.job.state === 'queued' ? '排队中' : task.running ? '运行中'
      : task.job.state === 'succeeded' ? '已完成' : task.job.state === 'cancelled' ? '已取消' : '失败'}</p>}
    <ImageNativeMeasurements draft={draft} onDraftChange={onDraftChange} capability={capability} asset={asset} availableAssets={availableAssets}
      indices={indices} roi={roi} busy={task.busy} disabledReason={!validPlane ? '请先修正当前 C/Z/T 轴索引。' : undefined}
      areaDisabledReason={!validSelection ? '请先修正工作台当前面积区域。' : undefined}
      error={capabilityError || task.error} result={task.job?.state === 'succeeded' ? task.job.result as NativeMeasureResult : null}
      renderRoiFiles={(selectedRoi, valid) => <ImageRoiFile asset={asset} indices={indices} roi={selectedRoi}
        valid={valid} busy={task.busy} jobs={jobs} onSubmitted={onSubmitted} onUse={(item) => {
          const next = draftFromImportedRoi(draft, item.roi)
          onDraftChange(next)
          onPlaneChange({ C: item.indices.C ?? 0, Z: item.indices.Z ?? 0, T: item.indices.T ?? 0 })
        }} />}
      onSubmit={task.submit} onCancel={task.cancel} />
  </>
}
