export type ScientificStatus = 'illustrative' | 'verified' | 'needs_review'
export type EntityType = 'context' | 'molecule' | 'ligand' | 'receptor' | 'protein' | 'gene' | 'transcript' | 'drug'
export type RelationType = 'association' | 'activation' | 'inhibition' | 'binding' | 'translocation' | 'expression'
export type EvidenceType = 'literature' | 'experiment' | 'database_record' | 'user_note'
export type DocumentKind = 'mechanism' | 'graphical_abstract' | 'experimental_workflow'
export type SectionKind = 'panel' | 'step'
export type AnchorId = 'top' | 'right' | 'bottom' | 'left'
export type ComponentId = 'cell_generic' | 'nucleus_generic' | 'dna_helix' | 'rna_single' | 'protein_generic' | 'receptor_membrane' | 'ligand_generic' | 'drug_tablet'
export type IllustrationNode = { id:string; component_id:ComponentId; x:number; y:number; width:number; height:number; rotation:number; z_index:number; label:string; fill:string; text_color:string; scientific_status:ScientificStatus; entity_type:EntityType; evidence_ids:string[]; section_id:string|null }
export type IllustrationEdge = { id:string; source:{node_id:string;anchor_id:AnchorId}; target:{node_id:string;anchor_id:AnchorId}; relation:RelationType; routing:'orthogonal'; label:string; scientific_status:ScientificStatus; evidence_ids:string[] }
export type IllustrationEvidence = { id:string; evidence_type:EvidenceType; citation:string; locator:string; note:string; added_by:string; date:string }
export type IllustrationGroup = { id:string; name:string; node_ids:string[]; edge_ids:string[] }
export type IllustrationSection = { id:string; kind:SectionKind; title:string; description:string; x:number; y:number; width:number; height:number; scientific_status:ScientificStatus; evidence_ids:string[] }
export type FlowLink = { id:string; source_section_id:string; target_section_id:string; label:string }
export type IllustrationTimeline = { version:'timeline-shared-scale/1.0'; unit:'day'; ticks:{id:string;day:number;label:string}[]; groups:{id:string;label:string;sample_days:number[]}[]; intervals:{id:string;group_id:string;start_day:number;end_day:number;label:string}[]; stages:{id:string;start_day:number;end_day:number;label:string}[] }
export type IllustrationSpec = { spec_version:'1.3'; document_kind:DocumentKind; title:string; canvas:{width:number;height:number;background:string;grid_size:number;show_grid:boolean;snap_to_grid:boolean}; nodes:IllustrationNode[]; edges:IllustrationEdge[]; groups:IllustrationGroup[]; sections:IllustrationSection[]; flow_links:FlowLink[]; timeline?:IllustrationTimeline; evidence_records:IllustrationEvidence[]; provenance:{registry_version:'1.0';mechanism_schema_version:'1.0';composition_schema_version:'1.0';component_ids:ComponentId[];note:string} }
export type ComponentDefinition = { id:ComponentId; name:string; english:string; meaning:string; version:'1.0'; source:string; license:string; width:number; height:number; fill:string }
export type Point = {x:number;y:number}
export type Bounds = {x:number;y:number;width:number;height:number}

export const entityLabels:Record<EntityType,string> = {context:'上下文/容器',molecule:'分子',ligand:'配体',receptor:'受体',protein:'蛋白质',gene:'基因',transcript:'转录本',drug:'药物'}
export const relationLabels:Record<RelationType,string> = {association:'关联',activation:'激活',inhibition:'抑制',binding:'结合',translocation:'转位',expression:'表达/产生'}
export const evidenceLabels:Record<EvidenceType,string> = {literature:'文献',experiment:'实验',database_record:'数据库记录',user_note:'用户说明'}

