# 第三方依赖说明

## Windows 0.4.2 公开测试候选

项目原创代码现采用 MIT；下列第三方条款保持不变。此版只补齐 Matplotlib/pandas 已有版本的元数据，没有增加运行时依赖。

- 安装包附带 Microsoft Evergreen WebView2 x64 独立离线安装器。审核构件 SHA-256 为 1BE9D2926954D99DD62653A22EFE813160FE0C40F1E422B44E6AAF5473F68EEC，微软签名已核验。微软条款见 [WebView2 Runtime EULA](licenses/desktop/Microsoft-WebView2-Runtime-EULA.html)。
- 安装目录的 third-party 保存依赖许可证、适用的第三方源码及构建来源记录。Fiji 原生命令使用独立配置的 Fiji 20261013-1517 运行时。
- Windows 上的 WebView2 可能向 Microsoft 发送诊断数据。SmartScreen 默认启用时可能与 Microsoft 通信。[WebView2 数据与隐私](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/data-privacy)
- 下方按阶段保留的 0.3.0 及更早构建记录供追溯。

阶段 2 新增依赖均已固定在 `backend/requirements.lock.txt`。许可证信息来自各项目的官方仓库许可证文件与 PyPI 项目元数据，核验日期为 2026-09-13。

| 依赖 | 固定版本 | 许可证 | 来源 |
| --- | --- | --- | --- |
| pandas | 3.0.5 | BSD-3-Clause | https://github.com/pandas-dev/pandas/blob/main/LICENSE |
| Matplotlib | 3.11.2 | Matplotlib License（BSD 风格） | https://matplotlib.org/stable/users/project/license.html |
| Seaborn | 0.13.2 | BSD-3-Clause | https://github.com/mwaskom/seaborn/blob/master/LICENSE.md |
| NumPy | 2.5.3 | BSD-3-Clause | https://github.com/numpy/numpy/blob/main/LICENSE.txt |
| Pillow | 12.3.0 | HPND | https://github.com/python-pillow/Pillow/blob/main/LICENSE |
| openpyxl | 3.1.5 | MIT | https://pypi.org/project/openpyxl/ |
| python-multipart | 0.0.32 | Apache-2.0 | https://github.com/Kludex/python-multipart |

其余传递依赖以锁文件为准；后续分发前应按 `LICENSE_POLICY.md` 复核完整依赖树与随附许可证文本。

## 阶段 4

没有新增依赖。色板候选、采用决定和精确发行物许可证副本见 docs/PALETTE_REVIEW.md 与 licenses/。Clay/Lagoon 为项目内新编固定色值，不含外部图像素材。

## 阶段 5 桌面封装（2026-09-16）

Tauri 2.11.5 / tauri-build 2.6.3 / CLI 2.11.4（MIT OR Apache-2.0）；
PyInstaller 6.22.3（GPL-2.0-or-later，含打包例外），hooks-contrib 2026.7（构建 hooks GPL，runtime hooks Apache-2.0）。
完整版本见 Cargo.lock、apps/desktop/package-lock.json、backend/requirements-packaging.lock.txt。
NSIS 3.11 使用 zlib 压缩；nsis-tauri-utils 0.5.3 为 MIT OR Apache-2.0；发行物由 Tauri CLI 固定 SHA1 校验。
许可证副本在 licenses/desktop。安装目录 third-party 包含 Python/Rust/React 依赖文本、inventory.json 和五项未修改 MPL 依赖的精确发行版源码压缩包。
清单含构建依赖，是运行时依赖的超集。此段描述阶段 5 当时的本机验收包：WebView2 使用系统已安装运行时，不随该历史包再分发；该包没有代码签名，也不对外发布。

## 后续离线 WebView2 候选状态

