import { componentRegistry, anchorPoint, orthogonalPoints, pointsPath, flowPoints, type IllustrationSpec, type IllustrationSection, type ComponentDefinition } from './illustration'
import { componentSvg, COMPONENT_ARTWORK_VERSION } from './illustrationArtwork'
import { minimalVectorSectionStyle, usesMinimalVectorStyle } from './illustrationSkill'
import { mechanismRelationLabelPosition, mechanismRelationStyle } from './illustrationMechanismStyle'
import { timelineSvg } from './illustrationTimeline'
import { mechanismRelationStyleVersion } from './illustrationMechanismStyle'

const escapeXml = (value: string) => value.replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[character]!)
export const relationInk = '#52635e'
export const sectionLines=(section:IllustrationSection)=>{const size=Math.max(8,Math.floor((section.width-32)/14));return section.description.match(new RegExp(`.{1,${size}}`,'gu'))??[]}

function renderShapeSvg(definition: ComponentDefinition, fill: string) {
  return componentSvg(definition.id, fill)
}

export function toSvg(doc: IllustrationSpec, locale: 'en' | 'zh-CN' = 'zh-CN') {
  if(doc.timeline)return `<svg xmlns="http://www.w3.org/2000/svg" width="${doc.canvas.width}" height="${doc.canvas.height}" viewBox="0 0 ${doc.canvas.width} ${doc.canvas.height}"><title>${escapeXml(doc.title)}</title><metadata>${escapeXml(JSON.stringify({spec_version:doc.spec_version,document_kind:doc.document_kind,timeline_version:doc.timeline.version,provenance:doc.provenance}))}</metadata><rect width="100%" height="100%" fill="${doc.canvas.background}"/>${timelineSvg(doc.timeline, locale)}</svg>`
  const byId = new Map(doc.nodes.map((node) => [node.id, node]))
  const minimal=usesMinimalVectorStyle(doc)
  const sections=doc.sections.map((section,index)=>{
    const style=minimalVectorSectionStyle(doc,section)
    const badge=style?.badge?`<g data-branch-mark="${style.badge}"><circle cx="${section.x+section.width-18}" cy="${section.y+23}" r="11" fill="#ffffff" stroke="${style.stroke}" stroke-width="2"/><text x="${section.x+section.width-18}" y="${section.y+28}" text-anchor="middle" font-family="Noto Sans SC, sans-serif" font-size="13" fill="#26332f">${style.badge}</text></g>`:''
    return `<g data-section-kind="${section.kind}" data-section-id="${section.id}" data-scientific-status="${section.scientific_status}"><rect x="${section.x}" y="${section.y}" width="${section.width}" height="${section.height}" rx="18" fill="${style?.fill??'#f7faf8'}" stroke="${style?.stroke??'#9ab8ad'}" stroke-width="${style?.strokeWidth??2}"/><text x="${section.x+18}" y="${section.y+32}" font-family="Noto Sans SC, sans-serif" font-size="18" fill="#26332f">${escapeXml(section.kind==='step'?`${index+1}. ${section.title}`:section.title)}</text>${sectionLines(section).map((line,i)=>`<text x="${section.x+18}" y="${section.y+60+i*20}" font-family="Noto Sans SC, sans-serif" font-size="14" fill="#52635e">${escapeXml(line)}</text>`).join('')}${badge}</g>`
  }).join('')
  const flows=doc.flow_links.map(link=>{const source=doc.sections.find(section=>section.id===link.source_section_id)!,target=doc.sections.find(section=>section.id===link.target_section_id)!,points=flowPoints(source,target),middle={x:(points[0].x+points[1].x)/2,y:(points[0].y+points[1].y)/2};return `<g data-flow-kind="sequence" data-flow-id="${link.id}"><path d="${pointsPath(points)}" fill="none" stroke="${minimal?'#56616a':'#a06128'}" stroke-width="3" ${minimal?'':'stroke-dasharray="7 5" '}marker-end="url(#flow-arrow)"/><title>流程顺序</title>${link.label?`<text x="${middle.x}" y="${middle.y-8}" text-anchor="middle" font-family="Noto Sans SC, sans-serif" font-size="13">${escapeXml(link.label)}</text>`:''}</g>`}).join('')
  const edges = doc.edges.map((edge) => {
    const start = anchorPoint(byId.get(edge.source.node_id)!, edge.source.anchor_id)
    const end = anchorPoint(byId.get(edge.target.node_id)!, edge.target.anchor_id)
    const points = orthogonalPoints(start, end)
    const position = mechanismRelationLabelPosition(points)
    const style = mechanismRelationStyle(edge, locale)
    const marker = style.markerEnd ? ` marker-end="${style.markerEnd}"` : ''
    const dash = style.strokeDasharray ? ` stroke-dasharray="${style.strokeDasharray}"` : ''
    return `<g data-relation="${edge.relation}" data-relation-style="${mechanismRelationStyleVersion}" data-scientific-status="${edge.scientific_status}"><path d="${pointsPath(points)}" fill="none" stroke="${relationInk}" stroke-width="3"${marker}${dash}/><text x="${position.x}" y="${position.y}" text-anchor="${position.anchor}" font-family="Noto Sans SC, sans-serif" font-size="14" fill="${relationInk}">${escapeXml(style.label)}</text></g>`
  }).join('')
  const nodes = [...doc.nodes].sort((a,b) => a.z_index-b.z_index).map((node) => { const def = componentRegistry.find((item) => item.id === node.component_id)!; return `<g id="${node.id}" data-component-id="${node.component_id}" data-entity-type="${node.entity_type}" data-scientific-status="${node.scientific_status}" transform="translate(${node.x+node.width/2} ${node.y+node.height/2}) rotate(${node.rotation}) translate(${-node.width/2} ${-node.height/2})"><g transform="scale(${node.width/def.width} ${node.height/def.height})">${renderShapeSvg(def,node.fill)}</g>${node.label ? `<text x="${node.width/2}" y="${node.height+20}" text-anchor="middle" font-family="Noto Sans SC, sans-serif" font-size="15" fill="${node.text_color}">${escapeXml(node.label)}</text>` : ''}</g>` }).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${doc.canvas.width}" height="${doc.canvas.height}" viewBox="0 0 ${doc.canvas.width} ${doc.canvas.height}"><title>${escapeXml(doc.title)}</title><metadata>${escapeXml(JSON.stringify({spec_version:doc.spec_version,document_kind:doc.document_kind,provenance:doc.provenance,component_artwork_version:COMPONENT_ARTWORK_VERSION,evidence_records:doc.evidence_records}))}</metadata><defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9Z" fill="#52635e"/></marker><marker id="flow-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0 L9 4.5 L0 9Z" fill="${minimal?'#56616a':'#a06128'}"/></marker><marker id="circle" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><circle cx="4.5" cy="4.5" r="3" fill="#fff" stroke="#52635e" stroke-width="2"/></marker><marker id="bar" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M8 0 V10" stroke="#52635e" stroke-width="3"/></marker></defs><rect width="100%" height="100%" fill="${doc.canvas.background}"/>${sections}${flows}${edges}${nodes}</svg>`
}

