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

## Combined English and Biodot delivery

The user changed the delivery order to one combined v0.4.3 update. The interim
English-only candidate is not released. Biodot uses a small Apache-2.0-adapted
DeepTutor persona block, fixed bilingual identity and a drawing playbook;
the existing proposal schemas, reviewed model identity and consent remain.
Simple greetings/help are local. The capability catalog reports actual tool
readiness, distinguishing paired connector tools from in-app model proposals.

The user's report of Chinese schematic/input text exposed software-authored
defaults beyond labels. New English examples, placeholder titles/sections,
gray-input hints and fixed timeline/relation labels now follow locale. Existing
source paragraphs and user/project text remain unchanged. SVG label locale
does not change geometry, identifiers, scientific status or evidence.
