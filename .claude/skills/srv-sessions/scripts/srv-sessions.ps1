<#
.SYNOPSIS
Сеансы кластера 1С через rac: список и завершение (с предохранителями).
#>
[CmdletBinding()]
param(
    [ValidateSet('list', 'terminate')]
    [string]$Action = 'list',
    [string]$V8Path,
    [string]$RasAddress = 'localhost:1545',
    [string]$Infobase,
    [string]$SessionId,
    [switch]$All,
    [switch]$IAmSure,
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
        Write-Error ("rac failed (is RAS running at {0}? see /srv-info SKILL.md): {1}" -f $RasAddress, (($out | Out-String).Trim()))
        exit 1
    }
    return ($out | Out-String)
}

function ConvertFrom-RacBlocks {
    param([string]$Text)
    $blocks = @()
    $current = @{}
    foreach ($line in $Text -split "`r?`n") {
        if ($line.Trim() -eq '') {
            if ($current.Count) { $blocks += , $current; $current = @{} }
            continue
        }
        if ($line -match '^\s*([\w-]+)\s*:\s*(.*)$') {
            $current[$Matches[1]] = $Matches[2].Trim().Trim('"')
        }
    }
    if ($current.Count) { $blocks += , $current }
    return $blocks
}

# --- Cluster ---
$clusterOut = Invoke-Rac @('cluster', 'list')
$cl = ([regex]::Match($clusterOut, '(?m)^cluster\s*:\s*(\S+)')).Groups[1].Value
if (-not $cl) { Write-Error 'No cluster found'; exit 1 }

# --- Optional infobase filter ---
$ibFilter = @()
if ($Infobase) {
    $ibOut = Invoke-Rac (@('infobase', 'summary', 'list', "--cluster=$cl") + $auth)
    $ib = ConvertFrom-RacBlocks $ibOut | Where-Object { $_['name'] -ieq $Infobase } | Select-Object -First 1
    if (-not $ib) {
        Write-Error "Infobase '$Infobase' not found in cluster. Known: $((ConvertFrom-RacBlocks $ibOut | ForEach-Object { $_['name'] }) -join ', ')"
        exit 1
    }
    $ibFilter = @("--infobase=$($ib['infobase'])")
}

$sessionsText = Invoke-Rac (@('session', 'list', "--cluster=$cl") + $ibFilter + $auth)
$sessions = @(ConvertFrom-RacBlocks $sessionsText)

if ($Action -eq 'list') {
    if (-not $sessions.Count) { Write-Host 'No active sessions.'; exit 0 }
    Write-Host ("{0,-38} {1,-20} {2,-16} {3,-12} {4}" -f 'SESSION', 'USER', 'APP', 'HOST', 'STARTED')
    foreach ($s in $sessions) {
        Write-Host ("{0,-38} {1,-20} {2,-16} {3,-12} {4}" -f $s['session'], $s['user-name'], $s['app-id'], $s['host'], $s['started-at'])
    }
    Write-Host "Total: $($sessions.Count)"
    exit 0
}

# --- terminate ---
if (-not $SessionId -and -not $All) { Write-Error 'terminate requires -SessionId or -All'; exit 1 }
if (-not $IAmSure) {
    [Console]::Error.WriteLine('Refusing to terminate sessions: this disconnects users. Re-run with -IAmSure after the user explicitly confirmed.')
    exit 2
}

$targets = @(if ($SessionId) { $sessions | Where-Object { $_['session'] -eq $SessionId } } else { $sessions })
if (-not $targets.Count) { Write-Host 'Nothing to terminate (no matching sessions).'; exit 0 }

$failed = 0
foreach ($s in $targets) {
    & $rac session terminate "--cluster=$cl" "--session=$($s['session'])" @auth $RasAddress 2>&1 | Out-String | Write-Host
    if ($LASTEXITCODE -ne 0) { $failed++ }
    else { Write-Host "Terminated: $($s['session']) ($($s['user-name']), $($s['app-id']))" }
}
Write-Host "Terminated $($targets.Count - $failed) of $($targets.Count) session(s)."
exit ([int]($failed -gt 0))
