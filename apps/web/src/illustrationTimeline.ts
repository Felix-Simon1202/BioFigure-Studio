import { emptyIllustration, validateIllustration, type IllustrationSpec, type IllustrationTimeline } from './illustration'

export type TimelineInput = { title:string; days:string; tickLabels:string; stageLabels:string; groupA:string; samplesA:string; groupB:string; samplesB:string; intervalGroup:'group_a'|'group_b'; intervalStart:string; intervalEnd:string; intervalLabel:string }
export const syntheticTimelineExample:TimelineInput={title:'合成实验时间轴',days:'0, 2, 9',tickLabels:'第 0 天, 第 2 天, 第 9 天',stageLabels:'准备阶段, 处理阶段',groupA:'对照组',samplesA:'0, 2, 9',groupB:'处理组',samplesB:'0, 2, 9',intervalGroup:'group_b',intervalStart:'2',intervalEnd:'9',intervalLabel:'示例干预'}
export const emptyTimelineInput:TimelineInput={title:'',days:'',tickLabels:'',stageLabels:'',groupA:'',samplesA:'',groupB:'',samplesB:'',intervalGroup:'group_b',intervalStart:'',intervalEnd:'',intervalLabel:''}
const split=(value:string)=>value.split(/[,，]/).map(part=>part.trim())
const integer=(value:string,label:string)=>{if(!/^\d+$/.test(value))throw new Error(`${label}须填写非负整数天数。`);return Number(value)}
const dayList=(value:string,label:string)=>split(value).map(part=>integer(part,label))
export function buildTimeline(input:TimelineInput):IllustrationSpec {
  const days=dayList(input.days,'时间点'),tickLabels=split(input.tickLabels),stageLabels=split(input.stageLabels)
  if(days.length<2||days.length>8)throw new Error('请填写 2–8 个时间点。')
  if(tickLabels.length!==days.length)throw new Error('刻度标签数量须与时间点相同。')
  if(stageLabels.length!==days.length-1)throw new Error('阶段说明数量须比时间点少一个。')
  const timeline:IllustrationTimeline={version:'timeline-shared-scale/1.0',unit:'day',ticks:days.map((day,index)=>({id:`tick_${index}`,day,label:tickLabels[index]})),groups:[{id:'group_a',label:input.groupA.trim(),sample_days:dayList(input.samplesA,'对照组采样')},{id:'group_b',label:input.groupB.trim(),sample_days:dayList(input.samplesB,'处理组采样')}],intervals:[{id:'intervention_1',group_id:input.intervalGroup,start_day:integer(input.intervalStart,'干预开始'),end_day:integer(input.intervalEnd,'干预结束'),label:input.intervalLabel.trim()}],stages:stageLabels.map((label,index)=>({id:`stage_${index}`,start_day:days[index],end_day:days[index+1],label}))}
  const doc=emptyIllustration('experimental_workflow');doc.title=input.title.trim();doc.canvas.show_grid=false;doc.timeline=timeline;doc.provenance.note='[timeline-shared-scale/1.0] 用户填写时间点、采样、干预与阶段；图示不推断科学事实。'
  return validateIllustration(doc)
}
export function timelineToInput(doc:IllustrationSpec):TimelineInput {
  const value=doc.timeline;if(!value)throw new Error('项目没有时间轴。')
  return {title:doc.title,days:value.ticks.map(t=>t.day).join(', '),tickLabels:value.ticks.map(t=>t.label).join(', '),stageLabels:value.stages.map(s=>s.label).join(', '),groupA:value.groups[0].label,samplesA:value.groups[0].sample_days.join(', '),groupB:value.groups[1].label,samplesB:value.groups[1].sample_days.join(', '),intervalGroup:value.intervals[0].group_id as 'group_a'|'group_b',intervalStart:String(value.intervals[0].start_day),intervalEnd:String(value.intervals[0].end_day),intervalLabel:value.intervals[0].label}
}

export function timelineGeometry(value:IllustrationTimeline) {
  const first=value.ticks[0].day,last=value.ticks.at(-1)!.day
  const x=(day:number)=>140+(day-first)/(last-first)*680
  const ticks=value.ticks.map((tick,index)=>({...tick,x:x(tick.day),labelY:index>0&&x(tick.day)-x(value.ticks[index-1].day)<90?index%2?258:238:238}))
  const stages=value.stages.map(stage=>({...stage,x:(x(stage.start_day)+x(stage.end_day))/2}))
  const groups=value.groups.map((group,index)=>({...group,y:335+index*135,samples:group.sample_days.map(day=>({day,x:x(day)}))}))
  const intervals=value.intervals.map(interval=>({...interval,x1:x(interval.start_day),x2:x(interval.end_day),y:groups.find(group=>group.id===interval.group_id)!.y+46}))
  return {axis:{x1:140,x2:820,y:205},ticks,stages,groups,intervals}
}

const escapeXml=(value:string)=>value.replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[char]!))
export function timelineSvg(value:IllustrationTimeline):string {
  const g=timelineGeometry(value)
  return `<g data-timeline-version="${value.version}" font-family="Noto Sans SC, sans-serif" fill="#26332f"><text x="140" y="82" font-size="15">实验时间（天）</text><line x1="${g.axis.x1}" x2="${g.axis.x2}" y1="${g.axis.y}" y2="${g.axis.y}" stroke="#454d56" stroke-width="3"/>${g.ticks.map(t=>`<g data-tick-day="${t.day}"><line x1="${t.x}" x2="${t.x}" y1="194" y2="216" stroke="#454d56" stroke-width="2"/><text x="${t.x}" y="${t.labelY}" text-anchor="middle" font-size="15">${escapeXml(t.label)}</text></g>`).join('')}${g.stages.map(s=>`<text data-stage="${s.id}" x="${s.x}" y="160" text-anchor="middle" font-size="14">${escapeXml(s.label)}</text>`).join('')}${g.groups.map(group=>`<g data-group="${group.id}"><text x="24" y="${group.y+5}" font-size="15">${escapeXml(group.label)}</text><line x1="140" x2="820" y1="${group.y}" y2="${group.y}" stroke="#a5adb5" stroke-width="1.5"/>${group.samples.map(sample=>`<g data-sample-day="${sample.day}"><circle cx="${sample.x}" cy="${group.y}" r="7" fill="#fff" stroke="#454d56" stroke-width="2"/><text x="${sample.x}" y="${group.y-18}" text-anchor="middle" font-size="12">采样</text></g>`).join('')}</g>`).join('')}${g.intervals.map(interval=>`<g data-intervention="${interval.id}"><line x1="${interval.x1}" x2="${interval.x2}" y1="${interval.y}" y2="${interval.y}" stroke="#454d56" stroke-width="8" stroke-linecap="round"/><text x="${(interval.x1+interval.x2)/2}" y="${interval.y+26}" text-anchor="middle" font-size="14">${escapeXml(interval.label)}</text></g>`).join('')}</g>`
}
