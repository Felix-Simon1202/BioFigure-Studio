import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const transpile=name=>ts.transpileModule(readFileSync(new URL(`../src/${name}`,import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText
const illustrationUrl=`data:text/javascript;base64,${Buffer.from(transpile('illustration.ts')).toString('base64')}`
const timelineSource=transpile('illustrationTimeline.ts').replace("from './illustration'",`from '${illustrationUrl}'`)
const {buildTimeline,syntheticTimelineExample,timelineGeometry,timelineToInput,timelineSvg}=await import(`data:text/javascript;base64,${Buffer.from(timelineSource).toString('base64')}`)
const {validateIllustration,emptyIllustration}=await import(illustrationUrl)

test('synthetic 0, 2, 9 day axis preserves the 2:7 distance and aligned groups',()=>{
  const doc=buildTimeline(syntheticTimelineExample),geometry=timelineGeometry(doc.timeline)
  const [a,b,c]=geometry.ticks.map(t=>t.x)
  assert.ok(Math.abs((b-a)/(c-b)-2/7)<1e-12)
  assert.deepEqual(geometry.groups.map(g=>g.samples.map(s=>s.x)),[[a,b,c],[a,b,c]])
  assert.equal(geometry.intervals[0].x1,b)
  assert.equal(geometry.intervals[0].x2,c)
  assert.equal(geometry.stages.length,2)
  assert.deepEqual(timelineToInput(doc),syntheticTimelineExample)
  assert.deepEqual(validateIllustration(JSON.parse(JSON.stringify(doc))),doc)
  const svg=timelineSvg(doc.timeline)
  assert.match(svg,/data-tick-day="2"/)
  assert.match(svg,/data-intervention="intervention_1"/)
  assert.match(svg,/<text[^>]*>示例干预<\/text>/)
  assert.match(svg,/data-stage="stage_0"/)
})

test('invalid or inferred timing is rejected with correctable errors',()=>{
  assert.throws(()=>buildTimeline({...syntheticTimelineExample,days:'0, 2, 2'}),/严格递增/)
  assert.throws(()=>buildTimeline({...syntheticTimelineExample,samplesA:'0, 3'}),/采样时刻/)
  assert.throws(()=>buildTimeline({...syntheticTimelineExample,intervalEnd:'5'}),/干预区间/)
  assert.throws(()=>buildTimeline({...syntheticTimelineExample,stageLabels:'准备阶段'}),/阶段说明数量/)
  assert.throws(()=>buildTimeline({...syntheticTimelineExample,days:'0, 1, 100'}),/距离过近/)
  assert.throws(()=>buildTimeline({...syntheticTimelineExample,stageLabels:'极长的早期准备及详细流程说明, 处理阶段'}),/阶段说明长于/)
})

test('close ticks stagger labels and user text is escaped in SVG',()=>{
  const doc=buildTimeline({...syntheticTimelineExample,days:'0, 1, 8',tickLabels:'第 0 天, 第 1 天, 第 8 天',samplesA:'0, 1, 8',samplesB:'0, 1, 8',intervalStart:'1',intervalEnd:'8',intervalLabel:'干预 & 观察'})
  const ticks=timelineGeometry(doc.timeline).ticks
  assert.notEqual(ticks[0].labelY,ticks[1].labelY)
  assert.match(timelineSvg(doc.timeline),/干预 &amp; 观察/)
})

test('old IllustrationSpec without timeline remains valid',()=>{
  const old=emptyIllustration('experimental_workflow')
  assert.equal(validateIllustration(old).timeline,undefined)
  const changed=buildTimeline(syntheticTimelineExample)
  changed.canvas.width=800
  assert.throws(()=>validateIllustration(changed),/960×640/)
})
