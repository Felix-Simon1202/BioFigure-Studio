import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/illustration.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } })
const { compositionTemplate, emptyIllustration, migrateIllustration, flowPoints, validateIllustration, createNodeMoveUpdate, deleteUnreferencedEvidence } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('original templates contain only blank panels or steps', () => {
  for (const kind of ['abstract_two','abstract_three','workflow_horizontal','workflow_vertical']) {
    const doc = Object.assign(emptyIllustration(), compositionTemplate(kind))
    validateIllustration(doc)
    assert.equal(doc.nodes.length + doc.edges.length + doc.flow_links.length + doc.evidence_records.length, 0)
    assert.equal(doc.sections.length, kind === 'abstract_two' ? 2 : 3)
  }
})

test('1.2 mechanism project migrates without adding scientific content', () => {
  const old = emptyIllustration()
  old.spec_version = '1.2'
  delete old.document_kind
  delete old.sections
  delete old.flow_links
  delete old.provenance.composition_schema_version
  const { document, migrated } = migrateIllustration(old)
  assert.equal(migrated, true)
  assert.equal(document.spec_version, '1.3')
  assert.equal(document.document_kind, 'mechanism')
  assert.deepEqual(document.flow_links, [])
  assert.equal(old.spec_version, '1.2', 'the input file stays unchanged')
})

test('sequence links remain distinct from scientific edges and assigned drags stay inside panel', () => {
  const doc = Object.assign(emptyIllustration(), compositionTemplate('workflow_horizontal'))
  doc.flow_links.push({id:'flow_1',source_section_id:'section_1',target_section_id:'section_2',label:''})
  assert.equal(doc.edges.length, 0)
  assert.equal(flowPoints(doc.sections[0],doc.sections[1]).length,2)
  doc.nodes.push({id:'node_1',component_id:'protein_generic',x:50,y:180,width:110,height:82,rotation:0,z_index:0,label:'占位组件',fill:'#e4b96c',text_color:'#26332f',scientific_status:'illustrative',entity_type:'protein',evidence_ids:[],section_id:'section_1'})
  doc.provenance.component_ids=['protein_generic']
  validateIllustration(doc)
  const moved=createNodeMoveUpdate(['node_1'],1000,0)(doc)
  assert.equal(moved.nodes[0].x,210)
  validateIllustration(moved)
  doc.flow_links[0].source_section_id='section_3'
  assert.throws(()=>validateIllustration(doc),/流程顺序箭头/)
})

test('referenced evidence cannot be deleted until user removes the reference', () => {
  const doc=Object.assign(emptyIllustration(),compositionTemplate('abstract_two'))
  doc.evidence_records.push({id:'ev_1',evidence_type:'user_note',citation:'合成说明',locator:'',note:'',added_by:'测试者',date:'2026-10-18'})
  doc.sections[0].evidence_ids=['ev_1']
  validateIllustration(doc)
  assert.throws(()=>deleteUnreferencedEvidence(doc,'ev_1'),/仍被对象引用/)
  doc.sections[0].evidence_ids=[]
  assert.equal(deleteUnreferencedEvidence(doc,'ev_1').evidence_records.length,0)
})

test('portable project rejects unreviewed fields', () => {
  const doc=Object.assign(emptyIllustration(),compositionTemplate('abstract_two'))
  doc.sections[0].unreviewed_markup='<svg/>'
  assert.throws(()=>validateIllustration(doc),/未审核字段/)
})
