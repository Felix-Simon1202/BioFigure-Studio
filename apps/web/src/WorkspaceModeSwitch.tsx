import { useI18n } from './i18n'
import './WorkspaceNavigation.css'

export default function WorkspaceModeSwitch({ ai, onChange }: { ai: boolean; onChange: (ai: boolean) => void }) {
  const { t } = useI18n()
  return <button type="button" role="switch" aria-checked={ai} aria-label={t('AI 模式', 'AI mode')}
    className="workspace-mode-switch" data-ai={ai} onClick={() => onChange(!ai)}>
    <span className="workspace-mode-thumb" aria-hidden="true" />
    <span>{t('AI 工作台', 'AI workspace')}</span><span>{t('本地', 'Local')}</span>
  </button>
}