export const componentRegistry:ComponentDefinition[] = [
  {id:'cell_generic',name:'通用细胞',english:'Generic cell',meaning:'抽象细胞轮廓，不代表特定细胞类型',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:190,height:130,fill:'#d7ece7'},
  {id:'nucleus_generic',name:'细胞核',english:'Nucleus',meaning:'抽象细胞核，不表达染色状态',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:110,height:82,fill:'#cfc8e8'},
  {id:'dna_helix',name:'DNA',english:'DNA helix',meaning:'教学式双链符号，不表达具体序列或构象',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:130,height:84,fill:'#6d91c9'},
  {id:'rna_single',name:'RNA',english:'RNA strand',meaning:'抽象单链 RNA，不表达具体转录本',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:130,height:70,fill:'#dc8e72'},
  {id:'protein_generic',name:'蛋白质',english:'Protein',meaning:'抽象折叠蛋白，不代表结构预测',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:110,height:82,fill:'#e4b96c'},
  {id:'receptor_membrane',name:'膜受体',english:'Membrane receptor',meaning:'通用跨膜受体，不代表具体家族',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:105,height:120,fill:'#79a3a0'},
  {id:'ligand_generic',name:'配体',english:'Ligand',meaning:'通用小型配体，不代表化学结构',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:70,height:58,fill:'#bc78a1'},
  {id:'drug_tablet',name:'药物',english:'Drug tablet',meaning:'通用药片，不代表具体药物或剂量',version:'1.0',source:'BioFigure Studio 原创',license:'项目许可证',width:92,height:54,fill:'#ef9b86'},
]

const componentEntity:Record<ComponentId,EntityType> = {cell_generic:'context',nucleus_generic:'context',dna_helix:'gene',rna_single:'transcript',protein_generic:'protein',receptor_membrane:'receptor',ligand_generic:'ligand',drug_tablet:'drug'}
export const defaultEntityType = (componentId:ComponentId) => componentEntity[componentId]
export const emptyIllustration = (kind:DocumentKind='mechanism'):IllustrationSpec => ({spec_version:'1.3',document_kind:kind,title:kind==='graphical_abstract'?'未命名图形摘要':kind==='experimental_workflow'?'未命名实验流程图':'未命名生物图示',canvas:{width:960,height:640,background:'#ffffff',grid_size:20,show_grid:true,snap_to_grid:true},nodes:[],edges:[],groups:[],sections:[],flow_links:[],evidence_records:[],provenance:{registry_version:'1.0',mechanism_schema_version:'1.0',composition_schema_version:'1.0',component_ids:[],note:'BioFigure Studio 原创组件；文字、流程和科学状态均由用户负责。'}})

const safeId = /^[A-Za-z0-9_-]{1,64}$/, color = /^#[0-9a-fA-F]{6}$/, isoDate = /^\d{4}-\d{2}-\d{2}$/, control = /[\r\n\0]/
const finite = (value:unknown):value is number => typeof value === 'number' && Number.isFinite(value)
const onlyKeys=(value:unknown, keys:string[],label:string)=>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error(`${label}格式无效。`);if(Object.keys(value).some(key=>!keys.includes(key)))throw new Error(`${label}含有未审核字段。`)}
export const normalizeRotation = (value:number) => ((value+180)%360+360)%360-180
export function rotatedBounds(node:IllustrationNode):Bounds { const r=node.rotation*Math.PI/180,w=Math.abs(node.width*Math.cos(r))+Math.abs(node.height*Math.sin(r)),h=Math.abs(node.width*Math.sin(r))+Math.abs(node.height*Math.cos(r)); return {x:node.x+(node.width-w)/2,y:node.y+(node.height-h)/2,width:w,height:h} }
export function selectionBounds(nodes:IllustrationNode[]):Bounds|null { if(!nodes.length)return null; const b=nodes.map(rotatedBounds),x=Math.min(...b.map(v=>v.x)),y=Math.min(...b.map(v=>v.y)),right=Math.max(...b.map(v=>v.x+v.width)),bottom=Math.max(...b.map(v=>v.y+v.height)); return {x,y,width:right-x,height:bottom-y} }
export function anchorPoint(node:IllustrationNode,anchor:AnchorId):Point { const p={top:{x:node.width/2,y:0},right:{x:node.width,y:node.height/2},bottom:{x:node.width/2,y:node.height},left:{x:0,y:node.height/2}}[anchor],c={x:node.width/2,y:node.height/2},r=node.rotation*Math.PI/180,dx=p.x-c.x,dy=p.y-c.y; return {x:node.x+c.x+dx*Math.cos(r)-dy*Math.sin(r),y:node.y+c.y+dx*Math.sin(r)+dy*Math.cos(r)} }
export function orthogonalPoints(source:Point,target:Point):Point[] { const horizontal=Math.abs(target.x-source.x)>=Math.abs(target.y-source.y),middle=horizontal?[{x:(source.x+target.x)/2,y:source.y},{x:(source.x+target.x)/2,y:target.y}]:[{x:source.x,y:(source.y+target.y)/2},{x:target.x,y:(source.y+target.y)/2}],points=[source,...middle,target].filter((p,i,a)=>i===0||p.x!==a[i-1].x||p.y!==a[i-1].y); return points.filter((p,i,a)=>i===0||i===a.length-1||!((a[i-1].x===p.x&&p.x===a[i+1].x)||(a[i-1].y===p.y&&p.y===a[i+1].y))) }
export const pointsPath = (points:Point[]) => points.map((value,index)=>`${index?'L':'M'} ${value.x} ${value.y}`).join(' ')

