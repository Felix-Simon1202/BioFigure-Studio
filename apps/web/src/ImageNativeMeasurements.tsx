import { useState, type Dispatch, type SetStateAction, type ReactNode } from 'react'
import { nativeMeasureGroup, nativeMeasureLabels, nativeMeasureRows, serializeNativeMeasureCsv,
  serializeNativeMeasureJson, validNativeMeasureCapability,
  type NativeMeasureAsset, type NativeMeasureRequest, type NativeMeasureResult } from './nativeMeasure'
import './ImageNativeMeasurements.css'
import { downloadFile as saveFile } from './downloadFile'
import { nonAreaLabels } from './nonAreaRoi'
import ImageNonAreaPreview from './ImageNonAreaPreview'
import ImageNativeAreaEditor from './ImageNativeAreaEditor'
import { nativeDraftGeometry, nativeDraftParameters, nativeDraftSetter, type NativeMeasurementDraft } from './nativeMeasurementDraft'
import { nativeAreaLabels } from './nativeArea'

const groups = [
  ['geometry', '形状与位置 / Geometry'],
  ['intensity', '强度与阈值 / Intensity'],
  ['position', '坐标与标识 / Position'],
  ['record', '结果记录 / Results'],
] as const
const planeAxes = [['Channel', 'C'], ['Z', 'Z'], ['Time', 'T']] as const

function planeText(plane: Record<string, number> | null | undefined) {
  return plane ? `C=${plane.C ?? 0} · Z=${plane.Z ?? 0} · T=${plane.T ?? 0}` : '无'
}

function calibrationText(calibration: NativeMeasureResult['sampled_calibration'] | undefined) {
  return calibration
    ? `X ${calibration.pixel_width}、Y ${calibration.pixel_height} ${calibration.unit}/px · 强度单位 ${calibration.value_unit}`
    : '未回传'
}

