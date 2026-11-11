import { useState } from 'react'

export type AnalysisJob = { id: string; asset_id: string; operation: string; state: string;
  created_at?: number; error: string | null; result: unknown }

// Observation belongs to the workspace poller; each panel only submits commands.
export function useImageAnalysisJob(assetId: string, operation: string, endpoint: string,
  jobs: AnalysisJob[], onSubmitted: (job: AnalysisJob) => void) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const job = jobs.filter((item) => item.asset_id === assetId && item.operation === operation)
    .sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0))[0]
  const running = Boolean(job && ['queued', 'running'].includes(job.state))

  async function send(url: string, body?: unknown) {
    const response = await fetch(url, { method: 'POST',
      ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) })
    const payload = await response.json() as AnalysisJob & { detail?: unknown }
    if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : '图像任务请求失败。')
    onSubmitted(payload)
  }
  async function submit(request: unknown) {
    if (submitting || running) return
    setSubmitting(true); setError('')
    try { await send(`/api/image/assets/${assetId}/${endpoint}`, request) }
    catch (cause) { setError(cause instanceof Error ? cause.message : '图像任务提交失败。') }
    finally { setSubmitting(false) }
  }
  async function cancel() {
    if (!job || !running) return
    try { await send(`/api/image/jobs/${job.id}/cancel`) }
    catch (cause) { setError(cause instanceof Error ? cause.message : '取消请求失败。') }
  }
  return { job, running, busy: submitting || running, error: error || job?.error, submit, cancel }
}
