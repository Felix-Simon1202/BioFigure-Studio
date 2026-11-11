import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import ts from 'typescript'
const {outputText}=ts.transpileModule(readFileSync(new URL('../src/nativeArea.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}})
const {buildNativeArea,defaultAreaDraft}=await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
test('area parameters retain subpixel, spline and rotation semantics',()=>{
 const d=defaultAreaDraft()
 assert.equal(buildNativeArea('rectangle',d).x,.5)
 assert.equal(buildNativeArea('spline_polygon',d).evaluation_points,32)
 assert.equal(buildNativeArea('rotated_ellipse',d).aspect_ratio,.5)
 assert.equal(buildNativeArea('freehand',d).kind,'freehand')
 assert.throws(()=>buildNativeArea('traced',d))
 for(const [field,value] of [['width',''],['width','NaN'],['width','0'],['width','0x2']]) assert.throws(()=>buildNativeArea('rectangle',{...d,fields:{...d.fields,[field]:value}}))
})
test('ordered boolean operands are independent immutable request snapshots',()=>{
 const d=defaultAreaDraft();const a=buildNativeArea('rectangle',d);const b=buildNativeArea('oval',d)
 const result=buildNativeArea('shape',{...d,operation:'subtract',operands:[a,b]})
 a.x=9
 assert.equal(result.operands[0].x,.5);assert.equal(result.operands[1].kind,'oval');assert.equal(result.operation,'subtract')
 assert.throws(()=>buildNativeArea('shape',d))
 assert.throws(()=>buildNativeArea('spline_polygon',{...d,fields:{...d.fields,evaluation_points:'7'}}))
})
