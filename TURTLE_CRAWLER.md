# Turtle Crawler

The turtle crawler is the project's slow, conservative tree-walking tool for reverse-engineering the LSR7 WebSocket object model.

Use it when you want to:

- build or extend the cached tree data
- inspect branches beyond what the live browser shows
- resume a long crawl safely over multiple rounds
- capture more of the speaker's internal parameter layout for offline study

## Run It

Run from the project root:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1
```

Point the crawler at a specific speaker IP:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -HostIp 192.168.2.145
```

Start from a specific branch instead of `\\this`:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -HostIp 192.168.2.145 -RootPath "\\this\Node\UserEq"
```

## Modes

- `sv_at_only`: conservative default. Skips most `DA` expansion except a small allowlist used by the GUI.
- `sv_first`: focuses on `SV` branches first and defers broader `AT` and `DA` expansion.
- `full`: expands everything it can.

Examples:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -Mode sv_at_only
```

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -Mode sv_first
```

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -Mode full
```

## Timing And Pacing Controls

- `-PauseSeconds`: wait between individual node reads
- `-TimeoutSeconds`: WebSocket timeout per request
- `-BatchSize`: number of reads before a cooldown pause
- `-BatchCooldownSeconds`: length of that cooldown pause
- `-MaxStepsPerRound`: stop after this many reads, save a checkpoint, and end the current round
- `-InterRoundSleepSeconds`: wait between rounds in the PowerShell runner
- `-MaxRounds`: total rounds to run before stopping. `0` means keep going until complete or until an error stops the run.
- `-MaxFailures`: how many failures to tolerate for a path before it is marked as deferred and skipped

Examples:

Slower, gentler crawl for a speaker that is easy to overwhelm:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -HostIp 192.168.2.145 -PauseSeconds 4 -BatchSize 6 -BatchCooldownSeconds 40
```

Short test run of one round with only 20 steps:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -HostIp 192.168.2.145 -MaxStepsPerRound 20 -MaxRounds 1
```

Three controlled rounds with a 30-second pause between rounds:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -HostIp 192.168.2.145 -Mode sv_first -MaxStepsPerRound 25 -InterRoundSleepSeconds 30 -MaxRounds 3
```

Longer timeout with a slower per-step pace:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -HostIp 192.168.2.145 -PauseSeconds 3 -TimeoutSeconds 8
```

## Include And Exclude Prefixes

Use include/exclude prefixes to focus the crawl on a branch family.

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_lsr7_turtle_crawl.ps1 -HostIp 192.168.2.145 -Mode full -IncludePrefix "\\this\Node\UserEq\SV" -ExcludePrefix "\\this\Presets"
```

## Rounds And Resume Behavior

- The crawler writes progress into [`lsr7_tree_checkpoint.json`](lsr7_tree_checkpoint.json) after each successful step.
- If you rerun the same host/root combination, it resumes from that checkpoint automatically.
- `MaxStepsPerRound` is the per-round cap.
- `InterRoundSleepSeconds` is the wait between rounds.
- If the queue reaches zero, the crawl is complete and the runner stops.

This makes it practical to crawl cautiously, power-cycle the speaker if needed, and continue later without losing progress.

## Output Files

Main artifacts:

- [`lsr7_tree_cache.json`](lsr7_tree_cache.json)
- [`lsr7_tree_checkpoint.json`](lsr7_tree_checkpoint.json)
- [`LSR7_TREE_SUMMARY.md`](LSR7_TREE_SUMMARY.md)
- `crawl_logs/`

## Notes

- The turtle crawler is intentionally slower and more conservative than a naive recursive crawl.
- It exists to reduce the chance of destabilizing the speaker while still making progress.
- For quick path checking, prefer the app's `Live Browser`.
