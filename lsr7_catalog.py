from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LSR7Control:
    key: str
    label: str
    path: str
    write_mode: str
    description: str


@dataclass(frozen=True)
class LSR7Panel:
    key: str
    label: str
    paths: dict[str, str]
    description: str
    graph_mode: str | None = None


@dataclass(frozen=True)
class LSR7InputHint:
    input_kind: Literal["text", "enum", "numeric_db", "numeric_ms", "numeric_plain"]
    choices: tuple[str, ...] = ()
    suffix: str = ""
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    decimals: int = 1


def _format_frequency_choice(hz: float) -> str:
    if hz >= 1000.0:
        khz = hz / 1000.0
        if khz >= 10.0:
            return f"{khz:.1f}kHz"
        return f"{khz:.2f}kHz"
    if hz >= 100.0:
        return f"{hz:.0f}Hz"
    return f"{hz:.1f}Hz"


def _octave_frequency_choices(min_hz: float = 20.0, max_hz: float = 22000.0, divisions: int = 24) -> tuple[str, ...]:
    values: list[str] = []
    index = 0
    seen: set[str] = set()
    while True:
        hz = min_hz * (2.0 ** (index / divisions))
        if hz > max_hz * 1.001:
            break
        label = _format_frequency_choice(hz)
        if label not in seen:
            values.append(label)
            seen.add(label)
        index += 1
    if _format_frequency_choice(max_hz) not in seen:
        values.append(_format_frequency_choice(max_hz))
    return tuple(values)


EQ_FREQUENCY_CHOICES = _octave_frequency_choices()


IDENTITY_PATHS: dict[str, str] = {
    "Class Name": "\\\\this\\Node\\AT\\Class_Name",
    "Instance Name": "\\\\this\\Node\\AT\\Instance_Name",
    "Software Version": "\\\\this\\Node\\AT\\Software_Version",
}


SYSTEM_INFO_PATHS: dict[str, str] = {
    "Locate": "\\\\this\\Node\\SV\\Locate",
    "Address Mode": "\\\\this\\Node\\AT\\Address_Mode",
    "System State": "\\\\this\\Node\\AT\\Node_State",
    "Configuration State": "\\\\this\\Node\\AT\\Configuration_State",
    "Input Count": "\\\\this\\Node\\InputMixer\\AT\\NumInputs",
    "Output Count": "\\\\this\\Node\\InputMixer\\AT\\NumOutputs",
}


COMMON_CONTROLS: list[LSR7Control] = [
    LSR7Control("locate", "Locate", "\\\\this\\Node\\SV\\Locate", "text", "Flash or clear the network locate state."),
    LSR7Control("input_source", "Input Source", "\\\\this\\Node\\InputMixer\\SV\\InputSource", "text", "Select Analog or AES input source."),
    LSR7Control("input_sensitivity", "Input Sensitivity", "\\\\this\\Node\\InputMixer\\SV\\InputSensitivity", "text", "Choose professional or consumer analog sensitivity."),
    LSR7Control("input_trim", "Input Trim", "\\\\this\\Node\\InputMixer\\SV\\InputTrim", "text", "Analog input trim from -24.0dB to 0.0dB in 0.1dB steps."),
    LSR7Control("aes_level_trim", "AES Level Trim", "\\\\this\\Node\\InputMixer\\SV\\AESGain", "text", "Digital AES trim from -24.0dB to +24.0dB in 0.1dB steps."),
    LSR7Control("speaker_select", "Speaker Select", "\\\\this\\Node\\InputMixer\\SV\\SpeakerSelect", "text", "Assign the monitor role used by presets and system configuration."),
    LSR7Control("mute", "Speaker Mute", "\\\\this\\Node\\SpeakerGain\\SV\\Channel_1_Mute", "text", "Main mute state."),
    LSR7Control("polarity", "Speaker Polarity", "\\\\this\\Node\\SpeakerGain\\SV\\Channel_1_Polarity", "text", "Polarity invert control."),
    LSR7Control("room_eq", "Room EQ Enable", "\\\\this\\Node\\RoomEQ\\SV\\Enable", "text", "Room EQ block enable."),
    LSR7Control("user_eq", "User EQ Enable", "\\\\this\\Node\\UserEQ\\SV\\Enable", "text", "User EQ block enable."),
    LSR7Control("room_delay", "Room Delay", "\\\\this\\Node\\RoomDelay\\SV\\Out_1_Delay", "text", "Speaker delay value."),
    LSR7Control("frame_delay", "AV Sync Delay", "\\\\this\\Node\\FrameDelay\\SV\\Out_1_Delay", "text", "Frame or AV synchronization delay."),
    LSR7Control("green_led", "Green LED Function", "\\\\this\\Node\\LSR7Hardware\\SV\\GreenLEDFunction", "text", "Green LED assignment."),
    LSR7Control("amber_led", "Amber LED Function", "\\\\this\\Node\\LSR7Hardware\\SV\\AmberLEDFunction", "text", "Amber LED assignment."),
]


