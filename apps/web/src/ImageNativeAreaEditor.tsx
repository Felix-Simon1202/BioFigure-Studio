import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import { useState } from 'react'
import { buildNativeArea, nativeAreaFields, nativeAreaLabels, type AreaDraft } from './nativeArea'

const labels: Record<string, string> = { x: '左上 X', y: '左上 Y', width: '宽', height: '高', x1: '轴起点 X',
  y1: '轴起点 Y', x2: '轴终点 X', y2: '轴终点 Y', rect_width: '矩形宽度', aspect_ratio: '短轴/长轴', evaluation_points: '样条拟合点数' }
export default function ImageNativeAreaEditor({ kind, draft, onChange }: {
  kind: string; draft: AreaDraft; onChange: (next: AreaDraft) => void
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const [error, setError] = useState('')
  return <div className="iw-native-area-editor">
    <div className="iw-nm-fields">{nativeAreaFields(kind).map((field) => <label className="iw-nm-field" key={field}>{tx(labels[field])}
      <input type="number" step="any" value={draft.fields[field] ?? ''} onChange={(event) => onChange({ ...draft,
        fields: { ...draft.fields, [field]: event.target.value } })} /></label>)}</div>
    {['polygon', 'freehand', 'traced', 'spline_polygon'].includes(kind) && <label className="iw-nm-field">{tx("面积顶点（每行 x,y）")}<textarea rows={5} value={draft.points} onChange={(event) => onChange({ ...draft, points: event.target.value })} /></label>}
    {kind !== 'shape' ? <button type="button" disabled={draft.operands.length >= 8} onClick={() => {
      try { onChange({ ...draft, operands: [...draft.operands, buildNativeArea(kind, draft)] }); setError('') }
      catch (cause) { setError(cause instanceof Error ? cause.message : '区域参数无效。') }
    }}>{tx("加入布尔组合（")}{draft.operands.length}/8）</button> : <label className="iw-nm-field">{tx("组合运算")}<select value={draft.operation} onChange={(event) => onChange({ ...draft, operation: event.target.value })}>
        <option value="union">{tx("并集")}</option><option value="intersection">{tx("交集")}</option><option value="xor">{tx("异或")}</option>
        <option value="subtract">{tx("依序相减（首项减后续项）")}</option></select></label>}
    {draft.operands.length > 0 && <ol>{draft.operands.map((operand, index) => <li key={index}>
      {tx(nativeAreaLabels[String(operand.kind)] ?? String(operand.kind))} <button type="button" onClick={() => onChange({ ...draft,
        operands: draft.operands.filter((_, offset) => offset !== index) })}>{tx("移除第")}{index + 1} {locale === 'zh-CN' ? tx("项") : ''}</button>
      <details><summary>{tx("区域参数")}</summary><pre>{JSON.stringify(operand, null, 2)}</pre></details></li>)}</ol>}
    <p>{tx("坐标和尺寸均为源像素。调整简单区域后可依序加入组合，再选择“布尔组合”执行；加入的是当时参数的独立副本。 原生引擎检查最终轮廓、图像边界、自交和采样预算；样条与旋转轮廓不会被普通多边形替代。")}</p>
    {error && <p role="alert">{tx(error)}</p>}
  </div>
}
