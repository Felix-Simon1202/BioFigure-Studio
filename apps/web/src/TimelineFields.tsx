import { useI18n } from './i18n'
import { workbenchText } from './workbenchEnglish'
import type { TimelineInput } from './illustrationTimeline'

type Props={value:TimelineInput;onChange:(value:TimelineInput)=>void;disabled?:boolean}
const fields:{key:keyof Omit<TimelineInput,'intervalGroup'>;label:string;hint:string}[]=[
  {key:'title',label:'图题',hint:'合成实验时间轴'},
  {key:'days',label:'时间点（天）',hint:'0, 2, 9'},
  {key:'tickLabels',label:'各刻度显示文字',hint:'第 0 天, 第 2 天, 第 9 天'},
  {key:'stageLabels',label:'相邻时间点之间的阶段',hint:'准备阶段, 处理阶段'},
  {key:'groupA',label:'第一组名称',hint:'对照组'},
  {key:'samplesA',label:'第一组采样天数',hint:'0, 2, 9'},
  {key:'groupB',label:'第二组名称',hint:'处理组'},
  {key:'samplesB',label:'第二组采样天数',hint:'0, 2, 9'},
  {key:'intervalStart',label:'干预开始（天）',hint:'2'},
  {key:'intervalEnd',label:'干预结束（天）',hint:'9'},
  {key:'intervalLabel',label:'干预名称',hint:'示例干预'},
]
export default function TimelineFields({value,onChange,disabled=false}:Props){
  const { locale } = useI18n()
  const ui = (text: string) => workbenchText(locale, text)

  return <div className="timeline-fields">{fields.map(field=><label key={field.key}>{ui(field.label)}<input value={value[field.key]} placeholder={ui(field.hint)} maxLength={120} disabled={disabled} onChange={event=>onChange({...value,[field.key]:event.target.value})}/></label>)}<label>{ui("干预所属组")}<select value={value.intervalGroup} disabled={disabled} onChange={event=>onChange({...value,intervalGroup:event.target.value as TimelineInput['intervalGroup']})}><option value="group_a">{ui("第一组")}</option><option value="group_b">{ui("第二组")}</option></select></label></div>
}
