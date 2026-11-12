# Tasks

## Cell biology component artwork (2026-11-12)

- [x] Study open AP-level/high-school and university cell biology references.
- [x] Add 8 cell types, 9 organelle/vesicle symbols and 3 membrane/molecular
  components; redraw all 8 legacy symbols (28 total).
- [x] Share one vector geometry source between thumbnail, editor and exports;
  isolate export assembly and retain legacy IDs/project values/evidence.
- [x] Add bilingual category filtering and scientific-use guidance.
- [x] Verify 13 frontend and 39 backend checks, build/lint, actual local browser
  insertion/save/reopen/export and preserved wheel behavior.
- [x] Deliver inspected SVG/PNG catalog, source notes and limits. User acceptance
  pending; no new installer or publication in this slice.

## Illustration wheel scrolling fix (2026-11-12)

- [x] Bind a canvas-local non-passive wheel listener with cleanup, preventing
  document scrolling while preserving cursor-centered zoom and zoom limits.
- [x] Contain scroll chaining within both editor sidebars; retain normal page
  scrolling outside those regions and keep document/artwork data unchanged.
- [x] Verify real headless Edge mouse-wheel input: zoom, clamps, local sidebar
  scrolling, top/bottom boundaries and outer page scrolling; build/lint pass.
- [x] Record evidence. Source-only fix; user acceptance and installer update pending.

## Additional 20 scientific palettes (2026-11-12)

- [x] Add exactly 20 reviewed-swatch combinations: 8 categorical (2 paired),
  8 sequential and 4 diverging; 25 curated palettes total.
- [x] Preserve previous five entries, existing project colors and palette IDs.
- [x] Share expanded IDs/names with Biodot, validate all proposals, and resolve
  every new ramp in actual heatmap exports rather than falling back silently.
- [x] Group and bound the swatch list; use bilingual advice and paired-order controls.
- [x] Verify 44 focused backend checks, 11 UI/language checks, build/lint,
  actual palette exports and spotlight preservation; deliver the 25-palette sample.
- [x] Record usage/provenance and source delivery. User acceptance pending;
  no new installer or repository publication in this slice.

## Scientific chart color and style choices

- [x] Review the five user-provided repositories and exact upstream licenses.
- [x] Add five local, versioned palettes and three presentation-only presets.
- [x] Share palette metadata between the chart UI and Biodot; permit validated
  chart proposals to select colors without changing data or tool permissions.
- [x] Add bilingual swatches, usage advice, low-contrast warnings and paired-order input.
- [x] Verify actual exports, schema/save roundtrip, locale UI, build/lint and spotlight preservation.
- [x] Record provenance, sample sheet and delivery limits. User acceptance pending;
  this source update is not a new published installer.

## Next release: interface language

- [x] Freeze shared locale API and persistence rules in docs/UI_LANGUAGE_SPEC.md.
- [x] Implement default English, shared locale state, and language settings.
- [x] Translate active plotting, image, workbench, and illustration interfaces.
- [x] Verify switching, persistence, fallback, workflow state, build and lint.
- [x] Prepare the combined English/Biodot release candidate, update the repository, and
  deliver installer/source/checksum attachments for user upload.
- [x] Record final packaged checks and user-reviewable delivery.

## Next task: Biodot drawing assistant

- [x] Review DeepTutor's licensed role/tool organization and record provenance.
- [x] Add a warm bilingual Biodot identity to existing supported drawing paths.
- [x] Keep real provider/model identity visible in settings; greetings use
  Biodot. Do not claim unavailable tools or completed actions.
- [x] Verify persona, supported operation dispatch and existing consent rules.
- [x] Fix and test English built-in examples, diagram labels and input hints;
  preserve original user/scientific content and spotlight.

Updated user order: deliver English-default UI and Biodot together as one
final v0.4.3 candidate. The interim English-only installer is not for release.
Before upload, also check built-in illustration labels, example values and
gray-input placeholders for untranslated UI content; preserve user content.
