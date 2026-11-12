// Render the original production vector library; no browser or network required.
const fs = require('node:fs')
const path = require('node:path')
const root = path.resolve(__dirname, '..')
const web = path.join(root, 'apps/web')
const ts = require(path.join(web, 'node_modules/typescript'))
require.extensions['.ts'] = (module, file) => {
  const { outputText } = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, esModuleInterop: true },
  })
  module._compile(outputText, file)
}
const { componentRegistry, componentCategory } = require(path.join(web, 'src/illustration.ts'))
const { componentSvg } = require(path.join(web, 'src/illustrationArtwork.ts'))
const escape = text => text.replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[char]))
const groups = ['cells', 'organelles', 'molecules']
const items = groups.flatMap(group => componentRegistry.filter(item => componentCategory(item) === group))
const columns = 4, cardWidth = 250, cardHeight = 210
let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1020" height="1570" viewBox="0 0 1020 1570"><rect width="100%" height="100%" fill="#f8f9fb"/><g font-family="Arial, sans-serif" fill="#374151"><text x="22" y="31" font-size="21">BioFigure Studio · cell biology components</text><text x="22" y="52" font-size="12">28 original editable vectors · schematic, not to scale · artwork 2.0</text>`
items.forEach((item, index) => {
  const x = 10 + index % columns * cardWidth, y = 72 + Math.floor(index / columns) * cardHeight
  const scale = Math.min(180 / item.width, 122 / item.height)
  const words = item.english.split(' '), lines = ['']
  for (const word of words) {
    if ((lines.at(-1) + ' ' + word).trim().length > 27) lines.push(word)
    else lines[lines.length - 1] = (lines.at(-1) + ' ' + word).trim()
  }
  svg += `<g><rect x="${x}" y="${y}" width="238" height="198" rx="12" fill="#ffffff" stroke="#e2e5eb"/><text x="${x+14}" y="${y+20}" font-size="10" fill="#7b8493">${componentCategory(item).toUpperCase()}</text><g transform="translate(${x+119-item.width*scale/2} ${y+33+(122-item.height*scale)/2}) scale(${scale})">${componentSvg(item.id,item.fill)}</g>${lines.map((line, row) => `<text x="${x+119}" y="${y+171+row*14}" text-anchor="middle" font-size="12">${escape(line)}</text>`).join('')}</g>`
})
svg += '</g></svg>'
fs.writeFileSync(path.join(root, 'docs/media/cell-component-catalog.svg'), svg)
console.log('Rendered 28 original components into docs/media/cell-component-catalog.svg')
