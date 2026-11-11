import type { Locale } from './i18n'
import { imageUiMessages, imageUiPatterns } from './imageUiMessages'

// Translate only explicit interface diagnostic boundaries. Unknown source or
// user text is returned verbatim; nothing is rewritten in documents or DOM.
const diagnosticEnglish: Record<string, string> = {
  'Multi Measure 运行序号无效。': 'Invalid Multi Measure run number.',
  'SVG 超过 2 MiB，本机检查已拒绝读取。': 'The SVG exceeds 2 MiB and cannot be inspected locally.',
  '中心轴两端点不能重合。': 'The two axis endpoints must be different.',
  '关系 ID、端点、类型、状态或证据无效。': 'Invalid relationship ID, endpoints, type, status, or evidence.',
  '分组包含重复或不存在的对象。': 'The group contains duplicate or missing objects.',
  '刻度标签数量须与时间点相同。': 'Provide one tick label for each time point.',
  '刻度标签超出画布；请缩短文字。': 'A tick label extends beyond the canvas. Shorten its text.',
  '刻度标签过密；请缩短文字或调整时间点。': 'Tick labels overlap. Shorten the text or adjust the time points.',
  '区域包围范围超过 100 万候选像素。': 'The region bounding box exceeds one million candidate pixels.',
  '发现外部文件或 URL 引用；本检查不会访问它们。': 'External file or URL references were found. This check does not access them.',
  '发现脚本、事件、动画、嵌入对象或样式导入等活动内容。': 'Active content was found, including scripts, events, animation, embedded objects, or stylesheet imports.',
  '只支持 IllustrationSpec 1.0、1.1、1.2 或 1.3；不会静默迁移未知版本。': 'Only IllustrationSpec 1.0, 1.1, 1.2, and 1.3 are supported. Unknown versions are not migrated automatically.',
  '含图像节点；部分图像类型或来源无法仅凭结构确定，需手动核对。': 'Image nodes were found. Some image types or sources require manual review.',
  '图像中保留的多边形顶点无效，请切回该图像修正后保存。': 'A saved polygon has invalid vertices. Return to that image and correct it before saving.',
  '图形摘要最多六个面板。': 'A graphical abstract supports up to six panels.',
  '实验组名称或采样时刻无效；请缩短组名，并把采样天数按顺序列在刻度中。': 'Invalid group name or sampling times. Shorten the name and list sampling days in tick order.',
  '宽和高必须为正。': 'Width and height must be positive.',
  '导入区域已失效，请重新导入。': 'The imported region is no longer available. Import it again.',
  '导入结果缺少区域顶点。': 'The import result is missing region vertices.',
  '布尔组合需要 2–8 个已加入的简单区域。': 'A Boolean combination requires 2–8 existing simple regions.',
  '干预区间须指定实验组、起止刻度和名称。': 'Specify the group, start and end ticks, and label for the intervention.',
  '干预名称长于区间；请缩短文字或调整时间点。': 'The intervention label is wider than its interval. Shorten it or adjust the time points.',
  '所有几何参数须填写有限数值。': 'All geometry parameters must be finite numbers.',
  '摘要或流程至少需要两个分区；请从空白模板开始。': 'An abstract or workflow requires at least two sections. Start from a blank template.',
  '文件不是可解析的 SVG XML。': 'The file is not valid SVG XML.',
  '文件包含文档类型、实体或外部样式声明，已停止检查。': 'Inspection stopped because the file contains a document type, entity, or external stylesheet declaration.',
  '旋转后的节点超出画布。': 'The rotated node extends beyond the canvas.',
  '旋转矩形宽度必须为正。': 'The rotated rectangle width must be positive.',
  '时间刻度须为 0–365 的严格递增整数天数，并填写简短标签。': 'Time ticks must be strictly increasing whole days from 0–365, each with a short label.',
  '时间轴结构无效；请使用 960×640 画布、两个组、明确刻度、阶段和一段干预。': 'Invalid timeline structure. Use a 960×640 canvas, two groups, explicit ticks and stages, and one intervention.',
  '显示精度须为 0–9。': 'Display precision must be from 0–9.',
  '未发现可编辑文字节点；原有文字可能已转曲。': 'No editable text nodes were found. Text may have been converted to paths.',
  '未支持的原生面积类型。': 'This native area type is not supported.',
  '本机模型结果与固定合成段落不一致，请改用手动填写。': 'The local model result does not match the fixed synthetic paragraph. Enter the fields manually.',
  '机制图不能包含摘要分区或流程箭头。': 'Mechanism diagrams cannot contain abstract sections or workflow arrows.',
  '样条拟合点数须为 8–512 整数。': 'The spline point count must be an integer from 8–512.',
  '流程箭头只能用于实验流程图。': 'Workflow arrows are available only in experimental workflows.',
  '流程顺序箭头 ID、步骤顺序或标签无效。': 'Invalid workflow arrow ID, step order, or label.',
  '用户已核实的关系必须引用至少一条证据。': 'A user-verified relationship must cite at least one evidence record.',
  '用户已核实的节点必须引用至少一条证据。': 'A user-verified node must cite at least one evidence record.',
  '用户已核实的面板或步骤必须引用证据。': 'A user-verified panel or step must cite evidence.',
  '画布尺寸、背景或网格设置无效。': 'Invalid canvas dimensions, background, or grid settings.',
  '相邻时间点距离过近；请缩小时间范围或减少刻度。': 'Adjacent time points are too close. Narrow the time range or use fewer ticks.',
  '第二来源已失效，请重新选择。': 'The second source is no longer available. Select it again.',
  '线不能为零长度；角度的相邻顶点必须不同。': 'Lines must have nonzero length, and adjacent angle vertices must be different.',
  '线宽须为 1–32 的有限像素数。': 'Line width must be a finite value from 1–32 pixels.',
  '组件或机制来源清单与项目不一致。': 'The component or mechanism provenance does not match the project.',
  '节点 ID 无效或重复。': 'A node ID is invalid or duplicated.',
  '节点必须完整位于所属面板或步骤内。': 'A node must fit entirely inside its parent panel or step.',
  '节点未知，或位置、尺寸、旋转无效。': 'The node is unknown, or its position, dimensions, or rotation are invalid.',
  '节点样式、实体、文字、状态或证据无效。': 'Invalid node style, entity, text, status, or evidence.',
  '证据仍被对象引用；请先逐项取消引用。': 'This evidence is still referenced. Remove its references before deleting it.',
  '证据记录不存在。': 'The evidence record does not exist.',
  '证据记录格式无效或 ID 重复。': 'An evidence record is invalid or has a duplicate ID.',
  '请为每对相邻时间点填写阶段说明。': 'Provide a stage label for each pair of adjacent time points.',
  '请填写 2–8 个时间点。': 'Enter 2–8 time points.',
  '请填写有效阈值范围，最小值不能大于最大值。': 'Enter a valid threshold range. The minimum must not exceed the maximum.',
  '请选择 .svg 文件。': 'Choose an .svg file.',
  '请选择已支持的原生区域类型。': 'Choose a supported native region type.',
  '这个区域类型尚无编辑入口。': 'An editor is not yet available for this region type.',
  '追踪区域节点必须为整数。': 'Traced-region vertices must use integer coordinates.',
  '长短轴比须在 0–1 之间，且不为 0。': 'The minor-to-major axis ratio must be greater than 0 and no greater than 1.',
  '阶段说明数量须比时间点少一个。': 'Provide one fewer stage label than time points.',
  '阶段说明长于对应时间段；请缩短文字或调整时间点。': 'The stage label is wider than its interval. Shorten it or adjust the time points.',
  '需要已检查的 X/Y 尺寸，且线性平面不超过 64。': 'Verified X/Y dimensions are required, with no more than 64 linear planes.',
  '面板或步骤不能重叠。': 'Panels or steps must not overlap.',
  '面板或步骤文字超出固定版式；请缩短文字或扩大分区。': 'Panel or step text exceeds the layout. Shorten it or enlarge the section.',
  '面板或步骤格式、边界、状态或证据无效。': 'Invalid panel or step format, bounds, status, or evidence.',
  '面积路径需要 3–64 个顶点。': 'An area path requires 3–64 vertices.',
  '顶点每行填写 x,y。': 'Enter one x,y vertex per line.',
  '项目对象或证据数量超过安全上限。': 'The project exceeds the supported object or evidence limit.',
  '项目必须是 JSON 对象。': 'The project must be a JSON object.',
  '项目标题无效。': 'The project title is invalid.',
  '项目没有时间轴。': 'This project does not contain a timeline.',
  '项目需先显式迁移为 IllustrationSpec 1.3。': 'Explicitly migrate the project to IllustrationSpec 1.3 first.',
  '图像任务请求失败。': 'The image task request failed.',
  '图像任务提交失败。': 'The image task could not be submitted.',
  '取消请求失败。': 'The cancellation request failed.',
  '未声明或无法识别': 'Not declared or not recognized',
  '面积': 'Area', '平均强度': 'Mean intensity', '标准差': 'Standard deviation', '众数': 'Mode',
  '最小值与最大值': 'Minimum and maximum', '几何中心': 'Centroid', '质心': 'Center of mass',
  '周长': 'Perimeter', '外接矩形': 'Bounding rectangle', '拟合椭圆': 'Fit ellipse',
  '形状描述': 'Shape descriptors', 'Feret 直径': 'Feret diameter', '积分密度': 'Integrated density',
  '中位数': 'Median', '偏度': 'Skewness', '峰度': 'Kurtosis', '面积占比': 'Area fraction',
  '栈位置': 'Stack position', '仅测量阈值内像素': 'Limit to threshold', '显示来源标签': 'Show source label',
  '反转 Y 坐标': 'Invert Y coordinates', '科学计数法': 'Scientific notation',
  '加入原生叠加层': 'Add to native overlay', '空单元格显示 NaN': 'Show NaN for empty cells',
  '标准差 / StdDev': 'Standard deviation / StdDev', '中位数 / Median': 'Median',
  '众数 / Mode': 'Mode', '积分密度 / IntDen': 'Integrated density / IntDen',
  '亚像素矩形': 'Subpixel rectangle', '亚像素椭圆': 'Subpixel ellipse', '原生多边形': 'Native polygon',
  '自由手面积': 'Freehand area', '追踪区域': 'Traced region', '样条区域': 'Spline region',
  '旋转矩形': 'Rotated rectangle', '旋转椭圆': 'Rotated ellipse', '布尔组合': 'Boolean combination',
  '直线': 'Straight line', '折线': 'Polyline', '自由线': 'Freehand line', '角度': 'Angle',
  '单点': 'Point', '多点': 'Multipoint', '上下文/容器': 'Context / container', '分子': 'Molecule',
  '配体': 'Ligand', '受体': 'Receptor', '蛋白质': 'Protein', '基因': 'Gene', '转录本': 'Transcript',
  '药物': 'Drug', '关联': 'Association', '激活': 'Activation', '抑制': 'Inhibition', '结合': 'Binding',
  '转位': 'Translocation', '表达/产生': 'Expression / production', '文献': 'Literature',
  '实验': 'Experiment', '数据库记录': 'Database record', '用户说明': 'User note',
  '图题': 'Figure title', '共同起始步骤': 'Shared initial step', '分支 A 名称': 'Branch A name',
  '分支 A 处理': 'Branch A procedure', '分支 A 结果': 'Branch A result',
  '分支 B 名称': 'Branch B name', '分支 B 处理': 'Branch B procedure', '分支 B 结果': 'Branch B result',
  '项目': 'Project', '画布': 'Canvas', '证据': 'Evidence', '节点': 'Node', '关系': 'Relationship',
  '分组': 'Group', '时间轴': 'Timeline', '时间点': 'Time points', '时间刻度': 'Time tick',
  '实验组': 'Experimental group', '干预区间': 'Intervention interval', '阶段': 'Stage',
  '对照组采样': 'Control sampling', '处理组采样': 'Treatment sampling',
  '干预开始': 'Intervention start', '干预结束': 'Intervention end',
}

