# Decisions

## Interface language

Use a shared lightweight React provider and explicit bilingual interface text
for English and Simplified Chinese. English is the default for new profiles;
local persistence changes only the interface. Scientific data and stable API
values remain unchanged. No external translation service or new dependency.
Work starts from the clean develop baseline on a separate task branch;
published v0.4.2 main, tag, installer, and source archive remain unchanged.

User clarification: preserve the existing spotlight artwork, interaction and
already bilingual copy exactly. All future UI additions and changes must
provide both languages through this same language system. This is a standing
development requirement, not an optional follow-up.

## Bundler cache isolation

The packaged desktop shell can redirect AppData differently from Tauri's native
known-folder lookup. An initial package attempt found the reviewed tools in
one cache but attempted to fetch NSIS from the other location. The builder now
verifies the same pinned cache, copies tools into the ignored project-local
Tauri tool directory, and enables the official useLocalToolsDir setting.
No dependency version, system installation or runtime behavior is changed.
