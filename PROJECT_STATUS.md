# JBL 7 Series Controller Project Status

Last updated: 2026-04-14

## Current State

- Active control path: JBL LSR7 WebSocket API on `tcp/19273`
- Current working version: `1.1`
- Stable baseline snapshot: `backups/v1.0`
- Primary app entry point: [`run_lsr7_controller.py`](run_lsr7_controller.py)
- Current executable output: `dist/JBL7SpeakerController.exe`


## Verified Live Findings

Confirmed on a live speaker:

- WebSocket handshake succeeds on `19273/TCP`
- `\\this\Node\AT\Class_Name` -> `LSR708`
- `\\this\Node\AT\Instance_Name` -> `LSR708`
- `\\this\Node\AT\Software_Version` -> `1.0.6.0`

Confirmed readable areas include:

- `UserEQ`
- `BassMgmtXover`
- `SpeakerEQ_Lo`
- `SpeakerEQ_Hi`
- `RoomEQ`
- `RoomDelay` / `FrameDelay` paths, surfaced together in the `Delay` tab
- `SpeakerTrim`
- meter branches under `DA\da_meter\p_Level`

## Current UI Shape

Top bar includes:

- speaker target
- theme toggle
- refresh/discovery controls
- write behavior toggles
- expanded status display

Current tab order:

1. `Overview`
2. `Delay`
3. `SpeakerTrim`
4. `SpeakerEQ_Lo`
5. `SpeakerEQ_Hi`
6. `BassMgmtXover`
7. `RoomEQ`
8. `UserEQ`
9. `Combined EQ`
10. `Meters`
11. `Live Browser`
12. `Diagnostics`

## Notable Current Behavior

- constrained UI controls are used where the valid range is known
- enable-style fields are normalized to `On` / `Off`
- editable rows support local `Undo`
- global undo/redo works with:
  - `Ctrl+Z`
  - `Ctrl+Y`
  - `Ctrl+Shift+Z`
- `Instant-Update` writes only the changed control and flashes while active
- EQ and crossover tabs redraw graphs after successful related writes

## Important Cautions

- `SpeakerEQ_Lo` and `SpeakerEQ_Hi` are factory-tuned and revert after reboot
- `SpeakerTrim` is closer to a service/factory function than a normal user control
- direct writes go to the live speaker

## Core Files

- [`run_lsr7_controller.py`](run_lsr7_controller.py)
- [`lsr7_gui.py`](lsr7_gui.py)
- [`lsr7_ws.py`](lsr7_ws.py)
- [`lsr7_catalog.py`](lsr7_catalog.py)
- [`lsr7_network.py`](lsr7_network.py)
- [`lsr7_storage.py`](lsr7_storage.py)

## Research / Support Files

- [`LSR7_WEBSOCKET_PROTOCOL.md`](LSR7_WEBSOCKET_PROTOCOL.md)
- [`LSR7_MAPPED_PATHS.md`](LSR7_MAPPED_PATHS.md)
- [`LSR7_TREE_SUMMARY.md`](LSR7_TREE_SUMMARY.md)
- [`VERSION.md`](VERSION.md)