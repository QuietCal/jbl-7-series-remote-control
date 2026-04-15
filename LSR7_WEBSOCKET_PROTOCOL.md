# JBL LSR7 WebSocket Protocol

This document summarizes the currently verified control protocol used by the JBL 7 Series speaker through its LSR7 WebSocket interface.

It is meant to be a practical reference for this repo, not a full protocol specification.

## Summary

- Transport: WebSocket over TCP
- Port: `19273`
- Payload format: plain text commands and plain text responses
- Main live target verified during development: `LSR708`

## What Is Confirmed

Confirmed on a live speaker:

- standard HTTP WebSocket upgrade succeeds
- the speaker responds with `101 WebSocket Protocol Handshake`
- identity reads succeed
- branch enumeration works
- value reads work
- writes and write confirmations work

Verified identity examples:

- `\\this\Node\AT\Class_Name` -> `LSR708`
- `\\this\Node\AT\Instance_Name` -> `LSR708`
- `\\this\Node\AT\Software_Version` -> `1.0.6.0`

## Request Format

Commands are sent as plain text frames terminated with `\r\n`.

### List Children

```text
lc "\\this\Node"
```

### Read A Value

```text
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain"
```

### Read Parameter Metadata

Examples:

```text
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\%"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\f"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\r"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\$"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\Min"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\Max"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\Type"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\Enabled"
get "\\this\Node\SpeakerGain\SV\Channel_1_Gain\Sensor"
```

### Write Text Or Enum Values

```text
set "\\this\Node\LSR7Hardware\SV\AmberLEDFunction" "None"
```

### Write Percent-Scaled Values

```text
set "\\this\Node\SpeakerGain\SV\Channel_1_Gain\%" 100
```

## Response Shapes

### `lc`

Structure:

- starts with `lc "path"`
- returns one child per line
- ends with `endlc`

### `get`

Typical shape:

```text
get "path" "value"
```

### `setr`

Typical shape:

```text
setr "path" "value"
```

### `error`

Typical shape:

```text
error "path"
```

## Confirmed Branches Under `\\this\Node`

- `DSPInputs`
- `DSPOutputs`
- `InputMixer`
- `UserEQ`
- `BassMgmtXover`
- `SpeakerEQ_Lo`
- `SpeakerEQ_Hi`
- `RoomEQ`
- `RoomDelay`
- `FrameDelay`
- `SpeakerGain`
- `SpeakerTrim`
- `SystemHP`
- `SideChainLP_Hi`
- `SideChainLP_Lo`
- `SideChainEQ_Lo`
- `SideChainEQ_Hi`
- `Limiter_Lo`
- `Limiter_Hi`
- `CompLowpass_Lo`
- `CompHighpass_Hi`
- `CompDelay_Hi`
- `CompGain_Hi`
- `AnalogInputMeter`
- `AES1InputMeter`
- `AES2InputMeter`
- `OutputHiMeter`
- `OutputLoMeter`
- `ChannelInputMeter`
- `LSR7Hardware`
- `SV`
- `AT`
- `DA`

## Example Readback Values

- `\\this\Node\SpeakerGain\SV\Channel_1_Gain` -> `0.0dB`
- `\\this\Node\SpeakerGain\SV\Channel_1_Mute` -> `Off`
- `\\this\Node\SpeakerGain\SV\Channel_1_Polarity` -> `Off`
- `\\this\Node\RoomEQ\SV\Enable` -> `Off`
- `\\this\Node\RoomDelay\SV\Out_1_Delay` -> `0ms/0ft/0m`
- `\\this\Node\InputMixer\SV\InputSensitivity` -> `Plus4`

## App-Relevant Areas

The current desktop app is centered on these sections:

- `InputMixer`
- `UserEQ`
- `BassMgmtXover`
- `SpeakerEQ_Lo`
- `SpeakerEQ_Hi`
- `RoomEQ`
- `RoomDelay`
- `FrameDelay`
- `SpeakerTrim`
- meter branches
- selected hardware/LED controls

The app does not attempt to surface every branch that exists on the speaker.

## Notes On Values

- Delay values may be returned as combined text such as `0ms/0ft/0m`
- enable-style values are not perfectly uniform across branches
- some fields act like enums even when they are not documented as such
- some factory/service paths are writable but should not be treated as normal user controls

## Safety Notes

- The protocol supports direct live writes to the speaker
- Not every writable path is appropriate for routine user adjustment
- Factory-tuned areas such as `SpeakerEQ_Lo`, `SpeakerEQ_Hi`, and parts of `SpeakerTrim` should be handled cautiously

## Related Files

- [`README.md`](README.md)
- [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
- [`lsr7_ws.py`](lsr7_ws.py)
- [`lsr7_catalog.py`](lsr7_catalog.py)
- [`LSR7_MAPPED_PATHS.md`](LSR7_MAPPED_PATHS.md)
