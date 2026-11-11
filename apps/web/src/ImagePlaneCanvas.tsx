import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import { useState, type ReactNode } from 'react'

type Axis = { name: string; length: number }
export default function ImagePlaneCanvas({ assetId, axes, bytes, bitDepth, indices, overlay }: {
  assetId: string; axes: Axis[]; bytes: number; bitDepth?: number | null
  indices: Record<string, number>; overlay: (width: number, height: number) => ReactNode
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const width = axes.find((axis) => axis.name === 'X')?.length ?? 0
  const height = axes.find((axis) => axis.name === 'Y')?.length ?? 0
  const planes = ['Channel', 'Z', 'Time'].map((name) => axes.find((axis) => axis.name === name))
  const invalid = planes.some((axis, offset) => axis && (!Number.isInteger(indices[['C', 'Z', 'T'][offset]])
    || indices[['C', 'Z', 'T'][offset]] < 0 || indices[['C', 'Z', 'T'][offset]] >= axis.length))
  const eligible = bitDepth === 16 && width > 0 && height > 0 && width * height <= 16_000_000
    && bytes <= 128 * 1024 * 1024 && planes.reduce((count, axis) => count * (axis?.length ?? 1), 1) <= 64
  const params = new URLSearchParams()
  for (const [axis, key] of [['Channel', 'c'], ['Z', 'z'], ['Time', 't']] as const)
    if (axes.some((entry) => entry.name === axis)) params.set(key, String(indices[key.toUpperCase()] ?? 0))
  const [attempt, setAttempt] = useState(0)
  const source = `/api/image/assets/${assetId}/plane-preview?${params.toString()}&attempt=${attempt}`
  const [loadedSource, setLoadedSource] = useState('')
  const [failedSource, setFailedSource] = useState('')
  if (!eligible) return <p className="iw-source-preview-note">{tx("此源图尚无受限平面预览，可继续使用坐标输入。当前支持至多 64 个 C/Z/T 组合平面、128 MiB 的 16 位灰度 TIFF。")}</p>
  if (invalid) return <p className="iw-source-preview-note">{tx("轴索引超出已检查的范围；修正后显示对应平面。")}</p>
  return <div className="iw-source-preview">
    <div className="iw-source-preview-head"><strong>{tx("所选平面预览")}</strong><span>{tx("仅供定位，按本平面有限值域映射显示；测量使用源像素值。")}</span></div>
    <div className="iw-source-preview-canvas" style={{ width: `min(100%, ${Math.min(720, Math.max(1, Math.floor(width * 520 / height)))}px)` }}>
      <img key={source} src={source} alt={tx("所选 Fiji 已检查平面预览")} draggable={false}
        onLoad={() => { setLoadedSource(source); setFailedSource('') }} onError={() => setFailedSource(source)} />
      {loadedSource === source && failedSource !== source && overlay(width, height)}
    </div>
    {failedSource === source && <p>{tx("无法生成当前平面预览，可继续使用坐标输入。")}<button type="button" onClick={() => setAttempt((count) => count + 1)}>{tx("重试预览")}</button></p>}
  </div>
}