export function flowPoints(source:IllustrationSection,target:IllustrationSection):Point[] {
  const sx=source.x+source.width/2,sy=source.y+source.height/2,tx=target.x+target.width/2,ty=target.y+target.height/2
  if(Math.abs(tx-sx)>=Math.abs(ty-sy))return [{x:tx>=sx?source.x+source.width:source.x,y:sy},{x:tx>=sx?target.x:target.x+target.width,y:ty}]
  return [{x:sx,y:ty>=sy?source.y+source.height:source.y},{x:tx,y:ty>=sy?target.y:target.y+target.height}]
}

export function deleteUnreferencedEvidence(doc:IllustrationSpec,id:string):IllustrationSpec {
  if(!doc.evidence_records.some(item=>item.id===id))throw new Error('证据记录不存在。')
  if([...doc.nodes,...doc.edges,...doc.sections].some(item=>item.evidence_ids.includes(id)))throw new Error('证据仍被对象引用；请先逐项取消引用。')
  const next=structuredClone(doc)
  next.evidence_records=next.evidence_records.filter(item=>item.id!==id)
  return validateIllustration(next)
}

export type CompositionTemplate = 'abstract_two'|'abstract_three'|'workflow_horizontal'|'workflow_vertical'
export function compositionTemplate(kind:CompositionTemplate):Pick<IllustrationSpec,'document_kind'|'sections'|'flow_links'> {
  const abstract=kind.startsWith('abstract'), count=kind==='abstract_two'?2:3
  const positions=kind==='abstract_two'?[[40,105,420,430],[500,105,420,430]]:kind==='abstract_three'||kind==='workflow_horizontal'?[[40,105,280,430],[340,105,280,430],[640,105,280,430]]:[[180,35,600,155],[180,235,600,155],[180,435,600,155]]
  return {document_kind:abstract?'graphical_abstract':'experimental_workflow',sections:positions.slice(0,count).map(([x,y,width,height],index)=>({id:`section_${index+1}`,kind:abstract?'panel':'step',title:`${abstract?'面板':'步骤'} ${index+1}`,description:'',x,y,width,height,scientific_status:'illustrative',evidence_ids:[]})),flow_links:[]}
}

// React may run this update after pointerup clears the active gesture.
// Capture immutable inputs now; never read the live drag ref in the updater.
export function createNodeMoveUpdate(ids:readonly string[], dx:number, dy:number) {
  const selectedIds = new Set(ids)
  return (current:IllustrationSpec):IllustrationSpec => {
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) return current
    const bounds = selectionBounds(current.nodes.filter(node=>selectedIds.has(node.id)))
    if (!bounds) return current
    const assigned = current.nodes.filter(node=>selectedIds.has(node.id)&&node.section_id)
    const limits = assigned.map(node=>({node, section:current.sections.find(section=>section.id===node.section_id)!}))
    const minX = Math.max(-bounds.x, ...limits.map(({node,section})=>section.x-rotatedBounds(node).x))
    const maxX = Math.min(current.canvas.width-bounds.x-bounds.width, ...limits.map(({node,section})=>section.x+section.width-rotatedBounds(node).x-rotatedBounds(node).width))
    const minY = Math.max(-bounds.y, ...limits.map(({node,section})=>section.y-rotatedBounds(node).y))
    const maxY = Math.min(current.canvas.height-bounds.y-bounds.height, ...limits.map(({node,section})=>section.y+section.height-rotatedBounds(node).y-rotatedBounds(node).height))
    if(minX>maxX||minY>maxY)return current
    const x = Math.max(minX, Math.min(maxX, dx))
    const y = Math.max(minY, Math.min(maxY, dy))
    return {...current, nodes:current.nodes.map(node=>selectedIds.has(node.id)?{...node,x:node.x+x,y:node.y+y}:node)}
  }
}

