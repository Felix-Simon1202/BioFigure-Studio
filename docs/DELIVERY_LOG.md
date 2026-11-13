# Delivery log

## Public refresh / v0.4.4 preparation — 2026-11-13

- English/Chinese README now follows AI conversation home and spotlight local
  home workflows, with reviewed screenshots and explicit model/connector limits.
- Tracked-source scan found no known personal device path/identifier, private key
  or credential pattern. Email matches were existing third-party license credits;
  retain them. README relative links resolve and screenshot EXIF is empty.
- User additionally requested installer attachments. Version metadata synchronized
  to 0.4.4; package build/checks and final GitHub synchronization remain pending.
  Existing source-only evidence is retained; no new package success is claimed yet.
- Initial bundling stopped before compilation because Microsoft's download GUID
  changed. Reviewed replacement: Microsoft signature valid, file version
  1.3.315.17, 215195856 bytes, SHA-256
  1D1C838E5971343C060415DA7C630C3C1CA7AD33FBB61CCA660F3C1122F4CCA8.
  Pins and third-party notice updated; no runtime installation performed.
- Fixed the native export gate to admit actual project/ZIP/TIFF formats and local
  API downloads while preserving local-origin and non-executable restrictions.
- First frozen queue check found Windows denying multiprocessing parent-handle
  duplication. This candidate was withheld. Replaced only the frozen startup path
  with a fixed stdin protocol and isolated subprocess, retaining one-worker/time/
  disk limits and validating owned UUID paths, hash and style snapshot. Source
  multiprocessing remains unchanged. Engine shutdown now closes its queue worker
  before exit. Relevant protocol and packaged checks must pass before delivery.
- Final build 091862a280c6a374e445730a1cfe84393976b968 passed actual frozen
  startup/style/PDF/selected-edit/project-reopen/queue/archive/retry/restart checks.
  Two native export tests and five focused protocol checks passed. All 1,210 engine
  files matched; 375 source/1,914 extracted/224 nested/2,904 frozen entries scanned
  without private-marker matches. Final installer SHA-256:
  80330FFFF921EE184DAC9A909E5572934F6657E162EF29C9A124F1DCB404FAAC.
  RELEASE_VALIDATION_0.4.4.md records actual limits; no clean install/upgrade matrix
  or user acceptance is inferred. Final attachments prepared separately.
- GitHub main/develop synchronized at c579de117574aad376489cd32f4b4b0d955a50e6;
  v0.4.4 points to exact build 091862a280c6a374e445730a1cfe84393976b968.
  Previous tags preserved and clean history retained. Remote English/Chinese README
  blob hashes match local files. This subsequent receipt is documentation-only;
  installer/source ZIP remain at the build commit. Release attachments are local,
  not uploaded; user acceptance remains pending.

中文：双语 README 和源码脱敏检查已整理；新版安装包另行构建核验，尚未声称完成。

## Ordered figure workflow source delivery — 2026-11-13

- Completed 1 → 2 → 3: shared four-panel styling with explicit group colors and
  atomic render/apply/undo; five reviewed selected-object edit operations; durable
  image presentation queue with three styles and exact original copies.
- Queue supports submission, isolated failures, retry/cancel, restart recovery,
  one coordinator/worker, manifests, individual and organized bulk downloads.
  PNG/RGB JPEG/single-plane 8-bit TIFF only; 100 jobs, 64 MiB/16 MP per input,
  120 seconds per item, five attempts, 1 GiB queue/512 MiB archive budgets.
- Stage 1/2: 23 backend checks passed. Updated four-panel PDF/project roundtrip:
  two passed. Queue: 97 valid of 100 done, three corrupt isolated, no repeated
  completed work on retry; recovery/TIFF/coordinator/cancel passed. An initial
  wrapped filename assertion was corrected with full SVG title metadata; the
  affected integrity/API checks passed. Final changed-path run: eight passed.
- Fifteen frontend language/UI checks, production build and lint passed. Existing
  bundle-size/framework deprecation warnings remain. Real local headless Edge
  checked preview/apply/stale rejection/save/undo and queue upload/retry/archive;
  original bytes and label-preservation metadata matched. Reviewed local model
  returned a valid color-only intent from a natural-language synthetic request.
- Inspected three tracked screenshots. FIGURE_WORKFLOW_DELIVERY.md records user
  flows, limits and evidence; roadmap and Biodot capability notes updated.
  Exact protected spotlight subtree/pointer/CSS/artwork check retained.
- Source only. No new dependency/model/service, real data upload, installation,
  push or publication. Frozen worker entry prepared, but no new installer built
  or verified. User acceptance remains pending. Once-only 06:00 continuation
  reads actual remaining work and stops when this bounded delivery is complete.

中文：按序完成三项源码和实际流程检查，保留原始数据及标签；批量美化限于展示层。
新安装包及用户验收未完成，不冒充已发布版本。凌晨任务不重复已通过验证或扩展范围。

## English-first interface candidate