桌面配置采用 Tauri `offlineInstaller`，`0.3.0` 本机 NSIS 候选已嵌入 Microsoft Evergreen Standalone WebView2 安装器。阶段 9 从 [Microsoft 官方 WebView2 下载页](https://developer.microsoft.com/en-us/microsoft-edge/webview2)指向的 x64 地址受控获取安装器：最终 Microsoft CDN 路径标识 `35871e19-d11b-432d-9d1e-7be0ff286540`，文件 214,156,024 字节，SHA256 `0625FB5C1E75BE58A164E14F95AA58A3E5BADB859B3D17C952385F3E4A9FF3E8`，Microsoft Authenticode 签名有效；安装器文件元数据版本 `1.3.287.9`，**不是**目标设备的 WebView2 Runtime 版本。构建入口只接受该精确发行物；若微软当前跳转变化，会在编译前停止。2026-10-18 对 `0.3.0` 安装包独立解包得到的 WebView2 文件 SHA256 与上述受审文件一致；目标设备安装结果仍待实测。

Microsoft Evergreen 条款原文保存在 `licenses/desktop/Microsoft-WebView2-Runtime-EULA.html`，获取自官方下载页使用的 `/microsoft-edge/api/eula/webview2?locale=en-us`；[官方分发说明](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)允许把独立安装器纳入应用安装程序。条款要求应用具备自身功能、从 Microsoft 取得运行时、随应用提供适当许可与通知；不可把该运行时作为单独产品转售。WebView2 可向 Microsoft 发送诊断数据，SmartScreen 默认启用时需向最终用户说明相关信息，参见 [Microsoft 隐私声明](https://privacy.microsoft.com/en-us/privacystatement)、[Microsoft Edge 用户数据与隐私](https://learn.microsoft.com/en-us/legal/microsoft-edge/privacy)和 [WebView2 数据与隐私](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/data-privacy)。BioFigure Studio 绘图引擎不主动上传科研数据，但不能因此宣称 WebView2 或操作系统完全无网络活动；公开分发前须落实用户可见告知并完成实际网络与干净设备测试。旧包不能代表 7D/阶段 8，新候选不因上述文件审核即视为可公开分发。
# 阶段 6A 新增运行时与字体

- anndata 0.13.3.post0 — BSD-3-Clause；官方来源：https://pypi.org/project/anndata/
- array-api-compat 1.15.0 — MIT；官方来源：https://github.com/data-apis/array-api-compat；许可证副本：licenses/desktop/array-api-compat-1.15.0/LICENSE
- h5py 3.16.0 — BSD-3-Clause；官方来源：https://www.h5py.org/
- scipy 1.18.1 — BSD-3-Clause；官方来源：https://scipy.org/
- zarr 3.4.0 — MIT；官方来源：https://zarr.dev/
- Noto Sans SC — SIL Open Font License 1.1；来源：https://github.com/google/fonts/tree/main/ofl/notosanssc；原文：licenses/NotoSansSC-OFL.txt


## 阶段 6B 组学候选运行时（已安装，待功能验收）

- biopython 1.88 — Biopython License（BSD 风格）；官方来源：https://biopython.org/
- pycirclize 1.10.1 — MIT；官方来源：https://github.com/moshi4/pyCirclize
- dna-features-viewer 3.1.5 — MIT；官方来源：https://github.com/Edinburgh-Genome-Foundry/DnaFeaturesViewer
- R 4.6.1 — GNU GPL-2-or-later；官方来源：https://cran.r-project.org/bin/windows/base/
- ggplot2 4.0.3 — MIT；CRAN 用户库安装于本机 %LOCALAPPDATA%\\BioFigureStudio\\R-4.6.1\\library，不随当前桌面安装包打包。


组学依赖的精确许可证文本位于 `licenses/omics/`：Biopython 1.88 的 `LICENSE.rst`、pyCirclize 1.10.1 的 MIT `LICENSE`、DNA Features Viewer 3.1.5 的 MIT `LICENSE`。R 4.6.1 与 ggplot2 4.0.3 保持为本机可选运行时，不复制进源码或桌面安装包；官方许可证入口见 `licenses/omics/README.md`。
