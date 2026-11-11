import { useI18n } from './i18n'
import { workbenchText } from './workbenchEnglish'
import { useEffect, useMemo, useState } from 'react'
import './App.css'
import FigureBuilder from './FigureBuilder'

type Column = { name: string; dtype: string; missing_count?: number }
type Preview = { dataset_id: string; row_count: number; columns: Column[]; rows: Record<string, string | number>[] }
type Theme = 'scientific_clear' | 'modern_soft' | 'high_contrast'
type ChartType = 'scatter' | 'bar' | 'line' | 'box' | 'heatmap'
const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

function App() {
  const { locale } = useI18n()
  const ui = (text: string) => workbenchText(locale, text)

  const [preview, setPreview] = useState<Preview | null>(null)
  const [xColumn, setXColumn] = useState('response')
  const [yColumn, setYColumn] = useState('viability')
  const [theme, setTheme] = useState<Theme>('scientific_clear')
  const [chartType, setChartType] = useState<ChartType>('scatter')
  const [groupColumn, setGroupColumn] = useState<string | null>('condition')
  const [title, setTitle] = useState('Cell response')
  const [fontSize, setFontSize] = useState(10)
  const [lineWidth, setLineWidth] = useState(1.2)
  const [widthMm, setWidthMm] = useState(160)
  const [heightMm, setHeightMm] = useState(105)
  const [showLegend, setShowLegend] = useState(true)
  const [palette, setPalette] = useState<'theme' | 'colorblind' | 'viridis' | 'coolwarm' | 'clay' | 'lagoon'>('theme')
  const [renderId, setRenderId] = useState('')
  const [message, setMessage] = useState('正在载入内置模拟 CSV…')

  useEffect(() => {
    fetch(`${API}/api/datasets/simulated/preview`).then((response) => response.ok ? response.json() : Promise.reject()).then((data: Preview) => { setPreview(data); setMessage('模拟 CSV 已载入；未上传任何本机文件。') }).catch(() => setMessage('无法连接本机 API。请先启动后端。'))
  }, [])

  const numericColumns = useMemo(() => preview?.columns.filter((column) => /int|float/.test(column.dtype)) ?? [], [preview])
  const chart = preview && { dataset_id: preview.dataset_id, chart_type: chartType, x_column: xColumn, y_column: yColumn, group_column: chartType === 'heatmap' ? null : groupColumn, title, theme_id: theme, palette_id: chartType === 'heatmap' && !['viridis', 'coolwarm'].includes(palette) ? 'coolwarm' : palette, font_size: fontSize, line_width: lineWidth, width_mm: widthMm, height_mm: heightMm, show_legend: showLegend }
  const uploadFile = async (file: File) => {
    if (file.size > 5 * 1024 * 1024) { setMessage('文件超过 5 MB 限制。'); return }
    setMessage('正在读取本机文件…')
    const formData = new FormData(); formData.append('file', file)
    const response = await fetch(`${API}/api/datasets`, { method: 'POST', body: formData })
    if (!response.ok) { const error = await response.json(); setMessage(error.detail ?? '文件读取失败。'); return }
    const data = await response.json() as Preview
    setPreview(data)
    const numeric = data.columns.filter((column) => /int|float/.test(column.dtype))
    if (numeric.length >= 2) { setXColumn(numeric[0].name); setYColumn(numeric[1].name) }
    setGroupColumn(null)
    setMessage('文件已在本机服务会话中读取；停止服务后会清除。')
  }
  const createRender = async () => {
    if (!chart) return
    setMessage('正在生成图表…')
    const response = await fetch(`${API}/api/renders`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chart }) })
    if (!response.ok) { setMessage('图表生成失败，请检查字段。'); return }
    setRenderId((await response.json() as { render_id: string }).render_id); setMessage('图表已生成，可导出 SVG、PDF 或 PNG。')
  }
  const saveConfig = async () => {
    if (!chart) return
    const response = await fetch(`${API}/api/configs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'current-figure', chart }) })
    setMessage(response.ok ? '配置已保存到本次本机服务会话。' : '配置保存失败。')
  }

  return <main className="page-shell">
    <header className="topbar"><div className="brand"><span className="brand-mark">◌</span>BioFigure Studio</div><span className="status-pill">{ui("本机模式 / Local only")}</span></header>
    <section className="hero"><p className="eyebrow">PHASE 4 · LOCAL WORKFLOW</p><h1>{ui("从本机数据到可导出的基础科研图表")}</h1><p className="hero-copy">{ui("CSV/XLSX 仅在本机服务会话中读取，不会自动上传或共享。")}</p></section>
    <section className="workspace"><div className="section-heading"><div><p className="eyebrow">01 · DATA PREVIEW</p><h2>{ui("数据预览")}</h2></div><a href={`${API}/api/datasets/simulated.csv`}>{ui("下载模拟 CSV")}</a></div><label className="file-picker">{ui("选择 CSV 或 XLSX（最多 5 MB）")}<input type="file" accept=".csv,.xlsx" onChange={(event) => event.target.files?.[0] && uploadFile(event.target.files[0])} /></label><p className="notice">{ui(message)}</p>{preview && <><p className="meta">{preview.row_count} {ui("行 ·")} {preview.columns.map((column) => `${column.name} (${column.dtype}) · ${ui('缺失')} ${column.missing_count ?? 0}`).join(' · ')}</p><div className="table-wrap"><table><thead><tr>{preview.columns.map((column) => <th key={column.name}>{column.name}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column.name}>{row[column.name]}</td>)}</tr>)}</tbody></table></div></>}</section>
    <section className="workspace controls"><div><p className="eyebrow">02 · CHART</p><h2>{ui("图表、字段与主题")}</h2></div><label>{ui("图表")}<select value={chartType} onChange={(event) => setChartType(event.target.value as ChartType)}><option value="scatter">{ui("散点图")}</option><option value="bar">{ui("柱状图（均值）")}</option><option value="line">{ui("折线图")}</option><option value="box">{ui("箱线图")}</option><option value="heatmap">{ui("热图（相关性）")}</option></select></label><label>{ui("X 轴/分组")}<select value={xColumn} onChange={(event) => setXColumn(event.target.value)}>{preview?.columns.map((column) => <option key={column.name}>{column.name}</option>)}</select></label><label>{ui("Y 轴")}<select value={yColumn} onChange={(event) => setYColumn(event.target.value)}>{numericColumns.map((column) => <option key={column.name}>{column.name}</option>)}</select></label><label>{ui("颜色分组")}<select value={groupColumn ?? ''} onChange={(event) => setGroupColumn(event.target.value || null)} disabled={chartType === 'heatmap'}><option value="">{ui("不分组")}</option>{preview?.columns.map((column) => <option key={column.name}>{column.name}</option>)}</select></label><label>{ui("主题")}<select value={theme} onChange={(event) => setTheme(event.target.value as Theme)}><option value="scientific_clear">Scientific Clear</option><option value="modern_soft">Modern Soft</option><option value="high_contrast">High Contrast</option></select></label><label>{ui("调色板（热图使用连续/发散色）")}<select value={palette} onChange={(event) => setPalette(event.target.value as typeof palette)}><option value="theme">{ui("主题分类色")}</option><option value="clay">{ui("陶土 / Clay v1")}</option><option value="lagoon">{ui("湖湾 / Lagoon v1")}</option><option value="colorblind">{ui("高辨识分类色")}</option><option value="viridis">{ui("连续 Viridis")}</option><option value="coolwarm">{ui("发散 Coolwarm")}</option></select></label><label>{ui("标题")}<input value={title} maxLength={160} onChange={(event) => setTitle(event.target.value)} /></label><label>{ui("字体")} {fontSize}<input type="range" min="7" max="24" value={fontSize} onChange={(event) => setFontSize(Number(event.target.value))} /></label><label>{ui("线宽")} {lineWidth}<input type="range" min="0.5" max="5" step="0.1" value={lineWidth} onChange={(event) => setLineWidth(Number(event.target.value))} /></label><label>{ui("宽度 mm")}<input type="number" min="60" max="300" value={widthMm} onChange={(event) => setWidthMm(Number(event.target.value))} /></label><label>{ui("高度 mm")}<input type="number" min="60" max="300" value={heightMm} onChange={(event) => setHeightMm(Number(event.target.value))} /></label><label className="checkbox"><input type="checkbox" checked={showLegend} onChange={(event) => setShowLegend(event.target.checked)} />{ui("显示图例")}</label><button onClick={createRender} disabled={!preview}>{ui("生成图表")}</button><button className="secondary" onClick={saveConfig} disabled={!preview}>{ui("保存配置")}</button></section>
    <section className="workspace export"><div><p className="eyebrow">03 · PREVIEW & EXPORT</p><h2>{ui("预览与导出")}</h2></div>{renderId ? <><img className="chart-preview" src={`${API}/api/renders/${renderId}.png`} alt={ui("图表预览")} />{['svg', 'pdf', 'png'].map((format) => <a key={format} className="export-link" href={`${API}/api/renders/${renderId}.${format}`}>{ui("导出")} {format.toUpperCase()}</a>)}</> : <p>{ui("先生成图表后，才会出现预览和导出链接。")}</p>}</section>
    <FigureBuilder chart={chart} api={API} />
    <footer><span>{ui("阶段 4：艺术配色与拼版")}</span><span>{ui("配置与数据仅保留至本机服务停止")}</span></footer>
  </main>
}
export default App
