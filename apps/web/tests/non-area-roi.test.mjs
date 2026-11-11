import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'

const { outputText } = ts.transpileModule(readFileSync(new URL('../src/nonAreaRoi.ts', import.meta.url), 'utf8'), {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
})
const { parseNonAreaRoi } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
const axes = [{ name: 'X', length: 8 }, { name: 'Y', length: 6 },
  { name: 'Channel', length: 2 }, { name: 'Z', length: 3 }, { name: 'Time', length: 2 }]

test('subpixel line and freehand types retain explicit coordinates and width', () => {
  const line = parseNonAreaRoi('line', '1.25,1.5\n5.25,1.5', '3', axes)
  assert.deepEqual(line, { version: '1.0', kind: 'line', points: [{ x: 1.25, y: 1.5 }, { x: 5.25, y: 1.5 }], stroke_width: 3 })
  for (const kind of ['polyline', 'freeline']) assert.equal(parseNonAreaRoi(kind, '1,1\n3,1\n3,3', '1', axes).kind, kind)
  assert.equal(parseNonAreaRoi('angle', '1,1\n3,1\n3,3', '', axes).stroke_width, undefined)
})

test('point order, linear positions and counters survive without coercion', () => {
  const roi = parseNonAreaRoi('multipoint', '2.5,3,1,1\n4,2,12,2', '', axes)
  assert.deepEqual(roi.point_positions, [1, 12]); assert.deepEqual(roi.point_counters, [1, 2])
  assert.deepEqual(parseNonAreaRoi('point', '2,3', '', axes).point_positions, [0])
})

test('invalid rows cannot silently become origin points or lose per-point state', () => {
  for (const text of ['', ',3', '1,', '1,2,3', 'NaN,1', 'Infinity,2', '0x2,3', '8,2', '2,6', '2,3,1.5,1', '2,3,13,1', '2,3,1,100'])
    assert.throws(() => parseNonAreaRoi('point', text, '', axes), text)
  assert.throws(() => parseNonAreaRoi('line', '1,1\n1,1', '1', axes))
  assert.throws(() => parseNonAreaRoi('angle', '1,1\n1,1\n3,3', '', axes))
  assert.throws(() => parseNonAreaRoi('line', '1,1\n3,3', '33', axes))
  assert.throws(() => parseNonAreaRoi('point', '1,1', '', [...axes, { name: 'Time', length: 65 }]))
})
