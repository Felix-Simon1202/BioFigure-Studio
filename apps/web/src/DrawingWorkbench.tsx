import { useEffect, useState, type ReactNode } from 'react'
import type { Chart } from './Workflow'
import WorkbenchSettings from './WorkbenchSettings'
import SvgHandoffInspector from './SvgHandoffInspector'
import { branchWorkflowFields, buildBranchWorkflow, syntheticBranchExample, verifySyntheticExtraction, type BranchWorkflowInput, type IllustrationModelExtraction } from './illustrationSkill'
import type { IllustrationSpec } from './illustration'
import { buildTimeline, emptyTimelineInput, syntheticTimelineExample, type TimelineInput } from './illustrationTimeline'
import TimelineFields from './TimelineFields'
import './DrawingWorkbench.css'

export type WorkbenchProvider = 'local' | 'demo' | 'external'
export type WorkbenchProposal = { action: 'chart'; chart: Chart } | { action: 'fiji_sample'; chart: null }
export type WorkbenchConnection = { url: string; token: string; expires_in: number }
export type ExternalDraft = { base_url: string; model: string; api_key: string; preset: 'scatter' | 'line'; consent: true }

type Category = 'chart' | 'image' | 'figure' | 'illustration'
type Integration = { id: string; name: string; mode: 'native' | 'file'; ready: boolean; detail: string; handoff: string; automation_ready?: boolean; path?: string }

type Props = {
  visible: boolean
  modeSwitch: ReactNode
  busy: boolean
  canApply: boolean
  recent: File[]
  onOpenProject: (file?: File) => void
  onOpen: (destination: Category) => void
  onDraft: (provider: WorkbenchProvider, prompt: string, receive: (proposal: WorkbenchProposal) => void, external?: ExternalDraft) => void
  onApply: (chart: Chart, render: boolean) => void
  onInspect: () => void
  onConnect: (receive: (connection: WorkbenchConnection) => void) => void
  onDisconnect: (done: () => void) => void
  onApplyIllustration: (document: IllustrationSpec) => void
  onDraftIllustration: (receive: (value: unknown) => void, fail: (message: string) => void) => void
}

const categories = {
  chart: { label: '统计图', icon: '▥', title: '从数据做一张图', description: '先检查草案里的图型、字段与主题，再到本地编辑和导出。', local: '打开统计图编辑器', connectors: ['r'] },
  image: { label: '显微图像', icon: '⊙', title: '从标定开始看图像', description: '先试用 Fiji 检查合成 TIFF。原图、ROI 和批量操作在本地工作台处理。', local: '打开本地图像工作台', connectors: ['fiji'] },
  figure: { label: '论文图版', icon: '▦', title: '把各张图编成一页', description: '在图版编辑器组合图像和统计图，检查版面与有效分辨率，再导出。', local: '打开论文图版编辑器', connectors: ['vector'] },
  illustration: { label: '科研图示', icon: '◇', title: '用图示讲清研究过程', description: '从可编辑模板开始，手动组织实验步骤、机制关系和图形摘要。', local: '打开本地图示编辑器', connectors: ['vector'] },
} satisfies Record<Category, { label: string; icon: string; title: string; description: string; local: string; connectors: string[] }>

const prompts = {
  chart: '用科研清晰主题为内置合成样例绘制散点图。',
  image: '检查内置合成 TIFF 的尺寸、像素类型和位深。',
}
const externalPrompts = {
  scatter: prompts.chart,
  line: '用现代柔和主题为内置合成样例绘制折线图。',
}
const themeNames: Record<string, string> = { scientific_clear: '科研清晰', modern_soft: '现代柔和', high_contrast: '高对比' }

