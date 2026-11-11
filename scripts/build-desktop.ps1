param(
    [switch]$SkipEngine,
    [switch]$NoBundle,
    [string]$PythonExecutable = (Join-Path (Split-Path $PSScriptRoot -Parent) '.venv/Scripts/python.exe'),
    [string]$ReviewedToolCache = (Join-Path $env:LOCALAPPDATA 'tauri')
)
$ErrorActionPreference = 'Stop'
if ($SkipEngine -and !$NoBundle) {
    throw 'A bundled release must rebuild the engine from the current source'
}
$projectRoot = Split-Path $PSScriptRoot -Parent
if (!(Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw 'Set up the project virtual environment or provide -PythonExecutable with its full path'
}
$PythonExecutable = (Resolve-Path -LiteralPath $PythonExecutable).Path
Set-Location $projectRoot
if (!$NoBundle) {
    $releaseVersion = (Get-Content -Raw -Encoding UTF8 'apps/desktop/src-tauri/tauri.conf.json' | ConvertFrom-Json).version
    if ($releaseVersion -eq '0.2.0') {
        throw 'Old 0.2.0 installer version cannot label a phase 9 candidate'
    }
}
if (Get-ChildItem Env:VITE_* -ErrorAction SilentlyContinue) {
    throw 'VITE_* environment overrides are not allowed in a release build'
}
if (!(Test-Path 'apps/desktop/node_modules/.bin/tauri.cmd')) {
    throw 'Reviewed local Tauri CLI is missing; release build will not install or download it automatically'
}
if (!$NoBundle) {
    $approvedGuid = '199041ce-790a-4bbc-9111-b81b4c926e9f'
    $approvedHash = '1BE9D2926954D99DD62653A22EFE813160FE0C40F1E422B44E6AAF5473F68EEC'
    $installerName = 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    $urlPrefix = 'https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/'
    try {
        $head = Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/?linkid=2124701' -Method Head -MaximumRedirection 10 -TimeoutSec 20
    } catch {
        throw 'Cannot confirm the current Microsoft WebView2 installer with a HEAD request; bundle stopped before compilation'
    }
    $currentUrl = $head.BaseResponse.RequestMessage.RequestUri.AbsoluteUri
    $approvedUrl = $urlPrefix + $approvedGuid + '/' + $installerName
    if ($currentUrl -ne $approvedUrl) {
        throw 'Current Microsoft WebView2 installer differs from the reviewed local cache; bundle stopped before download'
    }
    $webviewCache = Join-Path $ReviewedToolCache ('x64/' + $approvedGuid + '/' + $installerName)
    if (!(Test-Path -LiteralPath $webviewCache -PathType Leaf)) {
        throw 'Reviewed WebView2 offline installer is not in the Tauri cache'
    }
    if ((Get-FileHash -LiteralPath $webviewCache -Algorithm SHA256).Hash -ne $approvedHash) {
        throw 'WebView2 cache hash differs from the reviewed installer'
    }
    if ((Get-Item -LiteralPath $webviewCache).Length -ne 214990032) {
        throw 'WebView2 cache size differs from the reviewed installer'
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $webviewCache
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '^CN=Microsoft Corporation,') {
        throw 'WebView2 cache does not have a valid Microsoft signature'
    }
    $nsisRoot = Join-Path $ReviewedToolCache 'NSIS'
    foreach ($required in @('Bin/makensis.exe', 'Plugins/x86-unicode/additional/nsis_tauri_utils.dll', 'Include/MUI2.nsh')) {
        if (!(Test-Path -LiteralPath (Join-Path $nsisRoot $required) -PathType Leaf)) {
            throw "Reviewed NSIS cache is missing $required"
        }
    }
    $nsisHashes = @{
        'Bin/makensis.exe' = '841272B2BD4697FF562F1FB48AD88F71959051B2'
        'Plugins/x86-unicode/additional/nsis_tauri_utils.dll' = '75197FEE3C6A814FE035788D1C34EAD39349B860'
    }
    foreach ($required in $nsisHashes.Keys) {
        if ((Get-FileHash -LiteralPath (Join-Path $nsisRoot $required) -Algorithm SHA1).Hash -ne $nsisHashes[$required]) {
            throw "Reviewed NSIS cache hash differs for $required"
        }
    }
    # Keep Tauri's native known-folder lookup independent of packaged-shell
    # AppData redirection. All tool inputs above are pinned and verified.
    $localTools = Join-Path $projectRoot 'work/cargo-target/.tauri'
    $localNsis = Join-Path $localTools 'NSIS'
    New-Item -ItemType Directory -Path $localNsis -Force | Out-Null
    Get-ChildItem -LiteralPath $nsisRoot | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $localNsis -Recurse -Force
    }
    $localWebview = Join-Path $localTools ('x64/' + $approvedGuid)
    New-Item -ItemType Directory -Path $localWebview -Force | Out-Null
    Copy-Item -LiteralPath $webviewCache -Destination (Join-Path $localWebview $installerName) -Force
}
$env:CARGO_NET_OFFLINE = 'true'
$env:NPM_CONFIG_OFFLINE = 'true'
$env:RUSTUP_HOME = Join-Path $projectRoot 'work/tooling/rustup'
$env:CARGO_HOME = Join-Path $projectRoot 'work/tooling/cargo'
$env:CARGO_TARGET_DIR = Join-Path $projectRoot 'work/cargo-target'
$env:PATH = (Join-Path $env:CARGO_HOME 'bin') + ';' + $env:PATH
$userCargoBin = Join-Path $env:USERPROFILE '.cargo/bin'
if (!(Test-Path (Join-Path $env:CARGO_HOME 'bin/cargo.exe')) -and (Test-Path (Join-Path $userCargoBin 'cargo.exe'))) {
    $env:CARGO_HOME = Join-Path $env:USERPROFILE '.cargo'
    $env:RUSTUP_HOME = Join-Path $env:USERPROFILE '.rustup'
    $env:PATH = $userCargoBin + ';' + $env:PATH
}
if (!$NoBundle) {
    if ($env:RUSTFLAGS -or $env:CARGO_ENCODED_RUSTFLAGS) {
        throw 'Rust compiler flag overrides are not allowed in a release build'
    }
    # Rust can embed build-machine paths in panic messages and debug records.
    $remapRoots = [ordered]@{
        '/_build/profile' = $env:USERPROFILE
        '/_build/project' = $projectRoot
        '/_build/cargo' = $env:CARGO_HOME
        '/_build/rustup' = $env:RUSTUP_HOME
    }
    $remapFlags = foreach ($entry in $remapRoots.GetEnumerator()) {
        if ($entry.Value) {
            $native = [System.IO.Path]::GetFullPath($entry.Value).TrimEnd('\', '/')
            "--remap-path-prefix=$native=$($entry.Key)"
            "--remap-path-prefix=$($native.Replace('\', '/'))=$($entry.Key)"
        }
    }
    $env:CARGO_ENCODED_RUSTFLAGS = $remapFlags -join [char]31
}
$devShell = 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/Tools/Launch-VsDevShell.ps1'
& $devShell -Arch amd64 -HostArch amd64 -SkipAutomaticLocation
if (!$SkipEngine) {
    Push-Location apps/web
    try { npm.cmd run build; if ($LASTEXITCODE) { throw 'Web build failed' } } finally { Pop-Location }
    $env:PYTHONPATH = Join-Path $projectRoot 'work/tooling/python-packager'
    & $PythonExecutable -m PyInstaller --noconfirm --distpath work/engine-dist --workpath work/engine-build scripts/engine.spec
    if ($LASTEXITCODE) { throw 'Engine build failed' }
}
& $PythonExecutable scripts/collect_notices.py
if ($LASTEXITCODE) { throw 'License collection failed' }
if (!$NoBundle) {
    & $PythonExecutable scripts/write_release_source.py
    if ($LASTEXITCODE) { throw 'Release source record failed' }
}
Push-Location apps/desktop
try {
    if ($NoBundle) { npm.cmd run build -- --no-bundle } else { npm.cmd run build }
    if ($LASTEXITCODE) { throw 'Desktop build failed' }
} finally { Pop-Location }
if (!$NoBundle) {
    & $PythonExecutable scripts/record_release_artifact.py
    if ($LASTEXITCODE) { throw 'Installer evidence recording failed' }
}
