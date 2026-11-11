import catalog from '../../../assets/palettes/scientific.json'

export const scientificPalettes = catalog.palettes
export const scientificPaletteColors: Record<string, string[]> = Object.fromEntries(
  scientificPalettes.map(item => [item.id, item.colors]))

export function paletteChoices(chartType: string) {
  if (chartType === 'r_ggplot') return [] // R connector owns its plotting styles.
  const continuous = ['heatmap', 'embedding_continuous', 'feature', 'dotplot', 'spatial_continuous', 'spatial_feature', 'ecology_environment_gradient']
  return scientificPalettes.filter(item => continuous.includes(chartType) ? item.kind !== 'categorical' : item.kind === 'categorical')
}

/** Standard sRGB relative luminance; a mark/background check, not a CVD test. */
export function contrastAgainstWhite(hex: string): number {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error('Expected a six-digit hex color')
  const linear = [1, 3, 5].map(offset => {
    const value = parseInt(hex.slice(offset, offset + 2), 16) / 255
    return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4
  })
  return 1.05 / (.2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2] + .05)
}

// A preset changes presentation only, never fields, scientific labels or data.
export const chartStylePresets = [
  { id: 'clear', name: { en: 'Clean comparison', 'zh-CN': '清晰比较' }, theme_id: 'scientific_clear', palette_id: 'oc_clear', font_size: 10, line_width: 1.2 },
  { id: 'soft', name: { en: 'Soft composition', 'zh-CN': '柔和构成' }, theme_id: 'scientific_clear', palette_id: 'oc_soft', font_size: 10, line_width: 1.4 },
  { id: 'paired', name: { en: 'Paired comparison', 'zh-CN': '成对比较' }, theme_id: 'scientific_clear', palette_id: 'oc_paired', font_size: 11, line_width: 1.5 },
]