export default function ImageNativeMeasurements({ capability, asset, availableAssets, indices, roi,
  busy, disabledReason, areaDisabledReason, error, result, draft, onDraftChange, renderRoiFiles, onSubmit, onCancel }: {
    renderRoiFiles?: (roi: Record<string, unknown> | null, valid: boolean) => ReactNode
    draft: NativeMeasurementDraft
    onDraftChange: Dispatch<SetStateAction<NativeMeasurementDraft>>
    capability: unknown
    asset: NativeMeasureAsset
    availableAssets: NativeMeasureAsset[]
    indices: Record<string, number>
    roi: Record<string, unknown> | null
    disabledReason?: string
    areaDisabledReason?: string
    busy: boolean
    error?: string | null
    result?: NativeMeasureResult | null
    onSubmit: (request: NativeMeasureRequest) => void | Promise<void>
    onCancel: () => void | Promise<void>
  }) {
  const { selected, decimalPlaces, thresholdEnabled, thresholdMin, thresholdMax, redirectId, redirectIndices, roiKind, pointText, strokeWidth, areaDraft } = draft
  const [localError, setLocalError] = useState('')
  const setSelected = nativeDraftSetter('selected', onDraftChange)
  const setDecimalPlaces = nativeDraftSetter('decimalPlaces', onDraftChange)
  const setThresholdEnabled = nativeDraftSetter('thresholdEnabled', onDraftChange)
  const setThresholdMin = nativeDraftSetter('thresholdMin', onDraftChange)
  const setThresholdMax = nativeDraftSetter('thresholdMax', onDraftChange)
  const setRedirectId = nativeDraftSetter('redirectId', onDraftChange)
  const setRedirectIndices = nativeDraftSetter('redirectIndices', onDraftChange)
  const setRoiKind = nativeDraftSetter('roiKind', onDraftChange)
  const setPointText = nativeDraftSetter('pointText', onDraftChange)
  const setStrokeWidth = nativeDraftSetter('strokeWidth', onDraftChange)
  const setAreaDraft = nativeDraftSetter('areaDraft', onDraftChange)
  const valid = validNativeMeasureCapability(capability)
  const options = valid ? capability.measurements : []
  const activeIds = selected.filter((id) => options.some((entry) => entry.id === id))
  const targets = availableAssets.filter((candidate) => candidate.id !== asset.id && candidate.metadata_status === 'fiji_inspected')
  const target = targets.find((candidate) => candidate.id === redirectId)
  const activeResult = result?.source_sha256 === asset.sha256 ? result : null
  const resultRows = activeResult ? nativeMeasureRows(activeResult) : []
  const nonAreaKinds = valid ? Object.keys(capability.roi_support?.non_area_native_types ?? {})
    .filter((kind) => Object.hasOwn(nonAreaLabels, kind)) : []
  const areaKinds = valid ? Object.keys(capability.roi_support?.native_area_types ?? {}).filter((kind) => Object.hasOwn(nativeAreaLabels, kind)) : []
  let selectedRoi = roi
  let geometryError = roiKind === 'workspace' ? areaDisabledReason : ''
  if (roiKind !== 'workspace') {
    try {
      if (roiKind !== 'imported' && !areaKinds.includes(roiKind) && !nonAreaKinds.includes(roiKind))
        throw new Error('本机引擎未提供该区域类型。')
      selectedRoi = nativeDraftGeometry(draft, asset.axes)
    } catch (cause) { geometryError = cause instanceof Error ? cause.message : '区域参数无效。' }
  }

  function submit() {
    if (!valid || busy || disabledReason || geometryError || asset.metadata_status !== 'fiji_inspected') return
    try {
      const parameters = nativeDraftParameters({ ...draft, selected: activeIds }, targets)
      setLocalError('')
      void onSubmit({ version: '1.0', indices, roi: selectedRoi, settings: parameters.settings,
        redirect_asset_id: parameters.redirect_source, redirect_plane: parameters.redirect_plane })
    } catch (cause) { setLocalError(cause instanceof Error ? cause.message : '测量参数无效。') }
  }

  return <section className="iw-native-measure" aria-label="原生 Set Measurements">
    <header><h3>原生测量设置 <small>ImageJ1 Set Measurements</small></h3>
      <p>源图 {asset.original_name} · SHA-256 {asset.sha256} · {asset.bytes} 字节 · 当前平面 {planeText(indices)}</p>
      <p>当前平面沿用上方工作台；可选择工作台区域，或在下方定义独立原生几何。坐标均为源像素。</p></header>
    {!valid && <p role="alert">本机服务尚未返回完整的 1.0 原生测量能力，无法提交。</p>}
    {valid && <>
      <fieldset disabled={busy}><legend>测量区域</legend>
        <label className="iw-nm-field">原生区域类型
          <select value={roiKind} onChange={(event) => { setRoiKind(event.target.value); setLocalError('') }}>
            <option value="workspace">工作台当前面积区域 / 整个平面</option>
            {draft.importedRoi && <option value="imported">导入的原生复合区域</option>}
            {areaKinds.map((kind) => <option key={kind} value={kind}>{nativeAreaLabels[kind]} / {kind}</option>)}
            {nonAreaKinds.map((kind) => <option key={kind} value={kind}>{nonAreaLabels[kind]} / {kind}</option>)}
          </select></label>
        {areaKinds.includes(roiKind) && <ImageNativeAreaEditor key={roiKind} kind={roiKind} draft={areaDraft} onChange={setAreaDraft} />}
        {nonAreaKinds.includes(roiKind) && <>
          <label className="iw-nm-field">源图顶点（每行一个点）
            <textarea rows={5} value={pointText} placeholder="x,y" onChange={(event) => setPointText(event.target.value)} /></label>
          <p>坐标从 0 开始，可填小数，按源图像素记录。直线需 2 点，角度需 3 点，折线/自由线最多 64 点。</p>
          {['line', 'polyline', 'freeline'].includes(roiKind) && <label className="iw-nm-field">线宽（源像素）
            <input type="number" min={1} max={32} step="any" value={strokeWidth} onChange={(event) => setStrokeWidth(event.target.value)} /></label>}
          {['point', 'multipoint'].includes(roiKind) && <p>单点需 1 点，多点需 2–64 点。每行可填 x,y,位置,计数器编号；省略后两项时均为 0。
            位置 0 使用当前平面，1 起为线性栈位置（C 最快，其次 Z、T）；计数器编号为 0–99。点按原生位置分别生成结果行。</p>}
          <ImageNonAreaPreview key={`${asset.id}:${roiKind}:${indices.C}:${indices.Z}:${indices.T}`}
            asset={asset} indices={indices} kind={roiKind} text={pointText} busy={busy} onChange={setPointText} />
        </>}
        {roiKind === 'imported' && <p>保留文件中的原生复合路径，可直接测量或再次保存；重新定义区域时请选择其它类型。</p>}
        {geometryError && <p role="status">{geometryError}</p>}
        {renderRoiFiles?.(selectedRoi, !geometryError && !disabledReason)}
      </fieldset>
      <fieldset disabled={busy}><legend>原生测量项（{options.length}）</legend>
        <div className="iw-nm-groups">{groups.map(([group, label]) => <div key={group}>
          <h4>{label}</h4>
          {options.filter((entry) => nativeMeasureGroup(entry.id) === group).map((entry) => <label key={entry.id}>
            <input type="checkbox" checked={activeIds.includes(entry.id)}
              onChange={(event) => setSelected((current) => event.target.checked
                ? [...current, entry.id] : current.filter((id) => id !== entry.id))} />
            <span>{nativeMeasureLabels[entry.id] ?? entry.id} · {entry.id.replaceAll('_', ' ')}</span>
          </label>)}</div>)}</div>
      </fieldset>
      <fieldset disabled={busy}><legend>显示与阈值</legend>
        <label className="iw-nm-field">结果表小数位（仅影响显示）
          <input type="number" min={capability.decimal_places.min} max={capability.decimal_places.max}
            value={decimalPlaces} onChange={(event) => setDecimalPlaces(Number(event.target.value))} /></label>
        <label className="iw-nm-check"><input type="checkbox" checked={thresholdEnabled}
          onChange={(event) => setThresholdEnabled(event.target.checked)} />显式设置采样图阈值</label>
        {(thresholdEnabled || activeIds.includes(capability.threshold.explicit_when)) && <div className="iw-nm-fields">
          <label className="iw-nm-field">最小值 <input type="number" step="any" value={thresholdMin}
            onChange={(event) => setThresholdMin(event.target.value)} /></label>
          <label className="iw-nm-field">最大值 <input type="number" step="any" value={thresholdMax}
            onChange={(event) => setThresholdMax(event.target.value)} /></label></div>}
        <p>Limit to threshold 必须显式设置阈值；阈值作用于实际采样的源图或重定向目标。</p>
      </fieldset>
      <fieldset disabled={busy}><legend>第二来源 / Redirect to</legend>
        <label className="iw-nm-field">目标图
          <select value={redirectId} onChange={(event) => { setRedirectId(event.target.value); setRedirectIndices({}) }}>
            <option value="">无 · 使用当前源图</option>
            {redirectId && !target && <option value={redirectId} disabled>原目标已移除，请重新选择</option>}
            {targets.map((candidate) => <option key={candidate.id} value={candidate.id}>
              {candidate.original_name} · {candidate.sha256.slice(0, 12)}
            </option>)}</select></label>
        {target && <><p>目标图须具有相同 X/Y；多平面目标与主源按线性栈索引对齐。以下索引从 0 开始。</p>
          <div className="iw-nm-fields">{planeAxes.map(([axisName, key]) => {
            const axis = target.axes.find((entry) => entry.name === axisName)
            if (!axis || axis.length <= 1) return null
            return <label className="iw-nm-field" key={key}>{key}（0–{axis.length - 1}）
              <input type="number" min={0} max={axis.length - 1} step={1} placeholder={`输入 ${key} 索引`}
                value={redirectIndices[key] ?? ''} onChange={(event) => setRedirectIndices((current) =>
                  ({ ...current, [key]: event.target.value }))} /></label>
          })}</div></>}
      </fieldset>
      <div className="iw-nm-actions"><button type="button" disabled={busy || Boolean(disabledReason) || Boolean(geometryError) || asset.metadata_status !== 'fiji_inspected'}
        onClick={submit}>提交原生 Measure</button>
        {busy && <button type="button" onClick={() => void onCancel()}>取消任务</button>}</div>
    </>}
    {disabledReason && <p role="status">{disabledReason}</p>}
    {(localError || error) && <p role="alert">{localError || error}</p>}
    {activeResult && <section className="iw-nm-results" aria-label="原生测量结果">
      <p>以下为提交时的来源、区域和设置快照；修改当前参数后需重新测量。</p>
      <details><summary>提交时的区域与平面</summary><pre>{JSON.stringify(activeResult.selection ?? { roi: activeResult.roi, current_plane: activeResult.current_plane }, null, 2)}</pre></details>
      {activeResult.native_roi != null && <details><summary>实际原生区域与顶点</summary><pre>{JSON.stringify(activeResult.native_roi, null, 2)}</pre></details>}
      <h4>原生结果 · {activeResult.imagej1_version}</h4>
      <p>{activeResult.implementation} · Fiji SHA-256 {activeResult.fiji_archive_sha256}</p>
      <p>主源 SHA-256 {activeResult.source_sha256} · 第二来源 {activeResult.redirect_sha256 ?? '无'}</p>
      <p>原生设置位 {activeResult.measurement_bits} · 已选项 {activeResult.settings.measurements.join('、') || '无'} · 显示小数位 {activeResult.settings.decimal_places} · 阈值 {activeResult.settings.threshold
        ? `${activeResult.settings.threshold.min}–${activeResult.settings.threshold.max}` : '无'}</p>
      <p>主源线性平面 {activeResult.source_stack_index} · 实际采样平面 {activeResult.sampled_stack_index}</p>
      <p>ROI 主源标定：{calibrationText(activeResult.roi_source_calibration ?? activeResult.source_calibration)}</p>
      <p>实际采样标定：{calibrationText(activeResult.sampled_calibration)}</p>
      <p>Overlay：{activeResult.overlay_count_before ?? '未回传'} → {activeResult.overlay_count}</p>
      <div className="iw-nm-actions"><button type="button" onClick={() => saveFile(
        `biofigure-native-measure-${activeResult.source_sha256.slice(0, 12)}.json`,
        serializeNativeMeasureJson(activeResult), 'application/json')}>下载完整记录 JSON</button>
        <button type="button" onClick={() => saveFile(
          `biofigure-native-measure-${activeResult.source_sha256.slice(0, 12)}.csv`,
          serializeNativeMeasureCsv(activeResult), 'text/csv;charset=utf-8')}>下载原生数值 CSV</button></div>
      <div className="iw-nm-table"><table><thead><tr><th>行</th><th>标签</th>
        {activeResult.headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead>
        <tbody>{resultRows.map((row, index) => <tr key={index}><th>{index + 1}</th>
          <td>{activeResult.labels?.[index] ?? activeResult.label ?? '—'}</td>
          {activeResult.headings.map((heading) => <td key={heading}>
            {row[heading] === null ? <span className="iw-nm-null" title="原生非有限值">null · 非有限</span>
              : row[heading] ?? '—'}</td>)}</tr>)}</tbody></table></div>
      <details><summary>原生显示字符串与非有限列</summary>
        {resultRows.map((_, index) => <div key={index}><strong>第 {index + 1} 行</strong>
          <pre>{activeResult.displayed_rows?.[index] ?? activeResult.displayed_row ?? ''}</pre>
          <p>非有限列：{Array.isArray(activeResult.non_finite_headings[0])
            ? ((activeResult.non_finite_headings as string[][])[index] ?? []).join('、') || '无'
            : (activeResult.non_finite_headings as string[]).join('、') || '无'}</p>
        </div>)}</details>
    </section>}
  </section>
}
