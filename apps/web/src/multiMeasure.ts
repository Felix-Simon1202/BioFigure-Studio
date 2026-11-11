export type MultiMeasureAxis = { name: string; length: number; unit: string | null; scale: number | null }
export type MultiMeasureSource = { sha256: string; bytes: number; axes: MultiMeasureAxis[] }
export type MultiMeasureRoi = { id: string; name: string; indices: Record<string, number>; roi: {
  kind?: string; x?: number; y?: number; width?: number; height?: number; points?: { x: number; y: number }[]
} }
export type MultiMeasureCollection = { version: '1.0'; source: MultiMeasureSource; items: MultiMeasureRoi[] }
export type MultiMeasureOptions = { measure_all: boolean; one_row_per_slice: boolean; append_results: boolean }
export type MultiMeasureRequest = { collection: MultiMeasureCollection; selected_roi_ids: string[];
  current_plane: Record<string, number>; runs: MultiMeasureOptions[]; measurement_flags: string[] }
export type MultiMeasureRun = { options: MultiMeasureOptions; layout: 'one_row_per_slice' | 'one_row_per_measurement';
  headings: string[]; rows: Record<string, number>[]; row_count: number; new_row_start: number; new_row_count: number }
export type MultiMeasureResult = { source: MultiMeasureSource; roi_order: (Pick<MultiMeasureRoi, 'id' | 'name' | 'roi'> & { saved_indices: Record<string, number> })[];
  current_plane: Record<string, number>; current_stack_index: number;
  stack_planes: { stack_index: number; C: number; Z: number; T: number }[];
  measurement_flags: string[]; runs: MultiMeasureRun[]; imagej1_version: string;
  implementation: string; fiji_archive_sha256: string }

export const multiMeasureFlags = [
  ['std_dev', '标准差 / StdDev'], ['median', '中位数 / Median'], ['mode', '众数 / Mode'],
  ['integrated_density', '积分密度 / IntDen'],
] as const

function csvText(value: string): string {
  // Spreadsheet importers may execute a formula in a text field. Keep native numeric cells numeric.
  const guarded = ['=', '+', '-', '@'].includes(value.trimStart()[0]) ? `'${value}` : value
  return `"${guarded.replaceAll('"', '""')}"`
}

function csvNumber(value: number | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : ''
}

export function serializeMultiMeasureCsv(result: MultiMeasureResult, runIndex: number): string {
  const run = result.runs[runIndex]
  if (!run) throw new RangeError('Multi Measure 运行序号无效。')
  const headings = run.headings
  const columns = ['run_number', 'layout', 'table_row', 'new_in_run', 'source_sha256', 'roi_id', 'roi_name', ...headings]
  const lines = run.rows.map((row, index) => {
    const roi = run.layout === 'one_row_per_measurement'
      ? result.roi_order[index % result.roi_order.length] : undefined
    return [
    csvNumber(runIndex + 1), csvText(run.layout), csvNumber(index + 1), csvText(index >= run.new_row_start ? 'yes' : 'no'),
    csvText(result.source.sha256), csvText(roi?.id ?? ''), csvText(roi?.name ?? ''),
    ...headings.map((heading) => csvNumber(row[heading])),
    ].join(',')
  })
  return '\ufeff' + [columns.map(csvText).join(','), ...lines].join('\r\n') + '\r\n'
}

export function serializeMultiMeasureJson(result: MultiMeasureResult): string {
  return JSON.stringify({ version: '1.0', ...result }, null, 2) + '\n'
}
