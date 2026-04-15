param(
    [string]$HostIp = "192.168.2.145",
    [string]$RootPath = "\\this",
    [string]$PythonExe = "C:\Program Files\LibreOffice\program\python.exe",
    [ValidateSet("full", "sv_at_only", "sv_first")]
    [string]$Mode = "sv_at_only",
    [string[]]$IncludePrefix = @(),
    [string[]]$ExcludePrefix = @(),
    [double]$PauseSeconds = 2.5,
    [double]$TimeoutSeconds = 5.0,
    [int]$MaxFailures = 2,
    [int]$BatchSize = 10,
    [double]$BatchCooldownSeconds = 25.0,
    [int]$MaxStepsPerRound = 40,
    [double]$InterRoundSleepSeconds = 10.0,
    [int]$MaxRounds = 0
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$logsDir = Join-Path $PSScriptRoot "crawl_logs"
if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logPath = Join-Path $logsDir "lsr7_turtle_crawl_$timestamp.log"

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    $line | Tee-Object -FilePath $logPath -Append
}

function Get-CrawlState {
    $checkpointPath = Join-Path $PSScriptRoot "lsr7_tree_checkpoint.json"
    if (-not (Test-Path $checkpointPath)) {
        return $null
    }
    $json = Get-Content $checkpointPath -Raw | ConvertFrom-Json
    [pscustomobject]@{
        Nodes     = @($json.tree.PSObject.Properties).Count
        Queue     = @($json.queue).Count
        FailedAt  = $json.failed_at
        LastError = $json.last_error
        Mode      = $json.mode
    }
}

$baseArgs = @(
    "crawl_lsr7_tree_conservative.py",
    $HostIp,
    $RootPath,
    $PauseSeconds,
    $TimeoutSeconds,
    $MaxFailures,
    $BatchSize,
    $BatchCooldownSeconds,
    $MaxStepsPerRound,
    "--mode",
    $Mode
)

foreach ($prefix in $IncludePrefix) {
    $baseArgs += @("--include-prefix", $prefix)
}
foreach ($prefix in $ExcludePrefix) {
    $baseArgs += @("--exclude-prefix", $prefix)
}

Write-Log "Starting LSR7 turtle crawl runner"
Write-Log "Log file: $logPath"
Write-Log "Host=$HostIp Root=$RootPath Mode=$Mode MaxStepsPerRound=$MaxStepsPerRound BatchSize=$BatchSize BatchCooldownSeconds=$BatchCooldownSeconds"
if ($IncludePrefix.Count -gt 0) {
    Write-Log ("IncludePrefix=" + ($IncludePrefix -join ", "))
}
if ($ExcludePrefix.Count -gt 0) {
    Write-Log ("ExcludePrefix=" + ($ExcludePrefix -join ", "))
}

$round = 0
while ($true) {
    $round++
    if ($MaxRounds -gt 0 -and $round -gt $MaxRounds) {
        Write-Log "Reached MaxRounds=$MaxRounds, stopping."
        break
    }

    Write-Log "===== ROUND $round ====="
    & $PythonExe @baseArgs 2>&1 | Tee-Object -FilePath $logPath -Append

    $exitCode = $LASTEXITCODE
    & $PythonExe "analyze_lsr7_cache.py" 2>&1 | Tee-Object -FilePath $logPath -Append

    $state = Get-CrawlState
    if ($null -ne $state) {
        Write-Log ("Checkpoint: mode={0} nodes={1} queue={2} failed_at={3} last_error={4}" -f $state.Mode, $state.Nodes, $state.Queue, $state.FailedAt, $state.LastError)
        if ($state.Queue -eq 0) {
            Write-Log "Queue is empty. Crawl appears complete."
            break
        }
    }

    if ($exitCode -ne 0) {
        Write-Log "Crawler exited with code $exitCode. Stop here, power-cycle if needed, then re-run this script."
        break
    }

    Write-Log "Round $round completed cleanly. Sleeping $InterRoundSleepSeconds seconds before next round."
    Start-Sleep -Seconds $InterRoundSleepSeconds
}

Write-Log "Runner finished."
