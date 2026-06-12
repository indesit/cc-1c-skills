# cfe-compat v1.0 - thin wrapper over cfe-compat.py (the analysis engine is Python-only)
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExtensionPath,
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [string]$Json,
    [switch]$Strict
)
$py = Join-Path $PSScriptRoot 'cfe-compat.py'
$cmdArgs = @($py, '-ExtensionPath', $ExtensionPath, '-ConfigPath', $ConfigPath)
if ($Json) { $cmdArgs += @('-Json', $Json) }
if ($Strict) { $cmdArgs += '-Strict' }
& python @cmdArgs
exit $LASTEXITCODE
