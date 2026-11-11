import { useRef, useState, type PointerEvent } from 'react'
import ImagePlaneCanvas from './ImagePlaneCanvas'

type Region = { x: number; y: number; width: number; height: number }
type Axis = { name: string; length: number }

export default function ImageSourcePlanePreview({ assetId, axes, bytes, bitDepth, indices, roi, roiKind, polygonPoints, useRoi, onRoiChange, onPointAdd }: {
  assetId: string
  axes: Axis[]
  bytes: number
  bitDepth: number | null | undefined
  indices: Record<string, number>
  roi: Region
  roiKind: 'rectangle' | 'ellipse' | 'polygon'
  polygonPoints: { x: number; y: number }[] | null
  useRoi: boolean
  onRoiChange: (next: Region) => void
  onPointAdd: (point: { x: number; y: number }) => void
}) {
  const width = axes.find((axis) => axis.name === 'X')?.length ?? 0
  const height = axes.find((axis) => axis.name === 'Y')?.length ?? 0
  const [draft, setDraft] = useState<Region | null>(null)
  const anchor = useRef<{ x: number; y: number } | null>(null)
  const pointerId = useRef<number | null>(null)

  function point(event: PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    return {
      x: Math.min(width - 1, Math.max(0, Math.floor((event.clientX - bounds.left) / bounds.width * width))),
      y: Math.min(height - 1, Math.max(0, Math.floor((event.clientY - bounds.top) / bounds.height * height))),
    }
  }

  function region(from: { x: number; y: number }, to: { x: number; y: number }): Region {
    return { x: Math.min(from.x, to.x), y: Math.min(from.y, to.y),
      width: Math.abs(to.x - from.x) + 1, height: Math.abs(to.y - from.y) + 1 }
  }

  const shown = draft ?? (useRoi ? roi : null)
  return <><ImagePlaneCanvas assetId={assetId} axes={axes} bytes={bytes} bitDepth={bitDepth} indices={indices}
    overlay={() => <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={roiKind === 'polygon' ? '点击添加多边形顶点' : `拖动选择${roiKind === 'ellipse' ? '椭圆' : '矩形'} ROI`}
        onPointerDown={(event) => {
          if (event.button !== 0 || !event.isPrimary) return
          if (roiKind === 'polygon') { onPointAdd(point(event)); return }
          anchor.current = point(event)
          pointerId.current = event.pointerId
          setDraft(region(anchor.current, anchor.current))
          event.currentTarget.setPointerCapture(event.pointerId)
        }}
        onPointerMove={(event) => { if (roiKind !== 'polygon' && anchor.current && pointerId.current === event.pointerId) setDraft(region(anchor.current, point(event))) }}
        onPointerUp={(event) => {
          if (!anchor.current || pointerId.current !== event.pointerId) return
          onRoiChange(region(anchor.current, point(event)))
          anchor.current = null
          pointerId.current = null
          setDraft(null)
        }}
        onPointerCancel={(event) => { if (pointerId.current === event.pointerId) { anchor.current = null; pointerId.current = null; setDraft(null) } }}>
        {useRoi && roiKind === 'polygon' && polygonPoints && polygonPoints.length >= 3 &&
          <polygon points={polygonPoints.map((item) => `${item.x},${item.y}`).join(' ')} />}
        {shown && roiKind !== 'polygon' && (roiKind === 'ellipse'
          ? <ellipse cx={shown.x + shown.width / 2} cy={shown.y + shown.height / 2}
            rx={shown.width / 2} ry={shown.height / 2} />
          : <rect x={shown.x} y={shown.y} width={shown.width} height={shown.height} />)}
      </svg>} />
    <p>{roiKind === 'polygon' ? '在图像上点击可追加顶点；也可编辑上方坐标。' : `在图像上拖动即可填写${roiKind === 'ellipse' ? '椭圆' : '矩形'} ROI。`}边框仅供定位，测量按原生 ImageJ 像素掩膜取样。</p>
  </>
}
