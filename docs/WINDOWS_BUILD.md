# 本地开发与 Windows 打包

## 在本机启动开发版

开发验证使用 Python 3.13 和 Node.js。依赖版本以 backend/requirements.lock.txt、apps/web/package-lock.json 和桌面端锁文件为准。先在项目根目录准备 .venv 并安装后端锁定依赖，再在 apps/web 中安装其锁定的前端依赖。离线开发需要先准备对应的依赖缓存。

从项目根目录启动本地接口：

~~~powershell
.\.venv\Scripts\python.exe -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
~~~

在另一个终端，从项目根目录启动前端：

~~~powershell
Set-Location apps/web
npm run dev
~~~

用终端显示的本机地址打开界面。需要独立验证前端时，在 apps/web 运行 npm run build 和 npm run lint。桌面集成测试依赖已生成的 apps/web/dist。

## Windows 桌面候选

Bundler tools are copied from the reviewed cache into the project's ignored
`work/cargo-target/.tauri` directory after hash/signature checks. This keeps
packaged-shell AppData redirection from causing an unnecessary tool download.
Use `-ReviewedToolCache` to select an existing reviewed Tauri cache when the
default local-app-data cache is different. This option does not download tools.

构建入口先核验既有缓存中的工具，再放入项目内忽略的工具目录；可用
`-ReviewedToolCache` 指定已审核缓存位置，不自动获取新版本工具。

scripts/build-desktop.ps1 默认使用项目 .venv，也接受 -PythonExecutable 指定已准备好的 Python。完整安装包还需要已经审核的 Python 打包依赖、前端与桌面端的 Node 依赖、Rust、Visual Studio 2022 Build Tools，以及匹配脚本校验值的 NSIS 和 Microsoft WebView2 本机缓存。桌面打包脚本会先检查微软官方离线安装器当前链接与审核缓存是否一致，匹配后才继续打包。发布构建需要干净的 Git 提交，构建会记录来源。

绘图、拼版和手动图示可使用本机引擎。Fiji 原生命令需要另行配置经审核的 Fiji 运行时，R 绘图与模型提取也需要分别配置。Windows 安装包中的 Microsoft WebView2 组件可能向 Microsoft 发送诊断数据，默认启用时 SmartScreen 也可能与 Microsoft 通信。详见项目根目录的 THIRD_PARTY_NOTICES.md。
