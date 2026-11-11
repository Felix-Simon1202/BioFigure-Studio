import { useI18n } from './i18n'
import { chartStylePresets, contrastAgainstWhite, paletteChoices, scientificPalettes } from './chartPalettes'

type Presentation = { theme_id: string; palette_id: string; font_size: number; line_width: number }
export default function ChartStyleChoices({ chartType, paletteId, onChange }: {
  chartType: string; paletteId: string; onChange: (patch: Partial<Presentation>) => void
}) {
  const { locale, t } = useI18n()
  const choices = paletteChoices(chartType)
  const selected = scientificPalettes.find(item => item.id === paletteId)
  const minimumContrast = selected?.kind === 'categorical' ? Math.min(...selected.colors.map(contrastAgainstWhite)) : null
  if (!choices.length) return <p>{t('R 连接器使用自己的绘图样式；此处的精选配色不应用于 R。', 'The R connector manages its own plot styling; these curated palettes do not apply to R.')}</p>
  return <fieldset style={{ gridColumn: '1 / -1', border: '1px solid #d9d9d9', borderRadius: 8, padding: 12 }}>
    <legend>{t('科研配色与风格', 'Scientific color and style')}</legend>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {choices.map(item => <button type="button" key={item.id} className="secondary"
        aria-pressed={paletteId === item.id} title={item.description[locale]}
        onClick={() => onChange({ palette_id: item.id })}
        style={{ outline: paletteId === item.id ? '2px solid #333' : undefined }}>
        {item.name[locale]}
        <span aria-hidden="true" style={{ display: 'flex', height: 12, marginTop: 6 }}>
          {item.colors.map(color => <span key={color} style={{ background: color, flex: 1, minWidth: 12 }} />)}
        </span>
      </button>)}
    </div>
    <p>{selected ? selected.description[locale] : t('选择配色以预览；不会改动数据或标签。', 'Choose colors to preview; data and labels stay intact.')}</p>
    {minimumContrast !== null && minimumContrast < 3 && <p role="status">{t('部分颜色与白底对比度较低：请用于较大填色区域，或选择清晰分组。', 'Some colors have low contrast against white: use larger filled areas or choose Open Clear.')}</p>}
    {choices.some(item => item.kind === 'categorical') && <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {chartStylePresets.map(({ id, name, ...style }) => <button type="button" className="secondary" key={id}
        onClick={() => onChange(style)}>{t('应用风格：', 'Apply style: ')}{name[locale]}</button>)}
    </div>}
    <small>{t('类别颜色不保证色觉无障碍；细小元素优先清晰色，并结合点形或标签。成对配色请核对类别顺序。', 'Categorical colors are not certified colorblind-safe. Use clear colors and redundant shapes or labels for small elements. Check category order for paired colors.')}</small>
  </fieldset>
}
