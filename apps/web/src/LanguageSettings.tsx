import { useI18n } from './i18n'

export default function LanguageSettings() {
  const { locale, setLocale, t } = useI18n()
  return <section className="dw-card">
    <h2>{t('界面语言', 'Interface language')}</h2>
    <label>{t('语言', 'Language')}
      <select value={locale} onChange={(event) => setLocale(event.target.value === 'zh-CN' ? 'zh-CN' : 'en')}>
        <option value="en">English</option>
        <option value="zh-CN">简体中文</option>
      </select>
    </label>
    <p>{t('立即切换并在本机记住选择，不改变数据、图题或项目内容。', 'Changes apply immediately and are remembered on this device. Data, figure titles, and project contents stay unchanged.')}</p>
  </section>
}
