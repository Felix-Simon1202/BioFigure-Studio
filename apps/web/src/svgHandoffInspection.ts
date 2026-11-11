/** Local-only inspection of an untrusted SVG. Never attach the parsed document to the page. */

export const MAX_SVG_INSPECTION_BYTES = 2 * 1024 * 1024
const SVG_NS = 'http://www.w3.org/2000/svg'
const sizePattern = /^\d+(?:\.\d+)?(?:px|mm|cm|in|pt|pc|%)?$/i
const activeElements = new Set(['script', 'foreignObject', 'iframe', 'object', 'embed', 'animate', 'animateMotion', 'animateTransform', 'set'])
const rasterTypes = /^data:image\/(?:png|jpeg|jpg|gif|webp|bmp|tiff?)(?:;|,)/i
// Matplotlib writes this fixed SVG 1.1 PUBLIC declaration. Remove it before parsing,
// so the browser XML parser never receives its external DTD URL.
const matplotlibDoctype = /^(\uFEFF?\s*(?:<\?xml version="1\.0" encoding="utf-8" standalone="no"\?>\s*)?)<!DOCTYPE svg PUBLIC "-\/\/W3C\/\/DTD SVG 1\.1\/\/EN"\s+"http:\/\/www\.w3\.org\/Graphics\/SVG\/1\.1\/DTD\/svg11\.dtd">\s*/

export type SvgInspection = {
  size: string
  viewBox: string
  editableTextCount: number
  pathCount: number
  imageCount: number
  rasterCount: number
  externalReferenceCount: number
  activeContentCount: number
  warnings: string[]
}

function dimension(value: string | null): string {
  const trimmed = value?.trim() ?? ''
  return trimmed.length <= 40 && sizePattern.test(trimmed) ? trimmed : '未声明或无法识别'
}

function isExternalReference(value: string): boolean {
  const trimmed = value.trim().replace(/^['"]|['"]$/g, '')
  return Boolean(trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('data:'))
}

export function inspectSvgSource(source: string): SvgInspection {
  const normalized = source.replace(matplotlibDoctype, '$1')
  if (/<!DOCTYPE\b|<!ENTITY\b|<\?xml-stylesheet\b/i.test(normalized)) {
    throw new Error('文件包含文档类型、实体或外部样式声明，已停止检查。')
  }
  const xml = new DOMParser().parseFromString(normalized, 'image/svg+xml')
  if (xml.getElementsByTagName('parsererror').length || xml.documentElement.localName !== 'svg' || xml.documentElement.namespaceURI !== SVG_NS) {
    throw new Error('文件不是可解析的 SVG XML。')
  }
  const root = xml.documentElement
  const width = dimension(root.getAttribute('width'))
  const height = dimension(root.getAttribute('height'))
  const parts = (root.getAttribute('viewBox') ?? '').trim().split(/[\s,]+/)
  const validViewBox = parts.length === 4 && parts.every((part) => part !== '' && Number.isFinite(Number(part)))
  const viewBox = validViewBox ? parts.join(' ') : '未声明或无法识别'
  const elements = Array.from(xml.getElementsByTagName('*'))
  const editableTextCount = elements.filter((element) => element.namespaceURI === SVG_NS && element.localName === 'text').length
  const pathCount = elements.filter((element) => element.namespaceURI === SVG_NS && element.localName === 'path').length
  const images = elements.filter((element) => element.namespaceURI === SVG_NS && element.localName === 'image')
  let externalReferenceCount = 0
  let activeContentCount = 0
  let rasterCount = 0
  for (const element of elements) {
    if (activeElements.has(element.localName)) activeContentCount++
    if (element.localName === 'style' && /@import\b/i.test(element.textContent ?? '')) activeContentCount++
    for (const attribute of Array.from(element.attributes)) {
      if (/^on/i.test(attribute.localName)) activeContentCount++
      const value = attribute.value
      if (attribute.localName === 'href') {
        if (isExternalReference(value)) externalReferenceCount++
        if (/^\s*javascript:/i.test(value)) activeContentCount++
      }
      for (const match of value.matchAll(/url\(\s*([^)]*?)\s*\)/gi)) {
        if (isExternalReference(match[1])) externalReferenceCount++
      }
    }
    if (element.localName === 'style') {
      for (const match of (element.textContent ?? '').matchAll(/url\(\s*([^)]*?)\s*\)/gi)) {
        if (isExternalReference(match[1])) externalReferenceCount++
      }
    }
  }
  for (const image of images) {
    const href = image.getAttribute('href') ?? image.getAttributeNS('http://www.w3.org/1999/xlink', 'href') ?? ''
    if (rasterTypes.test(href)) rasterCount++
  }
  const warnings: string[] = []
  if (editableTextCount === 0 && pathCount > 0) warnings.push('未发现可编辑文字节点；原有文字可能已转曲。')
  if (images.length > 0 && rasterCount < images.length) warnings.push('含图像节点；部分图像类型或来源无法仅凭结构确定，需手动核对。')
  if (externalReferenceCount > 0) warnings.push('发现外部文件或 URL 引用；本检查不会访问它们。')
  if (activeContentCount > 0) warnings.push('发现脚本、事件、动画、嵌入对象或样式导入等活动内容。')
  return {
    size: `${width} × ${height}`, viewBox, editableTextCount, pathCount,
    imageCount: images.length, rasterCount, externalReferenceCount, activeContentCount, warnings,
  }
}

export async function inspectSvgFile(file: File): Promise<SvgInspection> {
  if (file.size > MAX_SVG_INSPECTION_BYTES) throw new Error('SVG 超过 2 MiB，本机检查已拒绝读取。')
  if (!file.name.toLowerCase().endsWith('.svg')) throw new Error('请选择 .svg 文件。')
  return inspectSvgSource(await file.text())
}
