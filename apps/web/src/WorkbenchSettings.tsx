import LanguageSettings from './LanguageSettings'
import { useI18n } from './i18n'
import { workbenchText } from './workbenchEnglish'
import { useEffect, useState } from 'react'
import type { WorkbenchConnection } from './DrawingWorkbench'

type ModelConfig = { base_url: string; model: string; api_key: string }
type Props = {
  visible: boolean
  provider: 'local' | 'external'
  external: ModelConfig
  onProvider: (provider: Props['provider']) => void
  onExternal: (config: ModelConfig) => void
  onConnect: (receive: (connection: WorkbenchConnection) => void) => void
  onDisconnect: (done: () => void) => void
  onClose: () => void
}

export default function WorkbenchSettings({ visible, provider, external, onProvider, onExternal, onConnect, onDisconnect, onClose }: Props) {
  const { locale } = useI18n()
  const ui = (text: string) => workbenchText(locale, text)

  const [connection, setConnection] = useState<WorkbenchConnection | null>(null)
  const [notice, setNotice] = useState('')
  const [showToken, setShowToken] = useState(false)
  useEffect(() => {
    if (!connection) return
    const timeout = window.setTimeout(() => {
      setConnection(null)
      setShowToken(false)
      setNotice('连接码已到期。')
    }, connection.expires_in * 1000)
    return () => window.clearTimeout(timeout)
  }, [connection])

  return <div className="dw-settings" hidden={!visible}>
    <LanguageSettings />
    <button onClick={onClose}>{ui("← 返回工作台")}</button>
    <section className="dw-card">
      <h2>{ui("模型连接")}</h2>
      <label>{ui("草案模型")}<select value={provider} onChange={(event) => onProvider(event.target.value === 'external' ? 'external' : 'local')}>
        <option value="local">{ui("本机 Ollama · 已审核 Qwen3")}</option><option value="external">{ui("外部模型 · Chat Completions")}</option>
      </select></label>
      {provider === 'external' && <>
        <p>{ui("外部模型当前只可生成内置合成统计图草案。每次发送须确认，密钥只在本次网页会话内保留。")}</p>
        <label>{ui("服务基础地址")}<input type="url" maxLength={320} placeholder="https://api.deepseek.com" value={external.base_url} onChange={(event) => onExternal({ ...external, base_url: event.target.value })} /></label>
        <label>{ui("模型名")}<input maxLength={120} value={external.model} onChange={(event) => onExternal({ ...external, model: event.target.value })} /></label>
        <label>API Key<input type="password" autoComplete="off" maxLength={512} value={external.api_key} onChange={(event) => onExternal({ ...external, api_key: event.target.value })} /></label>
      </>}
    </section>
    <section className="dw-card">
      <h2>{ui("绘图软件与本机客户端")}</h2>
      <p>{ui("连接码供本机 HTTP 或 MCP 客户端使用，可调用能力目录中的合成绘图、Fiji、R 和项目导出操作。连接码 10 分钟有效，生成新码会撤销旧码。")}</p>
      <div className="dw-quick">
        <button onClick={() => onConnect((next) => { setConnection(next); setShowToken(false); setNotice('连接码已生成。') })}>{ui("生成连接码")}</button>
        <button onClick={() => onDisconnect(() => { setConnection(null); setShowToken(false); setNotice('连接已撤销。') })}>{ui("撤销连接")}</button>
      </div>
      {connection && <>
        <label>{ui("本机连接地址")}<input readOnly value={connection.url} onFocus={(event) => event.target.select()} /></label>
        <label>{ui("连接码")}<input readOnly type={showToken ? 'text' : 'password'} value={connection.token}
          onFocus={(event) => { if (showToken) event.target.select() }} /></label>
        <div className="dw-quick">
          <button onClick={() => setShowToken(!showToken)}>{showToken ? ui("隐藏连接码") : ui("显示连接码")}</button>
          <button onClick={async () => {
            try {
              await navigator.clipboard.writeText(connection.token)
              setNotice('连接码已复制。')
            } catch {
              setShowToken(true)
              setNotice('剪贴板不可用。已显示连接码，可手动选中并复制。')
            }
          }}>{ui("复制连接码")}</button>
        </div>
      </>}
      {notice && <p role="status">{ui(notice)}</p>}
    </section>
  </div>
}