export function migrateIllustration(value:unknown):{document:IllustrationSpec;migrated:boolean;warnings:string[]} {
  if(!value||typeof value!=='object')throw new Error('项目必须是 JSON 对象。')
  const raw=structuredClone(value) as Record<string,unknown>, warnings:string[]=[]
  if(raw.spec_version==='1.3')return {document:validateIllustration(raw),migrated:false,warnings}
  if(raw.spec_version!=='1.0'&&raw.spec_version!=='1.1'&&raw.spec_version!=='1.2')throw new Error('只支持 IllustrationSpec 1.0、1.1、1.2 或 1.3；不会静默迁移未知版本。')
  if(raw.spec_version==='1.2'){
    raw.nodes=((raw.nodes??[]) as Record<string,unknown>[]).map(node=>({...node,section_id:null}))
    raw.spec_version='1.3'; raw.document_kind='mechanism';raw.sections=[];raw.flow_links=[]
    raw.provenance={...(raw.provenance as object),composition_schema_version:'1.0'}
    return {document:validateIllustration(raw),migrated:true,warnings}
  }
  const oldVersion=raw.spec_version, canvas=raw.canvas as Record<string,unknown>, nodes=(raw.nodes??[]) as Record<string,unknown>[], edges=(raw.edges??[]) as Record<string,unknown>[]
  raw.canvas=oldVersion==='1.0'?{...canvas,grid_size:20,show_grid:true,snap_to_grid:true}:canvas
  raw.nodes=nodes.map(node=>{const status=node.scientific_status==='verified'?'needs_review':node.scientific_status;if(node.scientific_status==='verified')warnings.push(`${String(node.id)} 因缺少证据已改为待核实`);return {...node,rotation:oldVersion==='1.0'?0:node.rotation,entity_type:defaultEntityType(node.component_id as ComponentId),evidence_ids:[],scientific_status:status}})
  raw.edges=edges.map(edge=>{const status=edge.scientific_status==='verified'?'needs_review':edge.scientific_status;if(edge.scientific_status==='verified')warnings.push(`${String(edge.id)} 因缺少证据已改为待核实`);return {...edge,routing:'orthogonal',relation:edge.relation==='normal'?'association':edge.relation,evidence_ids:[],scientific_status:status}})
  raw.spec_version='1.2'; raw.evidence_records=[]; raw.provenance={...(raw.provenance as object),mechanism_schema_version:'1.0'}
  const migrated=migrateIllustration(raw)
  return {document:migrated.document,migrated:true,warnings:[...warnings,...migrated.warnings]}
}

