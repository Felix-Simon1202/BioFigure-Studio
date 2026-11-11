import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const transpile = (name) => ts.transpileModule(readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const illustrationUrl = `data:text/javascript;base64,${Buffer.from(transpile('illustration.ts')).toString('base64')}`
const skillSource = transpile('illustrationSkill.ts').replace("from './illustration'", `from '${illustrationUrl}'`)
const { buildBranchWorkflow, minimalVectorSectionStyle, syntheticBranchExample, syntheticBranchParagraph, usesMinimalVectorStyle, visibleProvenanceNote, verifySyntheticExtraction } = await import(`data:text/javascript;base64,${Buffer.from(skillSource).toString('base64')}`)

test('synthetic two-branch input becomes a valid editable workflow without invented evidence', () => {
  const doc = buildBranchWorkflow(syntheticBranchExample)
  assert.equal(doc.document_kind, 'experimental_workflow')
  assert.equal(doc.sections.length, 5)
  assert.equal(doc.flow_links.length, 4)
  assert.deepEqual(doc.flow_links.map(({ source_section_id, target_section_id }) => [source_section_id, target_section_id]), [
    ['shared', 'branch_a'], ['shared', 'branch_b'], ['branch_a', 'result_a'], ['branch_b', 'result_b'],
  ])
  assert.ok(doc.sections.every((item) => item.scientific_status === 'needs_review' && item.evidence_ids.length === 0))
  assert.deepEqual(doc.evidence_records, [])
  assert.equal(doc.sections[2].description, syntheticBranchExample.stepB)
})

test('oversized or missing explicit steps are rejected before entering the editor', () => {
  assert.throws(() => buildBranchWorkflow({ ...syntheticBranchExample, branchA: '八个汉字超过限制文字' }), /分支 A 名称/)
  assert.throws(() => buildBranchWorkflow({ ...syntheticBranchExample, resultB: '  ' }), /分支 B 结果/)
})

test('reviewed model extraction must reproduce the fixed source and fields before layout', () => {
  const extraction = { provider: 'local', sample_id: 'synthetic-branch-v1', source_text: syntheticBranchParagraph, fields: syntheticBranchExample }
  assert.deepEqual(verifySyntheticExtraction(extraction), extraction)
  const doc = buildBranchWorkflow(extraction.fields, 'local_model')
  assert.match(doc.provenance.note, /本机已审核模型/)
  assert.ok(doc.sections.every((item) => item.scientific_status === 'needs_review'))
  assert.throws(() => verifySyntheticExtraction({ ...extraction, fields: { ...extraction.fields, resultB: '凭空增加结论' } }), /不一致/)
  assert.throws(() => verifySyntheticExtraction({ ...extraction, source_text: '用户提供的真实文本' }), /不一致/)
})

test('minimal vector branch markers survive grayscale while old projects keep their appearance', () => {
  const doc = buildBranchWorkflow(syntheticBranchExample)
  assert.equal(usesMinimalVectorStyle(doc), true)
  assert.deepEqual(doc.sections.map(section => minimalVectorSectionStyle(doc, section)?.badge), [null, 'A', 'B', 'A', 'B'])
  assert.ok(doc.sections.map(section => minimalVectorSectionStyle(doc, section)).every(style => style?.stroke === '#56616a'))
  assert.equal(doc.sections[1].title, syntheticBranchExample.branchA)
  assert.doesNotMatch(visibleProvenanceNote(doc), /biofigure-minimal-vector/)
  const oldDoc = structuredClone(doc)
  oldDoc.provenance.note = '内置双分支结构化草案；旧项目。'
  assert.equal(usesMinimalVectorStyle(oldDoc), false)
  assert.equal(minimalVectorSectionStyle(oldDoc, oldDoc.sections[1]), null)
})
