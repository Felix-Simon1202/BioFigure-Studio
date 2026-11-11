param([Parameter(Mandatory = $true)][string]$RuntimePath)
$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path -LiteralPath $RuntimePath).Path
$launcher = Join-Path $runtime 'fiji-windows-x64.exe'
$receiptPath = Join-Path (Split-Path $runtime -Parent) 'runtime-receipt.json'
if (!(Test-Path -LiteralPath $launcher -PathType Leaf) -or !(Test-Path -LiteralPath $receiptPath -PathType Leaf)) {
    throw '固定 Fiji 运行时或完整性清单缺失。'
}
$receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($receipt.snapshot_id -ne 'fiji-latest-win64-jdk-20261013-1517' -or
    $receipt.archive_sha256 -ne '9201287a86967d1dc93a5a8426ef8c5048c6186c50642c75164fb2c813794c54' -or
    !$receipt.components -or $receipt.components.Count -lt 1000) {
    throw 'Fiji 发行版标识或完整性清单不匹配。'
}
foreach ($entry in $receipt.components) {
    $relative = [string]$entry.path
    if ([IO.Path]::IsPathRooted($relative) -or $relative.Split('/') -contains '..') {
        throw 'Fiji 清单包含无效路径。'
    }
    $file = Join-Path $runtime $relative
    if (!(Test-Path -LiteralPath $file -PathType Leaf) -or (Get-Item -LiteralPath $file).Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.sha256) {
        throw "Fiji 文件与审核快照不符：$relative"
    }
}
$directory = Join-Path $env:LOCALAPPDATA 'BioFigureStudioData'
$config = Join-Path $directory 'fiji-runtime.json'
if (Test-Path -LiteralPath $config) {
    $existing = Get-Content -LiteralPath $config -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($existing.runtime_path -ne $runtime) {
        throw "已有不同的 Fiji 配置，未覆盖：$config"
    }
    Write-Output "固定 Fiji 已配置：$runtime"
    return
}
New-Item -ItemType Directory -Path $directory -Force | Out-Null
$payload = [ordered]@{
    snapshot_id = $receipt.snapshot_id
    archive_sha256 = $receipt.archive_sha256
    runtime_path = $runtime
} | ConvertTo-Json
[IO.File]::WriteAllText($config, $payload + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "固定 Fiji 配置成功：$config"
