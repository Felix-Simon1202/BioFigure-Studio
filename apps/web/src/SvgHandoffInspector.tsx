import { useI18n } from './i18n'
import { workbenchText } from './workbenchEnglish'
import { useRef, useState } from 'react'
import { inspectSvgFile, type SvgInspection } from './svgHandoffInspection'

export default function SvgHandoffInspector() {
  const { locale } = useI18n()
  const ui = (text: string) => workbenchText(locale, text)

  const [report, setReport] = useState<SvgInspection | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const sequence = useRef(0)

  const inspect = async (file?: File) => {
    const current = ++sequence.current
    setReport(null)
    setError('')
    if (!file) return
    setBusy(true)
    try {
      const result = await inspectSvgFile(file)
      if (current !== sequence.current) return
      setReport(result)
    } catch (cause) {
      if (current === sequence.current) setError(cause instanceof Error ? cause.message : 'SVG 检查失败。')
    } finally {
      if (current === sequence.current) setBusy(false)
    }
  }

  return <div className="dw-svg-inspector">
    <label>{ui("检查编辑后的 SVG")} <input type="file" accept=".svg,image/svg+xml" disabled={busy}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0]
          event.currentTarget.value = ''
          void inspect(file)
        }} />
    </label>
    <p>{ui("仅在浏览器内读取结构，最多 2 MiB；不显示图像、不上传、不写入项目。检查结果不能证明科研内容或软件兼容性。")}</p>
    {busy && <p role="status">{ui("正在本机检查 SVG…")}</p>}
    {error && <p role="alert">{ui(error)}</p>}
    {report && <div role="status" className="dw-svg-report">
      <strong>{ui("本机结构报告")}</strong>
      <dl>
        <dt>{ui("尺寸")}</dt><dd>{ui(report.size)}</dd>
        <dt>viewBox</dt><dd>{ui(report.viewBox)}</dd>
        <dt>{ui("可编辑文字")}</dt><dd>{report.editableTextCount} {ui("个 text 节点")}</dd>
        <dt>{ui("图像层")}</dt><dd>{report.imageCount} {ui("个，其中可识别栅格")} {report.rasterCount} {ui("个")}</dd>
        <dt>{ui("外部引用")}</dt><dd>{report.externalReferenceCount} {ui("处")}</dd>
        <dt>{ui("活动内容")}</dt><dd>{report.activeContentCount} {ui("处")}</dd>
      </dl>
      {report.warnings.map((warning) => <p key={ui(warning)}>{ui(warning)}</p>)}
      <p>{ui("原文件仍由您保留；本检查没有修改或保存文件。")}</p>
    </div>}
  </div>
}
