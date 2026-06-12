<#
.SYNOPSIS
Платформенная проверка конфигурации 1С (/CheckConfig, /CheckModules). Read-only.
#>
[CmdletBinding()]
param(
    [string]$V8Path,
    [string]$InfoBasePath,
    [string]$InfoBaseServer,
    [string]$InfoBaseRef,
    [string]$UserName,
    [string]$Password,
    [string]$PasswordEnv,
    [ValidateSet('config', 'modules', 'all')]
    [string]$Mode = 'all',
    [string]$Extension,
    [string]$ConfigArgs = '-ConfigLogIntegrity -IncorrectReferences -ExtendedModulesCheck',
    [string]$ModulesArgs = '-ThinClient -Server'
)

$ErrorActionPreference = 'Stop'

# --- Resolve 1cv8.exe ---
if (-not $V8Path) {
    $found = Get-ChildItem 'C:\Program Files\1cv8\*\bin\1cv8.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $found) { Write-Error '1cv8.exe not found. Specify -V8Path'; exit 1 }
    $V8Path = $found.FullName
} elseif (Test-Path $V8Path -PathType Container) {
    $V8Path = Join-Path $V8Path '1cv8.exe'
}
if (-not (Test-Path $V8Path)) { Write-Error "1cv8.exe not found at $V8Path"; exit 1 }

# --- Validate connection ---
if (-not $InfoBasePath -and (-not $InfoBaseServer -or -not $InfoBaseRef)) {
    Write-Error 'Specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef'; exit 1
}

# --- Resolve password ---
if (-not $Password -and $PasswordEnv) {
    foreach ($scope in 'Process', 'User', 'Machine') {
        $Password = [Environment]::GetEnvironmentVariable($PasswordEnv, $scope)
        if ($Password) { break }
    }
    if (-not $Password) { Write-Error "Environment variable $PasswordEnv is not set"; exit 1 }
}

function Invoke-DesignerCheck {
    param([string]$CheckCommand, [string]$CheckFlags)

    $arguments = @('DESIGNER')
    if ($InfoBaseServer -and $InfoBaseRef) {
        $arguments += '/S', "`"$InfoBaseServer/$InfoBaseRef`""
    } else {
        $arguments += '/F', "`"$InfoBasePath`""
    }
    if ($UserName) { $arguments += "/N`"$UserName`"" }
    if ($Password) { $arguments += "/P`"$Password`"" }

    $arguments += $CheckCommand
    if ($CheckFlags) { $arguments += ($CheckFlags -split '\s+' | Where-Object { $_ }) }
    if ($Extension) { $arguments += '-Extension', "`"$Extension`"" }

    $outFile = Join-Path $env:TEMP ("cf_check_{0}.txt" -f (Get-Random))
    $arguments += '/Out', "`"$outFile`""
    $arguments += '/DisableStartupDialogs'

    $masked = $arguments | ForEach-Object { if ($_ -like '/P"*') { '/P"********"' } else { $_ } }
    Write-Host "Running: 1cv8.exe $($masked -join ' ')"

    $proc = Start-Process -FilePath $V8Path -ArgumentList $arguments -Wait -PassThru -NoNewWindow
    $code = $proc.ExitCode

    if (Test-Path $outFile) {
        $log = Get-Content $outFile -Raw -Encoding UTF8
        if ($log.Trim()) {
            Write-Host "--- Log ($CheckCommand) ---"
            Write-Host $log
            Write-Host '--- End ---'
        }
        Remove-Item $outFile -Force -ErrorAction SilentlyContinue
    }
    return $code
}

$exitCode = 0
if ($Mode -in 'config', 'all') {
    $c = Invoke-DesignerCheck -CheckCommand '/CheckConfig' -CheckFlags $ConfigArgs
    if ($c -ne 0) { Write-Host "CheckConfig: FAILED (code $c)" } else { Write-Host 'CheckConfig: OK' }
    if ($c -ne 0) { $exitCode = $c }
}
if ($Mode -in 'modules', 'all') {
    $c = Invoke-DesignerCheck -CheckCommand '/CheckModules' -CheckFlags $ModulesArgs
    if ($c -ne 0) { Write-Host "CheckModules: FAILED (code $c)" } else { Write-Host 'CheckModules: OK' }
    if ($c -ne 0) { $exitCode = $c }
}
exit $exitCode
