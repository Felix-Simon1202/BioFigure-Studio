import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'

const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const transpile = (name) => ts.transpileModule(readFileSync(new URL(`../src/${name}.ts`, import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText

const baseUrl = moduleUrl(transpile('illustration'))
const { orthogonalPoints } = await import(baseUrl)
const { mechanismRelationStyle, mechanismRelationLabelPosition } = await import(moduleUrl(
  transpile('illustrationMechanismStyle').replace("from './illustration'", `from '${baseUrl}'`),
))

test('mechanism relation glyphs and editable labels convey meaning without color', () => {
  const edge = { label: '', scientific_status: 'illustrative' }
  assert.deepEqual(mechanismRelationStyle({ ...edge, relation: 'activation' }), {
    label: '激活',
    markerEnd: 'url(#arrow)',
    strokeDasharray: undefined,
  })
  assert.deepEqual(mechanismRelationStyle({ ...edge, relation: 'inhibition', label: '合成分子 B', scientific_status: 'needs_review' }), {
    label: '抑制 · 合成分子 B（待核实）',
    markerEnd: 'url(#bar)',
    strokeDasharray: '7 5',
  })
  assert.equal(mechanismRelationStyle({ ...edge, relation: 'association' }).markerEnd, undefined)
  assert.equal(mechanismRelationStyle({ ...edge, relation: 'binding' }).markerEnd, 'url(#circle)')
})

test('labels follow orthogonal routes without sitting directly on the line', () => {
  const horizontal = orthogonalPoints({ x: 20, y: 40 }, { x: 180, y: 40 })
  assert.deepEqual(mechanismRelationLabelPosition(horizontal), { x: 100, y: 32, anchor: 'middle' })

  const vertical = orthogonalPoints({ x: 30, y: 20 }, { x: 30, y: 200 })
  assert.deepEqual(mechanismRelationLabelPosition(vertical), { x: 38, y: 110, anchor: 'start' })
})

test('reopened mechanism exports the same relations as editable SVG', async () => {
  const { createServer } = await import('vite')
  const server = await createServer({
    configFile: false,
    server: { middlewareMode: true, hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
    plugins: [{
      name: 'expose-illustration-export-for-test',
      transform(source, id) {
        if (id.replaceAll('\\', '/').endsWith('/src/IllustrationStudio.tsx')) return source + '\nexport { toSvg }'
      },
    }],
  })
  try {
    const { toSvg } = await server.ssrLoadModule('/src/IllustrationStudio.tsx')
    const { emptyIllustration, validateIllustration } = await server.ssrLoadModule('/src/illustration.ts')
    const document = emptyIllustration()
    document.provenance.component_ids = ['protein_generic']
    document.nodes = Array.from({ length: 4 }, (_, index) => ({
      id: `n${index}`, component_id: 'protein_generic', x: 40 + 210 * index, y: 180, width: 110,
      height: 82, rotation: 0, z_index: index, label: `合成实体 ${index}`, fill: '#e4b96c',
      text_color: '#26332f', scientific_status: 'illustrative', entity_type: 'protein',
      evidence_ids: [], section_id: null,
    }))
    document.edges = ['activation', 'inhibition', 'association'].map((relation, index) => ({
      id: `e${index}`, source: { node_id: `n${index}`, anchor_id: 'right' },
      target: { node_id: `n${index + 1}`, anchor_id: 'left' }, relation, routing: 'orthogonal',
      label: index === 1 ? '合成 <核验> & 标签' : '', scientific_status: 'needs_review', evidence_ids: [],
    }))
    const reopened = validateIllustration(JSON.parse(JSON.stringify(validateIllustration(document))))
    const svg = toSvg(reopened)
    const groups = Object.fromEntries([...svg.matchAll(/<g data-relation="([^"]+)"[^>]*>(.*?)<\/g>/g)].map(match => [match[1], match[2]]))
    assert.match(groups.activation, /marker-end="url\(#arrow\)"/)
    assert.match(groups.inhibition, /marker-end="url\(#bar\)"/)
    assert.doesNotMatch(groups.association, /marker-end/)
    assert.match(groups.inhibition, /<text[^>]*>抑制 · 合成 &lt;核验&gt; &amp; 标签（待核实）<\/text>/)
    assert.equal((svg.match(/data-relation-style="mechanism-relation-semantics\/1\.0"/g) ?? []).length, 3)
  } finally {
    await server.close()
  }
})
