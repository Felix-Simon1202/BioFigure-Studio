# Interface language specification

Scope: settings-based English/Simplified Chinese interface selection for the
next release. Existing v0.4.2 main and tag remain unchanged.

Permanent user requirements: all future interface additions/changes provide
both languages and join this shared switch. The existing spotlight/fossil
relief visuals, pointer interaction, assets, and already bilingual copy are
explicitly excluded from this change and must remain exactly as they are.

- Supported locale IDs: `en` and `zh-CN`. A fresh profile defaults to English,
  independent of the operating-system or browser language.
- Persist only the locale in `localStorage['biofigure.ui.locale']`. Invalid or
  inaccessible storage falls back to English without breaking startup.
- A shared React provider in `apps/web/src/i18n.tsx` exports `Locale`,
  `LanguageProvider`, and `useI18n()`. The hook returns `{ locale, setLocale,
  t }`; `t(zh: string, en: string): string` explicitly selects interface text.
- A pure `translate(locale: Locale, zh: string, en: string): string` is also
  exported for helpers. Keep hooks in React components. Do not translate or
  change stable IDs, field values, API schemas, user data, entered titles,
  project contents, scientific symbols, or source filenames.
- Wrap the active application at the existing entry point and synchronize
  `document.documentElement.lang`. Changing locale updates the mounted UI
  without reloading or losing unfinished work.
- Language selection must be reachable from settings in local and AI modes.
  Use native names `English` and `简体中文` so users can recover their language.
- Translate visible labels, help, dialogs, placeholders, accessible names,
  menus, and locally generated status/error text. Keep source/user content
  original. Store bilingual notices when needed so existing notices can update.
- Keep current white visual design and existing offline behavior. No new
  dependencies or network translation service. The user subsequently authorized
  Biodot's persona on the existing reviewed AI paths in this same release.
  Lock files change only synchronized product-version
  metadata for the new installer, not dependency resolutions.
- Check English default, Chinese switching, persisted reopening, unavailable
  storage, representative workflows, and unchanged data/export inputs. Run
  build/lint and meaningful changed-behavior checks; reuse unchanged evidence.
