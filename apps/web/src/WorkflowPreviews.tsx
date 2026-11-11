import { useI18n } from './i18n'
import { workbenchText } from './workbenchEnglish'
import type { CSSProperties, ReactNode } from 'react'
import { getWorkflowCatalog, type EcologyDirection, type OmicsDirection } from './WorkflowCatalog'

const virtualSpatialPoints = [
  { x: 48, y: 42, c: '#527c78' },
  { x: 62, y: 54, c: '#527c78' },
  { x: 78, y: 43, c: '#527c78' },
  { x: 94, y: 64, c: '#d6806c' },
  { x: 110, y: 78, c: '#d6806c' },
  { x: 128, y: 61, c: '#d6806c' },
  { x: 150, y: 86, c: '#5f8f9b' },
  { x: 166, y: 72, c: '#5f8f9b' },
  { x: 182, y: 91, c: '#5f8f9b' },
]
const virtualRPoints = [
  { x: 44, y: 102 },
  { x: 58, y: 88 },
  { x: 72, y: 94 },
  { x: 88, y: 70 },
  { x: 103, y: 76 },
  { x: 118, y: 55 },
  { x: 134, y: 62 },
  { x: 150, y: 43 },
  { x: 168, y: 49 },
  { x: 187, y: 30 },
]
export function OmicsPreview({ direction, compact = false, colors = ['#527c78', '#d6806c', '#9eae79'] }: { direction: OmicsDirection; compact?: boolean; colors?: string[] }) {
  const { locale, t } = useI18n()
  const ui = (text: string) => workbenchText(locale, text)

  const { omicsDirections } = getWorkflowCatalog(t)
  const title = `${omicsDirections[direction].title} · ${ui('虚拟数据示意')}`
  const frame = (
    <>
      <line x1="34" y1="122" x2="208" y2="122" className="preview-axis" />
      <line x1="34" y1="20" x2="34" y2="122" className="preview-axis" />
    </>
  )
  let graphic: ReactNode
  if (direction === 'spatial')
    graphic = (
      <>
        {[0, 1, 2].map((i) => (
          <ellipse key={i} cx={112 + i * 4} cy={72 - i * 3} rx={75 - i * 10} ry={43 - i * 5} className="preview-tissue" />
        ))}
        {virtualSpatialPoints.map((point, i) => (
          <circle key={i} cx={point.x} cy={point.y} r="5" fill={colors[Math.floor(i / 3)] ?? colors[0]} className="preview-point" />
        ))}
      </>
    )
  else if (direction === 'genome')
    graphic = (
      <>
        {frame}
        {[42, 68, 94].map((y, i) => (
          <g key={y}>
            <text x="38" y={y - 7} className="preview-label">
              {i === 0 ? 'genes' : i === 1 ? 'signal' : 'peaks'}
            </text>
            <line x1="72" y1={y} x2="202" y2={y} className="preview-track" />
            {[0, 1, 2].map((j) => (
              <rect key={j} x={80 + j * 34 + i * 5} y={y - 6} width={18 + i * 4} height="12" rx="4" className={`preview-track-block block-${i}`} />
            ))}
          </g>
        ))}
      </>
    )
  else if (direction === 'circos')
    graphic = (
      <>
        <circle cx="120" cy="72" r="49" className="preview-ring" />
        <circle cx="120" cy="72" r="35" className="preview-ring inner" />
        <path d="M83 42 Q120 10 157 44" className="preview-link" />
        <path d="M83 102 Q124 136 168 92" className="preview-link second" />
        <path d="M74 72 A46 46 0 0 1 93 34" className="preview-sector sector-a" />
        <path d="M147 35 A46 46 0 0 1 166 73" className="preview-sector sector-b" />
      </>
    )
  else if (direction === 'dna')
    graphic = (
      <>
        <line x1="38" y1="72" x2="202" y2="72" className="preview-dna-line" />
        {[
          { x: 50, w: 35, c: colors[0] },
          { x: 94, w: 48, c: colors[1] ?? colors[0] },
          { x: 151, w: 37, c: colors[2] ?? colors[0] },
        ].map((feature, i) => (
          <g key={i}>
            <rect x={feature.x} y="57" width={feature.w} height="30" rx="8" fill={feature.c} className="preview-feature" />
            <path d={`M${feature.x + feature.w - 8} 57 l8 15 l-8 15`} fill="none" className="preview-arrow" />
          </g>
        ))}
        <text x="40" y="105" className="preview-label">
          0 bp
        </text>
        <text x="176" y="105" className="preview-label">
          5 kb
        </text>
      </>
    )
  else
    graphic = (
      <>
        {frame}
        <polyline points={virtualRPoints.map((point) => `${point.x},${point.y}`).join(' ')} className="preview-line" />
        {virtualRPoints.map((point, i) => (
          <circle key={i} cx={point.x} cy={point.y} r="4" className="preview-r-point" />
        ))}
        <text x="172" y="116" className="preview-label">
          x
        </text>
        <text x="22" y="24" className="preview-label">
          y
        </text>
      </>
    )
  const previewStyle = {
    '--preview-a': colors[0],
    '--preview-b': colors[1] ?? colors[0],
    '--preview-c': colors[2] ?? colors[0],
  } as CSSProperties
  return (
    <div className={`wf-omics-preview${compact ? ' compact' : ''}`} style={previewStyle} aria-label={title}>
      <svg viewBox="0 0 240 145" role="img" aria-label={title}>
        {graphic}
      </svg>
      <span>{ui("虚拟数据示意")}</span>
    </div>
  )
}
export function EcologyPreview({ direction, compact = false, variant = 'beta', colors = ['#527c78', '#d6806c', '#9eae79'] }: { direction: EcologyDirection; compact?: boolean; variant?: 'alpha' | 'beta'; colors?: string[] }) {
  const { locale, t } = useI18n()
  const ui = (text: string) => workbenchText(locale, text)

  const { ecologyDirections } = getWorkflowCatalog(t)
  const title = `${ecologyDirections[direction].title} · ${ui('虚拟数据示意')}`
  const frame = (
    <>
      <line x1="34" y1="122" x2="208" y2="122" className="preview-axis" />
      <line x1="34" y1="20" x2="34" y2="122" className="preview-axis" />
    </>
  )
  let graphic: ReactNode
  if (direction === 'community')
    graphic = (
      <>
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <rect x={52 + i * 46} y={42 + i * 2} width="30" height={80 - i * 9} rx="4" fill={colors[0]} />
            <rect x={52 + i * 46} y={31 + i * 2} width="30" height="11" rx="4" fill={colors[1] ?? colors[0]} />
            <rect x={52 + i * 46} y={23 + i * 2} width="30" height="8" rx="4" fill={colors[2] ?? colors[0]} />
          </g>
        ))}
      </>
    )
  else if (direction === 'diversity' && variant === 'alpha')
    graphic = (
      <>
        {frame}
        {[0, 1].map((i) => (
          <g key={i}>
            <rect x={63 + i * 78} y={53 + i * 12} width="30" height="47" rx="5" fill={i ? (colors[1] ?? colors[0]) : colors[0]} opacity=".72" />
            <line x1={78 + i * 78} y1={42 + i * 12} x2={78 + i * 78} y2={110 + i * 12} className="preview-axis" />
            <line x1={68 + i * 78} y1={77 + i * 12} x2={88 + i * 78} y2={77 + i * 12} className="preview-axis" />
            {[0, 1, 2].map((j) => (
              <circle key={j} cx={73 + i * 78 + j * 6} cy={65 + i * 12 + j * 12} r="3" fill={i ? (colors[1] ?? colors[0]) : colors[0]} className="preview-point" />
            ))}
          </g>
        ))}
      </>
    )
  else if (direction === 'diversity')
    graphic = (
      <>
        {frame}
        {[0, 1, 2, 3, 4, 5].map((_, i) => (
          <circle key={i} cx={61 + (i % 3) * 50} cy={45 + Math.floor(i / 3) * 34 + (i % 2) * 4} r="7" fill={i < 3 ? colors[0] : (colors[1] ?? colors[0])} className="preview-point" />
        ))}
      </>
    )
  else if (direction === 'ordination')
    graphic = (
      <>
        {frame}
        <ellipse cx="112" cy="75" rx="54" ry="30" className="preview-tissue" />
        <path d="M48 101 Q105 72 179 44" className="preview-line" />
        {[
          { x: 72, y: 91 },
          { x: 92, y: 80 },
          { x: 121, y: 66 },
          { x: 144, y: 58 },
          { x: 171, y: 46 },
        ].map((point, i) => (
          <circle key={i} cx={point.x} cy={point.y} r="5" fill={i < 3 ? colors[0] : (colors[1] ?? colors[0])} className="preview-point" />
        ))}
      </>
    )
  else if (direction === 'environment')
    graphic = (
      <>
        {frame}
        <polyline points="42,104 70,91 97,82 126,66 154,54 194,36" className="preview-line" />
        {[44, 78, 110, 144, 178].map((x, i) => (
          <circle key={i} cx={x} cy={104 - i * 16} r="5" fill={colors[0]} className="preview-point" />
        ))}
      </>
    )
  else if (direction === 'time')
    graphic = (
      <>
        {frame}
        <path d="M38 96 C64 84 66 48 91 58 S119 106 145 76 S177 36 204 47" className="preview-line" />
        <path d="M38 109 C65 104 75 86 98 90 S129 105 153 92 S181 74 204 78" className="preview-link second" />
        {[48, 78, 109, 141, 174].map((x, i) => (
          <circle key={i} cx={x} cy={i % 2 ? 59 : 89} r="4" fill={colors[0]} className="preview-point" />
        ))}
      </>
    )
  else
    graphic = (
      <>
        {[0, 1, 2].map((i) => (
          <circle key={i} cx={83 + i * 43} cy={74 - i * 8} r={28 - i * 6} fill="none" stroke={i === 1 ? (colors[1] ?? colors[0]) : (colors[2] ?? colors[0])} strokeWidth="9" opacity=".85" />
        ))}
        {[
          { x: 81, y: 71 },
          { x: 128, y: 63 },
          { x: 168, y: 54 },
        ].map((point, i) => (
          <circle key={i} cx={point.x} cy={point.y} r="5" fill={i === 1 ? (colors[1] ?? colors[0]) : colors[0]} className="preview-point" />
        ))}
      </>
    )
  const previewStyle = {
    '--preview-a': colors[0],
    '--preview-b': colors[1] ?? colors[0],
    '--preview-c': colors[2] ?? colors[0],
  } as CSSProperties
  return (
    <div className={`wf-ecology-preview${compact ? ' compact' : ''}`} style={previewStyle} aria-label={title}>
      <svg viewBox="0 0 240 145" role="img" aria-label={title}>
        {graphic}
      </svg>
      <span>{ui("虚拟数据示意")}</span>
    </div>
  )
}
