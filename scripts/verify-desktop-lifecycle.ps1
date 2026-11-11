param([Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference = 'Stop'
$binary = (Resolve-Path -LiteralPath $Executable).Path
function Find-Engine([int]$ParentId) {
    @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId" | Where-Object Name -eq 'biofigure-engine.exe')
}
$first = Start-Process -FilePath $binary -WindowStyle Hidden -PassThru
$second = $null
try {
    $engine = @()
    for ($attempt=0; $attempt -lt 45; $attempt++) {
        $engine = @(Find-Engine $first.Id)
        if ($engine.Count -eq 1) {
            $listeners = @(Get-NetTCPConnection -State Listen -OwningProcess $engine[0].ProcessId -ErrorAction SilentlyContinue)
            if ($listeners.Count) { break }
        }
        Start-Sleep -Milliseconds 1000
    }
    if ($engine.Count -ne 1 -or !$listeners.Count) { throw 'Desktop engine did not start' }
    if (@($listeners | Where-Object LocalAddress -ne '127.0.0.1').Count) { throw 'Non-loopback listener' }
    $engineId = [int]$engine[0].ProcessId
    $second = Start-Process -FilePath $binary -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 3
    if (@(Find-Engine $second.Id).Count) { throw 'Duplicate launch created another engine' }
    if ($first.HasExited) { throw 'Original app exited on duplicate launch' }
    Stop-Process -Id $second.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $first.Id
    for ($attempt=0; $attempt -lt 50; $attempt++) {
        if (!(Get-Process -Id $engineId -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 100
    }
    if (Get-Process -Id $engineId -ErrorAction SilentlyContinue) { throw 'Engine survived desktop crash' }
    if (Get-NetTCPConnection -State Listen -OwningProcess $engineId -ErrorAction SilentlyContinue) { throw 'Listener survived desktop crash' }
    Write-Output 'PASS: packaged desktop startup, loopback only, duplicate launch, parent crash cleanup'
} finally {
    foreach ($instance in @($first,$second)) {
        if ($null -ne $instance -and !$instance.HasExited) { Stop-Process -Id $instance.Id -ErrorAction SilentlyContinue }
    }
}
