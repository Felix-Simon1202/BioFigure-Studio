import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

// Run the actual TypeScript movement code using the already locked compiler.
const source = readFileSync(new URL('../src/illustration.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } })
const { createNodeMoveUpdate, emptyIllustration, validateIllustration } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
function document() {
  const doc = emptyIllustration()
  doc.canvas.snap_to_grid = false
  doc.nodes = [{id:'node_1',component_id:'protein_generic',x:100,y:100,width:110,height:82,rotation:0,z_index:0,label:'蛋白质',fill:'#e4b96c',text_color:'#26332f',scientific_status:'illustrative',entity_type:'protein',evidence_ids:[],section_id:null}]
  doc.provenance.component_ids = ['protein_generic']
  return doc
}

test('unsnapped queued drag remains safe after pointerup clears gesture', () => {
  let gesture = { ids:['node_1'] }
  const before = document()
  const update = createNodeMoveUpdate(gesture.ids, 13.25, -7.5)
  gesture.ids.length = 0
  gesture = null
  const after = update(before)
  assert.equal(after.nodes[0].x, 113.25)
  assert.equal(after.nodes[0].y, 92.5)
  assert.deepEqual(update(before), after, 'React replay must produce the same result')
  assert.equal(before.nodes[0].x, 100, 'undo snapshot must remain untouched')
  validateIllustration(after)
})

test('queued moves preserve fractional displacement and stay within canvas', () => {
  const before = document()
  const first = createNodeMoveUpdate(['node_1'], 0.75, 1.25)(before)
  const second = createNodeMoveUpdate(['node_1'], 2.5, 3.5)(first)
  assert.equal(second.nodes[0].x, 103.25)
  assert.equal(second.nodes[0].y, 104.75)
  const bounded = createNodeMoveUpdate(['node_1'], -1000, 1000)(second)
  assert.equal(bounded.nodes[0].x, 0)
  assert.equal(bounded.nodes[0].y, 558)
  validateIllustration(bounded)
})

test('empty selection and invalid displacement leave document intact', () => {
  const before = document()
  assert.equal(createNodeMoveUpdate([], 1, 1)(before), before)
  assert.equal(createNodeMoveUpdate(['node_1'], NaN, 1)(before), before)
})
