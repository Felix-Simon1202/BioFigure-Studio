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
- Installer build, packaged checks and repository synchronization are the
  remaining delivery steps. No user acceptance is inferred from these tests.

Next task, after this delivery: review the licensed DeepTutor role/tool
organization and implement Biodot's bilingual drawing-assistant identity on
the already supported, reviewed operation paths. Do not add unrestricted
shell access or claim unsupported tools.
