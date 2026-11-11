export const nativeAreaLabels: Record<string, string> = {
  rectangle: '亚像素矩形', oval: '亚像素椭圆', polygon: '原生多边形', freehand: '自由手面积',
  traced: '追踪区域', spline_polygon: '样条区域', rotated_rectangle: '旋转矩形',
  rotated_ellipse: '旋转椭圆', shape: '布尔组合',
}
export type AreaDraft = { fields: Record<string, string>; points: string;
  operation: string; operands: Record<string, unknown>[] }
export const defaultAreaDraft = (): AreaDraft => ({ fields: { x: '.5', y: '.5', width: '2.5', height: '2.5',
  x1: '1', y1: '1', x2: '3', y2: '2', rect_width: '1', aspect_ratio: '.5', evaluation_points: '32' },
  points: '1,1\n3,1\n2,2.5', operation: 'union', operands: [] })
export function nativeAreaFields(kind: string): string[] {
  if (['rectangle', 'oval'].includes(kind)) return ['x', 'y', 'width', 'height']
  if (kind.startsWith('rotated_')) return ['x1', 'y1', 'x2', 'y2', kind === 'rotated_rectangle' ? 'rect_width' : 'aspect_ratio']
  return kind === 'spline_polygon' ? ['evaluation_points'] : []
}
export function buildNativeArea(kind: string, draft: AreaDraft): Record<string, unknown> {
  if (!Object.hasOwn(nativeAreaLabels, kind)) throw new Error('未支持的原生面积类型。')
  const roi: Record<string, unknown> = { version: '1.0', kind }
  function number(text: string) {
    if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(text.trim()) || !Number.isFinite(Number(text)))
      throw new Error('所有几何参数须填写有限数值。')
    return Number(text)
  }
  if (kind === 'shape') {
    if (!['union', 'intersection', 'xor', 'subtract'].includes(draft.operation) || draft.operands.length < 2 || draft.operands.length > 8)
      throw new Error('布尔组合需要 2–8 个已加入的简单区域。')
    return { ...roi, operation: draft.operation, operands: structuredClone(draft.operands) }
  }
  for (const field of nativeAreaFields(kind)) roi[field] = number(draft.fields[field] ?? '')
  if (['rectangle', 'oval'].includes(kind) && (Number(roi.width) <= 0 || Number(roi.height) <= 0)) throw new Error('宽和高必须为正。')
  if (kind === 'rotated_rectangle' && Number(roi.rect_width) <= 0) throw new Error('旋转矩形宽度必须为正。')
  if (kind === 'rotated_ellipse' && !(Number(roi.aspect_ratio) > 0 && Number(roi.aspect_ratio) <= 1)) throw new Error('长短轴比须在 0–1 之间，且不为 0。')
  if (kind.startsWith('rotated_') && roi.x1 === roi.x2 && roi.y1 === roi.y2) throw new Error('中心轴两端点不能重合。')
  if (['polygon', 'freehand', 'traced', 'spline_polygon'].includes(kind)) {
    const lines = draft.points.trim().split(/\r?\n/)
    if (lines.length < 3 || lines.length > 64) throw new Error('面积路径需要 3–64 个顶点。')
    roi.points = lines.map((line) => {
      const parts = line.split(','); if (parts.length !== 2) throw new Error('顶点每行填写 x,y。')
      const [x, y] = parts.map(number)
      if (kind === 'traced' && (!Number.isInteger(x) || !Number.isInteger(y))) throw new Error('追踪区域节点必须为整数。')
      return { x, y }
    })
  }
  if (kind === 'spline_polygon' && (!Number.isInteger(roi.evaluation_points) || Number(roi.evaluation_points) < 8 || Number(roi.evaluation_points) > 512))
    throw new Error('样条拟合点数须为 8–512 整数。')
  return roi
}
