import { nativeAreaFields, nativeAreaLabels } from './nativeArea'
import { nonAreaLabels } from './nonAreaRoi'
import type { NativeMeasurementDraft } from './nativeMeasurementDraft'

export type ImportedRoiItem = { name: string; indices: Record<string, number>; roi: Record<string, unknown> }
export type RoiFileResult = { operation: string; source: { sha256: string; bytes: number }
  file_base64?: string; filename?: string; bytes?: number
  collection?: { items: ImportedRoiItem[] } }

export function currentRoiForFile(roi: Record<string, unknown> | null) {
  if (!roi || roi.kind === 'full') return null
  if (roi.version === '1.0') return roi
  return { ...roi, version: '1.0', kind: roi.kind === 'ellipse' ? 'oval' : roi.kind }
}

export function draftFromImportedRoi(draft: NativeMeasurementDraft, roi: Record<string, unknown>): NativeMeasurementDraft {
  const kind = String(roi.kind)
  if (kind === 'shape') return { ...draft, roiKind: kind, areaDraft: { ...draft.areaDraft,
    operation: String(roi.operation), operands: structuredClone(roi.operands as Record<string, unknown>[]) } }
  if (kind === 'shape_path') return { ...draft, roiKind: 'imported', importedRoi: structuredClone(roi) }
  if (!Object.hasOwn(nativeAreaLabels, kind) && !Object.hasOwn(nonAreaLabels, kind))
    throw new Error('这个区域类型尚无编辑入口。')
  const next = { ...draft, roiKind: kind }
  const points = roi.points as { x: number; y: number }[] | undefined
  if (Object.hasOwn(nativeAreaLabels, kind)) {
    next.areaDraft = { ...draft.areaDraft, fields: { ...draft.areaDraft.fields } }
    for (const key of nativeAreaFields(kind)) next.areaDraft.fields[key] = String(roi[key])
    if (points) next.areaDraft.points = points.map(({ x, y }) => `${x},${y}`).join('\n')
  } else {
    if (!points) throw new Error('导入结果缺少区域顶点。')
    const positions = roi.point_positions as number[] | undefined
    const counters = roi.point_counters as number[] | undefined
    const pointKind = kind === 'point' || kind === 'multipoint'
    next.pointText = points.map(({ x, y }, index) => `${x},${y}${pointKind ? `,${positions?.[index] ?? 0},${counters?.[index] ?? 0}` : ''}`).join('\n')
    if (roi.stroke_width !== undefined) next.strokeWidth = String(roi.stroke_width)
  }
  return next
}
