param(
  [string]$Product = "islam",
  [string]$ProjectDir = "",
  [string]$Diff = "",
  [string]$DbPath = "",
  [ValidateSet("auto", "disabled", "real")]
  [string]$Llm = "auto",
  [int]$Port = 0,
  [switch]$InstallDeps,
  [switch]$SkipVerify,
  [switch]$SkipSmoke,
  [switch]$ExitAfterSmoke,
  [switch]$NoOpenBrowser,
  [switch]$AllowMissingDb
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ArgsList = @("$ScriptDir\standalone_run.py", "--product", $Product, "--llm", $Llm)

if ($ProjectDir) { $ArgsList += @("--project-dir", $ProjectDir) }
if ($Diff) { $ArgsList += @("--diff", $Diff) }
if ($DbPath) { $ArgsList += @("--db", $DbPath) }
if ($Port -gt 0) { $ArgsList += @("--port", "$Port") }
if ($InstallDeps) { $ArgsList += "--install-deps" }
if ($SkipVerify) { $ArgsList += "--skip-verify" }
if ($SkipSmoke) { $ArgsList += "--skip-smoke" }
if ($ExitAfterSmoke) { $ArgsList += "--exit-after-smoke" }
if ($NoOpenBrowser) { $ArgsList += "--no-open-browser" }
if ($AllowMissingDb) { $ArgsList += "--allow-missing-db" }

python @ArgsList
