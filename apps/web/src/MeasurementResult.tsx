import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
export type MeasurementStatistics = {
  area: number; area_unit: string; mean: number; min: number; max: number
  std_dev?: number; median?: number; mode?: number
  integrated_density?: number; raw_integrated_density?: number
}

const optionalStatistics = [
  ['std_dev', '标准差'], ['median', '中位数'], ['mode', '众数'],
  ['integrated_density', 'IntDen'], ['raw_integrated_density', 'RawIntDen'],
] as const

const shapeNames: Record<string, string> = { ellipse: '椭圆', polygon: '多边形', full: '全平面', rectangle: '矩形' }

export default function MeasurementResult({ jobId, selection, sampleCount, statistics }: {
  jobId: string
  selection?: { indices: Record<string, number>; roi: { kind: string; x: number; y: number; width: number; height: number } } | null
  sampleCount?: number
  statistics?: MeasurementStatistics
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const roi = selection?.roi
  return <div className="iw-measure-report">
    <p>C/Z/T：{JSON.stringify(selection?.indices ?? {})} · {tx(shapeNames[roi?.kind ?? ''] ?? roi?.kind ?? '')} ROI：
      {roi?.x},{roi?.y} / {roi?.width}×{roi?.height} · {sampleCount} {tx("个像素 · ImageJ1 Measure 面积")}{statistics?.area} {statistics?.area_unit}
      {' · '}{tx("均值")}{statistics?.mean} {tx("· 最小")}{statistics?.min} {tx("· 最大")}{statistics?.max}
      {optionalStatistics.map(([key, label]) => statistics?.[key] !== undefined
        ? <span key={key}> · {tx(label)} {statistics[key]}</span> : null)}
    </p>
    <div className="iw-measure-downloads">
      <a href={`/api/image/jobs/${jobId}/measurement.csv`} download>{tx("下载测量 CSV")}</a>
      <a href={`/api/image/jobs/${jobId}/measurement.json`} download>{tx("保存完整测量记录 JSON")}</a>
      <small>{tx("近期任务只在当前会话保留，请及时下载。JSON 包含来源摘要、ROI、轴位置和完整结果，不含源图文件。")}</small>
    </div>
  </div>
}
