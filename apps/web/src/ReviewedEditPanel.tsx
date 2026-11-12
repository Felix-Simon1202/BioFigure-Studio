import { useState } from 'react'
import { useI18n } from './i18n'
import type { IllustrationSpec } from './illustration'
import './ReviewedEditPanel.css'

type Proposal = { document: IllustrationSpec; changes: { target: string; field: string; before: unknown; after: unknown }[] }
export default function ReviewedEditPanel({ document, selected, apply }: {
  document: IllustrationSpec; selected: string[]; apply: (next: IllustrationSpec, before: string) => void
}) {
  const { t } = useI18n()
  const [prompt, setPrompt] = useState(''), [provider, setProvider] = useState('rules')
  const [proposal, setProposal] = useState<{value:Proposal;before:string;selection:string}|null>(null)
  const [pending,setPending]=useState(false),[error,setError]=useState('')
  const stale=proposal&&(proposal.before!==JSON.stringify(document)||proposal.selection!==JSON.stringify(selected))
  const prepare=async()=>{
    setPending(true);setError('');setProposal(null)
    const before=JSON.stringify(document),selection=JSON.stringify(selected)
    try {
      const response=await fetch('/api/figure-workflow/v1/edit-preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({document,selected_ids:selected,prompt,provider})})
      if(!response.ok)throw new Error('invalid')
      setProposal({value:await response.json(),before,selection})
    }catch{setError(t('无法生成修改：请选择未核实对象，核对指令、坐标和尺寸。本机模型模式需要已核验的本地模型。','Could not propose an edit. Select unverified nodes and check the command, bounds and dimensions. Model mode requires the reviewed local model.'))}
    finally{setPending(false)}
  }
  const fields:Record<string,string>={fill:t('颜色','Color'),label:t('标签','Label'),x:'X',y:'Y',width:t('宽度','Width'),height:t('高度','Height')}
  return <section className="ill-summary" aria-label={t('Biodot 局部改图','Biodot reviewed edit')}>
    <p>{t('先选择节点，再预览修改。原始数据、未选中对象和证据不变；已核实对象受保护。','Select nodes, then preview changes. Source data, unselected objects and evidence stay intact. Verified objects are protected.')}</p>
    <label>{t('解析方式','Proposal method')}<select value={provider} onChange={e=>{setProvider(e.target.value);setProposal(null)}}><option value="rules">{t('本地指令（不调用模型）','Local commands (no model)')}</option><option value="local">{t('Biodot · 本机模型','Biodot · local model')}</option></select></label>
    <label>{t('修改指令','Edit request')}<textarea value={prompt} placeholder={t('例如：颜色 #1971c2；或 移动 100,120','For example: color #1971c2; or move 100,120')} onChange={e=>{setPrompt(e.target.value);setProposal(null)}}/></label>
    <div className="ill-composition-modes">{[
      [t('改色','Color'),t('颜色 #1971c2','color #1971c2')],[t('改标签','Label'),t('标签：新标签','label: New label')],[t('移动','Move'),t('移动 100,120','move 100,120')],[t('对齐','Align'),t('左对齐','align left')],[t('尺寸','Size'),t('尺寸 120,80','size 120,80')],
    ].map(([label,example])=><button key={example} type="button" onClick={()=>{setPrompt(example);setProposal(null)}}>{label}</button>)}</div>
    <button type="button" disabled={pending||!selected.length||!prompt.trim()} onClick={()=>void prepare()}>{t('预览修改','Preview edit')}</button>
    {error&&<p role="alert">{error}</p>}
    {proposal&&<><p>{t('以下仅为草案，请核对后确认。修改后可使用编辑器的撤销。','This is a proposal. Review before confirming; the editor Undo restores the previous drawing.')}</p>
      <ul>{proposal.value.changes.map((change,index)=><li key={index}>{document.nodes.find(node=>node.id===change.target)?.label||change.target} · {fields[change.field]||change.field}: {String(change.before)} → {String(change.after)}</li>)}</ul>
      {stale&&<p role="status">{t('文档或选择已变化，请重新预览。','Document or selection changed. Preview again.')}</p>}
      <button type="button" disabled={Boolean(stale)||!proposal.value.changes.length} onClick={()=>{apply(proposal.value.document,proposal.before);setProposal(null)}}>{t('确认应用修改','Confirm and apply edit')}</button>
    </>}
  </section>
}
