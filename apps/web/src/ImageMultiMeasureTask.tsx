import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import ImageMultiMeasure from './ImageMultiMeasure'
import type { MultiMeasureCollection, MultiMeasureResult } from './multiMeasure'

import { useImageAnalysisJob, type AnalysisJob as Job } from './useImageAnalysisJob'

export default function ImageMultiMeasureTask({ assetId, collection, currentPlane, jobs, validPlane, onSubmitted }: {
  assetId: string; collection: MultiMeasureCollection; currentPlane: Record<string, number>
  jobs: Job[]; validPlane: boolean; onSubmitted: (job: Job) => void
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const { job, running, busy, error, submit, cancel } = useImageAnalysisJob(
    assetId, 'native_multi_measure', 'multi-measure', jobs, onSubmitted)

  return <>
    {job && <p role="status">Multi Measure：{job.state === 'queued' ? tx('排队中') : running ? tx('运行中')
      : job.state === 'succeeded' ? tx('已完成') : job.state === 'cancelled' ? tx('已取消') : tx('失败')}</p>}
    <ImageMultiMeasure collection={collection} currentPlane={currentPlane}
      busy={busy} error={error}
      disabledReason={!validPlane ? tx('请先修正当前 C/Z/T 轴索引。') : undefined}
      result={job?.state === 'succeeded' ? job.result as MultiMeasureResult : null}
      onSubmit={submit} onCancel={cancel} />
  </>
}
