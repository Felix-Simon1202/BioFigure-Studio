import type { Locale } from './i18n'
import { syntheticBranchExample, type BranchWorkflowInput } from './illustrationSkill'
import { syntheticTimelineExample, type TimelineInput } from './illustrationTimeline'

// These factories create new examples only. Never run them on an open project
// or on language changes, so scientific/user-entered text remains intact.
export function branchExample(locale: Locale): BranchWorkflowInput {
  if (locale === 'zh-CN') return { ...syntheticBranchExample }
  return { title: 'Synthetic two-branch workflow', sharedStep: 'Prepare synthetic cells for a layout demonstration.',
    branchA: 'Control', stepA: 'Apply example procedure A.', resultA: 'Record example observation A.',
    branchB: 'Treated', stepB: 'Apply example procedure B.', resultB: 'Record example observation B.' }
}

export function timelineExample(locale: Locale): TimelineInput {
  if (locale === 'zh-CN') return { ...syntheticTimelineExample }
  return { ...syntheticTimelineExample, title: 'Synthetic experimental timeline',
    tickLabels: 'Day 0, Day 2, Day 9', stageLabels: 'Preparation, Treatment',
    groupA: 'Control', groupB: 'Treated', intervalLabel: 'Example intervention' }
}
