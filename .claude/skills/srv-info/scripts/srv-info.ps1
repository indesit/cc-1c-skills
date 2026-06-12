<#
.SYNOPSIS
Read-only обзор кластера 1С через rac: кластер, инфобазы, процессы, сводка сеансов.
#>
[CmdletBinding()]
param(
    [string]$V8Path,
    [string]$RasAddress = 'localhost:1545',
    [ValidateSet('cluster', 'infobases', 'processes', 'all')]
    [string]$Mode = 'all',
    [string]$ClusterUser,
    [string]$ClusterPwd,
    [string]$ClusterPwdEnv
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Resolve rac.exe ---
$rac = $null
if ($V8Path) {
    $candidate = if (Test-Path $V8Path -PathType Container) { Join-Path $V8Path 'rac.exe' } else { Join-Path (Split-Path $V8Path -Parent) 'rac.exe' }
    if (Test-Path $candidate) { $rac = $candidate }
}
if (-not $rac) {
    $found = Get-ChildItem 'C:\Program Files\1cv8\*\bin\rac.exe', 'C:\Program Files\BAF\*\bin\rac.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($found) { $rac = $found.FullName }
}
if (-not $rac) { Write-Error 'rac.exe not found. Specify -V8Path'; exit 1 }

if (-not $ClusterPwd -and $ClusterPwdEnv) {
    foreach ($scope in 'Process', 'User', 'Machine') {
        $ClusterPwd = [Environment]::GetEnvironmentVariable($ClusterPwdEnv, $scope)
        if ($ClusterPwd) { break }
    }
}
$auth = @()
if ($ClusterUser) { $auth += "--cluster-user=$ClusterUser"; if ($ClusterPwd) { $auth += "--cluster-pwd=$ClusterPwd" } }

function Invoke-Rac {
    param([string[]]$RacArgs)
    $out = & $rac @RacArgs $RasAddress 2>&1
    if ($LASTEXITCODE -ne 0) {
        $msg = ($out | Out-String).Trim()
        if ($msg -match 'No connection|відмов|отказ|refused|соедин|єднання') {
            Write-Error ("Cannot connect to RAS at {0}. Start the RAS service first (see SKILL.md). Details: {1}" -f $RasAddress, $msg)
        } else {
            Write-Error "rac failed: $msg"
        }
        exit 1
    }
    return $out
}

# --- Clusters ---
$clusterOut = Invoke-Rac @('cluster', 'list')
Write-Host '=== Clusters ==='
$clusterOut | Write-Host
$clusterIds = $clusterOut | Select-String '^cluster\s*:\s*(\S+)' | ForEach-Object { $_.Matches[0].Groups[1].Value }
if (-not $clusterIds) { Write-Error 'No clusters found'; exit 1 }

foreach ($cl in $clusterIds) {
    if ($Mode -in 'infobases', 'all') {
        Write-Host "=== Infobases (cluster $cl) ==="
        Invoke-Rac (@('infobase', 'summary', 'list', "--cluster=$cl") + $auth) | Write-Host
    }
    if ($Mode -in 'processes', 'all') {
        Write-Host "=== Working processes (cluster $cl) ==="
        Invoke-Rac (@('process', 'list', "--cluster=$cl") + $auth) |
            Select-String '^(process|host|port|pid|running|memory-size|connections|started-at)\s*:' | ForEach-Object { $_.Line } | Write-Host
    }
    if ($Mode -eq 'all') {
        $sessions = Invoke-Rac (@('session', 'list', "--cluster=$cl") + $auth)
        $count = ($sessions | Select-String '^session\s*:').Count
        Write-Host "=== Sessions (cluster $cl): $count active ==="
    }
}
exit 0
