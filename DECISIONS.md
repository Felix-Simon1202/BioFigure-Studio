# Decisions

## Public source refresh and next candidate (2026-11-13)

The user authorized updating GitHub code and bilingual README, then requested
the new installer/release attachments. Describe actual AI/local home workflows,
keep model/connector limits explicit and distinguish old v0.4.3 packages from
current source. Prepare a new v0.4.4 candidate with synchronized desktop versions;
never replace old tags/assets. Reuse reviewed tools and prior unchanged checks,
but verify actual newly frozen queue workers and current packaged project paths.
Keep logs, local model/runtime caches and credentials outside published source.

中文：本次授权同步源码文档并准备新版附件，使用 0.4.4 候选版本；保留旧标签及安装包，
双语说明双主页流程和能力边界。新冻结程序须实际检查，不以源码测试替代。

## Ordered figure workflow (2026-11-13)

Reuse existing FigureSpec, ThemeDraft, IllustrationSpec, rendering and undo paths.
Shared style is a pure preview with explicit group mapping; only confirmed panels
render, then commit atomically. Preserve continuous heatmap colors. Selected-object
Biodot uses strict typed intents and the existing reviewed model/admission lock;
it cannot run code, widen selection or bypass verified-object/document constraints.

The user's batch requirement explicitly preserves original data and labels.
Implement presentation-only styles with retained source bytes, separate caption,
an editable SVG and operation manifest. No microscopy recoloring, OCR rewriting,
high-bit flattening or generative replacement. Support bounded PNG/RGB JPEG/8-bit
single-plane TIFF first; reject unsupported types instead of converting silently.
Persist queue state and style snapshots locally, isolate each worker process,
limit capacity/time/disk/retry, and elect one coordinator across app instances.
Archive only queue-owned opaque references, never caller-supplied server paths.

中文：三项复用现有图版、图示和项目协议，避免建立平行框架。确认前不改文档；
共享样式保留科研数据，局部改图不越过选区与核验保护。队列只统一展示层并保留
原图、标签和核验清单，采用有界容量、独立进程与持久化恢复。源码交付后停止扩展，
待用户验收；新安装包须另行验证，不沿用旧包结论。06:00 为一次性续接。

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
# Scientific chart color and style choices (2026-11-11)

The user clarified that color research must improve generated biological charts,
not the application shell. Keep the white UI and spotlight untouched. Add a bounded
set of five Open Color-derived palettes (three categorical, one sequential, one
diverging) and three chart presentation presets. Freeze existing palette IDs and
values; new IDs are additive within the existing palette version. Use one bundled
JSON catalog for Python rendering, the bilingual UI and Biodot metadata.

No npm/Python dependency or remote runtime is added. ColorUI informs saturated
accent usage only; Colorbox is a jQuery lightbox, not a palette generator; iTerm's
collection license does not replace individual theme rights, so no themes are
copied. TinyColor informs the distinction between contrast and color accessibility;
the local contrast helper implements the standard sRGB luminance formula independently.
Do not certify categorical palettes as colorblind-safe. R retains its own styling.
Only presentation fields change when applying a preset; project/scientific data
and saved v0.4.3 defaults are retained. No publication or installer rebuild here.
# Additional palette library (2026-11-12)

The user requested 20 additional palettes, interpreted as 20 beyond the existing
five, not a total of 20. Continue using the same reviewed Open Color commit and
MIT notice without new dependencies or upstream runtime code. Add 8 categorical,
8 light-to-dark sequential and 4 neutral-centered diverging combinations.
Existing five catalog objects and colors remain identical; names indicate visual
mood, not biological truth, diagnostic status or journal approval.

Resolve reviewed ramps from catalog membership rather than maintaining a second
hardcoded heatmap allowlist. Generate compact categorical palette names in the
chart proposal instructions from the same catalog; keep classifier/extraction
prompts free from the larger catalog. All 25 remain discoverable in capabilities.
Group swatches by meaning in a bounded keyboard-accessible region. Extend paired
ordering to both new paired palettes. No additional one-click style bundles,
services, software installation, published tag changes or installer rebuild.
# Illustration wheel handling (2026-11-12)

The user reported wheel zoom and sidebar scrolling moving the entire editor.
Use a native non-passive listener on the canvas rather than React's delegated
wheel listener, so preventDefault can cancel browser scrolling. Remove it on
cleanup and rebind when viewport zoom or the timeline/canvas branch changes.
Keep cursor-centered zoom, 25–400% bounds and existing pointer interactions.
CSS overscroll containment applies only to direct grid sidebars and the canvas;
do not lock body scrolling or hide the lower composition/evidence sections.
No interface text, user/project data, dependency or spotlight code is changed.
# Cell biology artwork 2.0 (2026-11-12)

The user explicitly authorized redrawing all illustration components and adding
cell types based on textbook cell biology. Use original SVG primitives informed
by openly accessible AP-level and university OpenStax texts, not copied figures.
Keep distinct cell/organellar cues and bilingual limitations instead of implying
species, signaling activity, diagnostic status or scale from generic icons.

Unify the formerly duplicated JSX/SVG geometry in illustrationArtwork.ts and move
export assembly to illustrationExport.ts. Extend the reviewed ID allowlist and
provenance capacity to 28; retain old IDs, dimensions and project/schema versions.
Record artwork 2.0 in SVG metadata. Existing projects deliberately display the
requested new art while their scientific data, labels, transforms and evidence
remain intact. Category filters keep the larger library usable. No new network
service, dependency, model action or spotlight modification is introduced.
# AI-first navigation (2026-11-12)

The user requested a DeepTutor-like conversation landing page, a sliding switch
to the existing local spotlight home, concise task groups with explanatory child
flyouts and restrained Apple-like material treatment. Use original local CSS and
shared bilingual components rather than new UI dependencies or copied product art.
AI is the default interface mode only; no model inference runs automatically.

Retain the exact spotlight subtree, pointer effect and assets. Replace only its
outside navigation. Reuse real routes/actions and separate connectors from examples.
Hover is optional: click/touch, ArrowDown, Tab, Escape and outside dismissal all work.
Only open groups attach outside-pointer listeners; motion respects reduced-motion.

Switching Local goes to the home, so preserve already opened illustration/image
instances instead of unmounting unsaved content. Retention is bounded to those two
instances; route events set retention directly. Hidden illustration keyboard hooks
are inactive. Choosing a new blank illustration increments its reset revision.
Keep the existing parent chart/figure state and offer a plot resume entry when data
is present. Navigation is not autosave; no new project persistence format is added.
