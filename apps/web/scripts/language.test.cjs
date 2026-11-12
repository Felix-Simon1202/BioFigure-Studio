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
const ChartStyleChoices = require(path.join(web, 'src/ChartStyleChoices.tsx')).default
const { paletteChoices, chartStylePresets, contrastAgainstWhite, isPairedPalette } = require(path.join(web, 'src/chartPalettes.ts'))

test('linked figure, reviewed edit and image queue interfaces follow both languages', () => {
  require.extensions['.css'] = module => { module.exports = {} }
  const FigureStyle = require(path.join(web, 'src/FigureConsistencyPanel.tsx')).default
  const ReviewedEdit = require(path.join(web, 'src/ReviewedEditPanel.tsx')).default
  const ImageQueue = require(path.join(web, 'src/ImageStyleQueue.tsx')).default
  const { emptyIllustration } = require(path.join(web, 'src/illustration.ts'))
  for (const locale of ['en','zh-CN']) {
    global.window = { localStorage: { getItem: () => locale } }
    for (const [Component, props, en, zh] of [
      [FigureStyle,{figure:{panels:[]},busy:false,canUndo:false,onApply:()=>{},onUndo:()=>{}},'Linked figure style','整套图版风格'],
      [ReviewedEdit,{document:emptyIllustration(),selected:[],apply:()=>{}},'Biodot reviewed edit','Biodot 局部改图'],
      [ImageQueue,{},'Unified image presentation queue','统一风格处理队列'],
    ]) {
      const markup = renderToStaticMarkup(React.createElement(LanguageProvider,null,React.createElement(Component,props)))
      assert.ok(markup.includes(locale==='en'?en:zh))
      if(locale==='en') assert.doesNotMatch(markup,/\p{Script=Han}/u)
    }
  }
})

test('navigation and sliding mode control are bilingual accessible disclosures', () => {
  require.extensions['.css'] = module => { module.exports = {} }
  const ModeSwitch = require(path.join(web, 'src/WorkspaceModeSwitch.tsx')).default
  const Group = require(path.join(web, 'src/NavigationGroup.tsx')).default
  for (const locale of ['en', 'zh-CN']) {
    global.window = { localStorage: { getItem: () => locale } }
    for (const ai of [true, false]) {
      const markup = renderToStaticMarkup(React.createElement(LanguageProvider, null,
        React.createElement(ModeSwitch, { ai, onChange: () => {} })))
      assert.match(markup, /role="switch"/)
      assert.ok(markup.includes(`aria-checked="${ai}"`))
      assert.match(markup, locale === 'en' ? /AI workspace/ : /AI 工作台/)
    }
    const menu = renderToStaticMarkup(React.createElement(Group, {label:'Synthetic navigation',
      description:'Purpose and child actions',items:[{label:'Open synthetic editor',onSelect:()=>{}}]}))
    assert.match(menu, /aria-expanded="false"/)
    assert.match(menu, /aria-controls=/)
    assert.match(menu, /class="nav-group-panel" hidden=""/)
  }
})

