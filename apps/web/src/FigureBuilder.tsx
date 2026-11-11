import { useState } from 'react'

type Chart = { dataset_id: string; chart_type: string; x_column: string; y_column: string; group_column: string | null; title: string; theme_id: string; palette_id: string; font_size: number; line_width: number; width_mm: number; height_mm: number; show_legend: boolean }
type Figure = { spec_version: string; panels: Chart[]; columns: number; labels: string; theme_id: string; width_mm: number; height_mm: number; dpi: number }

export default function FigureBuilder({ chart, api }: { chart: Chart | null; api: string }) {
  const [figure, setFigure] = useState<Figure>({ spec_version: '1.0', panels: [], columns: 2, labels: 'upper', theme_id: 'scientific_clear', width_mm: 280, height_mm: 210, dpi: 150 })
  const [renderId, setRenderId] = useState('')
  const [message, setMessage] = useState('先在上方设置单图，再逐一添加。子图保存添加时的设置，整页主题在这里统一选择。')
  const [busy, setBusy] = useState(false)
  const update = (patch: Partial<Figure>) => { setFigure(current => ({ ...current, ...patch })); setRenderId('') }
  const request = async (path: string, body?: unknown) => {
    const response = await fetch(`${api}${path}`, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined)
    const data = await response.json()
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '请检查画布尺寸、字段和参数。')
    return data
  }
  const run = async (action: 'render' | 'save' | 'load') => {
    setBusy(true)
    try {
      if (action === 'render') {
        setRenderId('')
        const data = await request('/api/figures', figure)
        setRenderId(data.render_id); setMessage('拼版已生成。预览与 PNG 下载为同一文件；SVG/PDF 使用同一版式。')
      } else if (action === 'save') {
        await request('/api/figure-configs', { name: 'current-layout', figure }); setMessage('拼版配置已保存至本次会话。')
      } else {
        const data = await request('/api/figure-configs/current-layout'); update(data.figure); setMessage('拼版配置已加载，请重新生成。')
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : '本机服务连接失败。') }
    finally { setBusy(false) }
  }
  return <section className="workspace"><p className="eyebrow">04 · FIGURE LAYOUT</p><h2>多图拼版 / Figure layout</h2><p>{message}</p>
    <div className="controls">
      <button disabled={!chart || figure.panels.length >= 4 || busy} onClick={() => chart && update({ panels: [...figure.panels, { ...chart }] })}>添加当前图 / Add panel</button>
      <label>列数 / Columns<select value={figure.columns} onChange={event => update({ columns: Number(event.target.value) })}><option value={1}>1</option><option value={2}>2</option></select></label>
      <label>子图标签 / Labels<select value={figure.labels} onChange={event => update({ labels: event.target.value })}><option value="upper">A, B, C, D</option><option value="lower">a, b, c, d</option><option value="none">无 / None</option></select></label>
      <label>整页主题 / Theme<select value={figure.theme_id} onChange={event => update({ theme_id: event.target.value })}><option value="scientific_clear">Scientific Clear</option><option value="modern_soft">Modern Soft</option><option value="high_contrast">High Contrast</option></select></label>
      <label>宽 mm<input type="number" min="120" max="300" value={figure.width_mm} onChange={event => update({ width_mm: Number(event.target.value) })}/></label>
      <label>高 mm<input type="number" min="120" max="300" value={figure.height_mm} onChange={event => update({ height_mm: Number(event.target.value) })}/></label>
      <label>DPI<input type="number" min="72" max="600" value={figure.dpi} onChange={event => update({ dpi: Number(event.target.value) })}/></label>
    </div>
    <ol>{figure.panels.map((panel, index) => <li key={index}>{panel.title || panel.chart_type} · {panel.palette_id} <button className="secondary" disabled={busy || index === 0} onClick={() => { const panels = [...figure.panels]; [panels[index - 1], panels[index]] = [panels[index], panels[index - 1]]; update({ panels }) }}>上移 / Up</button> <button className="secondary" disabled={busy} onClick={() => update({ panels: figure.panels.filter((_, i) => i !== index) })}>移除 / Remove</button></li>)}</ol>
    <div className="controls"><button disabled={busy || !figure.panels.length} onClick={() => run('render')}>{busy ? '处理中…' : '生成拼版 / Render'}</button><button disabled={busy || !figure.panels.length} onClick={() => run('save')}>保存拼版 / Save</button><button disabled={busy} onClick={() => run('load')}>加载拼版 / Load</button></div>
    {renderId && <><img className="chart-preview" src={`${api}/api/figures/${renderId}.png`} alt="拼版预览 / Figure preview" />{['svg', 'pdf', 'png'].map(format => <a className="export-link" key={format} href={`${api}/api/figures/${renderId}.${format}`}>导出 {format.toUpperCase()}</a>)}</>}
    <p className="meta">最多 4 图。预览仅保留最近 8 次拼版；配置和数据在服务停止后清除。艺术分类色用于区分类别，不代表色盲可读认证。</p>
  </section>
}
