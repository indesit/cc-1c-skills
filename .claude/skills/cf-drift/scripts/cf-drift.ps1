# cf-drift v1.0 - thin wrapper over cf-drift.py (the compare engine is Python-only)
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Reference,
    [Parameter(Mandatory = $true)]
    [string]$Actual,
    [string]$Json,
    [int]$MaxList = 50,
    [switch]$NoDefaultIgnore
)
$py = Join-Path $PSScriptRoot 'cf-drift.py'
$cmdArgs = @($py, '-Reference', $Reference, '-Actual', $Actual, '-MaxList', $MaxList)
if ($Json) { $cmdArgs += @('-Json', $Json) }
if ($NoDefaultIgnore) { $cmdArgs += '-NoDefaultIgnore' }
& python @cmdArgs
exit $LASTEXITCODE
