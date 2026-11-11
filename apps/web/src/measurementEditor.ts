import { useCallback, useState, type SetStateAction } from 'react'

export type MeasurementRegion = { kind?: 'rectangle' | 'ellipse' | 'polygon' | 'full';
  x?: number; y?: number; width?: number; height?: number; points?: { x: number; y: number }[] }
export type SavedMeasurementSelection = { indices: Record<string, number>; roi: MeasurementRegion | null; extra_measurements: string[] }
export type MeasurementEditor = {
  indices: Record<string, number>; useRoi: boolean; kind: 'rectangle' | 'ellipse' | 'polygon'
  rectangle: { x: number; y: number; width: number; height: number }
  polygonText: string; extras: string[]
}
export function defaultMeasurementEditor(): MeasurementEditor {
  return { indices: { C: 0, Z: 0, T: 0 }, useRoi: false, kind: 'rectangle',
    rectangle: { x: 0, y: 0, width: 8, height: 8 }, polygonText: '1,1\n7,1\n1,6', extras: [] }
}

export function editorFromSelection(selection: SavedMeasurementSelection | null): MeasurementEditor {
  const editor = defaultMeasurementEditor()
  if (!selection) return editor
  editor.indices = { ...selection.indices }; editor.extras = [...selection.extra_measurements]
  editor.useRoi = Boolean(selection.roi)
  const roi = selection.roi
  if (roi?.kind === 'polygon') {
    editor.kind = 'polygon'; editor.polygonText = (roi.points ?? []).map(({ x, y }) => `${x},${y}`).join('\n')
  } else if (roi) {
    editor.kind = roi.kind === 'ellipse' ? 'ellipse' : 'rectangle'
    editor.rectangle = { x: roi.x ?? 0, y: roi.y ?? 0, width: roi.width ?? 1, height: roi.height ?? 1 }
  }
  return editor
}

export function selectionFromEditor(editor: MeasurementEditor, axes: { name: string }[]): SavedMeasurementSelection {
  const indices: Record<string, number> = {}
  for (const axis of axes) {
    const key = axis.name === 'Channel' ? 'C' : axis.name === 'Z' ? 'Z' : axis.name === 'Time' ? 'T' : null
    if (key) indices[key] = editor.indices[key] ?? 0
  }
  let roi: MeasurementRegion | null = null
  if (editor.useRoi) {
    if (editor.kind === 'polygon') {
      const lines = editor.polygonText.trim().split(/\r?\n/)
      if (lines.length < 3 || lines.length > 32 || lines.some((line) => !/^\s*\d+\s*,\s*\d+\s*$/.test(line)))
        throw new Error('图像中保留的多边形顶点无效，请切回该图像修正后保存。')
      roi = { kind: 'polygon', points: lines.map((line) => {
        const [x, y] = line.split(',').map(Number); return { x, y }
      }) }
    } else roi = { kind: editor.kind, ...editor.rectangle }
  }
  return { indices, roi, extra_measurements: [...editor.extras] }
}

export function useMeasurementEditors(activeId: string | null) {
  const [drafts, setDrafts] = useState<Record<string, MeasurementEditor>>({})
  const restoreSelections = useCallback((selections: Record<string, SavedMeasurementSelection | null>) => {
    setDrafts((current) => ({ ...current, ...Object.fromEntries(Object.entries(selections)
      .map(([id, selection]) => [id, editorFromSelection(selection)])) }))
  }, [])
  const removeDraft = useCallback((identifier: string) => {
    setDrafts((current) => {
      const next = { ...current }; delete next[identifier]; return next
    })
  }, [])
  function setter<K extends keyof MeasurementEditor>(key: K) {
    return (value: SetStateAction<MeasurementEditor[K]>) => {
      if (!activeId) return
      setDrafts((current) => {
        const before = current[activeId] ?? defaultMeasurementEditor()
        const next = typeof value === 'function' ? (value as (previous: MeasurementEditor[K]) => MeasurementEditor[K])(before[key]) : value
        return { ...current, [activeId]: { ...before, [key]: next } }
      })
    }
  }
  return { drafts, editor: activeId ? drafts[activeId] ?? defaultMeasurementEditor() : defaultMeasurementEditor(),
    restoreSelections, removeDraft, setters: { indices: setter('indices'), useRoi: setter('useRoi'), kind: setter('kind'),
      rectangle: setter('rectangle'), polygonText: setter('polygonText'), extras: setter('extras') } }
}
