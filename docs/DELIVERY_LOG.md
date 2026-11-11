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
