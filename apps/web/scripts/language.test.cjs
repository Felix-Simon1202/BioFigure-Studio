const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const web = path.resolve(__dirname, '..')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, file) => {
    const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      fileName: file,
      compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    })
    module._compile(result.outputText, file)
  }
}
const { LanguageProvider, LOCALE_STORAGE_KEY } = require(path.join(web, 'src/i18n.tsx'))
const LanguageSettings = require(path.join(web, 'src/LanguageSettings.tsx')).default
const { interfaceDiagnostic } = require(path.join(web, 'src/interfaceDiagnostics.ts'))
const { biodotGreeting, biodotReply } = require(path.join(web, 'src/biodot.ts'))
const { branchExample, timelineExample } = require(path.join(web, 'src/builtinExamples.ts'))
const { buildTimeline, timelineSvg } = require(path.join(web, 'src/illustrationTimeline.ts'))
const { mechanismRelationStyle } = require(path.join(web, 'src/illustrationMechanismStyle.ts'))

function settings(storage) {
  global.window = { localStorage: storage }
  return renderToStaticMarkup(React.createElement(LanguageProvider, null,
    React.createElement(LanguageSettings)))
}

test('new profile starts in English without changing the Chinese option name', () => {
  const markup = settings({ getItem: key => { assert.equal(key, LOCALE_STORAGE_KEY); return null } })
  assert.match(markup, /Interface language/)
  assert.match(markup, /value="en" selected=""/)
  assert.match(markup, /简体中文/)
})

test('saved Simplified Chinese is restored', () => {
  const markup = settings({ getItem: () => 'zh-CN' })
  assert.match(markup, /界面语言/)
  assert.match(markup, /value="zh-CN" selected=""/)
})

test('invalid preference falls back to English', () => {
  assert.match(settings({ getItem: () => 'unsupported' }), /Interface language/)
})

test('unavailable local storage does not prevent English startup', () => {
  assert.match(settings({ getItem: () => { throw new Error('Storage unavailable') } }), /Interface language/)
})

test('dynamic interface notices preserve original filenames and ROI names', () => {
  assert.equal(interfaceDiagnostic('en', '已加入「试样_α 01.tif」。'), 'Added “试样_α 01.tif”.')
  assert.equal(interfaceDiagnostic('en', '已重命名为「原始 ROI_甲」。'), 'Renamed to “原始 ROI_甲”.')
  assert.equal(interfaceDiagnostic('zh-CN', '已加入「试样_α 01.tif」。'), '已加入「试样_α 01.tif」。')
  assert.equal(interfaceDiagnostic('en', '研究标题_样本 A'), '研究标题_样本 A')
})

test('local scientific validation diagnostics have usable English messages', () => {
  const helpers = ['illustration.ts', 'illustrationTimeline.ts', 'illustrationSkill.ts',
    'nativeArea.ts', 'nonAreaRoi.ts', 'nativeMeasurementDraft.ts', 'svgHandoffInspection.ts',
    'measurementEditor.ts', 'multiMeasure.ts', 'roiFile.ts']
  let checked = 0
  for (const helper of helpers) {
    const content = fs.readFileSync(path.join(web, 'src', helper), 'utf8')
    const ast = ts.createSourceFile(helper, content, ts.ScriptTarget.Latest, true)
    function visit(node) {
      if (ts.isNewExpression(node) && ['Error', 'RangeError'].includes(node.expression.getText(ast))) {
        const first = node.arguments?.[0]
        if (first && ts.isStringLiteral(first) && /\p{Script=Han}/u.test(first.text)) {
          assert.doesNotMatch(interfaceDiagnostic('en', first.text), /\p{Script=Han}/u, helper + ': ' + first.text)
          assert.equal(interfaceDiagnostic('zh-CN', first.text), first.text)
          checked++
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(ast)
  }
  assert.ok(checked >= 60, 'Expected broad coverage of existing validation paths')
})

test('Biodot greetings are bilingual, local and do not intercept drawing requests', () => {
  assert.equal(biodotReply('Hello Biodot!', 'en'), biodotGreeting.en)
  assert.equal(biodotReply('你好', 'zh-CN'), biodotGreeting['zh-CN'])
  assert.match(biodotReply('help', 'en'), /Biodot/)
  assert.equal(biodotReply('Draw a scatter plot for Sample A.', 'en'), null)
})

test('new built-in English examples contain English labels and validate', () => {
  assert.doesNotMatch(JSON.stringify(branchExample('en')), /\p{Script=Han}/u)
  assert.match(branchExample('zh-CN').title, /合成/)
  const document = buildTimeline(timelineExample('en'))
  assert.doesNotMatch(JSON.stringify(document.timeline), /\p{Script=Han}/u)
  const before = JSON.stringify(document)
  const en = timelineSvg(document.timeline, 'en')
  const zh = timelineSvg(document.timeline, 'zh-CN')
  assert.match(en, /Experimental time \(days\)/)
  assert.doesNotMatch(en, /\p{Script=Han}/u)
  assert.equal(en.replace('Experimental time (days)', '实验时间（天）').replaceAll('>Sample<', '>采样<'), zh)
  assert.equal(JSON.stringify(document), before)
})

test('mechanism interface labels switch without rewriting evidence or custom labels', () => {
  const edge = { relation: 'inhibition', label: '用户科学标签', scientific_status: 'needs_review' }
  const before = JSON.stringify(edge)
  const en = mechanismRelationStyle(edge, 'en')
  const zh = mechanismRelationStyle(edge, 'zh-CN')
  assert.match(en.label, /^Inhibition · 用户科学标签 \(needs review\)$/)
  assert.equal(en.markerEnd, zh.markerEnd)
  assert.equal(en.strokeDasharray, zh.strokeDasharray)
  assert.equal(JSON.stringify(edge), before)
})

test('English gray-input placeholders and workbench welcome are translated', () => {
  require.extensions['.css'] = module => { module.exports = {} }
  const { emptyTimelineInput } = require(path.join(web, 'src/illustrationTimeline.ts'))
  const Fields = require(path.join(web, 'src/TimelineFields.tsx')).default
  global.window = { localStorage: { getItem: () => 'en' } }
  const markup = renderToStaticMarkup(React.createElement(LanguageProvider, null,
    React.createElement(Fields, { value: emptyTimelineInput, onChange: () => {} })))
  const placeholders = [...markup.matchAll(/placeholder="([^"]*)"/g)].map(match => match[1])
  assert.ok(placeholders.length >= 8)
  assert.doesNotMatch(placeholders.join(' '), /\p{Script=Han}/u)
  const Workbench = require(path.join(web, 'src/DrawingWorkbench.tsx')).default
  const noop = () => {}
  const workbench = renderToStaticMarkup(React.createElement(LanguageProvider, null,
    React.createElement(Workbench, { visible: true, modeSwitch: null, busy: false, canApply: true,
      recent: [], onOpenProject: noop, onOpen: noop, onDraft: noop, onApply: noop,
      onInspect: noop, onConnect: noop, onDisconnect: noop, onApplyIllustration: noop, onDraftIllustration: noop })))
  assert.match(workbench, /I&#x27;m Biodot/)
  assert.match(workbench, /placeholder="Draw a scatter plot/)
})
