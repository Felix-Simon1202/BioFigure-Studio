import { emptyIllustration, validateIllustration, type IllustrationSection, type IllustrationSpec } from './illustration'

export const minimalVectorStyleVersion = 'biofigure-minimal-vector/1.0'

export function minimalVectorSectionStyle(doc: IllustrationSpec, section: IllustrationSection) {
  if (!doc.provenance.note.startsWith(`[${minimalVectorStyleVersion}] `)) return null
  const badge = section.id === 'branch_a' || section.id === 'result_a' ? 'A'
    : section.id === 'branch_b' || section.id === 'result_b' ? 'B' : null
  return { fill: section.id === 'shared' ? '#eef1f2' : '#ffffff', stroke: '#56616a', strokeWidth: section.id === 'shared' ? 3 : 2, badge }
}

export const usesMinimalVectorStyle = (doc: IllustrationSpec) => doc.provenance.note.startsWith(`[${minimalVectorStyleVersion}] `)
export const visibleProvenanceNote = (doc: IllustrationSpec) => usesMinimalVectorStyle(doc)
  ? doc.provenance.note.slice(`[${minimalVectorStyleVersion}] `.length) : doc.provenance.note

export type BranchWorkflowInput = {
  title: string
  sharedStep: string
  branchA: string
  stepA: string
  resultA: string
  branchB: string
  stepB: string
  resultB: string
}

export const syntheticBranchExample: BranchWorkflowInput = {
  title: '合成细胞样本双分支流程',
  sharedStep: '准备合成细胞样本；以下步骤仅用于演示排版。',
  branchA: '对照组',
  stepA: '按示例方案 A 处理。',
  resultA: '记录示例观察结果 A。',
  branchB: '处理组',
  stepB: '按示例方案 B 处理。',
  resultB: '记录示例观察结果 B。',
}
export const syntheticBranchParagraph = '本段为合成演示。图题为[1]“合成细胞样本双分支流程”。共同起始步骤为[2]“准备合成细胞样本；以下步骤仅用于演示排版。”。分支 A 名为[3]“对照组”，处理为[4]“按示例方案 A 处理。”，结果为[5]“记录示例观察结果 A。”。分支 B 名为[6]“处理组”，处理为[7]“按示例方案 B 处理。”，结果为[8]“记录示例观察结果 B。”。'

export type IllustrationModelExtraction = { provider: 'local'; sample_id: 'synthetic-branch-v1'; source_text: string; fields: BranchWorkflowInput }

export function verifySyntheticExtraction(value: unknown): IllustrationModelExtraction {
  const response = value as IllustrationModelExtraction
  if (!response || response.provider !== 'local' || response.sample_id !== 'synthetic-branch-v1' || response.source_text !== syntheticBranchParagraph ||
      !response.fields || Object.keys(response.fields).length !== Object.keys(syntheticBranchExample).length ||
      (Object.keys(syntheticBranchExample) as (keyof BranchWorkflowInput)[]).some((key) => response.fields[key] !== syntheticBranchExample[key])) {
    throw new Error('本机模型结果与固定合成段落不一致，请改用手动填写。')
  }
  return response
}

const fields: { key: keyof BranchWorkflowInput; label: string; max: number }[] = [
  { key: 'title', label: '图题', max: 120 },
  { key: 'sharedStep', label: '共同起始步骤', max: 60 },
  { key: 'branchA', label: '分支 A 名称', max: 7 },
  { key: 'stepA', label: '分支 A 处理', max: 60 },
  { key: 'resultA', label: '分支 A 结果', max: 60 },
  { key: 'branchB', label: '分支 B 名称', max: 7 },
  { key: 'stepB', label: '分支 B 处理', max: 60 },
  { key: 'resultB', label: '分支 B 结果', max: 60 },
]
export const branchWorkflowFields = fields

export function buildBranchWorkflow(input: BranchWorkflowInput, source: 'manual' | 'local_model' = 'manual'): IllustrationSpec {
  const clean = {} as BranchWorkflowInput
  for (const { key, label, max } of fields) {
    const value = input[key]?.trim()
    if (!value || value.length > max || [...value].some((character) => { const code = character.codePointAt(0)!; return code < 32 || code === 127 })) {
      throw new Error(`${label}不能为空、含控制字符或超过 ${max} 字。`)
    }
    clean[key] = value
  }
  const doc = emptyIllustration('experimental_workflow')
  doc.title = clean.title
  doc.provenance.note = `[${minimalVectorStyleVersion}] ` + (source === 'local_model'
    ? '本机已审核模型从固定合成段落提取字段，逐字核对后由用户确认；未推断科研事实；所有步骤待核实。来源：synthetic-branch-v1。'
    : '内置双分支结构化草案；全部文字来自用户输入或明确选择的合成示例；未调用模型、未推断科研事实；所有步骤待核实。')
  const step = (id: string, title: string, description: string, x: number, y: number) => ({
    id, kind: 'step' as const, title, description, x, y, width: 230, height: 190,
    scientific_status: 'needs_review' as const, evidence_ids: [],
  })
  doc.sections = [
    step('shared', '起始步骤', clean.sharedStep, 30, 225),
    step('branch_a', clean.branchA, clean.stepA, 345, 30),
    step('branch_b', clean.branchB, clean.stepB, 345, 420),
    step('result_a', 'A 结果', clean.resultA, 700, 30),
    step('result_b', 'B 结果', clean.resultB, 700, 420),
  ]
  doc.flow_links = [
    { id: 'flow_a', source_section_id: 'shared', target_section_id: 'branch_a', label: clean.branchA },
    { id: 'flow_b', source_section_id: 'shared', target_section_id: 'branch_b', label: clean.branchB },
    { id: 'flow_a_result', source_section_id: 'branch_a', target_section_id: 'result_a', label: '' },
    { id: 'flow_b_result', source_section_id: 'branch_b', target_section_id: 'result_b', label: '' },
  ]
  return validateIllustration(doc)
}
