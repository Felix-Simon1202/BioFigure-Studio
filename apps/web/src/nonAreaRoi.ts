export const nonAreaLabels: Record<string, string> = {
  line: '直线', polyline: '折线', freeline: '自由线', angle: '角度', point: '单点', multipoint: '多点',
}

// Parse explicit source-pixel coordinates; never infer geometry from a scaled preview.
export function parseNonAreaRoi(kind: string, text: string, strokeText: string,
  axes: { name: string; length: number }[]): Record<string, unknown> {
  if (!Object.hasOwn(nonAreaLabels, kind)) throw new Error('请选择已支持的原生区域类型。')
  const width = axes.find((axis) => axis.name === 'X')?.length ?? 0
  const height = axes.find((axis) => axis.name === 'Y')?.length ?? 0
  const planes = axes.filter((axis) => ['Channel', 'Z', 'Time'].includes(axis.name))
    .reduce((count, axis) => count * axis.length, 1)
  if (!width || !height || planes > 64) throw new Error('需要已检查的 X/Y 尺寸，且线性平面不超过 64。')
  const pointKind = kind === 'point' || kind === 'multipoint'
  const lineKind = ['line', 'polyline', 'freeline'].includes(kind)
  const lines = text.trim().split(/\r?\n/)
  const min = kind === 'point' ? 1 : kind === 'angle' ? 3 : 2
  const max = kind === 'point' ? 1 : kind === 'angle' ? 3 : kind === 'line' ? 2 : 64
  if (lines.length < min || lines.length > max) throw new Error(`该类型需要 ${min === max ? min : `${min}–${max}`} 个点。`)
  const numeric = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i
  const positions: number[] = [], counters: number[] = []
  const points = lines.map((line, index) => {
    const parts = line.split(',').map((part) => part.trim())
    if (!(parts.length === 2 || (pointKind && parts.length === 4))
      || parts.some((part) => !numeric.test(part) || !Number.isFinite(Number(part))))
      throw new Error(`第 ${index + 1} 行格式无效；填写 x,y${pointKind ? ' 或 x,y,位置,计数器编号' : ''}。`)
    const [x, y, position = 0, counter = 0] = parts.map(Number)
    if (x < 0 || y < 0 || x >= width || y >= height) throw new Error(`第 ${index + 1} 行坐标超出源图范围。`)
    if (pointKind && (!Number.isInteger(position) || position < 0 || position > planes
      || !Number.isInteger(counter) || counter < 0 || counter > 99))
      throw new Error(`第 ${index + 1} 行位置须为 0–${planes} 整数，计数器编号须为 0–99 整数。`)
    positions.push(position); counters.push(counter)
    return { x, y }
  })
  if (lineKind || kind === 'angle') {
    const lengths = points.slice(1).map((point, index) => Math.hypot(point.x - points[index].x, point.y - points[index].y))
    if (!lengths.some((length) => length > 0) || (kind === 'angle' && lengths.some((length) => length === 0)))
      throw new Error('线不能为零长度；角度的相邻顶点必须不同。')
  }
  const padding = lineKind ? 32 : 1
  const spanX = Math.max(...points.map((p) => p.x)) - Math.min(...points.map((p) => p.x))
  const spanY = Math.max(...points.map((p) => p.y)) - Math.min(...points.map((p) => p.y))
  if ((spanX + padding) * (spanY + padding) > 1_000_000) throw new Error('区域包围范围超过 100 万候选像素。')
  const roi: Record<string, unknown> = { version: '1.0', kind, points }
  if (lineKind) {
    if (!numeric.test(strokeText.trim()) || !Number.isFinite(Number(strokeText)) || Number(strokeText) < 1 || Number(strokeText) > 32)
      throw new Error('线宽须为 1–32 的有限像素数。')
    roi.stroke_width = Number(strokeText)
  }
  if (pointKind) { roi.point_positions = positions; roi.point_counters = counters }
  return roi
}
