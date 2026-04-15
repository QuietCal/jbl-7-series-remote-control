# LSR7 Tree Summary

Host: `192.168.2.145`
Root: `\\this`

## Counts

- Total nodes: `371`
- node: `46`
- parameter: `300`
- unknown: `25`

## Family Counts

- SV: `326`
- AT: `39`
- DA: `6`

## Queue Growth Note

- The queue can legitimately grow during a healthy crawl when a single branch expands into many children.
- A positive queue delta means discovery is outpacing consumption for that branch.
- This is most common in deep `DA` and indexed parameter subtrees.

## Top-Level Branch Sizes


## High-Value GUI Candidate Branches

- `\\this\Node\InputMixer\SV`: `18` nodes
- `\\this\Node\SpeakerGain\SV`: `4` nodes
- `\\this\Node\RoomDelay\SV`: `3` nodes
- `\\this\Node\RoomEQ\SV`: `50` nodes
- `\\this\Node\Limiter_Lo\SV`: `13` nodes
- `\\this\Node\Limiter_Hi\SV`: `13` nodes
- `\\this\Node\LSR7Hardware\SV`: `10` nodes
- `\\this\Presets\Presets\SV`: `19` nodes

## Top Queue-Expanding Prefixes


## Deferred / Noisy Prefixes

- None recorded in the current cache

## Parameter Samples


### `\\this\Node\BassMgmtXover\SV`

- `\\this\Node\BassMgmtXover\SV\Frequency` -> `60 Hz`
- `\\this\Node\BassMgmtXover\SV\Type` -> `BW 12`
- `\\this\Node\BassMgmtXover\SV\Enable` -> `Off`

### `\\this\Node\FrameDelay\SV`

- `\\this\Node\FrameDelay\SV\Out_1_Enable` -> `Off`
- `\\this\Node\FrameDelay\SV\Out_1_Delay` -> `0ms/0ft/0m`

### `\\this\Node\InputMixer\SV`

- `\\this\Node\InputMixer\SV\InputSource` -> `Analog`
- `\\this\Node\InputMixer\SV\AnalogGain` -> `0.0dB`
- `\\this\Node\InputMixer\SV\AESGain` -> `0.0dB`
- `\\this\Node\InputMixer\SV\SampleRate` -> `192000`
- `\\this\Node\InputMixer\SV\InputSensitivity` -> `Plus4`
- `\\this\Node\InputMixer\SV\AESMeasuredSampleRate` -> `0`
- `\\this\Node\InputMixer\SV\AESClockLock` -> `Off`
- `\\this\Node\InputMixer\SV\InputTrim` -> `0.0dB`

### `\\this\Node\LSR7Hardware\SV`

- `\\this\Node\LSR7Hardware\SV\AmpBoardMute` -> `Off`
- `\\this\Node\LSR7Hardware\SV\LCDLight` -> `On`
- `\\this\Node\LSR7Hardware\SV\AmpBoardManagerEnable` -> `Enable`
- `\\this\Node\LSR7Hardware\SV\ManualAmpDetCon` -> `High`
- `\\this\Node\LSR7Hardware\SV\ManualAmpCtrlMute` -> `High`
- `\\this\Node\LSR7Hardware\SV\ManualFuncMute` -> `High`
- `\\this\Node\LSR7Hardware\SV\PWMOutRate` -> `370`
- `\\this\Node\LSR7Hardware\SV\GreenLEDFunction` -> `None`

### `\\this\Node\Limiter_Hi\SV`

- `\\this\Node\Limiter_Hi\SV\Bypass` -> `Off`
- `\\this\Node\Limiter_Hi\SV\Threshold` -> `-0.2dB`
- `\\this\Node\Limiter_Hi\SV\OverEasy` -> `Off`
- `\\this\Node\Limiter_Hi\SV\Attack` -> `2`
- `\\this\Node\Limiter_Hi\SV\Hold` -> `0`
- `\\this\Node\Limiter_Hi\SV\Release` -> `40`
- `\\this\Node\Limiter_Hi\SV\AutoMode` -> `Off`
- `\\this\Node\Limiter_Hi\SV\PeakStop` -> `On`

### `\\this\Node\Limiter_Lo\SV`

- `\\this\Node\Limiter_Lo\SV\Bypass` -> `Off`
- `\\this\Node\Limiter_Lo\SV\Threshold` -> `-0.2dB`
- `\\this\Node\Limiter_Lo\SV\OverEasy` -> `Off`
- `\\this\Node\Limiter_Lo\SV\Attack` -> `2`
- `\\this\Node\Limiter_Lo\SV\Hold` -> `0`
- `\\this\Node\Limiter_Lo\SV\Release` -> `40`
- `\\this\Node\Limiter_Lo\SV\AutoMode` -> `Off`
- `\\this\Node\Limiter_Lo\SV\PeakStop` -> `On`

### `\\this\Node\RoomDelay\SV`