OVERVIEW_PATHS: dict[str, str] = {
    "Mute": "\\\\this\\Node\\SpeakerGain\\SV\\Channel_1_Mute",
    "Polarity": "\\\\this\\Node\\SpeakerGain\\SV\\Channel_1_Polarity",
    "Room EQ": "\\\\this\\Node\\RoomEQ\\SV\\Enable",
    "User EQ": "\\\\this\\Node\\UserEQ\\SV\\Enable",
    "Room Delay": "\\\\this\\Node\\RoomDelay\\SV\\Out_1_Delay",
    "AV Sync": "\\\\this\\Node\\FrameDelay\\SV\\Out_1_Delay",
}


def _banded_paths(root: str, count: int, *, include_enable: bool, include_flatten: bool, omit_q_for_bands: tuple[int, ...] = ()) -> dict[str, str]:
    paths: dict[str, str] = {
        "Enable": f"{root}\\Enable",
    }
    if include_flatten:
        paths["Flatten"] = f"{root}\\Flatten"
    for band in range(1, count + 1):
        paths[f"Band {band} Type"] = f"{root}\\Channel_1_Band_{band}_Type"
        paths[f"Band {band} Frequency"] = f"{root}\\Channel_1_Band_{band}_Frequency"
        paths[f"Band {band} Gain"] = f"{root}\\Channel_1_Band_{band}_Gain"
        if band not in omit_q_for_bands:
            paths[f"Band {band} Q"] = f"{root}\\Channel_1_Band_{band}_Q"
        if include_enable:
            paths[f"Band {band} Enable"] = f"{root}\\Channel_1_Band_{band}_Enable"
    return paths


