<#
.SYNOPSIS
Восстановление информационной базы 1С из бэкапа (.dt или MS SQL .bak). ДЕСТРУКТИВНО.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dt', 'sql')]
    [string]$Mode,
    [Parameter(Mandatory = $true)]
    [string]$InputFile,
    [switch]$IAmSure,
    [string]$V8Path,
    [string]$InfoBasePath,
    [string]$InfoBaseServer,
    [string]$InfoBaseRef,
    [string]$UserName,
    [string]$Password,
    [string]$PasswordEnv,
    [string]$SqlServer = 'localhost',
    [string]$SqlDatabase
)

$ErrorActionPreference = 'Stop'

if (-not $IAmSure) {
    [Console]::Error.WriteLine('Refusing to restore: this OVERWRITES the target database. Re-run with -IAmSure after the user explicitly confirmed.')
    exit 2
}
if (-not (Test-Path $InputFile)) { Write-Error "Backup file not found: $InputFile"; exit 1 }

$manifestPath = "$InputFile.manifest.json"
if (Test-Path $manifestPath) {
    Write-Host "--- Backup manifest ---"
    Get-Content $manifestPath -Raw -Encoding UTF8 | Write-Host
    Write-Host '-----------------------'
}

if ($Mode -eq 'sql') {
    if (-not $SqlDatabase) { Write-Error 'Specify -SqlDatabase for sql mode'; exit 1 }
    $sqlcmd = Get-Command sqlcmd -ErrorAction SilentlyContinue
    if (-not $sqlcmd) { Write-Error 'sqlcmd not found in PATH'; exit 1 }

    $dbEsc = $SqlDatabase -replace ']', ']]'
    $fileEsc = $InputFile -replace "'", "''"
    $query = @"
ALTER DATABASE [$dbEsc] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
RESTORE DATABASE [$dbEsc] FROM DISK = N'$fileEsc' WITH REPLACE, CHECKSUM, STATS = 10;
ALTER DATABASE [$dbEsc] SET MULTI_USER;
"@
    Write-Host "Restoring [$SqlDatabase] on $SqlServer from $InputFile ..."
    & sqlcmd -S $SqlServer -E -b -Q $query
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        Write-Host "Restore completed: [$SqlDatabase] <- $InputFile"
    } else {
        Write-Error "SQL restore failed (code $code). Check database state: it may be left in SINGLE_USER or RESTORING."
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
$arguments += '/RestoreIB', "`"$InputFile`""
$outFile = Join-Path $env:TEMP ("db_restore_{0}.txt" -f (Get-Random))
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

if ($code -eq 0) {
    Write-Host "Restore completed from: $InputFile"
} else {
    Write-Error "RestoreIB failed (code $code). Server infobases require exclusive access - disconnect sessions first."
}
exit $code
