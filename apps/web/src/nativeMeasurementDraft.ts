import type { Dispatch, SetStateAction } from 'react'
import { buildNativeArea, defaultAreaDraft, nativeAreaLabels, type AreaDraft } from './nativeArea'
import { parseNonAreaRoi } from './nonAreaRoi'
import type { NativeMeasureAsset, NativeMeasureRequest } from './nativeMeasure'
export type NativeMeasurementDraft = {
  importedRoi?: Record<string, unknown>
  selected: string[]; decimalPlaces: number; thresholdEnabled: boolean; thresholdMin: string; thresholdMax: string
  redirectId: string; redirectIndices: Record<string, string>; roiKind: string; pointText: string; strokeWidth: string; areaDraft: AreaDraft
}
export const defaultNativeMeasurementDraft = (): NativeMeasurementDraft => ({
  selected: [], decimalPlaces: 3, thresholdEnabled: false, thresholdMin: '', thresholdMax: '',
  redirectId: '', redirectIndices: {}, roiKind: 'workspace', pointText: '', strokeWidth: '1', areaDraft: defaultAreaDraft(),
})
export function nativeDraftSetter<K extends keyof NativeMeasurementDraft>(key: K,
  update: Dispatch<SetStateAction<NativeMeasurementDraft>>): Dispatch<SetStateAction<NativeMeasurementDraft[K]>> {
  return (value) => update((current) => ({ ...current, [key]: typeof value === 'function'
    ? (value as (before: NativeMeasurementDraft[K]) => NativeMeasurementDraft[K])(current[key]) : value }))
}

export type SavedNativeMeasurement = {
  settings: NativeMeasureRequest['settings']
  roi: Record<string, unknown> | null
  redirect_source: string | null
  redirect_plane: Record<string, number> | null
}

export function nativeDraftGeometry(draft: NativeMeasurementDraft, axes: NativeMeasureAsset['axes']) {
  if (draft.roiKind === 'workspace') return null
  if (draft.roiKind === 'imported') {
    if (!draft.importedRoi) throw new Error('导入区域已失效，请重新导入。')
    return draft.importedRoi
  }
  if (Object.hasOwn(nativeAreaLabels, draft.roiKind)) return buildNativeArea(draft.roiKind, draft.areaDraft)
  return parseNonAreaRoi(draft.roiKind, draft.pointText, draft.strokeWidth, axes)
}

export function nativeDraftParameters(draft: NativeMeasurementDraft, targets: NativeMeasureAsset[]): Omit<SavedNativeMeasurement, 'roi'> {
  const { selected, decimalPlaces, thresholdEnabled, thresholdMin, thresholdMax, redirectId, redirectIndices } = draft
  if (!Number.isInteger(decimalPlaces) || decimalPlaces < 0 || decimalPlaces > 9) throw new Error('显示精度须为 0–9。')
  let threshold: SavedNativeMeasurement['settings']['threshold'] = null
  if (thresholdEnabled || selected.includes('limit_to_threshold')) {
    const min = Number(thresholdMin), max = Number(thresholdMax)
    if (!thresholdMin.trim() || !thresholdMax.trim() || !Number.isFinite(min) || !Number.isFinite(max) || min > max)
      throw new Error('请填写有效阈值范围，最小值不能大于最大值。')
    threshold = { min, max }
  }
  let redirectPlane: Record<string, number> | null = null
  if (redirectId) {
    const target = targets.find((candidate) => candidate.id === redirectId && candidate.metadata_status === 'fiji_inspected')
    if (!target) throw new Error('第二来源已失效，请重新选择。')
    redirectPlane = {}
    for (const [axisName, key] of [['Channel', 'C'], ['Z', 'Z'], ['Time', 'T']]) {
      const axis = target.axes.find((entry) => entry.name === axisName)
      if (!axis) continue
      const raw = redirectIndices[key]
      const index = Number(raw ?? 0)
      if ((axis.length > 1 && !raw?.trim()) || !Number.isInteger(index) || index < 0 || index >= axis.length)
        throw new Error(`请选择有效的目标图 ${key} 轴平面。`)
      redirectPlane[key] = index
    }
  }
  return { settings: { measurements: selected, decimal_places: decimalPlaces, threshold },
    redirect_source: redirectId || null, redirect_plane: redirectPlane }
}