- Baseline: clean develop commit 067a532, keeping the published v0.4.2 tag intact.
- Added shared English/Simplified Chinese Settings preference. New profiles
  default to English; selection persists locally and updates without reload.
- Translated plotting, image/measurement, workbench, and illustration UI,
  accessible labels, help and local messages. Source text, real file names,
  scientific values, IDs and existing document content remain unchanged.
- Preserved the original spotlight intro, pointer/fossil effect, all CSS and
  artwork. Added a permanent bilingual/spotlight rule in AGENTS.md and
  CONTRIBUTING.md.
- Six locale tests, 31 workbench/illustration render assertions, and 14 image
  render checks passed. Production build and lint passed. Browser checks
  confirmed English on a fresh origin, Chinese switching, restored Chinese
  after reload, and switching back to English. A closed-dialog CSS interaction
  discovered in this check was fixed with explicit closed display state.
- Generated new placeholder illustration titles/component labels in the
  chosen language; reopening or switching does not rewrite existing content.
- Original code MIT text is included in future packaged third-party notices.
- Installer build and packaged checks subsequently completed for the combined
  candidate below. No user acceptance is inferred from these tests.

## Combined release scope, as subsequently requested

The user requested one final v0.4.3 containing both the English-first UI and
Biodot. The interim English-only package is archived and is not for upload.

- Reviewed pinned DeepTutor persona sources and license, adapted a small
  Apache-2.0 persona-framing block with attribution, and added a drawing
  playbook. All other original project code remains MIT.
- Biodot now supplies the same identity to local/external structured drawing
  requests and fixed synthetic extraction. Greetings/help are bilingual local
  UI replies; settings retain the real provider/model. Capability metadata
  lists actual connector readiness and the limited in-app proposal actions.
- Addressed the user's remaining English input/diagram report: built-in
  placeholders and newly chosen examples use English, including external-demo
  prompts actually sent with consent. Fresh document/component/section defaults
  and fixed timeline/relation labels use the selected language. Existing user
  content, source paragraphs, geometry and evidence remain unchanged.
- Current checks: 10 locale/Biodot/English-example/placeholder tests and 17
  focused backend tests pass. These include a mocked model proposal through
  the real plotting engine to PDF, external request identity/prompt checks,
  invalid-action rejection and the pre-existing extraction/consent checks.
- Spotlight subtree, pointer effect, CSS and artwork still match the original.
  Final package, privacy and remote checks are recorded with the attachments.
- Final installer and exact tagged source use build commit 963854240b63e9a1fcf16e9ba0a20fbaef4136f8,
  SHA-256 5BEDD3D5DF0400E1297D6A5B76C0A80C37EA1DB6F90D4C6E81194CC65939BD54.
  Real reviewed-model-to-PDF, packaged project restart/reopen/PDF, native
  homepage, manifest and privacy checks passed. Detailed scope is in
  RELEASE_VALIDATION_0.4.3.md. Only later documentation records were added
  after the installer build; release runtime code is unchanged.
- Deliver one installer/source/checksum set for user upload. New repository
  main/develop synchronization preserves v0.4.2 and adds immutable v0.4.3;
  no repository visibility change or automatic Release publication.
# Scientific chart styles — 2026-11-11

- Reviewed pinned README/license snapshots for all five requested color projects.
  Redistributed only selected Open Color swatches, with its full MIT license.
  Study and reuse choices: SCIENTIFIC_CHART_STYLES.md.
- Added three categorical palettes, expression-blue and blue/orange ramps, and
  three presentation-only chart presets. Bilingual swatch cards, usage advice,
  low-contrast warnings and paired category ordering join the existing workflow.
- Biodot discovers the same palette catalog and can propose a validated optional
  palette ID. Existing schemas, synthetic-data scope and model consent remain.
- Real SVG exports and preserved data/labels, save/config roundtrip, heatmap
  limits/endpoints, single-cell resolver, genome track colors, ecology ramp and
  Biodot metadata/validation: 9 focused tests passed. Earlier combined palette,
  Biodot and workbench run: 21 passed; 2 subsequently added renderer tests passed
  in the final focused run. Existing dependency deprecation warnings only.
- Language/UI tests: 11 passed; production build and lint passed. Existing bundle
  chunk-size warning remains. Original spotlight/interaction/CSS/assets check passed.
- Inspected the generated synthetic sample sheet in docs/media. No personal data,
  network runtime, new dependency or real research data was introduced.
- Delivered source on codex/scientific-chart-palettes. User acceptance pending.
  No push, Release/tag mutation or new installer build. v0.4.3 artifacts remain
  unchanged; frozen-engine palette data inclusion is prepared for the next build.
# Additional 20 palettes — 2026-11-12

- Delivered exactly 20 additions, making 25 curated choices: 11 categorical,
  9 sequential and 5 diverging overall. Reused the fixed reviewed Open Color
  snapshot and retained the MIT notice. Previous five catalog entries match
  the prior commit exactly as data; all complete color arrays are distinct.
