# log-analyze v1.0 - thin wrapper over log-analyze.py (the parser engine is Python-only)
[CmdletBinding()]
param(
    [string]$LogDir,
    [string]$Infobase,
    [string]$From,
    [string]$To,
    [string]$Severity = 'E,W',
    [int]$Top = 10,
    [int]$Details = 20,
    [string]$Json
)
$py = Join-Path $PSScriptRoot 'log-analyze.py'
$cmdArgs = @($py, '-Severity', $Severity, '-Top', $Top, '-Details', $Details)
if ($LogDir) { $cmdArgs += @('-LogDir', $LogDir) }
if ($Infobase) { $cmdArgs += @('-Infobase', $Infobase) }
if ($From) { $cmdArgs += @('-From', $From) }
if ($To) { $cmdArgs += @('-To', $To) }
if ($Json) { $cmdArgs += @('-Json', $Json) }
& python @cmdArgs
exit $LASTEXITCODE
