# bootstrap.ps1 - deploy the cc-1c-skills toolset onto a new server (idempotent).
# Usage (run as Administrator):
#   powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap.ps1 `
#       -WorkspaceDir C:\BAF\MyAddon [-ReposDir C:\BAF\repos] [-RepoUrl <git url>]
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceDir,
    [string]$ReposDir = 'C:\BAF\repos',
    [string]$RepoUrl = 'git@github.com:Nikolay-Shirokov/cc-1c-skills.git'
)

$ErrorActionPreference = 'Stop'
$skillsRepo = Join-Path $ReposDir 'cc-1c-skills'

Write-Host '=== 1. Prerequisites ==='
$ok = $true
foreach ($tool in 'git', 'python') {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) { Write-Host ("  [OK] {0}: {1}" -f $tool, $cmd.Source) }
    else { Write-Host "  [MISSING] $tool - install it first"; $ok = $false }
}
$v8 = Get-ChildItem 'C:\Program Files\1cv8\*\bin\1cv8.exe', 'C:\Program Files\BAF\*\bin\1cv8.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
if ($v8) { Write-Host "  [OK] 1C platform: $($v8.Directory)" } else { Write-Host '  [MISSING] 1C platform (1cv8.exe)'; $ok = $false }
foreach ($extra in 'rac.exe', 'ras.exe') {
    if ($v8 -and (Test-Path (Join-Path $v8.Directory $extra))) { Write-Host "  [OK] $extra" }
    else { Write-Host "  [WARN] $extra not found - srv-* skills will not work" }
}
if (Get-Command sqlcmd -ErrorAction SilentlyContinue) { Write-Host '  [OK] sqlcmd' }
else { Write-Host '  [WARN] sqlcmd not found - db-backup/db-restore sql mode will not work' }
if (-not $ok) { Write-Error 'Missing required prerequisites, aborting.'; exit 1 }

Write-Host '=== 2. Skills repository ==='
if (Test-Path (Join-Path $skillsRepo '.git')) {
    Write-Host "  Updating existing checkout: $skillsRepo"
    git -C $skillsRepo pull --ff-only
} else {
    New-Item -ItemType Directory -Force $ReposDir | Out-Null
    Write-Host "  Cloning $RepoUrl -> $skillsRepo"
    git clone $RepoUrl $skillsRepo
}

Write-Host '=== 3. Workspace junction ==='
New-Item -ItemType Directory -Force (Join-Path $WorkspaceDir '.claude') | Out-Null
$link = Join-Path $WorkspaceDir '.claude\skills'
$target = Join-Path $skillsRepo '.claude\skills'
$existing = Get-Item $link -ErrorAction SilentlyContinue
if ($existing -and $existing.LinkType -eq 'Junction' -and $existing.Target -eq $target) {
    Write-Host "  [OK] junction already in place: $link -> $target"
} elseif ($existing) {
    Write-Error "  $link exists and is not the expected junction - resolve manually (move it away and re-run)."
    exit 1
} else {
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    Write-Host "  [OK] created junction: $link -> $target"
}

Write-Host '=== 4. Project registry ==='
$registry = Join-Path $WorkspaceDir '.v8-project.json'
if (Test-Path $registry) {
    Write-Host "  [OK] $registry exists (not touched)"
    if ((Get-Content $registry -Raw) -match '"password"\s*:\s*"[^"]+"') {
        Write-Host '  [WARN] plaintext password found - switch to passwordEnv (see db-list SKILL.md)'
    }
} else {
    $template = @'
{
  "v8path": "<<BIN DIR OF 1C PLATFORM>>",
  "databases": [
    {
      "id": "main",
      "name": "<<INFOBASE NAME>>",
      "type": "server",
      "server": "<<1C SERVER>>",
      "ref": "<<INFOBASE REF>>",
      "user": "<<USER>>",
      "passwordEnv": "<<ENV VAR NAME, e.g. BAF_MAIN_PASSWORD>>",
      "aliases": ["main"],
      "configSrc": ""
    }
  ],
  "default": "main"
}
'@
    $template | Out-File -FilePath $registry -Encoding utf8
    Write-Host "  [CREATED] template $registry - fill in the placeholders."
    Write-Host '  Then set the password (as Administrator):'
    Write-Host '    [Environment]::SetEnvironmentVariable(''<ENV VAR NAME>'', ''<password>'', ''Machine'')'
}

Write-Host '=== 5. RAS service (for srv-* skills) ==='
if (Test-NetConnection localhost -Port 1545 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    Write-Host '  [OK] RAS answers on localhost:1545'
} elseif ($v8) {
    Write-Host '  RAS is not running. Install it as a service (run once as Administrator):'
    Write-Host ("    sc.exe --% create `"1C RAS`" binPath= `"\`"{0}\ras.exe\`" cluster --service --port=1545 localhost:1540`" start= auto" -f $v8.Directory)
    Write-Host '    sc.exe start "1C RAS"'
}

Write-Host ''
Write-Host 'Bootstrap finished. Verify with read-only commands first: /db-list, /srv-info, /cf-check.'
