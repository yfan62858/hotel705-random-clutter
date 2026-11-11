[CmdletBinding()]
param(
    [string]$IsaacSimPath = $env:ISAAC_SIM_PATH,
    [int]$Seed = 705,
    [ValidateSet('clean', 'low', 'medium', 'high')]
    [string]$Level = 'medium',
    [switch]$Preview,
    [switch]$CheckControls
)
$ErrorActionPreference = 'Stop'
if (-not $IsaacSimPath) {
    throw 'Set ISAAC_SIM_PATH or pass -IsaacSimPath with your Isaac Sim 5.1 installation folder.'
}
$isaacRoot = (Resolve-Path -LiteralPath $IsaacSimPath).Path
$pythonLauncher = Join-Path $isaacRoot 'python.bat'
if (-not (Test-Path -LiteralPath $pythonLauncher -PathType Leaf)) {
    throw "Isaac Sim python.bat was not found at $pythonLauncher"
}
if ($Preview -and $CheckControls) {
    throw 'Choose one mode from -Preview and -CheckControls.'
}
$env:ISAAC_SIM_PATH = $isaacRoot
$pythonArguments = @((Join-Path $PSScriptRoot 'app.py'), '--seed', "$Seed", '--level', $Level)
if ($Preview) { $pythonArguments += '--preview' }
if ($CheckControls) { $pythonArguments += '--check-controls' }
& $pythonLauncher @pythonArguments
exit $LASTEXITCODE