export function interfaceDiagnostic(locale: Locale, text: string): string {
  if (locale === 'zh-CN' || !text) return text
  const exact = diagnosticEnglish[text] ?? imageUiMessages[text]
  if (exact !== undefined) return exact
  for (const { pattern, translate } of imageUiPatterns) {
    const match = text.match(pattern)
    if (match) return translate(match)
  }
  let match: RegExpMatchArray | null
  if ((match = text.match(/^该类型需要 ([\d–-]+) 个点。$/))) return `This region type requires ${match[1]} points.`
  if ((match = text.match(/^第 (\d+) 行坐标超出源图范围。$/))) return `Coordinates on line ${match[1]} are outside the source image.`
  if ((match = text.match(/^第 (\d+) 行格式无效；填写 x,y( 或 x,y,位置,计数器编号)?。$/)))
    return `Invalid line ${match[1]}. Enter x,y${match[2] ? ' or x,y,position,counter' : ''}.`
  if ((match = text.match(/^第 (\d+) 行位置须为 0–(\d+) 整数，计数器编号须为 0–99 整数。$/)))
    return `On line ${match[1]}, position must be an integer from 0–${match[2]}, and counter from 0–99.`
  if ((match = text.match(/^请选择有效的目标图 (.+) 轴平面。$/))) return `Choose a valid target image ${match[1]} plane.`
  if ((match = text.match(/^(.+) 因缺少证据已改为待核实$/))) return `${match[1]} was marked as requiring review because evidence is missing.`
  if ((match = text.match(/^(.+)不能为空、含控制字符或超过 (\d+) 字。$/)))
    return `${interfaceDiagnostic(locale, match[1])} is required, must not contain control characters, and must be at most ${match[2]} characters.`
  if ((match = text.match(/^(.+)须填写非负整数天数。$/))) return `${interfaceDiagnostic(locale, match[1])} must use nonnegative whole days.`
  if ((match = text.match(/^(.+)格式无效。$/))) return `Invalid ${interfaceDiagnostic(locale, match[1]).toLowerCase()} format.`
  if ((match = text.match(/^(.+)含有未审核字段。$/))) return `${interfaceDiagnostic(locale, match[1])} contains unsupported fields.`
  return text
}
