import { useI18n } from './i18n'
import { interfaceDiagnostic } from './interfaceDiagnostics'
import { useState } from 'react'
import { multiMeasureFlags, serializeMultiMeasureCsv, serializeMultiMeasureJson,
  type MultiMeasureCollection, type MultiMeasureOptions, type MultiMeasureRequest,
  type MultiMeasureResult } from './multiMeasure'
import './ImageMultiMeasure.css'

const initialRun: MultiMeasureOptions = { measure_all: true, one_row_per_slice: true, append_results: false }

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function planeText(plane: Record<string, number>) {
  return `C=${plane.C ?? 0}, Z=${plane.Z ?? 0}, T=${plane.T ?? 0}`
}

export default function ImageMultiMeasure({ collection, currentPlane, busy, error, result, onSubmit, onCancel, disabledReason }: {
  collection: MultiMeasureCollection
  currentPlane: Record<string, number>
  busy: boolean
  disabledReason?: string
  error?: string | null
  result?: MultiMeasureResult | null
  onSubmit: (request: MultiMeasureRequest) => void | Promise<void>
  onCancel: () => void | Promise<void>
}) {
  const { locale } = useI18n()
  const tx = (text: string) => interfaceDiagnostic(locale, text)

  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [runs, setRuns] = useState<MultiMeasureOptions[]>([initialRun])
  const [flags, setFlags] = useState<string[]>([])
  const items = collection.items
  const available = new Map(items.map((item) => [item.id, item]))
  const selected = selectedIds.filter((id) => available.has(id))
  const selectedNames = selected.map((id) => available.get(id)?.name)
  const duplicateNames = new Set(selectedNames).size !== selectedNames.length
  const activeResult = result?.source.sha256 === collection.source.sha256
    && result.source.bytes === collection.source.bytes ? result : null

  function toggleRoi(id: string, checked: boolean) {
    setSelectedIds((current) => checked ? [...current.filter((value) => value !== id), id]
      : current.filter((value) => value !== id))
  }

  function updateRun(index: number, key: keyof MultiMeasureOptions, checked: boolean) {
    setRuns((current) => current.map((run, position) => position === index ? { ...run, [key]: checked } : run))
  }

  function submit() {
    if (busy || disabledReason || selected.length === 0 || selected.length > 16 || duplicateNames) return
    void onSubmit({ collection, selected_roi_ids: selected, current_plane: currentPlane,
      runs, measurement_flags: flags })
  }

  return <section className="iw-multi-measure" aria-label="ROI Manager Multi Measure">
    <header><h3>{tx("原生 Multi Measure")}<span>ImageJ1 ROI Manager</span></h3>
      <p>{tx("跨线性栈平面测量。保存的 ROI C/Z/T 位置只作来源记录；当前平面仅用于未勾选“全部平面”的运行。")}</p></header>
    <p className="iw-mm-source">{tx("源图 SHA-256")}{collection.source.sha256} · {collection.source.bytes} {tx("字节 · 当前")}{planeText(currentPlane)}</p>
    <fieldset disabled={busy}><legend>{tx("ROI 顺序 / ROI order（1–16）")}</legend>
      <p>{tx("按勾选先后决定原生命令的 ROI 顺序。所选名称必须互异。")}</p>
      <div className="iw-mm-rois">{items.map((item) => <label key={item.id}>
        <input type="checkbox" checked={selected.includes(item.id)} disabled={!selected.includes(item.id) && selected.length >= 16}
          onChange={(event) => toggleRoi(item.id, event.target.checked)} />
        <span>{selected.includes(item.id) ? `${selected.indexOf(item.id) + 1}. ` : ''}{item.name}</span>
        <small>{tx("保存位置")}{planeText(item.indices)}</small>
      </label>)}</div>
    </fieldset>
    {duplicateNames && <p role="alert">{tx("所选 ROI 名称重复，原生结果列无法区分。")}</p>}
    <fieldset disabled={busy}><legend>{tx("统计选项 / Measurements")}</legend>
      <p>{tx("面积、均值、最小值、最大值固定启用。")}</p>
      <div className="iw-mm-checks">{multiMeasureFlags.map(([key, label]) => <label key={key}>
        <input type="checkbox" checked={flags.includes(key)} onChange={(event) => setFlags((current) =>
          event.target.checked ? [...current, key] : current.filter((value) => value !== key))} />{tx(label)}
      </label>)}</div>
    </fieldset>
    <fieldset disabled={busy}><legend>{tx("原生命令运行 / Native runs（最多 3 次）")}</legend>
      <p>{tx("每次在同一 Fiji 进程执行；追加仅使用相同表格布局的历史结果。首次追加等同新表。")}</p>
      {runs.map((run, index) => <div className="iw-mm-run" key={index}>
        <strong>{tx("第")}{index + 1} {tx("次")}</strong>
        <label><input type="checkbox" checked={run.measure_all} onChange={(event) => updateRun(index, 'measure_all', event.target.checked)} />{tx("测量所有线性平面 / Measure all")}</label>
        <label><input type="checkbox" checked={run.one_row_per_slice} onChange={(event) => updateRun(index, 'one_row_per_slice', event.target.checked)} />{tx("每平面一行 / One row per slice")}</label>
        <label><input type="checkbox" checked={run.append_results} onChange={(event) => updateRun(index, 'append_results', event.target.checked)} />{tx("追加同布局结果 / Append")}</label>
        {runs.length > 1 && <button type="button" onClick={() => setRuns((current) => current.filter((_, position) => position !== index))}>{tx("移除")}</button>}
      </div>)}
      <button type="button" disabled={runs.length >= 3} onClick={() => setRuns((current) => [...current, { ...initialRun }])}>{tx("添加一次运行")}</button>
    </fieldset>
    <div className="iw-mm-actions"><button type="button" disabled={busy || Boolean(disabledReason) || selected.length === 0 || duplicateNames} onClick={submit}>{tx("运行原生 Multi Measure")}</button>
      {busy && <button type="button" onClick={() => void onCancel()}>{tx("取消")}</button>}</div>
    {disabledReason && <p role="status">{tx(disabledReason)}</p>}
    {error && <p role="alert">{tx(error)}</p>}
    {activeResult && <section className="iw-mm-results" aria-label={tx("Multi Measure 结果")}>
      <h4>{tx("原生结果 / Native results")}</h4>
      <p>{tx("以下结果使用提交时的参数快照；修改上方选项后需重新运行。")}</p>
      <p>{activeResult.implementation} · ImageJ1 {activeResult.imagej1_version} · Fiji SHA-256 {activeResult.fiji_archive_sha256}</p>
      <p>{tx("执行时当前平面")}{planeText(activeResult.current_plane)} {tx("· 线性栈索引")}{activeResult.current_stack_index}</p>
      <p>{tx("ROI 顺序：")}{activeResult.roi_order.map((item, index) => tx(`${index + 1}. ${item.name}（保存 ${planeText(item.saved_indices)}）`)).join('；')}</p>
      <details><summary>{tx("线性平面映射 / C/Z/T map（")}{activeResult.stack_planes.length}）</summary>
        <div className="iw-mm-plane-map">{activeResult.stack_planes.map((plane) => <span key={plane.stack_index}>
          {plane.stack_index} → C={plane.C}, Z={plane.Z}, T={plane.T}</span>)}</div>
      </details>
      <button type="button" onClick={() => download(`biofigure-multi-measure-${activeResult.source.sha256.slice(0, 12)}.json`,
        serializeMultiMeasureJson(activeResult), 'application/json')}>{tx("下载完整记录 JSON")}</button>
      {activeResult.runs.map((run, index) => <section className="iw-mm-result-run" key={index}>
        <h5>{tx("第")}{index + 1} {tx("次 ·")}{run.layout === 'one_row_per_slice' ? tx('每平面一行') : tx('每次 ROI 测量一行')}</h5>
        <p>{tx("全部平面")}{run.options.measure_all ? tx('是') : tx('否')} {tx("· 追加")}{run.options.append_results ? tx('是') : tx('否')} {tx("· 全表")}{run.row_count} {tx("行 · 本次新增第")}{run.new_row_start + 1}–{run.new_row_start + run.new_row_count} {tx("行")}</p>
        <button type="button" onClick={() => download(`biofigure-multi-measure-${activeResult.source.sha256.slice(0, 12)}-run-${index + 1}.csv`,
          serializeMultiMeasureCsv(activeResult, index), 'text/csv;charset=utf-8')}>{tx("下载本次全表 CSV")}</button>
        <div className="iw-mm-table"><table><thead><tr><th>{tx("表格行")}</th>{run.headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead>
          <tbody>{run.rows.map((row, rowIndex) => <tr key={rowIndex} className={rowIndex >= run.new_row_start ? 'iw-mm-new' : ''}>
            <th>{rowIndex + 1}{rowIndex >= run.new_row_start ? tx(' · 新增') : ''}</th>
            {run.headings.map((heading) => <td key={heading}>{row[heading] ?? '—'}</td>)}
          </tr>)}</tbody></table></div>
      </section>)}
    </section>}
  </section>
}
