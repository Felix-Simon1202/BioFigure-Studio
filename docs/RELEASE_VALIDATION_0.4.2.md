# v0.4.2 release validation / 发布验证

## Artifact provenance

- Version: 0.4.2, Windows x64, per-user NSIS installer, unsigned.
- Installer build commit: `70a7e5438f9513818d25bb2e9bde0961d43272ac`.
- Installer SHA-256: `704E333F8A4EC72580EFBFAF2055380BB07620435DFA2DA67BBF7AEA977707D6`.
- The public source snapshot adds MIT licensing and release documentation after this build. Runtime code, build scripts, assets, dependency locks, and desktop version files match the build commit byte for byte. The public documentation commit is therefore distinct from the installer build commit.
- Gallery images are retained synthetic exports from v0.4.1. No journal images, real research data, local model files, Fiji runtime, R runtime, or credentials are included.

## Existing evidence reused

- Independent package extraction and verification: 1,209 frozen-engine files; required Matplotlib and pandas distribution metadata; valid Microsoft signature on the embedded WebView2 offline installer.
- Actual installation, synthetic project save/reopen and PDF export, v0.4.1-to-v0.4.2 upgrade, maintenance uninstall, and restoration of the prior installation.
- Physical host disconnection test with existing WebView2: install, launch, project save/reopen, PDF, and maintenance uninstall passed.
- Direct packaged-engine verification: five chart types, supported exports and panels, project data hashes and versions, restart/reopen and PDF. This does not require WebView2.

## Fresh Windows offline first install, 2026-11-11

Environment: Microsoft Windows 10 Enterprise LTSC Evaluation 10.0.19044 x64 in an isolated guest. No network device or host file share; software supplied on read-only media. The same original verification script required a dedicated machine identity before making changes.

```text
Guest OS: Microsoft Windows 10 Enterprise LTSC Evaluation / 10.0.19044 / 64-bit
PASS preflight: no WebView2 runtime and no active network adapter or default route.
PASS offline setup: BioFigure Studio 0.4.2 and WebView2 157.0.4341.46 are installed.
PASS native launch: WebView2 loaded the local homepage while the guest was offline.
RESULT PASS
```

The verifier checked the installer checksum, installed product version and runtime registration, native window startup, and a loopback homepage HTTP 200 HTML response in the runtime NetLog. Network conditions were checked again after installation and launch. A QEMU SMBIOS compatibility correction was required before the initial machine-identity guard passed; the guard was not relaxed. This test environment has since been shut down.

## Limits / 适用边界

- No claim of Windows 11 first-install coverage without a preinstalled runtime or full cross-device compatibility.
- Whole-system online behavior on a clean Windows guest remains unverified. Prior runtime observation recorded Microsoft configuration requests; offline core operation does not mean all operating-system/runtime components are network silent. See THIRD_PARTY_NOTICES.md.
- Fiji, R, and models are separately configured optional software. The installer does not bundle those runtimes.
- No new feature claims or broad regression run are inferred from this packaging fix. User acceptance remains separate.

本版修复安装版项目保存失败；全新 Windows 10 LTSC 无 WebView2、无网卡条件下，首次安装与真实桌面首页加载已通过。沿用已有项目、导出和升级证据，不扩展为未测试系统的保证。外部软件仍需单独配置。
