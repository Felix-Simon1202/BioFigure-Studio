# BioFigure Studio collaboration rules

- Read CONTRIBUTING.md and docs/UI_LANGUAGE_SPEC.md before interface work.
- Every new or changed user-facing interface must provide English and
  Simplified Chinese through the shared language provider and Settings
  preference. Fresh profiles default to English. Include help, accessible
  names, placeholders, and local messages, not only button labels.
- Preserve user data, scientific labels, identifiers, and saved project
  values when switching interface language.
- Preserve the existing spotlight/fossil-relief artwork, pointer interaction,
  assets, and already bilingual copy exactly. Changes to that feature require
  separate explicit user authorization.
- Keep changes modular, local-first, and within the approved task. Do not add
  network services, dependencies, credentials, or real research data without
  authorization. Retain third-party licenses and the original-code MIT license.
- Update TASKS.md for changes and DECISIONS.md for material choices. Record
  completed delivery evidence and unresolved items in docs/DELIVERY_LOG.md.
- Use the clean develop history for future work. Do not merge private backup
  history into this repository. Do not rewrite published tags. Pushes and
  publication require explicit user authorization.

后续界面更新必须双语并接入统一切换；英文默认。探照灯原有美术、交互和双语内容保持原样。