export default function DrawingWorkbench({ visible, modeSwitch, busy, canApply, recent, onOpenProject, onOpen, onDraft, onApply, onInspect, onConnect, onDisconnect, onApplyIllustration, onDraftIllustration }: Props) {
  const [category, setCategory] = useState<Category>('chart')
  const [workspace, setWorkspace] = useState<'draw' | 'generate'>('draw')
  const [settings, setSettings] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [provider, setProvider] = useState<'local' | 'external'>('local')
  const [external, setExternal] = useState({ base_url: '', model: '', api_key: '' })
  const [preset, setPreset] = useState<ExternalDraft['preset']>('scatter')
  const [consent, setConsent] = useState(false)
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [connector, setConnector] = useState<Integration | null>(null)
  const [proposal, setProposal] = useState<(WorkbenchProposal & { provider: WorkbenchProvider }) | null>(null)
  const [failedCatalog, setFailedCatalog] = useState(false)
  const [handoffError, setHandoffError] = useState('')
  const [handoffBusy, setHandoffBusy] = useState(false)
  const [illustrationForm, setIllustrationForm] = useState<'branch'|'timeline'>('branch')
  const [timelineInput, setTimelineInput] = useState<TimelineInput>(emptyTimelineInput)
  const [timelineDraft, setTimelineDraft] = useState<IllustrationSpec | null>(null)
  const [timelineError, setTimelineError] = useState('')
  const [workflowInput, setWorkflowInput] = useState<BranchWorkflowInput>({ title: '', sharedStep: '', branchA: '', stepA: '', resultA: '', branchB: '', stepB: '', resultB: '' })
  const [workflowDraft, setWorkflowDraft] = useState<IllustrationSpec | null>(null)
  const [workflowError, setWorkflowError] = useState('')
  const [modelExtraction, setModelExtraction] = useState<IllustrationModelExtraction | null>(null)
  const [workflowSource, setWorkflowSource] = useState<'manual' | 'local_model'>('manual')
  const prepareWorkflow = () => {
    setModelExtraction(null)
    try { setWorkflowDraft(buildBranchWorkflow(workflowInput)); setWorkflowSource('manual'); setWorkflowError('') }
    catch (error) { setWorkflowDraft(null); setWorkflowError(error instanceof Error ? error.message : '草案检查失败。') }
  }
  const receiveExtraction = (value: unknown) => {
    try { setModelExtraction(verifySyntheticExtraction(value)); setWorkflowDraft(null); setWorkflowError('') }
    catch (error) { setModelExtraction(null); setWorkflowError(error instanceof Error ? error.message : '提取结果无效。') }
  }
  const acceptExtraction = () => {
    if (!modelExtraction) return
    try { setWorkflowDraft(buildBranchWorkflow(modelExtraction.fields, 'local_model')); setWorkflowSource('local_model'); setWorkflowError('') }
    catch (error) { setWorkflowDraft(null); setWorkflowError(error instanceof Error ? error.message : '草案检查失败。') }
  }

  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/workbench/v1/capabilities', { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Capability catalog unavailable')
        return response.json()
      })
      .then((catalog) => setIntegrations(catalog.integrations))
      .catch(() => { if (!controller.signal.aborted) setFailedCatalog(true) })
    return () => controller.abort()
  }, [])

  const section = categories[category]
  const usesExternal = category === 'chart' && provider === 'external'
  const canDraft = category === 'chart' || category === 'image'
  const currentPrompt = usesExternal ? externalPrompts[preset] : prompt
  const canSend = canDraft && !busy && (usesExternal
    ? consent && Boolean(external.base_url.trim() && external.model.trim() && external.api_key.trim())
    : Boolean(prompt.trim()))

  const changeCategory = (next: Category) => {
    if (next !== category) {
      setCategory(next)
      setPrompt('')
      setProposal(null)
      setConnector(null)
      setConsent(false)
    }
    setWorkspace('draw')
    setSettings(false)
  }
  const receive = (source: WorkbenchProvider) => (draft: WorkbenchProposal) => setProposal({ ...draft, provider: source })
  const submit = () => {
    if (!canSend) return
    setProposal(null)
    setConnector(null)
    if (usesExternal) {
      setConsent(false)
      onDraft('external', '', receive('external'), { ...external, preset, consent: true })
    } else {
      onDraft('local', prompt, receive('local'))
    }
  }
  const downloadSample = async (kind: 'r' | 'vector') => {
    setHandoffError('')
    setHandoffBusy(true)
    try {
      const response = await fetch(`/api/workbench/v1/${kind === 'r' ? 'r-sample' : 'vector-sample'}`, {
        method: 'POST', headers: kind === 'r' ? { 'Content-Type': 'application/json' } : undefined,
        body: kind === 'r' ? JSON.stringify({ title: '合成细胞响应' }) : undefined,
      })
      if (!response.ok) throw new Error(`生成失败（${response.status}），请检查本机绘图能力。`)
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = kind === 'r' ? 'biofigure-r-sample.pdf' : 'biofigure-editable-sample.svg'
      anchor.click()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      setHandoffError(error instanceof Error ? error.message : '文件交接失败。')
    } finally {
      setHandoffBusy(false)
    }
  }

  return (
    <div className="drawing-workbench" hidden={!visible}>
      <aside className="dw-sidebar">
        <div className="dw-brand"><span aria-hidden="true">✳</span><strong>BioFigure</strong><small>Studio</small></div>
        <nav className="dw-nav" aria-label="作图大类">
          <p className="dw-caption">作图大类</p>
          {(Object.keys(categories) as Category[]).map((key) => (
            <button key={key} aria-pressed={category === key && workspace === 'draw' && !settings} onClick={() => changeCategory(key)}>
              <span aria-hidden="true">{categories[key].icon}</span>{categories[key].label}
            </button>
          ))}
        </nav>
        <section className="dw-recent" aria-labelledby="dw-recent-title">
          <p className="dw-caption" id="dw-recent-title">近期项目 · 本次会话</p>
          {recent.length === 0 && <p className="dw-muted">最近打开的图表和图版将显示在这里。</p>}
          {recent.map((file) => <button key={file.name} title={file.name} onClick={() => onOpenProject(file)}>{file.name}</button>)}
          <button onClick={() => onOpenProject()}>＋ 打开已有项目</button>
        </section>
        <div className="dw-sidebar-footer"><button aria-pressed={settings} onClick={() => { setSettings(!settings); setConsent(false) }}>⚙ 工作台设置</button></div>
      </aside>

      <main className="dw-main">
        <div className="dw-top"><span>{settings ? '工作台设置' : workspace === 'generate' ? '论文示意图' : section.label}</span>{modeSwitch}</div>
        <WorkbenchSettings visible={settings} provider={provider} external={external}
          onProvider={(next) => { setProvider(next); setConsent(false); setProposal(null) }}
          onExternal={(next) => { setExternal(next); setConsent(false); setProposal(null) }}
          onConnect={onConnect} onDisconnect={onDisconnect} onClose={() => setSettings(false)} />
        {!settings && (
          <div className="dw-center">
            <div className="dw-intro">
              <p className="dw-caption">{workspace === 'generate' ? 'SCIENTIFIC ILLUSTRATION' : 'DRAWING WORKBENCH'}</p>
              <h1>{workspace === 'generate' ? '论文示意图' : section.title}</h1>
              <p>{workspace === 'generate' ? '把实验流程、机制关系与图形摘要做成可编辑的科研示意图。' : section.description}</p>
            </div>
            <form className="dw-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
              {workspace === 'generate' ? (
                <div className="dw-skill-form">
                  <div className="dw-illustration-tabs" role="group" aria-label="图示类型"><button type="button" aria-pressed={illustrationForm==='branch'} onClick={()=>setIllustrationForm('branch')}>双分支流程</button><button type="button" aria-pressed={illustrationForm==='timeline'} onClick={()=>setIllustrationForm('timeline')}>共享尺度时间轴</button></div>
                  {illustrationForm==='timeline' ? <><strong>共享尺度实验时间轴</strong><p>逐项填写时间点、两个组的采样、干预区间与阶段。数值决定间距；软件不会从文字推测实验事实。</p><TimelineFields value={timelineInput} disabled={busy} onChange={value=>{setTimelineInput(value);setTimelineDraft(null);setTimelineError('')}}/><div className="dw-quick"><button type="button" onClick={()=>{setTimelineInput(syntheticTimelineExample);setTimelineDraft(null);setTimelineError('')}}>填入合成示例</button><button type="button" className="dw-primary" onClick={()=>{try{setTimelineDraft(buildTimeline(timelineInput));setTimelineError('')}catch(error){setTimelineDraft(null);setTimelineError(error instanceof Error?error.message:'时间轴输入无效。')}}}>检查时间轴草案</button></div>{timelineError&&<p role="alert">{timelineError}</p>}</> : <><strong>双分支实验流程草案</strong>
                  <p>可让已审核的本机模型从固定合成段落逐字提取，再核对字段；也可手动填写已有步骤。不会上传数据或推断科学结论。</p>
                  <button type="button" disabled={busy} onClick={() => { setModelExtraction(null); setWorkflowDraft(null); setWorkflowError(''); onDraftIllustration(receiveExtraction, setWorkflowError) }}>从固定合成段落提取 · 本机模型</button>
                  {busy && <p role="status">本机任务正在处理，请稍候。</p>}
                  <p>手动填写</p>
                  <div className="dw-skill-grid">{branchWorkflowFields.map(({ key, label, max }) => <label key={key}>{label}
                    <input value={workflowInput[key]} maxLength={max} disabled={busy} onChange={(event) => { setWorkflowInput({ ...workflowInput, [key]: event.target.value }); setModelExtraction(null); setWorkflowDraft(null); setWorkflowError('') }} />
                  </label>)}</div>
                  <div className="dw-quick"><button type="button" disabled={busy} onClick={() => { setWorkflowInput(syntheticBranchExample); setModelExtraction(null); setWorkflowDraft(null); setWorkflowError('') }}>填入合成示例</button><button type="button" className="dw-primary" disabled={busy} onClick={prepareWorkflow}>检查结构化草案</button></div>
                  {workflowError && <p role="alert">{workflowError}</p>}</>}
                </div>
              ) : canDraft ? (
                <textarea aria-label="合成样例绘图指令" rows={3} maxLength={320} value={currentPrompt} readOnly={usesExternal}
                  placeholder={prompts[category]} onChange={(event) => { setPrompt(event.target.value); setProposal(null); setConnector(null) }} />
              ) : (
                <div className="dw-placeholder"><strong>{section.label}</strong><p>从本地编辑器继续。此类别的 AI 草案尚未开放。</p></div>
              )}
              <div className="dw-composer-bar">
                <div className="dw-switch" role="group" aria-label="AI 工作区">
                  <button type="button" aria-pressed={workspace === 'draw'} onClick={() => setWorkspace('draw')}>制图</button>
                  <button type="button" aria-pressed={workspace === 'generate'} onClick={() => { setWorkspace('generate'); setConsent(false) }}>生图</button>
                </div>
                {workspace === 'draw' && canDraft && <span className="dw-model">{usesExternal ? external.model || '外部模型 · 待配置' : '本机 · Ollama'}</span>}
                {workspace === 'draw' && canDraft && <button className="dw-primary" disabled={!canSend} type="submit">生成草案 <span aria-hidden="true">↑</span></button>}
                {workspace === 'generate' && <button type="button" onClick={() => onOpen('illustration')}>打开手动图示编辑器 ↗</button>}
                {workspace === 'draw' && !canDraft && <button type="button" className="dw-primary" onClick={() => onOpen(category)}>{section.local} ↗</button>}
              </div>
            </form>
            {workspace === 'generate' && illustrationForm==='branch' && modelExtraction && <section className="dw-card" aria-label="本机模型提取核对">
              <p className="dw-caption">本机模型提取 · 固定合成文本 · 待确认</p>
              <h2>逐字段核对原文</h2>
              <p className="dw-source-text">{modelExtraction.source_text}</p>
              <dl className="dw-extracted-fields">{branchWorkflowFields.map(({ key, label }) => <div key={key}><dt>{label}</dt><dd>{modelExtraction.fields[key]}</dd></div>)}</dl>
              <p>字段必须逐字来自上方原文。确认后才按固定版式生成结构化草案；所有科学状态仍为待核实。</p>
              <button type="button" className="dw-primary" disabled={busy} onClick={acceptExtraction}>确认字段，生成结构化草案</button>
            </section>}
            {workspace === 'generate' && illustrationForm==='branch' && workflowDraft && <section className="dw-card" aria-label="双分支流程草案">
              <p className="dw-caption">{workflowSource === 'local_model' ? '本机模型提取 + 固定版式' : '内置规则整理'} · 待核实</p><h2>{workflowDraft.title}</h2>
              <p>起始步骤 → {workflowDraft.sections[1].title} → A 结果<br />起始步骤 → {workflowDraft.sections[2].title} → B 结果</p>
              <ol>{workflowDraft.sections.map((item) => <li key={item.id}><strong>{item.title}：</strong>{item.description}</li>)}</ol>
              <p>5 个可编辑步骤、4 条箭头。全部标记为“待核实”，未附证据。进入编辑器后可修改文字、流程与状态，并导出 SVG。</p>
              {!canApply && <p role="status">当前有手动项目或图版，请保存后在单独会话应用草案。</p>}
              <button type="button" className="dw-primary" disabled={!canApply} onClick={() => onApplyIllustration(workflowDraft)}>确认进入图示编辑器 ↗</button>
            </section>}
            {workspace === 'generate' && illustrationForm==='timeline' && timelineDraft && <section className="dw-card" aria-label="时间轴草案"><p className="dw-caption">内置共享尺度规则 · 待核实</p><h2>{timelineDraft.title}</h2><p>{timelineDraft.timeline!.ticks.map(t=>t.label).join(' → ')}；{timelineDraft.timeline!.groups.map(g=>g.label).join('、')}；{timelineDraft.timeline!.intervals[0].label}：第 {timelineDraft.timeline!.intervals[0].start_day}–{timelineDraft.timeline!.intervals[0].end_day} 天。</p><p>进入编辑器后可修改全部时间轴字段，并保存项目或导出保留文字的 SVG。</p>{!canApply&&<p role="status">当前有手动项目或图版，请保存后在单独会话应用草案。</p>}<button type="button" className="dw-primary" disabled={!canApply} onClick={()=>onApplyIllustration(timelineDraft)}>确认进入图示编辑器 ↗</button></section>}
            {workspace === 'draw' && <>
              {usesExternal && <div className="dw-external">
                <label>合成示例 <select value={preset} onChange={(event) => { setPreset(event.target.value === 'line' ? 'line' : 'scatter'); setConsent(false); setProposal(null) }}>
                  <option value="scatter">散点图</option><option value="line">折线图</option>
                </select></label>
                <label><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
                  同意本次向所配置服务发送内置合成指令，服务可能计费。</label>
                {(!external.api_key || !external.model || !external.base_url) && <button onClick={() => setSettings(true)}>配置外部模型</button>}
              </div>}
              <div className="dw-connectors" aria-label="绘图连接器">
                <span className="dw-caption">连接器</span>
                {integrations.filter((entry) => section.connectors.includes(entry.id)).map((entry) => (
                  <button key={entry.id} aria-pressed={connector?.id === entry.id} onClick={() => setConnector(connector?.id === entry.id ? null : entry)}>
                    {entry.name} <small>{entry.mode === 'file' ? '文件交接' : entry.ready ? '已就绪' : '待配置'}</small>
                  </button>
                ))}
                {failedCatalog && <span className="dw-muted">暂时无法读取连接状态。</span>}
                <button onClick={() => setSettings(true)}>连接设置</button>
              </div>
              {connector && <section className="dw-card" aria-label={connector.name}>
                <h2>{connector.name}</h2><p>{connector.detail}</p>
                {connector.id === 'fiji' && connector.ready &&
                  <button className="dw-primary" onClick={onInspect}>确认检查合成 TIFF</button>}
                {connector.id === 'r' && connector.ready &&
                  <button className="dw-primary" disabled={handoffBusy} onClick={() => void downloadSample('r')}>生成并下载 R 合成散点 PDF</button>}
                {connector.mode === 'file' && <>
                  <p>文件交接：独立 SVG 可在 Inkscape 或 Illustrator 中继续编辑文字；当前不接收编辑后的文件，也不保存为 .bfsproj。</p>
                  <button className="dw-primary" disabled={handoffBusy} onClick={() => void downloadSample('vector')}>下载可编辑 SVG 合成样例</button>
                  <SvgHandoffInspector />
                </>}
                {handoffError && <p role="alert">{handoffError}</p>}
                <button onClick={() => onOpen(category)}>{section.local} ↗</button>
              </section>}
              {canDraft && <div className="dw-quick">
                {!usesExternal && <button onClick={() => { setPrompt(prompts[category]); setProposal(null) }}>使用合成指令</button>}
                {category === 'chart' && <button onClick={() => { setProposal(null); setConnector(null); onDraft('demo', '', receive('demo')) }}>打开内置草案</button>}
                <button onClick={() => onOpen(category)}>{section.local} ↗</button>
              </div>}
              {proposal?.action === 'chart' && (
                <section className="dw-card" aria-label="图表草案">
                  <p className="dw-caption">{({ local: '本机模型', external: '外部模型', demo: '内置合成示例' })[proposal.provider]} · 待确认</p>
                  <h2>{proposal.chart.title}</h2>
                  <p>{proposal.chart.chart_type === 'scatter' ? '散点图' : '折线图'} · {themeNames[proposal.chart.theme_id]} · X response / Y viability</p>
                  {!canApply && <p role="status">当前有手动项目或图版，请保存后在单独会话试用合成草案。</p>}
                  <div className="dw-quick">
                    <button disabled={!canApply} onClick={() => onApply(proposal.chart, false)}>继续手动编辑</button>
                    <button disabled={!canApply} className="dw-primary" onClick={() => onApply(proposal.chart, true)}>确认生成图表</button>
                  </div>
                </section>
              )}
              {proposal?.action === 'fiji_sample' && (
                <section className="dw-card" aria-label="Fiji 操作草案">
                  <p className="dw-caption">本机模型 · 待确认</p>
                  <h2>检查合成 TIFF</h2><p>通过 Fiji 读取内置样例的尺寸、像素类型和位深。</p>
                  <button className="dw-primary" onClick={onInspect}>确认检查并查看任务</button>
                </section>
              )}
            </>}
          </div>
        )}
      </main>
    </div>
  )
}
