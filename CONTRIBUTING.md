# Development structure and version workflow

BioFigure Studio uses one modular source tree across releases. The repository
root remains the source entry point for the current version; Git branches,
tags, and Releases retain development and release history.

## Source tree

```text
BioFigure-Studio/
├── apps/
│   ├── web/                 # Bilingual interface, workbench and editors
│   └── desktop/             # Windows desktop shell and installer configuration
├── backend/
│   ├── adapters/            # Reviewed plotting-engine adapters
│   ├── api/                 # Local API routes
│   ├── core/                # Shared specifications and workflow rules
│   ├── data/                # Data-handling application code
│   ├── desktop/             # Packaged-engine lifecycle
│   ├── image/               # Image operations, measurements and assembly
│   ├── registry/            # Registered plotting capabilities
│   └── themes/              # Shared visual themes
├── assets/                  # Reviewed application assets
├── examples/                # Synthetic examples
├── tests/                   # Automated checks
├── scripts/                 # Build, packaging and verification tools
├── docs/                    # Format specifications, build guide and evidence
│   └── media/              # README screenshots, diagrams and language buttons
├── licenses/                # Third-party license texts
├── README.md                # Default English overview
├── README.zh-CN.md          # Chinese overview
├── LICENSE                  # MIT license for original code
└── THIRD_PARTY_NOTICES.md    # Third-party obligations and runtime notices
```

`backend/data` contains application source. User datasets, exports, local
models, credentials, environments, and build output remain outside version
control under the existing ignore rules.

## Branches and releases

| Reference | Purpose |
| --- | --- |
| `main` | Published, validated source; the default repository branch. |
| `develop` | Integration branch for the next version; initially identical to main. |
| `codex/<task>` | A bounded implementation branch created from develop when needed. |
| `v0.4.2`, future version tags | Fixed source snapshots for individual releases. |
| GitHub Releases | Version-specific installer, source ZIP, checksums, license and notes. |

The initial main and develop branches point to the same reviewed source.
Branch names describe the workflow; server-side branch protection is a
separate repository setting and is not claimed to be enabled.

## Preparing the next version

1. Start a bounded task from develop. Extend the existing module that owns the
   behavior; use a reviewed adapter for a new engine or connector.
2. Keep shared specifications, error handling, and visual rules reusable.
   Keep tasks and scientific evidence separate from UI presentation.
3. Run checks relevant to the changed behavior. Reuse existing evidence for
   unchanged paths, and document actual limits and user acceptance separately.
4. Update the desktop version and corresponding lock-file entries together.
   Update bilingual release documentation and retain third-party notices.
5. Integrate the reviewed change into develop, then promote the release-ready
   state to main. Tag the exact release commit with the new version.
6. Build and verify the installer from that source. Record the build commit,
   artifact checksum, and any later documentation-only differences explicitly.
7. Create a new GitHub Release with that version's attachments. Keep prior
   tags and release artifacts available with their original checksums.

The current installer was built before MIT/release-documentation additions;
the exact relationship is recorded in the attached SOURCE_PROVENANCE.json.

The existing roadmap prioritizes the illustration skill/tool library, a
reviewable AI figure queue, bounded high-throughput processing, and additional
software adapters. These are future work rather than completed capabilities.

## Privacy and contributions

Use synthetic or explicitly licensed examples. Never commit real research
data, API keys, private keys, machine-specific paths, runtime profiles, or raw
test-machine images. Review external code and asset licenses before reuse.
Original contributions use the project MIT license; third-party materials
retain their own terms.

## 中文说明

后续版本继续使用上面的同一套模块目录。main 保存发布源码，develop 承接下一版开发，每个版本用独立标签固定源码，并在对应 GitHub Release 保存安装包、源码、许可和校验文件。第一次建库时两个分支内容一致。

新功能放进负责该能力的现有模块；只有真正新增的独立能力才新增模块。后续生图 Skill、工作队列和连接器沿现有边界扩展。当前未声称已启用远端分支保护。版本发布前完成相关检查和用户验收，保留旧版本及其校验值。