- Bilingual names, usage guidance, grouped scrollable swatches and paired-order
  controls are wired to the current chart workflow. Biodot's compact categorical
  names and capability metadata use the shared registry. No runtime network or
  dependency was added; no underlying user/scientific data was modified.
- Focused palette/Biodot/workbench tests: 44 passed, including all 25 real SVG
  exports/config roundtrips, actual ramp names/endpoints, strictly descending
  sequential luminance, expanded model IDs and unknown-ID rejection.
- UI/language checks: 11 passed; build and lint passed. Existing bundle-size
  warning and two dependency deprecation warnings remain. Spotlight subtree,
  pointer, CSS and decorative assets match the protected baseline; the asset
  checker explicitly excludes the authorized chart palette data directory.
- Generated and visually inspected docs/media/scientific-palette-catalog.png:
  synthetic category lines, nonnegative magnitude maps and signed correlation
  heatmaps. Reproducible via scripts/render_palette_catalog.py.
- Source update only; user acceptance pending. Existing v0.4.3 installation
  artifacts and remote repository remain unchanged.
# Illustration wheel fix — 2026-11-12

- Fixed canvas zoom leaking wheel default scrolling: canvas-local native wheel
  listener is explicitly non-passive, prevents the default even at zoom limits,
  and removes its listener on cleanup. Horizontal-only wheel does not zoom.
- Contained scroll chaining for both direct grid sidebars; canvas/panels can
  shrink within their layout. Outside-page scrolling remains enabled, keeping
  composition and evidence sections reachable. No scientific data or copy changed.
- Actual existing headless Edge + local Vite check passed with native CDP wheel
  events: zoom changes, zoom clamps, sidebar scroll, both sidebars' top/bottom
  boundaries, and ordinary outer-page scrolling. Evidence: ignored local
  work/illustration-wheel-check.log. Isolated synthetic editor fixture only;
  no user browser profile, external service or dependency installation.
- Production build and lint passed; existing large-chunk warning remains.
  Original spotlight content, pointer code and decorative assets are unchanged.
- Local source fix only. No new installer, push or Release publication;
  user acceptance remains pending.
# Cell biology component artwork — 2026-11-12

- Added 20 original components: 8 cell types, 9 organelle/vesicle symbols and
  3 membrane/molecular symbols. Redrew the prior 8, making 28 total. Bilingual
  library names, guidance and category filtering follow the shared locale.
- Reviewed AP-level and university textbook sources; documented links, biological
  cues and schematic limitations in CELL_COMPONENT_ARTWORK.md. No textbook images
  or third-party art/code were copied. Original artwork remains project MIT.
- Unified React/thumbnail/SVG geometry; separated export assembly. Old component
  IDs, dimensions and scientific/project values remain; all symbols use artwork
  2.0. A pre-existing untranslated default provenance note now translates only
  at display, leaving saved notes unchanged.
- 13 frontend language/artwork checks and 39 backend illustration/extraction
  checks passed. Build/lint passed; existing chunk/deprecation warnings remain.
- Real existing local headless Edge check passed: category counts, component
  insertion, local project save/reopen, SVG export and previous wheel-scroll fix.
  All 28 entries also insert successfully into the default canvas after bounding
  new-node placement; existing nodes are not moved automatically.
  Evidence: ignored work/cell-browser-check.log. Isolated synthetic data only.
- Rendered and inspected docs/media/cell-component-catalog.svg and .png. SVG is
  reproducible with scripts/render_cell_catalog.cjs. Original spotlight remains
  unchanged. No new dependency/service, installation package, push or publication.
- Source delivered for user review; user acceptance pending.
# AI-first workspace navigation — 2026-11-12

- Default entry is Biodot's conversation workspace. Shared bilingual sliding switch
  opens the original local spotlight home. No model is invoked by startup.
- Four local disclosure groups replace long task cards; AI sidebar groups reveal
  workbench/local destinations, illustration generation and a separate connector
  group. Examples/shortcuts are collapsed. Recent projects and settings remain.
- Added original neutral surfaces, translucency, soft shadows and reduced-motion
  support. Hover/click, touch, keyboard and outside dismissal share one component.
- Retained chat draft and existing image/illustration editor instances across
  home changes. Hidden illustration keyboard shortcuts are inactive. Resume actions
  use retained state; explicit new illustrations reset, and project saving is manual.
- 14 language/UI checks, production build and lint passed. Actual existing local
  headless Edge passed home switching, real editor route, draft retention, unsaved
  illustration resume/hidden Delete protection, hover, Escape/ArrowDown, generation
  entry, 390px viewport bounds and native tap-to-open. No live model/real data used.
- Inspected docs/media/navigation-ai-home.png and navigation-local-home.png.
  WORKSPACE_NAVIGATION.md records flow, limits and evidence. Original spotlight
  subtree, pointer effect and decorative assets remain unchanged.
- Source only; no backend/dependency/service changes, installer, push or publication.
  User acceptance remains pending.
