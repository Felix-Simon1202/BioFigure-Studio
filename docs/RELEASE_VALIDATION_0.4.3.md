# v0.4.3 combined English and Biodot candidate

The release tag and installer use build commit
`963854240b63e9a1fcf16e9ba0a20fbaef4136f8`.
The later repository documentation commit records completed verification;
it does not change release runtime code. The attached source ZIP matches
the installer build commit and tag exactly.

Installer SHA-256:
`5BEDD3D5DF0400E1297D6A5B76C0A80C37EA1DB6F90D4C6E81194CC65939BD54`.

## Actual checks

- Production frontend build and lint passed; no new runtime dependencies.
- Ten interface checks passed: default English, saved Chinese, invalid and
  blocked storage fallback, source-name preservation, scientific validation
  diagnostics, local Biodot greetings, English examples, mechanism semantics,
  input placeholders, and workbench welcome.
- Seventeen focused backend tests passed for persona injection, true model
  identity, current operation dispatch, invalid-action rejection, external
  synthetic-prompt consent, and fixed-source extraction.
- A real reviewed local model produced a structured synthetic chart proposal;
  the actual drawing engine rendered it to a valid PDF. No external model
  request was made with a real key or research data.
- Original spotlight intro/pointer effect matched the clean baseline.
  No CSS, fossil artwork, or public decorative assets changed.
- New English-built-in title/component/panel examples and fixed timeline and
  mechanism labels were checked; SVG geometry, evidence, raw input and user
  labels remain unchanged by language selection.
- Independent installer extraction passed with 1,912 files. All 1,209 engine
  files matched the build manifest. Microsoft WebView2's signature and pinned
  hash passed. MIT and DeepTutor Apache-2.0 attribution are included.
- The packaged engine returned Biodot capability metadata and served the new
  English assets. A synthetic project saved with verified dependency metadata
  and embedded-data hash, reopened in a new engine session, and exported PDF.
- The actual packaged native desktop loaded the local HTML homepage with a
  fresh isolated WebView profile. A process-local proxy prevented external
  WebView requests during this smoke check. Test processes were closed.
- Privacy review checked 333 release-source files, 1,912 extracted files,
  224 nested archive entries, 2,899 frozen Python entries, and screenshot
  metadata. No known personal identifier, build-workspace path, suspicious
  credential pattern, or sensitive screenshot metadata matched.

## Scope

The prior v0.4.2 clean Windows 10 LTSC no-WebView2 offline first-install,
installation/upgrade, and host-disconnection results remain baseline evidence;
this update does not claim that matrix was rerun for v0.4.3. The current
installer is unsigned. Fiji, R, and models still require separate setup.
Biodot uses current supported proposal/connector paths, not unrestricted
software automation. Source paragraphs, user text and OS-provided dialogs may
retain their original language. User acceptance and public release are separate.

## 中文摘要

英文默认、设置内双语切换、Biodot 人格和受支持绘图流程已合并。新增的输入框、示例和固定图示标签已核对；用户内容与探照灯保留原样。真实本机模型到 PDF、打包程序启动、项目重开、包内摘要和脱敏检查通过。旧版断网首装证据作为基线复用，本版未重新执行完整系统矩阵，也不代替用户验收。
