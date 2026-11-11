import { Suspense, lazy } from 'react'
import Workflow from './Workflow'

// The archived prototype has global CSS; load it only for its explicit route.
const LegacyApp = lazy(() => import('./App.tsx'))

export default function Screen() {
  const legacy = new URLSearchParams(window.location.search).has('legacy')
  return <Suspense fallback={null}>{legacy ? <LegacyApp /> : <Workflow />}</Suspense>
}