export function validateIllustration(value:unknown):IllustrationSpec {
  if(!value||typeof value!=='object')throw new Error('项目必须是 JSON 对象。')
  const doc=value as IllustrationSpec
  if(doc.spec_version!=='1.3'||!['mechanism','graphical_abstract','experimental_workflow'].includes(doc.document_kind))throw new Error('项目需先显式迁移为 IllustrationSpec 1.3。')
  onlyKeys(doc,['spec_version','document_kind','title','canvas','nodes','edges','groups','sections','flow_links','timeline','evidence_records','provenance'],'项目')
  if(!doc.title||doc.title.length>120||control.test(doc.title))throw new Error('项目标题无效。')
  const c=doc.canvas
  if(c)onlyKeys(c,['width','height','background','grid_size','show_grid','snap_to_grid'],'画布')
  if(!c||!Number.isInteger(c.width)||!Number.isInteger(c.height)||c.width<320||c.width>2400||c.height<240||c.height>1800||!color.test(c.background)||!Number.isInteger(c.grid_size)||c.grid_size<4||c.grid_size>100||typeof c.show_grid!=='boolean'||typeof c.snap_to_grid!=='boolean')throw new Error('画布尺寸、背景或网格设置无效。')
  if(!Array.isArray(doc.nodes)||doc.nodes.length>200||!Array.isArray(doc.edges)||doc.edges.length>400||!Array.isArray(doc.groups)||doc.groups.length>100||!Array.isArray(doc.sections)||doc.sections.length>8||!Array.isArray(doc.flow_links)||doc.flow_links.length>16||!Array.isArray(doc.evidence_records)||doc.evidence_records.length>300)throw new Error('项目对象或证据数量超过安全上限。')
  if(doc.timeline!==undefined){
    const timeline=doc.timeline
    onlyKeys(timeline,['version','unit','ticks','groups','intervals','stages'],'时间轴')
    if(doc.document_kind!=='experimental_workflow'||c.width!==960||c.height!==640||doc.nodes.length||doc.edges.length||doc.groups.length||doc.sections.length||doc.flow_links.length||timeline.version!=='timeline-shared-scale/1.0'||timeline.unit!=='day'||!Array.isArray(timeline.ticks)||timeline.ticks.length<2||timeline.ticks.length>8||!Array.isArray(timeline.groups)||timeline.groups.length!==2||!Array.isArray(timeline.intervals)||timeline.intervals.length!==1||!Array.isArray(timeline.stages)||timeline.stages.length!==timeline.ticks.length-1)throw new Error('时间轴结构无效；请使用 960×640 画布、两个组、明确刻度、阶段和一段干预。')
    const label=(value:unknown,max:number)=>typeof value==='string'&&!!value.trim()&&value.length<=max&&!control.test(value)
    const labelWidth=(value:string,size:number)=>Array.from(value).reduce((width,char)=>width+(char.codePointAt(0)!<128?size*.55:size),0)
    const days:number[]=[],usedIds=new Set<string>()
    for(const tick of timeline.ticks){onlyKeys(tick,['id','day','label'],'时间刻度');if(!safeId.test(tick.id)||usedIds.has(tick.id)||!Number.isInteger(tick.day)||tick.day<0||tick.day>365||!label(tick.label,24)||days.length&&tick.day<=days.at(-1)!)throw new Error('时间刻度须为 0–365 的严格递增整数天数，并填写简短标签。');usedIds.add(tick.id);days.push(tick.day)}
    const x=(day:number)=>140+(day-days[0])/(days.at(-1)!-days[0])*680
    if(days.some((day,index)=>index>0&&x(day)-x(days[index-1])<48))throw new Error('相邻时间点距离过近；请缩小时间范围或减少刻度。')
    const tickLanes=timeline.ticks.map((tick,index)=>index>0&&x(tick.day)-x(days[index-1])<90?index%2:0)
    for(let index=0;index<timeline.ticks.length;index++){
      const tick=timeline.ticks[index],width=labelWidth(tick.label,15)
      if(x(tick.day)-width/2<16||x(tick.day)+width/2>c.width-16)throw new Error('刻度标签超出画布；请缩短文字。')
      for(let previous=0;previous<index;previous++)if(tickLanes[index]===tickLanes[previous]&&x(tick.day)-x(days[previous])<(width+labelWidth(timeline.ticks[previous].label,15))/2+10)throw new Error('刻度标签过密；请缩短文字或调整时间点。')
    }
    const groupIds=new Set<string>()
    for(const group of timeline.groups){onlyKeys(group,['id','label','sample_days'],'实验组');if(!safeId.test(group.id)||usedIds.has(group.id)||!label(group.label,22)||labelWidth(group.label,15)>105||!Array.isArray(group.sample_days)||!group.sample_days.length||group.sample_days.length>days.length||group.sample_days.some((day,index)=>!days.includes(day)||index>0&&day<=group.sample_days[index-1]))throw new Error('实验组名称或采样时刻无效；请缩短组名，并把采样天数按顺序列在刻度中。');usedIds.add(group.id);groupIds.add(group.id)}
    const interval=timeline.intervals[0];onlyKeys(interval,['id','group_id','start_day','end_day','label'],'干预区间');if(!safeId.test(interval.id)||usedIds.has(interval.id)||!groupIds.has(interval.group_id)||!days.includes(interval.start_day)||!days.includes(interval.end_day)||interval.start_day>=interval.end_day||!label(interval.label,28))throw new Error('干预区间须指定实验组、起止刻度和名称。');usedIds.add(interval.id)
    if(labelWidth(interval.label,14)>x(interval.end_day)-x(interval.start_day)-12)throw new Error('干预名称长于区间；请缩短文字或调整时间点。')
    for(let index=0;index<timeline.stages.length;index++){const stage=timeline.stages[index];onlyKeys(stage,['id','start_day','end_day','label'],'阶段');if(!safeId.test(stage.id)||usedIds.has(stage.id)||stage.start_day!==days[index]||stage.end_day!==days[index+1]||!label(stage.label,28))throw new Error('请为每对相邻时间点填写阶段说明。');usedIds.add(stage.id)}
    for(const stage of timeline.stages)if(labelWidth(stage.label,14)>x(stage.end_day)-x(stage.start_day)-12)throw new Error('阶段说明长于对应时间段；请缩短文字或调整时间点。')
  }
  const evidenceIds=new Set<string>()
  for(const e of doc.evidence_records){onlyKeys(e,['id','evidence_type','citation','locator','note','added_by','date'],'证据');if(!safeId.test(e.id)||evidenceIds.has(e.id)||!Object.keys(evidenceLabels).includes(e.evidence_type)||!e.citation||e.citation.length>500||control.test(e.citation)||e.locator.length>200||e.note.length>200||!e.added_by||e.added_by.length>200||[e.locator,e.note,e.added_by].some(v=>control.test(v))||!isoDate.test(e.date))throw new Error('证据记录格式无效或 ID 重复。');evidenceIds.add(e.id)}
  const ids=new Set<string>(),known=new Set(componentRegistry.map(value=>value.id))
  const sections=new Map<string,IllustrationSection>()
  if(doc.document_kind==='mechanism'&&(doc.sections.length||doc.flow_links.length))throw new Error('机制图不能包含摘要分区或流程箭头。')
  if(doc.document_kind==='graphical_abstract'&&doc.sections.length>6)throw new Error('图形摘要最多六个面板。')
  if(doc.document_kind!=='mechanism'&&doc.sections.length===1)throw new Error('摘要或流程至少需要两个分区；请从空白模板开始。')
  for(const section of doc.sections){
    onlyKeys(section,['id','kind','title','description','x','y','width','height','scientific_status','evidence_ids'],'面板或步骤')
    if(!safeId.test(section.id)||sections.has(section.id)||section.kind!==(doc.document_kind==='graphical_abstract'?'panel':'step')||!section.title||section.title.length>80||control.test(section.title)||typeof section.description!=='string'||section.description.length>300||control.test(section.description)||![section.x,section.y,section.width,section.height].every(finite)||section.width<100||section.height<100||section.x<0||section.y<0||section.x+section.width>c.width||section.y+section.height>c.height||!['illustrative','needs_review','verified'].includes(section.scientific_status)||!Array.isArray(section.evidence_ids)||section.evidence_ids.length>20||section.evidence_ids.some(id=>!evidenceIds.has(id)))throw new Error('面板或步骤格式、边界、状态或证据无效。')
    if(section.scientific_status==='verified'&&!section.evidence_ids.length)throw new Error('用户已核实的面板或步骤必须引用证据。')
    const chars=Math.max(8,Math.floor((section.width-32)/14))
    if((section.title.length+(section.kind==='step'?3:0))*18>section.width-36||Math.ceil(section.description.length/chars)>Math.floor((section.height-85)/20))throw new Error('面板或步骤文字超出固定版式；请缩短文字或扩大分区。')
    for(const other of sections.values())if(section.x<other.x+other.width&&section.x+section.width>other.x&&section.y<other.y+other.height&&section.y+section.height>other.y)throw new Error('面板或步骤不能重叠。')
    sections.set(section.id,section)
  }
  if(doc.document_kind!=='experimental_workflow'&&doc.flow_links.length)throw new Error('流程箭头只能用于实验流程图。')
  const flowIds=new Set<string>(), flowPairs=new Set<string>()
  for(const link of doc.flow_links){onlyKeys(link,['id','source_section_id','target_section_id','label'],'流程箭头');const source=doc.sections.findIndex(section=>section.id===link.source_section_id),target=doc.sections.findIndex(section=>section.id===link.target_section_id),pair=`${link.source_section_id}:${link.target_section_id}`;if(!safeId.test(link.id)||flowIds.has(link.id)||source<0||target<=source||flowPairs.has(pair)||typeof link.label!=='string'||link.label.length>120||control.test(link.label))throw new Error('流程顺序箭头 ID、步骤顺序或标签无效。');flowIds.add(link.id);flowPairs.add(pair)}
  doc.nodes.forEach(n=>onlyKeys(n,['id','component_id','x','y','width','height','rotation','z_index','label','fill','text_color','scientific_status','entity_type','evidence_ids','section_id'],'节点'))
  doc.edges.forEach(e=>{onlyKeys(e,['id','source','target','relation','routing','label','scientific_status','evidence_ids'],'机制关系');onlyKeys(e.source,['node_id','anchor_id'],'关系起点');onlyKeys(e.target,['node_id','anchor_id'],'关系终点')})
  doc.groups.forEach(g=>onlyKeys(g,['id','name','node_ids','edge_ids'],'分组'))
  if(doc.provenance)onlyKeys(doc.provenance,['registry_version','mechanism_schema_version','composition_schema_version','component_ids','note'],'来源清单')
  for(const n of doc.nodes){if(!safeId.test(n.id)||ids.has(n.id))throw new Error('节点 ID 无效或重复。');ids.add(n.id);if(!known.has(n.component_id)||![n.x,n.y,n.width,n.height,n.rotation].every(finite)||n.width<24||n.width>800||n.height<24||n.height>800||n.rotation<-180||n.rotation>180)throw new Error('节点未知，或位置、尺寸、旋转无效。');const b=rotatedBounds(n);if(b.x<-.001||b.y<-.001||b.x+b.width>c.width+.001||b.y+b.height>c.height+.001)throw new Error('旋转后的节点超出画布。');if(!Number.isInteger(n.z_index)||n.z_index<0||n.z_index>999||typeof n.label!=='string'||n.label.length>200||control.test(n.label)||!color.test(n.fill)||!color.test(n.text_color)||!['illustrative','verified','needs_review'].includes(n.scientific_status)||!Object.keys(entityLabels).includes(n.entity_type)||!Array.isArray(n.evidence_ids)||n.evidence_ids.length>20||n.evidence_ids.some(id=>!evidenceIds.has(id)))throw new Error('节点样式、实体、文字、状态或证据无效。');if(n.scientific_status==='verified'&&!n.evidence_ids.length)throw new Error('用户已核实的节点必须引用至少一条证据。')}
  for(const node of doc.nodes){if(node.section_id!==null){const section=sections.get(node.section_id);const b=rotatedBounds(node);if(!section||b.x<section.x||b.y<section.y||b.x+b.width>section.x+section.width||b.y+b.height>section.y+section.height)throw new Error('节点必须完整位于所属面板或步骤内。')}}
  const edgeIds=new Set<string>()
  for(const e of doc.edges){if(!safeId.test(e.id)||edgeIds.has(e.id)||!ids.has(e.source.node_id)||!ids.has(e.target.node_id)||!['top','right','bottom','left'].includes(e.source.anchor_id)||!['top','right','bottom','left'].includes(e.target.anchor_id)||e.routing!=='orthogonal'||!Object.keys(relationLabels).includes(e.relation)||typeof e.label!=='string'||e.label.length>200||control.test(e.label)||!['illustrative','verified','needs_review'].includes(e.scientific_status)||!Array.isArray(e.evidence_ids)||e.evidence_ids.length>20||e.evidence_ids.some(id=>!evidenceIds.has(id)))throw new Error('关系 ID、端点、类型、状态或证据无效。');if(e.scientific_status==='verified'&&!e.evidence_ids.length)throw new Error('用户已核实的关系必须引用至少一条证据。');edgeIds.add(e.id)}
  const grouped=new Set<string>(),groupIds=new Set<string>()
  for(const g of doc.groups){if(!safeId.test(g.id)||groupIds.has(g.id)||!g.name||g.name.length>80||!Array.isArray(g.node_ids)||!g.node_ids.length||g.node_ids.some(id=>!ids.has(id)||grouped.has(id))||g.edge_ids.some(id=>!edgeIds.has(id)))throw new Error('分组包含重复或不存在的对象。');groupIds.add(g.id);g.node_ids.forEach(id=>grouped.add(id))}
  const used=[...new Set(doc.nodes.map(n=>n.component_id))].sort(),listed=[...(doc.provenance?.component_ids??[])].sort()
  if(doc.provenance?.registry_version!=='1.0'||doc.provenance?.mechanism_schema_version!=='1.0'||doc.provenance?.composition_schema_version!=='1.0'||JSON.stringify(used)!==JSON.stringify(listed))throw new Error('组件或机制来源清单与项目不一致。')
  return structuredClone(doc)
}