PANEL_SECTIONS: list[LSR7Panel] = [
    LSR7Panel(
        "user_eq",
        "UserEQ",
        _banded_paths("\\\\this\\Node\\UserEQ\\SV", 6, include_enable=False, include_flatten=False, omit_q_for_bands=(1, 2)),
        "User EQ block.",
        "peq",
    ),
    LSR7Panel(
        "bass_mgmt_xover",
        "BassMgmtXover",
        {
            "Enable": "\\\\this\\Node\\BassMgmtXover\\SV\\Enable",
            "Frequency": "\\\\this\\Node\\BassMgmtXover\\SV\\Frequency",
            "Type": "\\\\this\\Node\\BassMgmtXover\\SV\\Type",
        },
        "Bass management crossover block.",
        "crossover",
    ),
    LSR7Panel(
        "speaker_eq_lo",
        "SpeakerEQ_Lo",
        _banded_paths("\\\\this\\Node\\SpeakerEQ_Lo\\SV", 14, include_enable=False, include_flatten=True),
        "Factory-tuned low speaker EQ. Changes are temporary, revert to factory values after every reboot, and are not recommended.",
        "peq",
    ),
    LSR7Panel(
        "speaker_eq_hi",
        "SpeakerEQ_Hi",
        _banded_paths("\\\\this\\Node\\SpeakerEQ_Hi\\SV", 14, include_enable=False, include_flatten=True),
        "Factory-tuned high speaker EQ. Changes are temporary, revert to factory values after every reboot, and are not recommended.",
        "peq",
    ),
    LSR7Panel(
        "room_eq",
        "RoomEQ",
        _banded_paths("\\\\this\\Node\\RoomEQ\\SV", 8, include_enable=True, include_flatten=False),
        "Room EQ block.",
        "peq",
    ),
    LSR7Panel(
        "room_delay",
        "Delay",
        {
            "Room Delay Enable": "\\\\this\\Node\\RoomDelay\\SV\\Out_1_Enable",
            "Room Delay": "\\\\this\\Node\\RoomDelay\\SV\\Out_1_Delay",
            "AV Sync Enable": "\\\\this\\Node\\FrameDelay\\SV\\Out_1_Enable",
            "AV Sync Delay": "\\\\this\\Node\\FrameDelay\\SV\\Out_1_Delay",
        },
        "Room delay and AV sync delay block.",
    ),
    LSR7Panel(
        "speaker_trim",
        "SpeakerTrim",
        {
            "Gain": "\\\\this\\Node\\SpeakerTrim\\SV\\Channel_1_Gain",
            "Mute": "\\\\this\\Node\\SpeakerTrim\\SV\\Channel_1_Mute",
            "Polarity": "\\\\this\\Node\\SpeakerTrim\\SV\\Channel_1_Polarity",
        },
        "Speaker trim is intended for factory/service use. Changes may not be retained after power cycle and are not recommended.",
    ),
    LSR7Panel(
        "meters",
        "Meters",
        {
            "AnalogInputMeter": "\\\\this\\Node\\AnalogInputMeter\\DA\\da_meter\\p_Level",
            "AES1InputMeter": "\\\\this\\Node\\AES1InputMeter\\DA\\da_meter\\p_Level",
            "AES2InputMeter": "\\\\this\\Node\\AES2InputMeter\\DA\\da_meter\\p_Level",
            "OutputHiMeter": "\\\\this\\Node\\OutputHiMeter\\DA\\da_meter\\p_Level",
            "OutputLoMeter": "\\\\this\\Node\\OutputLoMeter\\DA\\da_meter\\p_Level",
            "ChannelInputMeter": "\\\\this\\Node\\ChannelInputMeter\\DA\\da_meter\\p_Level",
        },
        "All input and output meters on one tab.",
    ),
]


FAVORITE_BRANCHES: list[str] = [
    "\\\\this\\Node",
    "\\\\this\\Presets",
]


