param(
  [double]$Interval = 300,
  [int]$Cycles = 288,
  [switch]$Resume
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @("scripts/run_long_soak.py", "--interval", "$Interval", "--cycles", "$Cycles")
if ($Resume) {
  $argsList += "--resume"
}

py -3 @argsList