- `\\this\Node\RoomDelay\SV\Out_1_Enable` -> `Off`
- `\\this\Node\RoomDelay\SV\Out_1_Delay` -> `0ms/0ft/0m`

### `\\this\Node\RoomEQ\SV`

- `\\this\Node\RoomEQ\SV\Enable` -> `Off`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Frequency` -> `1.02kHz`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Gain` -> `0.0dB`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Q` -> `1`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Slope` -> `3`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Type` -> `Bell`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Enable` -> `Enabled`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_2_Frequency` -> `1.02kHz`

### `\\this\Node\SV`

- `\\this\Node\SV\Locate` -> `Off`

### `\\this\Node\SpeakerEQ_Hi\SV`

- `\\this\Node\SpeakerEQ_Hi\SV\Enable` -> `On`
- `\\this\Node\SpeakerEQ_Hi\SV\Flatten` -> `Restore`
- `\\this\Node\SpeakerEQ_Hi\SV\Channel_1_Band_1_Frequency` -> `1.34kHz`
- `\\this\Node\SpeakerEQ_Hi\SV\Channel_1_Band_1_Gain` -> `-2.5dB`
- `\\this\Node\SpeakerEQ_Hi\SV\Channel_1_Band_1_Q` -> `1.32`
- `\\this\Node\SpeakerEQ_Hi\SV\Channel_1_Band_1_Slope` -> `3`
- `\\this\Node\SpeakerEQ_Hi\SV\Channel_1_Band_1_Type` -> `Bell`
- `\\this\Node\SpeakerEQ_Hi\SV\Channel_1_Band_2_Frequency` -> `2.15kHz`

### `\\this\Node\SpeakerEQ_Lo\SV`

- `\\this\Node\SpeakerEQ_Lo\SV\Enable` -> `On`
- `\\this\Node\SpeakerEQ_Lo\SV\Flatten` -> `Restore`
- `\\this\Node\SpeakerEQ_Lo\SV\Channel_1_Band_1_Frequency` -> `690Hz`
- `\\this\Node\SpeakerEQ_Lo\SV\Channel_1_Band_1_Gain` -> `-7.3dB`
- `\\this\Node\SpeakerEQ_Lo\SV\Channel_1_Band_1_Q` -> `0.984`
- `\\this\Node\SpeakerEQ_Lo\SV\Channel_1_Band_1_Slope` -> `3`
- `\\this\Node\SpeakerEQ_Lo\SV\Channel_1_Band_1_Type` -> `Bell`
- `\\this\Node\SpeakerEQ_Lo\SV\Channel_1_Band_2_Frequency` -> `38.7Hz`

### `\\this\Node\SpeakerGain\SV`

- `\\this\Node\SpeakerGain\SV\Channel_1_Gain` -> `0.0dB`
- `\\this\Node\SpeakerGain\SV\Channel_1_Mute` -> `Off`
- `\\this\Node\SpeakerGain\SV\Channel_1_Polarity` -> `Off`

### `\\this\Node\SpeakerTrim\SV`

- `\\this\Node\SpeakerTrim\SV\Channel_1_Gain` -> `4.9dB`
- `\\this\Node\SpeakerTrim\SV\Channel_1_Mute` -> `Off`
- `\\this\Node\SpeakerTrim\SV\Channel_1_Polarity` -> `Off`

### `\\this\Node\SystemHP\SV`

- `\\this\Node\SystemHP\SV\Frequency` -> `42Hz`
- `\\this\Node\SystemHP\SV\Type` -> `BW 12`
- `\\this\Node\SystemHP\SV\Enable` -> `On`

### `\\this\Node\UserEQ\SV`

- `\\this\Node\UserEQ\SV\Enable` -> `Off`
- `\\this\Node\UserEQ\SV\Flatten` -> `Restore`
- `\\this\Node\UserEQ\SV\Channel_1_Band_1_Frequency` -> `2.03kHz`
- `\\this\Node\UserEQ\SV\Channel_1_Band_1_Gain` -> `0.0dB`
- `\\this\Node\UserEQ\SV\Channel_1_Band_1_Q` -> `1`
- `\\this\Node\UserEQ\SV\Channel_1_Band_1_Slope` -> `3`
- `\\this\Node\UserEQ\SV\Channel_1_Band_1_Type` -> `High Shelf`
- `\\this\Node\UserEQ\SV\Channel_1_Band_2_Frequency` -> `89.8Hz`

### `\\this\Presets\Presets\SV`

- `\\this\Presets\Presets\SV\Store` -> `1`
- `\\this\Presets\Presets\SV\Recall` -> `1`
- `\\this\Presets\Presets\SV\Changed` -> `Changed`
- `\\this\Presets\Presets\SV\CurrentPreset` -> `1`
- `\\this\Presets\Presets\SV\CurrentPresetChanged` -> `0`
- `\\this\Presets\Presets\SV\Name_1` -> `Preset_1`
- `\\this\Presets\Presets\SV\Name_2` -> `Preset_2`
- `\\this\Presets\Presets\SV\Name_3` -> `Preset_3`