test('all cell components share vector artwork across preview/export and survive projects', () => {
  require.extensions['.css'] = module => { module.exports = {} }
  const { componentRegistry, emptyIllustration, validateIllustration, defaultEntityType } = require(path.join(web, 'src/illustration.ts'))
  const { componentArtwork, componentSvg } = require(path.join(web, 'src/illustrationArtwork.ts'))
  const { toSvg } = require(path.join(web, 'src/illustrationExport.ts'))
  assert.equal(componentRegistry.length, 28)
  assert.equal(new Set(componentRegistry.map(item => item.id)).size, 28)
  const doc = emptyIllustration()
  doc.nodes = componentRegistry.map((item, index) => ({ id: `shape_${index}`, component_id: item.id,
    x: 50, y: 50, width: item.width, height: item.height, rotation: 0, z_index: index,
    label: `Original 科学标签 ${index}`, fill: item.fill, text_color: '#26332f', scientific_status: 'illustrative',
    entity_type: defaultEntityType(item.id), evidence_ids: [], section_id: null }))
  doc.provenance.component_ids = componentRegistry.map(item => item.id).sort()
  const before = JSON.stringify(doc)
  const restored = validateIllustration(JSON.parse(before))
  assert.equal(JSON.stringify(doc), before)
  assert.deepEqual(restored, doc)
  const svg = toSvg(restored, 'en')
  assert.match(svg, /component_artwork_version/)
  for (const item of componentRegistry) {
    const primitives = componentArtwork(item.id, item.fill)
    const fragment = componentSvg(item.id, item.fill)
    assert.ok(primitives.length >= 2, item.id)
    assert.ok(svg.includes(fragment), item.id)
    assert.equal((fragment.match(/<\w+ /g) || []).length, primitives.length)
    assert.doesNotMatch(fragment, /<script|<image|<foreignObject|https?:|onload=|NaN|undefined/)
    assert.ok(svg.includes(`data-component-id="${item.id}"`))
  }
  assert.match(svg, /Original 科学标签 27/)
  assert.throws(() => componentSvg('cell_animal', 'url(https://invalid.test)'))
  assert.equal(defaultEntityType('ion_channel'), 'protein')
})

test('expanded component library uses English and Chinese names and guidance', () => {
  require.extensions['.css'] = module => { module.exports = {} }
  const Studio = require(path.join(web, 'src/IllustrationStudio.tsx')).default
  for (const locale of ['en', 'zh-CN']) {
    global.window = { localStorage: { getItem: () => locale } }
    const markup = renderToStaticMarkup(React.createElement(LanguageProvider, null,
      React.createElement(Studio, { onBack: () => {} })))
    assert.equal((markup.match(/class="ill-component"/g) || []).length, 28)
    assert.match(markup, locale === 'en' ? /Mature mammalian erythrocyte/ : /成熟哺乳动物红细胞/)
    assert.match(markup, locale === 'en' ? /Component category/ : /组件分类/)
    if (locale === 'en') assert.equal(markup.match(/.{0,35}\p{Script=Han}.{0,35}/u)?.[0] ?? '', '', 'Unexpected Chinese interface text')
  }
})

test('scientific palette choices are bilingual and distinguish categorical from numeric values', () => {
  for (const locale of ['en', 'zh-CN']) {
    global.window = { localStorage: { getItem: () => locale } }
    const markup = renderToStaticMarkup(React.createElement(LanguageProvider, null,
      React.createElement(ChartStyleChoices, { chartType: 'scatter', paletteId: 'oc_clear', onChange: () => {} })))
    assert.match(markup, /aria-pressed="true"/)
    assert.match(markup, locale === 'en' ? /Open Clear/ : /清晰分组/)
    assert.match(markup, locale === 'en' ? /not certified colorblind-safe/ : /不保证色觉无障碍/)
    if (locale === 'en') assert.doesNotMatch(markup, /\p{Script=Han}/u)
  }
  assert.equal(paletteChoices('heatmap').filter(item => item.kind === 'sequential').length, 9)
  assert.equal(paletteChoices('heatmap').filter(item => item.kind === 'diverging').length, 5)
  assert.equal(paletteChoices('embedding_continuous').length, 14)
  assert.equal(paletteChoices('scatter').length, 11)
  assert.ok(isPairedPalette('oc_paired'))
  assert.ok(isPairedPalette('oc_pair_teal_rose'))
  assert.ok(isPairedPalette('oc_pair_garden'))
  assert.equal(isPairedPalette('oc_ocean'), false)
  assert.equal(paletteChoices('r_ggplot').length, 0)
  assert.equal(contrastAgainstWhite('#000000'), 21)
  assert.equal(contrastAgainstWhite('#ffffff'), 1)
  assert.throws(() => contrastAgainstWhite('invalid'))
  for (const preset of chartStylePresets) {
    assert.deepEqual(Object.keys(preset).sort(), ['font_size', 'id', 'line_width', 'name', 'palette_id', 'theme_id'])
  }
})

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
