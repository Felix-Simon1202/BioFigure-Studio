export type NativeMeasureCapability = {
  version: '1.0'
  operation: 'native_set_measurements'
  measurements: { id: string; native_bit: number }[]
  decimal_places: { min: number; max: number; affects: string }
  threshold: { explicit_when: string; applied_to: string }
  redirect: { identity: string; same_xy_required: boolean; stack_alignment: string }
  request_schema: Record<string, unknown>
  roi_support?: { non_area_native_types: Record<string, number>; native_area_types?: Record<string, number> }
}

export type NativeMeasureAsset = {
  id: string; original_name: string; sha256: string; bytes: number
  axes: { name: string; length: number; unit?: string | null; scale?: number | null }[]
  metadata_status: string
  bit_depth?: number | null
}

export type NativeMeasureRequest = {
  version: '1.0'
  indices: Record<string, number>
  roi: Record<string, unknown> | null
  settings: { measurements: string[]; decimal_places: number;
    threshold: { min: number; max: number } | null }
  redirect_asset_id: string | null
  redirect_plane: Record<string, number> | null
}

export type NativeCalibration = {
  pixel_width: number; pixel_height: number; unit: string; value_unit: string
  calibrated_density?: boolean
}

export type NativeMeasureResult = {
  source_sha256: string; redirect_sha256: string | null
  selection?: unknown; current_plane?: Record<string, number>; roi?: unknown
  native_roi?: unknown
  settings: NativeMeasureRequest['settings']; measurement_bits: number
  source_stack_index: number; sampled_stack_index: number
  sampled_calibration: NativeCalibration
  roi_source_calibration?: NativeCalibration; source_calibration?: NativeCalibration
  headings: string[]; row?: Record<string, number | null>; rows?: Record<string, number | null>[]
  label?: string | null; labels?: (string | null)[]
  displayed_row?: string; displayed_rows?: string[]
  non_finite_headings: string[] | string[][]
  overlay_count_before?: number; overlay_count: number; row_count: number
  imagej1_version: string; implementation: string; fiji_archive_sha256: string
}

export function validNativeMeasureCapability(value: unknown): value is NativeMeasureCapability {
  if (!value || typeof value !== 'object') return false
  const item = value as Partial<NativeMeasureCapability>
  const measurements = item.measurements
  return item.version === '1.0' && item.operation === 'native_set_measurements'
    && Array.isArray(measurements) && measurements.length === 24
    && measurements.every((entry) => entry && typeof entry.id === 'string'
      && Number.isInteger(entry.native_bit) && entry.native_bit > 0)
    && new Set(measurements.map((entry) => entry.id)).size === 24
    && new Set(measurements.map((entry) => entry.native_bit)).size === 24
    && !!item.decimal_places && Number.isInteger(item.decimal_places.min)
    && Number.isInteger(item.decimal_places.max) && item.decimal_places.min >= 0
    && item.decimal_places.max <= 9 && item.decimal_places.min <= item.decimal_places.max
    && item.threshold?.explicit_when === 'limit_to_threshold'
    && item.threshold.applied_to === 'sampled_source_or_redirect'
    && item.redirect?.identity === 'asset_id' && item.redirect.same_xy_required === true
    && !!item.request_schema && typeof item.request_schema === 'object'
}

export function nativeMeasureGroup(id: string): 'geometry' | 'intensity' | 'position' | 'record' {
  if (/^(area|centroid|center_of_mass|perimeter|bounding_rectangle|fit_ellipse|shape_descriptors|feret)$/.test(id))
    return 'geometry'
  if (/^(stack_position|invert_y|display_label)$/.test(id)) return 'position'
  if (/^(scientific_notation|nan_empty_cells|add_to_overlay)$/.test(id)) return 'record'
  return 'intensity'
}

// Labels only: supported IDs and native bits always come from the capability API.
export const nativeMeasureLabels: Record<string, string> = {
  area: '面积', mean: '平均强度', std_dev: '标准差', mode: '众数', min_max: '最小值与最大值',
  centroid: '几何中心', center_of_mass: '质心', perimeter: '周长', bounding_rectangle: '外接矩形',
  fit_ellipse: '拟合椭圆', shape_descriptors: '形状描述', feret: 'Feret 直径',
  integrated_density: '积分密度', median: '中位数', skewness: '偏度', kurtosis: '峰度',
  area_fraction: '面积占比', stack_position: '栈位置', limit_to_threshold: '仅测量阈值内像素',
  display_label: '显示来源标签', invert_y: '反转 Y 坐标', scientific_notation: '科学计数法',
  add_to_overlay: '加入原生叠加层', nan_empty_cells: '空单元格显示 NaN',
}

export function nativeMeasureRows(result: NativeMeasureResult): Record<string, number | null>[] {
  return result.rows ?? (result.row ? [result.row] : [])
}

function csvText(value: string): string {
  const guarded = ['=', '+', '-', '@'].includes(value.trimStart()[0]) ? `'${value}` : value
  return `"${guarded.replaceAll('"', '""')}"`
}

function csvNumber(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : ''
}

export function serializeNativeMeasureCsv(result: NativeMeasureResult): string {
  const rows = nativeMeasureRows(result)
  const headings = result.headings
  const header = ['row', 'source_sha256', 'redirect_sha256', 'source_stack_index',
    'sampled_stack_index', 'label', 'displayed_row', 'non_finite_headings',
    'source_calibration_json', 'sampled_calibration_json', 'overlay_count_before',
    'overlay_count_after', ...headings]
  const body = rows.map((row, index) => {
    const invalid = result.non_finite_headings
    const nonFinite = Array.isArray(invalid[0]) ? (invalid as string[][])[index] ?? [] : invalid as string[]
    const displayed = result.displayed_rows?.[index] ?? result.displayed_row ?? ''
    const label = result.labels?.[index] ?? result.label ?? ''
    return [csvNumber(index + 1), csvText(result.source_sha256),
      csvText(result.redirect_sha256 ?? ''), csvNumber(result.source_stack_index),
      csvNumber(result.sampled_stack_index), csvText(label), csvText(displayed),
      csvText(nonFinite.join('|')),
      csvText(JSON.stringify(result.roi_source_calibration ?? result.source_calibration ?? null)),
      csvText(JSON.stringify(result.sampled_calibration)),
      csvNumber(result.overlay_count_before), csvNumber(result.overlay_count),
      ...headings.map((heading) => csvNumber(row[heading])),
    ].join(',')
  })
  return '\ufeff' + [header.map(csvText).join(','), ...body].join('\r\n') + '\r\n'
}

export function serializeNativeMeasureJson(result: NativeMeasureResult): string {
  return JSON.stringify({ version: '1.0', ...result }, null, 2) + '\n'
}
