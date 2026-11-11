import { relationLabels, type IllustrationEdge, type Point, type RelationType } from './illustration'

export const mechanismRelationStyleVersion = 'mechanism-relation-semantics/1.0'

type RelationMarker = 'arrow' | 'bar' | 'circle'

const targetMarkers: Record<RelationType, RelationMarker | undefined> = {
  association: undefined,
  activation: 'arrow',
  inhibition: 'bar',
  binding: 'circle',
  translocation: 'arrow',
  expression: 'arrow',
}

export function mechanismRelationStyle(edge: Pick<IllustrationEdge, 'relation' | 'label' | 'scientific_status'>, locale: 'en' | 'zh-CN' = 'zh-CN') {
  const english: Record<RelationType, string> = { association: 'Association', activation: 'Activation', inhibition: 'Inhibition', binding: 'Binding', translocation: 'Translocation', expression: 'Expression/production' }
  const originalName = relationLabels[edge.relation]
  const name = locale === 'en' ? english[edge.relation] : originalName
  const customLabel = edge.label.trim()
  const pending = edge.scientific_status === 'needs_review'
  const marker = targetMarkers[edge.relation]
  const label = customLabel && customLabel !== originalName && customLabel !== english[edge.relation] ? `${name} · ${customLabel}` : name
  return {
    label: pending ? `${label}${locale === 'en' ? ' (needs review)' : '（待核实）'}` : label,
    markerEnd: marker ? `url(#${marker})` : undefined,
    strokeDasharray: pending ? '7 5' : undefined,
  }
}

/** Position a label beside the longest straight segment of the orthogonal route. */
export function mechanismRelationLabelPosition(points: Point[]) {
  let start = points[0]
  let end = start
  let length = 0
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1]
    const next = points[index]
    const segmentLength = Math.abs(previous.x - next.x) + Math.abs(previous.y - next.y)
    if (segmentLength > length) {
      start = previous
      end = next
      length = segmentLength
    }
  }
  const horizontal = start.y === end.y
  return {
    x: (start.x + end.x) / 2 + (horizontal ? 0 : 8),
    y: (start.y + end.y) / 2 - (horizontal ? 8 : 0),
    anchor: horizontal ? 'middle' as const : 'start' as const,
  }
}
