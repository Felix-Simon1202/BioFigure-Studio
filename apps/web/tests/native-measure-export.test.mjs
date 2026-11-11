import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const source = readFileSync(new URL('../src/nativeMeasure.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
})
const { validNativeMeasureCapability, nativeMeasureGroup, serializeNativeMeasureCsv,
  serializeNativeMeasureJson } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

const capability = {
  version: '1.0', operation: 'native_set_measurements',
  measurements: Array.from({ length: 24 }, (_, index) => ({ id: `option_${index}`, native_bit: 2 ** index })),
  decimal_places: { min: 0, max: 9, affects: 'native_display_only' },
  threshold: { explicit_when: 'limit_to_threshold', applied_to: 'sampled_source_or_redirect' },
  redirect: { identity: 'asset_id', same_xy_required: true,
    stack_alignment: 'same_linear_index_or_single_plane' },
  request_schema: { type: 'object' },
}

const result = {
  source_sha256: 'source123', redirect_sha256: 'target456',
  settings: { measurements: ['area', 'mean', 'scientific_notation'], decimal_places: 2,
    threshold: { min: 120, max: 135 } },
  measurement_bits: 2097155, source_stack_index: 1, sampled_stack_index: 1,
  roi_source_calibration: { pixel_width: 1, pixel_height: 1, unit: 'pixel', value_unit: 'Gray Value' },
  sampled_calibration: { pixel_width: 0.25, pixel_height: 0.5, unit: 'um', value_unit: 'Gray Value' },
  headings: ['Area', 'Mean', 'Kurt', 'AR', 'Round'],
  row: { Area: 1, Mean: 127.5, Kurt: -1.8171428571428572, AR: null, Round: null },
  label: '=SUM(1,2)', displayed_row: '1\t1.00E0\t1.28E2\t-1.82E0\tNaN\tInfinity',
  non_finite_headings: ['AR', 'Round'], overlay_count_before: 0, overlay_count: 1,
  row_count: 1, imagej1_version: '1.54p', implementation: 'ImageJ1 Analyzer.run/measure',
  fiji_archive_sha256: 'fixed',
}

test('capability controls 24 native options and semantic grouping', () => {
  assert.equal(validNativeMeasureCapability(capability), true)
  assert.equal(validNativeMeasureCapability({ ...capability, measurements: capability.measurements.slice(1) }), false)
  assert.equal(validNativeMeasureCapability({ ...capability, version: '2.0' }), false)
  assert.equal(nativeMeasureGroup('feret'), 'geometry')
  assert.equal(nativeMeasureGroup('mean'), 'intensity')
  assert.equal(nativeMeasureGroup('display_label'), 'position')
  assert.equal(nativeMeasureGroup('add_to_overlay'), 'record')
})

test('CSV retains raw numeric values, marks non-finite cells and guards text', () => {
  const csv = serializeNativeMeasureCsv(result)
  assert.ok(csv.startsWith('\ufeff'))
  assert.match(csv, /"'=SUM\(1,2\)"/)
  assert.match(csv, /"AR\|Round"/)
  assert.match(csv, /,1,127\.5,-1\.8171428571428572,,\r\n/)
  assert.ok(!csv.includes("'-1.817"), 'negative numeric values remain numeric')
  assert.match(csv, /1\.28E2/)
  assert.match(csv, /"target456"/)
  assert.match(csv, /"overlay_count_before","overlay_count_after"/)
})

test('JSON keeps complete native result and source calibration', () => {
  const json = JSON.parse(serializeNativeMeasureJson(result))
  assert.equal(json.version, '1.0')
  assert.equal(json.row.Mean, 127.5)
  assert.equal(json.row.AR, null)
  assert.equal(json.sampled_calibration.pixel_width, 0.25)
  assert.equal(json.roi_source_calibration.pixel_width, 1)
  assert.equal(json.overlay_count_before, 0)
  assert.equal(json.overlay_count, 1)
})

test('multi-point rows retain their own native stack columns, labels and null markers', () => {
  const points = { ...result, row: undefined, row_count: 2, headings: ['Mean', 'Ch', 'Slice', 'Frame'],
    rows: [{ Mean: 82, Ch: 1, Slice: 1, Frame: 1 }, { Mean: null, Ch: 2, Slice: 3, Frame: 2 }],
    labels: ['first', '=second'], displayed_rows: ['82\t1\t1\t1', 'NaN\t2\t3\t2'],
    non_finite_headings: [[], ['Mean']],
    roi: { kind: 'multipoint', point_positions: [1, 12], point_counters: [1, 2] },
    native_roi: { type_code: 10, point_positions: [1, 12] } }
  const csv = serializeNativeMeasureCsv(points)
  assert.match(csv, /,82,1,1,1\r\n/)
  assert.match(csv, /,,2,3,2\r\n/)
  assert.match(csv, /"'=second"/)
  assert.match(csv, /"Mean"/)
  const json = JSON.parse(serializeNativeMeasureJson(points))
  assert.deepEqual(json.roi.point_positions, [1, 12])
  assert.equal(json.native_roi.type_code, 10)
  assert.deepEqual(json.rows[1], points.rows[1])
})
