# JBL 7 Series Speaker Controller

An unofficial remote controller for JBL 7 Series powered monitors, built make all the inbuilt DSP of the speaker practically usable.

This app gives you direct access to EQ, delay, trim, source, bass management, diagnostics, and live speaker-state browsing from a desktop UI. Instead of reaching behind the speaker or guessing at hidden DSP behavior, you can connect over the network and work in a focused control surface designed around real tuning workflows.

## Download

If you just want to use the controller on Windows, start here:

- [Download the latest Windows release](https://github.com/JonathonZener/jbl-7-series-remote-control/releases/latest/download/JBL7SpeakerController.exe)
- [Download the default config file](https://github.com/JonathonZener/jbl-7-series-remote-control/releases/latest/download/lsr7_controller_config.json)
- [Open the latest release page](https://github.com/JonathonZener/jbl-7-series-remote-control/releases/latest)

No build step is required. Download `JBL7SpeakerController.exe`, optionally keep `lsr7_controller_config.json` beside it, and run the app.

## Why It's Useful

- DSP built into the speaker is now controllable while the speaker is placed in its final position
- Works over WiFi or LAN, with speaker discovery on the same subnet
- Uses bounded controls for reliable parameter entry
- See EQ response graphs while working
- Browse the live speaker tree and inspect protocol activity when you need deeper visibility

## Quick Start

### Windows

1. Download `JBL7SpeakerController.exe`.
2. Optionally download `lsr7_controller_config.json` and place it beside the `.exe`.
3. Launch the app.
4. Enter the speaker IP or use `Discover Speakers`.
5. Select the correct local network interface.
6. Refresh the speaker and start working in the tab you need.

### Run From Source

From the project folder:

```powershell
python .\run_lsr7_controller.py
```

Compatibility launcher:

```powershell
python .\run_controller.py
```

`run_controller.py` simply forwards into the main app.

## Screenshots

The app is organized around the tasks that matter in real use: quick adjustments, EQ work, combined response inspection, live browsing, and diagnostics.

### Overview

![Overview tab](docs/screenshots/overview-tab.png)

### Combined EQ

![Combined EQ tab](docs/screenshots/combined-eq-tab.png)

### Diagnostics

![Diagnostics tab](docs/screenshots/diagnostics-tab.png)

See the full gallery in [`docs/SCREENSHOTS.md`](docs/SCREENSHOTS.md).

## Main Features

- `Overview`
  - speaker identity
  - current speaker state
  - quick actions for commonly adjusted settings
- `Delay`
  - room delay
  - AV sync delay
- `SpeakerTrim`
  - factory and service-oriented trim controls
- `SpeakerEQ_Lo` and `SpeakerEQ_Hi`
  - factory-tuned EQ sections
  - response graphs
- `BassMgmtXover`
  - bass management controls
  - crossover response view
- `RoomEQ` and `UserEQ`
  - editable EQ blocks
  - response graphs
- `Combined EQ`
  - merged view of the major EQ blocks and bass management
- `Live Browser`
  - branch-by-branch live speaker tree browsing
- `Diagnostics`
  - app log
  - protocol trace
  - snapshot export tools

## Editing Experience

- Most editable values use dropdowns, sliders, or bounded entry controls instead of free-form input
- Dirty values turn orange
- Successfully applied values turn blue
- Freshly loaded values turn green
- Row-level `Undo` is available on editable controls
- Global undo/redo uses:
  - `Ctrl+Z`
  - `Ctrl+Y`
  - `Ctrl+Shift+Z`
- `Instant-Update` can apply one changed control at a time for faster tuning

## Build

To build the executable yourself:

```powershell
python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name JBL7SpeakerController run_lsr7_controller.py
```

Build outputs:

- `dist/JBL7SpeakerController.exe`
- [`JBL7SpeakerController.spec`](JBL7SpeakerController.spec)

## Current Status

- Current working version: `1.1`
- Verified live against the JBL LSR7 WebSocket control path on `tcp/19273`
- Available as both source code and a prebuilt Windows executable
- Open to feedback, cleanup, and future improvements

## Important Notes

- `SpeakerEQ_Lo` and `SpeakerEQ_Hi` are factory-tuned sections
- Their changes do not survive a reboot
- `SpeakerTrim` is closer to a service or factory function than a normal day-to-day user control
- The app writes directly to the live speaker, so keep `Confirm writes` enabled unless you intentionally want faster iteration

## Additional Docs

- [`docs/SCREENSHOTS.md`](docs/SCREENSHOTS.md): full screenshot gallery
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md): project handoff and current state
- [`LSR7_WEBSOCKET_PROTOCOL.md`](LSR7_WEBSOCKET_PROTOCOL.md): protocol notes and response shapes
- [`TURTLE_CRAWLER.md`](TURTLE_CRAWLER.md): crawler usage and reverse-engineering workflow
- [`LSR7_MAPPED_PATHS.md`](LSR7_MAPPED_PATHS.md): mapped path reference
- [`LSR7_TREE_SUMMARY.md`](LSR7_TREE_SUMMARY.md): cache summary
- [`708P_INVESTIGATION_LOG.md`](708P_INVESTIGATION_LOG.md): older reverse-engineering notes

## Credit

This project was built and iterated rapidly with Codex, going from blank-slate discovery to a working controller in a very short time, then refined through real-world testing and cleanup.