INPUT_HINTS: dict[str, LSR7InputHint] = {
    "\\\\this\\Node\\SV\\Locate": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\InputMixer\\SV\\InputSource": LSR7InputHint("enum", ("Analog", "AES Ch1", "AES Ch2", "AES Ch1+Ch2")),
    "\\\\this\\Node\\InputMixer\\SV\\InputSensitivity": LSR7InputHint("enum", ("Plus4", "Minus10")),
    "\\\\this\\Node\\InputMixer\\SV\\InputTrim": LSR7InputHint("numeric_db", suffix="dB", minimum=-24.0, maximum=0.0, step=0.1, decimals=1),
    "\\\\this\\Node\\InputMixer\\SV\\AESGain": LSR7InputHint("numeric_db", suffix="dB", minimum=-24.0, maximum=24.0, step=0.1, decimals=1),
    "\\\\this\\Node\\InputMixer\\SV\\SpeakerSelect": LSR7InputHint(
        "enum",
        (
            "Left",
            "Center",
            "Right",
            "Left Side Surround",
            "Right Side Surround",
            "Left Rear Surround",
            "Right Rear Surround",
            "Left Front OH Surround",
            "Right Front OH Surround",
            "Left Rear OH Surround",
            "Right Rear OH Surround",
        ),
    ),
    "\\\\this\\Node\\SpeakerGain\\SV\\Channel_1_Mute": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\SpeakerGain\\SV\\Channel_1_Polarity": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\UserEQ\\SV\\Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\SystemHP\\SV\\Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomDelay\\SV\\Out_1_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\FrameDelay\\SV\\Out_1_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\BassMgmtXover\\SV\\Frequency": LSR7InputHint("enum", ("60 Hz", "70 Hz", "80 Hz", "100 Hz", "120 Hz")),
    "\\\\this\\Node\\LSR7Hardware\\SV\\LCDLight": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\UserEQ\\SV\\Flatten": LSR7InputHint("enum", ("Restore",)),
    "\\\\this\\Node\\LSR7Hardware\\SV\\GreenLEDFunction": LSR7InputHint("enum", ("SignalPresent", "None")),
    "\\\\this\\Node\\LSR7Hardware\\SV\\AmberLEDFunction": LSR7InputHint("enum", ("BassManagement", "None")),
    "\\\\this\\Node\\InputMixer\\SV\\AESClockLock": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\InputMixer\\SV\\SRC": LSR7InputHint("enum", ("Disengaged", "Engaged")),
    "\\\\this\\Node\\LSR7Hardware\\SV\\AmpBoardManagerEnable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\LSR7Hardware\\SV\\AmpBoardMute": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\LSR7Hardware\\SV\\ManualAmpCtrlMute": LSR7InputHint("enum", ("Low", "High")),
    "\\\\this\\Node\\LSR7Hardware\\SV\\ManualAmpDetCon": LSR7InputHint("enum", ("Low", "High")),
    "\\\\this\\Node\\LSR7Hardware\\SV\\ManualFuncMute": LSR7InputHint("enum", ("Low", "High")),
    "\\\\this\\Node\\Limiter_Lo\\SV\\AutoMode": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\Limiter_Lo\\SV\\Bypass": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\Limiter_Lo\\SV\\PeakStop": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\Limiter_Hi\\SV\\AutoMode": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\Limiter_Hi\\SV\\Bypass": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\Limiter_Hi\\SV\\PeakStop": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\SpeakerTrim\\SV\\Channel_1_Mute": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\SpeakerTrim\\SV\\Channel_1_Polarity": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_1_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_2_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_3_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_4_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_5_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_6_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_7_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_8_Enable": LSR7InputHint("enum", ("Off", "On")),
    "\\\\this\\Node\\InputMixer\\SV\\AnalogGain": LSR7InputHint("numeric_db", suffix="dB"),
    "\\\\this\\Node\\SpeakerTrim\\SV\\Channel_1_Gain": LSR7InputHint("numeric_db", suffix="dB"),
    "\\\\this\\Node\\SpeakerGain\\SV\\Channel_1_Gain": LSR7InputHint("numeric_db", suffix="dB"),
    "\\\\this\\Node\\RoomDelay\\SV\\Out_1_Delay": LSR7InputHint("numeric_ms", suffix="ms", minimum=0.0, maximum=18.0, step=0.1, decimals=1),
    "\\\\this\\Node\\FrameDelay\\SV\\Out_1_Delay": LSR7InputHint("numeric_ms", suffix="ms", minimum=0.0, maximum=150.0, step=1.0, decimals=0),
}


for band in range(1, 7):
    root = f"\\\\this\\Node\\UserEQ\\SV\\Channel_1_Band_{band}"
    INPUT_HINTS[f"{root}_Frequency"] = LSR7InputHint("enum", EQ_FREQUENCY_CHOICES)
    INPUT_HINTS[f"{root}_Gain"] = LSR7InputHint("numeric_db", suffix="dB", minimum=-12.0, maximum=12.0, step=0.1, decimals=1)
    if band >= 3:
        INPUT_HINTS[f"{root}_Q"] = LSR7InputHint("numeric_plain", minimum=0.1, maximum=12.0, step=0.1, decimals=1)


for band in range(1, 9):
    root = f"\\\\this\\Node\\RoomEQ\\SV\\Channel_1_Band_{band}"
    INPUT_HINTS[f"{root}_Enable"] = LSR7InputHint("enum", ("Off", "On"))
    INPUT_HINTS[f"{root}_Frequency"] = LSR7InputHint("enum", EQ_FREQUENCY_CHOICES)
    INPUT_HINTS[f"{root}_Gain"] = LSR7InputHint("numeric_db", suffix="dB", minimum=-12.0, maximum=12.0, step=0.1, decimals=1)
    INPUT_HINTS[f"{root}_Q"] = LSR7InputHint("numeric_plain", minimum=0.1, maximum=12.0, step=0.1, decimals=1)
