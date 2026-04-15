# LSR7 Mapped Paths

This file is the quickest reference for the JBL 7 Series speaker paths that have already been identified.

## Identity

- `\\this\Node\AT\Class_Name`
- `\\this\Node\AT\Instance_Name`
- `\\this\Node\AT\Software_Version`

## Common Controls

- `\\this\Node\SpeakerGain\SV\Channel_1_Gain`
- `\\this\Node\SpeakerGain\SV\Channel_1_Mute`
- `\\this\Node\SpeakerGain\SV\Channel_1_Polarity`
- `\\this\Node\RoomEQ\SV\Enable`
- `\\this\Node\RoomDelay\SV\Out_1_Delay`
- `\\this\Node\LSR7Hardware\SV\LCDLight`
- `\\this\Node\LSR7Hardware\SV\GreenLEDFunction`
- `\\this\Node\LSR7Hardware\SV\AmberLEDFunction`

## Confirmed Current-State Parameters

- `\\this\Node\InputMixer\SV\InputSource` -> `Analog`
- `\\this\Node\InputMixer\SV\AnalogGain` -> `0.0dB`
- `\\this\Node\InputMixer\SV\AESGain` -> `0.0dB`
- `\\this\Node\InputMixer\SV\InputSensitivity` -> `Plus4`
- `\\this\Node\InputMixer\SV\SpeakerSelect` -> `Left`
- `\\this\Node\InputMixer\SV\SampleRate` -> `192000`
- `\\this\Node\InputMixer\SV\SRC` -> `Disengaged`
- `\\this\Node\RoomDelay\SV\Out_1_Enable` -> `Off`
- `\\this\Node\RoomDelay\SV\Out_1_Delay` -> `0ms/0ft/0m`
- `\\this\Node\SpeakerGain\SV\Channel_1_Gain` -> `0.0dB`
- `\\this\Node\SpeakerGain\SV\Channel_1_Mute` -> `Off`
- `\\this\Node\SpeakerGain\SV\Channel_1_Polarity` -> `Off`

## Confirmed Limiter Low Parameters

- `\\this\Node\Limiter_Lo\SV\Attack`
- `\\this\Node\Limiter_Lo\SV\AutoMode`
- `\\this\Node\Limiter_Lo\SV\Bypass`
- `\\this\Node\Limiter_Lo\SV\GainReductionMeter`
- `\\this\Node\Limiter_Lo\SV\Hold`
- `\\this\Node\Limiter_Lo\SV\InputLevel`
- `\\this\Node\Limiter_Lo\SV\OverEasy`
- `\\this\Node\Limiter_Lo\SV\OverShoot`
- `\\this\Node\Limiter_Lo\SV\PeakStop`
- `\\this\Node\Limiter_Lo\SV\Release`
- `\\this\Node\Limiter_Lo\SV\Threshold`
- `\\this\Node\Limiter_Lo\SV\ThresholdMeter`

## Confirmed Room EQ Band Parameters

- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Enable`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Frequency`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Gain`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Q`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Slope`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_1_Type`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_2_Enable`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_2_Frequency`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_2_Gain`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_2_Q`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_2_Slope`
- `\\this\Node\RoomEQ\SV\Channel_1_Band_2_Type`

## High-Value Branches

- `\\this\Node\SpeakerGain\SV`
- `\\this\Node\RoomEQ\SV`
- `\\this\Node\RoomDelay\SV`
- `\\this\Node\FrameDelay\SV`
- `\\this\Node\SpeakerTrim\SV`
- `\\this\Node\SystemHP\SV`
- `\\this\Node\Limiter_Lo\SV`
- `\\this\Node\Limiter_Hi\SV`
- `\\this\Node\UserEQ`
- `\\this\Node\SpeakerEQ_Lo`
- `\\this\Node\SpeakerEQ_Hi`
- `\\this\Node\BassMgmtXover`
- `\\this\Node\LSR7Hardware\SV`
- `\\this\Presets\Presets\SV`

## Meter And Signal Branches

- `\\this\Node\AnalogInputMeter`
- `\\this\Node\AES1InputMeter`
- `\\this\Node\AES2InputMeter`
- `\\this\Node\OutputHiMeter`
- `\\this\Node\OutputLoMeter`
- `\\this\Node\ChannelInputMeter`
- `\\this\Node\DSPInputs`
- `\\this\Node\DSPOutputs`
- `\\this\Node\InputMixer`

## Supporting Branches

- `\\this\Node\AT`
- `\\this\Node\SV`
- `\\this\Node\DA`
- `\\this\Presets`

## Confirmed Metadata Suffixes

- `\$`
- `\%`
- `\f`
- `\r`
- `\Min`
- `\Max`
- `\Sensor`
- `\Enabled`
- `\Type`

## Notes

- The main app exposes the common controls directly.
- The conservative crawler has mapped at least `587` nodes so far and stores progress in `lsr7_tree_cache.json` plus `lsr7_tree_checkpoint.json`.
- `LSR7_TREE_SUMMARY.md` reflects the most recent cached crawl.
- The Explorer tab is the right place to continue deeper mapping.
- Exported snapshots are the best way to preserve a baseline of the speaker state before making broader write changes.
