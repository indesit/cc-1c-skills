<#
.SYNOPSIS
Резервное копирование информационной базы 1С: .dt через Конфигуратор или online-бэкап MS SQL.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dt', 'sql')]
    [string]$Mode,
    [Parameter(Mandatory = $true)]
    [string]$OutputFile,
    [string]$V8Path,
    [string]$InfoBasePath,
    [string]$InfoBaseServer,
    [string]$InfoBaseRef,
    [string]$UserName,
    [string]$Password,
    [string]$PasswordEnv,
    [string]$SqlServer = 'localhost',
    [string]$SqlDatabase,
    [switch]$Compress
)

$ErrorActionPreference = 'Stop'

$outDir = Split-Path $OutputFile -Parent
if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force $outDir | Out-Null }

function Write-Manifest {
    param([string]$BackupFile, [hashtable]$Extra)
    $size = if (Test-Path $BackupFile) { (Get-Item $BackupFile).Length } else { $null }
    $manifest = @{
        timestampUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        mode         = $Mode
        file         = $BackupFile
        sizeBytes    = $size
    } + $Extra
    $manifestPath = "$BackupFile.manifest.json"
    $manifest | ConvertTo-Json | Out-File -FilePath $manifestPath -Encoding utf8
    Write-Host "Manifest: $manifestPath"
}

if ($Mode -eq 'sql') {
    if (-not $SqlDatabase) { Write-Error 'Specify -SqlDatabase for sql mode'; exit 1 }
    $sqlcmd = Get-Command sqlcmd -ErrorAction SilentlyContinue
    if (-not $sqlcmd) { Write-Error 'sqlcmd not found in PATH'; exit 1 }

    $dbEsc = $SqlDatabase -replace ']', ']]'
    $fileEsc = $OutputFile -replace "'", "''"
    $withOpts = 'COPY_ONLY, INIT, CHECKSUM, STATS = 10'
    if ($Compress) { $withOpts += ', COMPRESSION' }
    $query = "BACKUP DATABASE [$dbEsc] TO DISK = N'$fileEsc' WITH $withOpts"
    Write-Host "Running: sqlcmd -S $SqlServer -E -b -Q `"$query`""
    & sqlcmd -S $SqlServer -E -b -Q $query
    $code = $LASTEXITCODE
    if ($code -eq 0 -and (Test-Path $OutputFile)) {
        Write-Host "Backup completed: $OutputFile ($([math]::Round((Get-Item $OutputFile).Length / 1MB, 1)) MB)"
        Write-Manifest -BackupFile $OutputFile -Extra @{ sqlServer = $SqlServer; sqlDatabase = $SqlDatabase; copyOnly = $true; compression = [bool]$Compress }
    } else {
        Write-Error "SQL backup failed (code $code)"
    }
    exit $code
}

# --- dt mode ---
if (-not $V8Path) {
    $found = Get-ChildItem 'C:\Program Files\1cv8\*\bin\1cv8.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $found) { Write-Error '1cv8.exe not found. Specify -V8Path'; exit 1 }
    $V8Path = $found.FullName
} elseif (Test-Path $V8Path -PathType Container) {
    $V8Path = Join-Path $V8Path '1cv8.exe'
}
if (-not (Test-Path $V8Path)) { Write-Error "1cv8.exe not found at $V8Path"; exit 1 }

if (-not $InfoBasePath -and (-not $InfoBaseServer -or -not $InfoBaseRef)) {
    Write-Error 'Specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef'; exit 1
}

if (-not $Password -and $PasswordEnv) {
    foreach ($scope in 'Process', 'User', 'Machine') {
        $Password = [Environment]::GetEnvironmentVariable($PasswordEnv, $scope)
        if ($Password) { break }
    }
    if (-not $Password) { Write-Error "Environment variable $PasswordEnv is not set"; exit 1 }
}

$arguments = @('DESIGNER')
if ($InfoBaseServer -and $InfoBaseRef) {
    $arguments += '/S', "`"$InfoBaseServer/$InfoBaseRef`""
} else {
    $arguments += '/F', "`"$InfoBasePath`""
}
if ($UserName) { $arguments += "/N`"$UserName`"" }
if ($Password) { $arguments += "/P`"$Password`"" }
$arguments += '/DumpIB', "`"$OutputFile`""
$outFile = Join-Path $env:TEMP ("db_backup_{0}.txt" -f (Get-Random))
$arguments += '/Out', "`"$outFile`""
$arguments += '/DisableStartupDialogs'

$masked = $arguments | ForEach-Object { if ($_ -like '/P"*') { '/P"********"' } else { $_ } }
Write-Host "Running: 1cv8.exe $($masked -join ' ')"

$proc = Start-Process -FilePath $V8Path -ArgumentList $arguments -Wait -PassThru -NoNewWindow
$code = $proc.ExitCode

if (Test-Path $outFile) {
    $log = Get-Content $outFile -Raw -Encoding UTF8
    if ($log.Trim()) { Write-Host '--- Log ---'; Write-Host $log; Write-Host '--- End ---' }
    Remove-Item $outFile -Force -ErrorAction SilentlyContinue
}

if ($code -eq 0 -and (Test-Path $OutputFile)) {
    Write-Host "Backup completed: $OutputFile ($([math]::Round((Get-Item $OutputFile).Length / 1MB, 1)) MB)"
    $extra = if ($InfoBaseServer) { @{ server = $InfoBaseServer; ref = $InfoBaseRef } } else { @{ path = $InfoBasePath } }
    Write-Manifest -BackupFile $OutputFile -Extra $extra
} else {
    Write-Error "DT dump failed (code $code). For a busy server infobase use -Mode sql (online) or disconnect sessions first."
}
exit $code
