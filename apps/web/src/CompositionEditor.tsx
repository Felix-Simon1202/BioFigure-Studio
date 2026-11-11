import { useState } from 'react'
import { compositionTemplate, type CompositionTemplate, type DocumentKind, type IllustrationSection, type IllustrationSpec } from './illustration'

type Props = {
  doc: IllustrationSpec
  selectedSectionId: string
  selectSection: (id:string)=>void
  commit: (next:IllustrationSpec, notice?:string)=>void
  notify: (message:string)=>void
  nextId: (prefix:string)=>string
  resetDocument: (kind:DocumentKind)=>void
}

export default function CompositionEditor({doc,selectedSectionId,selectSection,commit,notify,nextId,resetDocument}:Props){
  const [flowSource,setFlowSource]=useState(''),[flowTarget,setFlowTarget]=useState('')
  const selected=doc.sections.find(section=>section.id===selectedSectionId)
  const update=(change:(section:IllustrationSection)=>void)=>{if(!selected)return;const next=structuredClone(doc);change(next.sections.find(section=>section.id===selected.id)!);commit(next)}
  const insert=(kind:CompositionTemplate)=>{
    if(doc.nodes.length||doc.edges.length||doc.sections.length||doc.flow_links.length)return notify('布局模板只能插入空白项目；请先新建文档。')
    const next={...structuredClone(doc),...compositionTemplate(kind)}
    commit(next,'已插入原创空白布局；没有组件、科学关系、流程箭头或结论。')
    selectSection(next.sections[0].id)
  }
  const addSection=()=>{
    if(doc.document_kind==='mechanism')return notify('请先选择摘要或实验流程模式。')
    const limit=doc.document_kind==='graphical_abstract'?6:8
    if(doc.sections.length<2)return notify('请先选用一个空白布局模板。')
    if(doc.sections.length>=limit)return notify(`此模式最多 ${limit} 个分区。`)
    if(doc.nodes.some(node=>node.section_id))return notify('先解除组件的分区归属，再使用“增加并重排”。')
    const next=structuredClone(doc),index=next.sections.length,cols=doc.document_kind==='graphical_abstract'?Math.min(3,index+1):2,rows=Math.ceil((index+1)/cols),width=(880-(cols-1)*20)/cols,height=(540-(rows-1)*20)/rows
    next.sections.push({id:nextId('section'),kind:doc.document_kind==='graphical_abstract'?'panel':'step',title:`${doc.document_kind==='graphical_abstract'?'面板':'步骤'} ${index+1}`,description:'',x:0,y:0,width,height,scientific_status:'illustrative',evidence_ids:[]})
    next.sections.forEach((section,i)=>{section.x=40+(i%cols)*(width+20);section.y=50+Math.floor(i/cols)*(height+20);section.width=width;section.height=height})
    commit(next,'已增加分区并重新排版；请检查各分区文字和流程顺序。')
  }
  const deleteSection=()=>{
    if(!selected)return
    if(doc.sections.length<=2)return notify('摘要或流程至少保留两个分区。')
    if(doc.nodes.some(node=>node.section_id===selected.id))return notify('此分区仍含组件，请先在节点检查器中解除归属。')
    const next=structuredClone(doc)
    next.sections=next.sections.filter(section=>section.id!==selected.id)
    next.flow_links=next.flow_links.filter(link=>link.source_section_id!==selected.id&&link.target_section_id!==selected.id)
    commit(next,'已删除分区及其流程箭头。')
    selectSection('')
  }
  const reorder=(direction:-1|1)=>{
    if(!selected)return
    const next=structuredClone(doc),index=next.sections.findIndex(section=>section.id===selected.id),target=index+direction
    if(target<0||target>=next.sections.length)return
    const position={x:next.sections[index].x,y:next.sections[index].y,width:next.sections[index].width,height:next.sections[index].height},other=next.sections[target]
    const otherPosition={x:other.x,y:other.y,width:other.width,height:other.height}
    Object.assign(next.sections[index],otherPosition)
    Object.assign(other,position)
    ;[next.sections[index],next.sections[target]]=[next.sections[target],next.sections[index]]
    commit(next,'已调整步骤顺序；流程箭头需仍沿正向。')
  }
  const addFlow=()=>{
    if(!flowSource||!flowTarget)return notify('请明确选择流程起点与终点。')
    const next=structuredClone(doc)
    next.flow_links.push({id:nextId('flow'),source_section_id:flowSource,target_section_id:flowTarget,label:''})
    commit(next,'流程顺序箭头已创建；它不表示科学机制关系。')
  }
  return <section className="ill-inspector ill-composition" aria-label="摘要与流程编辑">
    <h2>图形摘要与实验流程</h2>
    <p>选择文档类型，再明确填写分区、步骤和流程顺序。模板不含实验参数或科学结论。</p>
    <div className="ill-composition-modes"><button className={doc.document_kind==='mechanism'?'active':''} onClick={()=>resetDocument('mechanism')}>机制图</button><button className={doc.document_kind==='graphical_abstract'?'active':''} onClick={()=>resetDocument('graphical_abstract')}>图形摘要</button><button className={doc.document_kind==='experimental_workflow'?'active':''} onClick={()=>resetDocument('experimental_workflow')}>实验流程图</button></div>
    {doc.document_kind!=='mechanism'&&<>
      <h3>原创空白布局</h3>
      <div className="ill-composition-modes">{doc.document_kind==='graphical_abstract'?<><button onClick={()=>insert('abstract_two')}>双栏摘要</button><button onClick={()=>insert('abstract_three')}>三栏摘要</button></>:<><button onClick={()=>insert('workflow_horizontal')}>横向三步</button><button onClick={()=>insert('workflow_vertical')}>纵向三步</button></>}</div>
      <button onClick={addSection}>增加并重排{doc.document_kind==='graphical_abstract'?'面板':'步骤'}</button>
      <h3>{doc.document_kind==='graphical_abstract'?'面板':'步骤'}列表</h3>
      <div className="ill-section-list">{doc.sections.map((section,index)=><button key={section.id} className={selectedSectionId===section.id?'active':''} onClick={()=>selectSection(section.id)}>{index+1}. {section.title}</button>)}</div>
      {selected&&<div className="ill-section-fields"><h3>编辑{selected.kind==='panel'?'面板':'步骤'}</h3><label>标题<input value={selected.title} maxLength={80} onChange={event=>update(section=>{section.title=event.target.value})}/></label><label>说明<textarea value={selected.description} maxLength={300} onChange={event=>update(section=>{section.description=event.target.value})}/></label><div className="ill-dimensions">{(['x','y','width','height'] as const).map(key=><label key={key}>{key}<input type="number" value={selected[key]} onChange={event=>update(section=>{section[key]=Number(event.target.value)})}/></label>)}</div><label>科学状态<select value={selected.scientific_status} onChange={event=>update(section=>{section.scientific_status=event.target.value as IllustrationSection['scientific_status']})}><option value="illustrative">示意</option><option value="needs_review">待核实</option><option value="verified">用户已核实</option></select></label><div className="ill-composition-modes">{selected.kind==='step'&&<><button onClick={()=>reorder(-1)}>前移</button><button onClick={()=>reorder(1)}>后移</button></>}<button className="ill-danger" onClick={deleteSection}>删除分区</button></div></div>}
      {doc.document_kind==='experimental_workflow'&&<><h3>流程顺序箭头</h3><p>仅表示用户指定的步骤展示顺序；与六类机制关系分开。</p><div className="ill-composition-modes"><label>起点<select value={flowSource} onChange={event=>setFlowSource(event.target.value)}><option value="">选择步骤</option>{doc.sections.map(section=><option key={section.id} value={section.id}>{section.title}</option>)}</select></label><label>终点<select value={flowTarget} onChange={event=>setFlowTarget(event.target.value)}><option value="">选择步骤</option>{doc.sections.map(section=><option key={section.id} value={section.id}>{section.title}</option>)}</select></label><button onClick={addFlow}>添加流程箭头</button></div>{doc.flow_links.map(link=><div className="ill-flow-row" key={link.id}><span>{doc.sections.find(section=>section.id===link.source_section_id)?.title} → {doc.sections.find(section=>section.id===link.target_section_id)?.title}</span><input aria-label="流程标签" value={link.label} maxLength={120} onChange={event=>{const next=structuredClone(doc);next.flow_links.find(item=>item.id===link.id)!.label=event.target.value;commit(next)}}/><button className="ill-danger" onClick={()=>{const next=structuredClone(doc);next.flow_links=next.flow_links.filter(item=>item.id!==link.id);commit(next,'流程箭头已删除。')}}>删除</button></div>)}</>}
    </>}
  </section>
}
