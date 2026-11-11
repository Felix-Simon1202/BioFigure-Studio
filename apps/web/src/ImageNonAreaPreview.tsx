import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import { useRef, useState, type PointerEvent } from 'react'
import ImagePlaneCanvas from './ImagePlaneCanvas'
import { parseNonAreaRoi } from './nonAreaRoi'
import type { NativeMeasureAsset } from './nativeMeasure'

type Point = { x: number; y: number }
export default function ImageNonAreaPreview({ asset, indices, kind, text, busy, onChange }: {
  asset: NativeMeasureAsset; indices: Record<string, number>; kind: string; text: string
  busy: boolean; onChange: (text: string) => void
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const [draft, setDraft] = useState<Point[] | null>(null)
  const anchor = useRef<{ point: Point; pointerId: number } | null>(null)
  const pointKind = ['point', 'multipoint'].includes(kind)
  const lines = text.trim() ? text.trim().split(/\r?\n/) : []
  const points: Point[] = [], positions: number[] = []
  let error = ''
  try {
    if (lines.length > 64) throw new Error('最多显示 64 个顶点。')
    for (const line of lines) {
      if (!pointKind && line.split(',').length !== 2) throw new Error('线和角的每行只填写 x,y。')
      const parsed = parseNonAreaRoi('point', line, '', asset.axes)
      points.push((parsed.points as Point[])[0]); positions.push((parsed.point_positions as number[])[0])
    }
  } catch (cause) { error = cause instanceof Error ? cause.message : '请修正顶点后使用预览。' }
  const maximum = kind === 'line' ? 2 : kind === 'angle' ? 3 : kind === 'point' ? 1 : 64
  const channels = asset.axes.find((axis) => axis.name === 'Channel')?.length ?? 1
  const slices = asset.axes.find((axis) => axis.name === 'Z')?.length ?? 1
  const current = 1 + (indices.C ?? 0) + channels * ((indices.Z ?? 0) + slices * (indices.T ?? 0))
  const visible = (draft ?? points).filter((_, index) => !pointKind || !positions[index] || positions[index] === current)
  const hidden = points.length - visible.length

  function sourcePoint(event: PointerEvent<SVGSVGElement>, width: number, height: number): Point {
    const bounds = event.currentTarget.getBoundingClientRect()
    return { x: Math.min(width * (1 - Number.EPSILON), Math.max(0, (event.clientX - bounds.left) * width / bounds.width)),
      y: Math.min(height * (1 - Number.EPSILON), Math.max(0, (event.clientY - bounds.top) * height / bounds.height)) }
  }
  function stop() { anchor.current = null; setDraft(null) }
  return <div className="iw-non-area-preview">
    <div className="iw-nm-actions"><button type="button" disabled={busy || !lines.length}
      onClick={() => { stop(); onChange(lines.slice(0, -1).join('\n')) }}>{tx("撤回末点")}</button>
      <button type="button" disabled={busy || !text} onClick={() => { stop(); onChange('') }}>{tx("清空顶点")}</button></div>
    <ImagePlaneCanvas assetId={asset.id} axes={asset.axes} bytes={asset.bytes} bitDepth={asset.bit_depth} indices={indices}
      overlay={(width, height) => <svg className="iw-native-geometry" role="img" aria-label={tx("在源图上编辑非面积区域")}
        viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
        onPointerDown={(event) => {
          if (busy || error || event.button !== 0 || !event.isPrimary) return
          const point = sourcePoint(event, width, height)
          if (kind === 'line') {
            anchor.current = { point, pointerId: event.pointerId }; setDraft([point, point]); event.currentTarget.setPointerCapture(event.pointerId)
          } else if (lines.length < maximum) onChange([...lines, `${point.x},${point.y}${pointKind ? ',0,0' : ''}`].join('\n'))
        }}
        onPointerMove={(event) => { if (anchor.current?.pointerId === event.pointerId && !busy) setDraft([anchor.current.point, sourcePoint(event, width, height)]) }}
        onPointerUp={(event) => {
          if (anchor.current?.pointerId !== event.pointerId) return
          if (!busy) {
            const end = sourcePoint(event, width, height)
            onChange(`${anchor.current.point.x},${anchor.current.point.y}\n${end.x},${end.y}`)
          }
          stop()
        }} onPointerCancel={(event) => { if (anchor.current?.pointerId === event.pointerId) stop() }}>
        {!error && <>
          {!pointKind && visible.length > 1 && <polyline points={visible.map(({ x, y }) => `${x},${y}`).join(' ')} />}
          {visible.map(({ x, y }, index) => <circle key={index} cx={x} cy={y} r={Math.max(width, height) / 110} />)}
        </>}
      </svg>} />
    <p>{kind === 'line' ? tx('在图像上拖动定义两端点，重新拖动替换直线。') : tx(`在图像上点击依次添加顶点（最多 ${maximum} 点）；可撤回末点或清空后重画。`)}
      {tx("顶点同时写入精确坐标输入。轮廓仅用于定位，自由线的实际插值和线宽取样由 Fiji 执行。")}</p>
    {pointKind && hidden > 0 && <p>{hidden} {tx("个点绑定其它线性平面，此处不显示；切换对应 C/Z/T 可查看。")}</p>}
    {error && <p role="status">{tx("请先修正坐标或清空顶点：")}{tx(error)}</p>}
  </div>
}
