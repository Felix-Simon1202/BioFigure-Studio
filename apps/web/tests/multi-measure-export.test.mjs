import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/multiMeasure.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
})
const { serializeMultiMeasureCsv, serializeMultiMeasureJson } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`
)

const result = {
  source: { sha256: 'abc123', bytes: 100, axes: [] },
  roi_order: [
    { id: 'a', name: '=HYPERLINK("bad")', saved_indices: { C: 1, Z: 2, T: 1 }, roi: { kind: 'rectangle' } },
    { id: 'b', name: 'Region B', saved_indices: { C: 0, Z: 1, T: 0 }, roi: { kind: 'rectangle' } },
  ],
  current_plane: { C: 1, Z: 2, T: 1 }, current_stack_index: 12,
  stack_planes: [{ stack_index: 1, C: 0, Z: 0, T: 0 }, { stack_index: 12, C: 1, Z: 2, T: 1 }],
  measurement_flags: [], imagej1_version: '1.54p', implementation: 'ImageJ1 RoiManager.runCommand multi-measure',
  fiji_archive_sha256: 'fixed',
  runs: [{
    options: { measure_all: true, one_row_per_slice: true, append_results: true },
    layout: 'one_row_per_slice', headings: ['Slice', 'Mean(Region A)', '=danger'],
    rows: [{ Slice: 1, 'Mean(Region A)': 31.5, '=danger': -3.5 },
      { Slice: 12, 'Mean(Region A)': 14531.5, '=danger': 7 }],
    row_count: 2, new_row_start: 1, new_row_count: 1,
  }],
}

test('CSV keeps native numeric values and marks only appended rows as new', () => {
  const csv = serializeMultiMeasureCsv(result, 0)
  assert.match(csv, /^\ufeff/)
  assert.match(csv, /"'=danger"/)
  assert.match(csv, /1,"one_row_per_slice",1,"no","abc123","","",1,31\.5,-3\.5/)
  assert.match(csv, /1,"one_row_per_slice",2,"yes","abc123","","",12,14531\.5,7/)
  assert.ok(!csv.includes("'-3.5"), 'negative numeric measurements stay numeric')
})

test('per-measurement CSV keeps ROI names as guarded text', () => {
  const individual = structuredClone(result)
  individual.runs[0].layout = 'one_row_per_measurement'
  const csv = serializeMultiMeasureCsv(individual, 0)
  assert.match(csv, /"a","'=HYPERLINK\(""bad""\)"/)
  assert.match(csv, /"b","Region B"/)
})

test('JSON export preserves source, ROI positions, plane map, options and rows', () => {
  const json = JSON.parse(serializeMultiMeasureJson(result))
  assert.equal(json.version, '1.0')
  assert.equal(json.roi_order[0].name, '=HYPERLINK("bad")')
  assert.deepEqual(json.roi_order[0].saved_indices, { C: 1, Z: 2, T: 1 })
  assert.equal(json.stack_planes[1].stack_index, 12)
  assert.equal(json.runs[0].options.append_results, true)
  assert.equal(json.runs[0].rows[1]['Mean(Region A)'], 14531.5)
  assert.throws(() => serializeMultiMeasureCsv(result, 1), RangeError)
})
