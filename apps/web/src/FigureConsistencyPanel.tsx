import { useState } from 'react'
import { useI18n } from './i18n'
import { scientificPalettes } from './chartPalettes'
import type { Figure } from './Workflow'

type Preview = { figure: Figure; changes: { target: string; field: string; before: unknown; after: unknown }[]; group_colors: Record<string, string> }
export default function FigureConsistencyPanel({ figure, busy, canUndo, onApply, onUndo }: {
  figure: Figure; busy: boolean; canUndo: boolean
  onApply: (next: Figure, before: Figure, changed: number[]) => void; onUndo: () => void
}) {
  const { locale, t } = useI18n()
  const [palette, setPalette] = useState('oc_clear'), [font, setFont] = useState(10), [line, setLine] = useState(1.2)
  const [order, setOrder] = useState(''), [preview, setPreview] = useState<{ value: Preview; before: Figure; signature: string } | null>(null)
  const [pending, setPending] = useState(false), [error, setError] = useState('')
  const stale = preview?.signature !== JSON.stringify(figure)
  const fields:Record<string,string>={theme_id:t('主题','Theme'),palette_id:t('配色','Palette'),font_size:t('字号','Font size'),line_width:t('线宽','Line width'),show_legend:t('显示图例','Show legend'),category_order:t('分组顺序','Group order'),label_font_size:t('面板标签字号','Panel label size')}
  const prepare = async () => {
    setPending(true); setError(''); setPreview(null)
    const before = structuredClone(figure)
    try {
      const response = await fetch('/api/figure-workflow/v1/style-preview', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({figure:before,style:{theme_id:'scientific_clear',palette_id:palette,font_size:font,line_width:line},category_order:order.split('\n').filter(Boolean)})})
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '')
      setPreview({value:data,before,signature:JSON.stringify(before)})
    } catch (cause) { setError(locale==='en'&&cause instanceof Error?cause.message:t('请核对分组名称、色板容量及图表类型；支持五类基础图表。', 'Check group names, palette capacity and standard plot types.')) }
    finally { setPending(false) }
  }
  return <section className="wf-config" aria-label={t('整套图版风格', 'Linked figure style')}>
    <h2>{t('整套图版风格', 'Linked figure style')}</h2>
    <p>{t('统一字体、线宽和分组颜色；不修改数据、标题或原图。热图保留连续色阶。', 'Unify fonts, line widths and group colors without changing data, titles or source images. Heatmaps keep their continuous colors.')}</p>
    <label>{t('分类配色', 'Categorical palette')}<select value={palette} onChange={e=>{setPalette(e.target.value);setPreview(null)}}>{scientificPalettes.filter(item=>item.kind==='categorical').map(item=><option key={item.id} value={item.id}>{item.name[locale]}</option>)}</select></label>
    <label>{t('统一字号', 'Shared font size')}<input type="number" min={7} max={24} value={font} onChange={e=>{setFont(+e.target.value);setPreview(null)}}/></label>
    <label>{t('统一线宽', 'Shared line width')}<input type="number" min={.5} max={5} step={.1} value={line} onChange={e=>{setLine(+e.target.value);setPreview(null)}}/></label>
    <label>{t('分组顺序（每行一个原名称；留空先预览全部组）', 'Group order (one original name per line; leave blank to preview all groups)')}<textarea value={order} onChange={e=>{setOrder(e.target.value);setPreview(null)}}/></label>
    <button type="button" disabled={busy||pending||!figure.panels.length} onClick={()=>void prepare()}>{t('预览统一方案', 'Preview linked style')}</button>
    <button type="button" disabled={busy||!canUndo} onClick={onUndo}>{t('撤销上次统一', 'Undo linked style')}</button>
    {error&&<p role="alert">{error}</p>}
    {preview&&<div><p>{t(`将修改 ${preview.value.changes.length} 项展示属性。请确认同名分组确实代表同一实验组。`, `${preview.value.changes.length} presentation changes. Confirm matching names represent the same experimental groups.`)}</p>
      <ul>{Object.entries(preview.value.group_colors).map(([name,color])=><li key={name}><span aria-hidden="true" style={{display:'inline-block',width:12,height:12,background:color,marginRight:6}}/>{name} · {color}</li>)}</ul>
      <details><summary>{t('查看修改范围', 'Review change scope')}</summary><ul>{preview.value.changes.map((change,index)=><li key={index}>{change.target==='figure'?t('整页','Figure'):t('面板','Panel')+' '+change.target.split(':')[1]} · {fields[change.field]||change.field}: {JSON.stringify(change.before)} → {JSON.stringify(change.after)}</li>)}</ul></details>
      {stale&&<p role="status">{t('图版已变化，请重新预览。', 'The figure changed. Preview again.')}</p>}
      <button type="button" disabled={busy||stale||!preview.value.changes.length} onClick={()=>{onApply(preview.value.figure,preview.before,[...new Set(preview.value.changes.filter(item=>item.target.startsWith('panel:')).map(item=>+item.target.split(':')[1]-1))]);setPreview(null)}}>{t('确认分组映射并应用', 'Confirm group mapping and apply')}</button>
    </div>}
  </section>
}
