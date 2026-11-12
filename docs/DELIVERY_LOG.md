# Delivery log

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
