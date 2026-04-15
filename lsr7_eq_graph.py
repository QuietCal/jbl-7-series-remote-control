from __future__ import annotations

import cmath
import math
import re
import tkinter as tk


SAMPLE_RATE = 48000.0
EQ_RANGE_DB = 24.0
GRAPH_FREQS = tuple(20.0 * (1000.0 ** (index / 255.0)) for index in range(256))
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
_BAND_COLORS = ("#6aa3ff", "#7ac7c4", "#f3a65a", "#e58ac8", "#a6d854", "#ffd166", "#9d84ff", "#ff8c69")
_BLOCK_COLORS = {
    "UserEQ": "#0B84A5",
    "SpeakerEQ_Lo": "#7F3C8D",
    "SpeakerEQ_Hi": "#11A579",
    "RoomEQ": "#E76F51",
    "BassMgmtXover": "#C17C00",
}


def get_block_color(block_name: str) -> str:
    return _BLOCK_COLORS.get(block_name, "#0B4F6C")


def draw_eq_canvas(canvas: tk.Canvas, values: dict[str, str], graph_mode: str | None, block_name: str | None = None) -> None:
    canvas.delete("all")
    width = max(canvas.winfo_width(), 560)
    height = max(canvas.winfo_height(), 250)
    plot = _plot_geometry(width, height)
    native_color = _BLOCK_COLORS.get(block_name or "", "#0B4F6C")
    if graph_mode == "peq":
        filters, enabled = extract_eq_filters(values)
        if not filters:
            _draw_background(canvas, width, height, enabled)
            canvas.create_text(width / 2, height / 2, text="No EQ bands available yet.", fill="#666666")
            canvas._lsr7_graph_state = None
            return
        _draw_grid(canvas, plot)
        total = [0.0 for _ in GRAPH_FREQS]
        for band_index, band in enumerate(filters):
            if not band["enabled"]:
                continue
            response = band_response_db(band, GRAPH_FREQS)
            total = [left + right for left, right in zip(total, response)]
            _draw_curve(canvas, plot, response, _BAND_COLORS[band_index % len(_BAND_COLORS)], width_px=1, stipple="gray25")
        _draw_curve(canvas, plot, total, native_color, width_px=3)
        canvas.create_text(plot["left"], 6, anchor="nw", text=f"Approximate magnitude response ({'Enabled' if enabled else 'Block Off'})", fill="#333333", font=("Segoe UI", 9, "bold"))
        canvas._lsr7_graph_state = {
            "plot": plot,
            "series": [{"label": block_name or "Response", "color": native_color, "response": total}],
            "title": block_name or "Response",
        }
        return
    if graph_mode == "crossover":
        response, enabled, description = extract_crossover_response(values, GRAPH_FREQS)
        _draw_grid(canvas, plot)
        _draw_curve(canvas, plot, response, native_color, width_px=3)
        canvas.create_text(plot["left"], 6, anchor="nw", text=f"Bass management crossover ({'Enabled' if enabled else 'Block Off'})", fill="#333333", font=("Segoe UI", 9, "bold"))
        canvas.create_text(plot["left"], 22, anchor="nw", text=description, fill="#666666", font=("Segoe UI", 8))
        canvas._lsr7_graph_state = {
            "plot": plot,
            "series": [{"label": block_name or "BassMgmtXover", "color": native_color, "response": response}],
            "title": block_name or "BassMgmtXover",
        }
        return
    _draw_background(canvas, width, height, True)
    canvas.create_text(width / 2, height / 2, text="No graph available for this tab.", fill="#666666")
    canvas._lsr7_graph_state = None


def draw_combined_eq_canvas(canvas: tk.Canvas, blocks: dict[str, dict[str, str]], visibility: dict[str, bool]) -> None:
    canvas.delete("all")
    width = max(canvas.winfo_width(), 700)
    height = max(canvas.winfo_height(), 300)
    plot = _plot_geometry(width, height)
    _draw_grid(canvas, plot)

    total = [0.0 for _ in GRAPH_FREQS]
    legend_x = plot["left"]
    legend_y = 6
    visible_count = 0
    hover_series: list[dict] = []

    for block_name, values in blocks.items():
        if not visibility.get(block_name, True):
            continue
        visible_count += 1
        if block_name == "BassMgmtXover":
            response, _, description = extract_crossover_response(values, GRAPH_FREQS)
        else:
            filters, enabled = extract_eq_filters(values)
            if not enabled:
                response = [0.0 for _ in GRAPH_FREQS]
                description = "Block Off"
            else:
                response = [0.0 for _ in GRAPH_FREQS]
                for band in filters:
                    if band["enabled"]:
                        contribution = band_response_db(band, GRAPH_FREQS)
                        response = [left + right for left, right in zip(response, contribution)]
                description = "EQ"
        total = [left + right for left, right in zip(total, response)]
        color = _BLOCK_COLORS.get(block_name, "#555555")
        _draw_curve(canvas, plot, response, color, width_px=2)
        hover_series.append({"label": block_name, "color": color, "response": response})
        canvas.create_rectangle(legend_x, legend_y + 2, legend_x + 12, legend_y + 14, fill=color, outline="")
        canvas.create_text(legend_x + 18, legend_y + 8, anchor="w", text=f"{block_name} ({description})", fill="#444444", font=("Segoe UI", 8))
        legend_y += 18

    if visible_count > 1:
        _draw_curve(canvas, plot, total, "#111111", width_px=3)
        hover_series.append({"label": "Total combined response", "color": "#111111", "response": total})
        canvas.create_rectangle(legend_x, legend_y + 2, legend_x + 12, legend_y + 14, fill="#111111", outline="")
        canvas.create_text(legend_x + 18, legend_y + 8, anchor="w", text="Total combined response", fill="#111111", font=("Segoe UI", 9, "bold"))
    canvas._lsr7_graph_state = {"plot": plot, "series": hover_series, "title": "Combined EQ"}


def update_hover(canvas: tk.Canvas, x: float, y: float) -> None:
    state = getattr(canvas, "_lsr7_graph_state", None)
    canvas.delete("hover")
    if not state:
        return
    plot = state["plot"]
    left = plot["left"]
    right = left + plot["plot_width"]
    top = plot["top"]
    bottom = top + plot["plot_height"]
    if x < left or x > right or y < top or y > bottom:
        return
    index = min(max(int(round(((x - left) / plot["plot_width"]) * (len(GRAPH_FREQS) - 1))), 0), len(GRAPH_FREQS) - 1)
    freq = GRAPH_FREQS[index]
    cursor_x = _freq_to_x(freq, left, plot["plot_width"])
    canvas.create_line(cursor_x, top, cursor_x, bottom, fill="#888888", dash=(3, 3), tags="hover")
    lines = [_format_frequency(freq)]
    for series in state["series"]:
        value = series["response"][index]
        lines.append(f"{series['label']}: {value:+.2f} dB")
    box_width = 190
    box_height = 18 * len(lines) + 8
    box_x = cursor_x + 12
    if box_x + box_width > plot["width"] - 8:
        box_x = cursor_x - box_width - 12
    box_y = top + 8
    canvas.create_rectangle(box_x, box_y, box_x + box_width, box_y + box_height, fill="#fffdf2", outline="#bbbbbb", tags="hover")
    for offset, line in enumerate(lines):
        color = "#333333" if offset == 0 else state["series"][offset - 1]["color"]
        canvas.create_text(box_x + 8, box_y + 6 + offset * 18, anchor="nw", text=line, fill=color, font=("Segoe UI", 8, "bold" if offset == 0 else "normal"), tags="hover")


def clear_hover(canvas: tk.Canvas) -> None:
    canvas.delete("hover")


def extract_eq_filters(values: dict[str, str]) -> tuple[list[dict], bool]:
    overall_enable = _canonical_on_off(values.get("Enable", "On")) == "On"
    band_numbers = sorted(
        {
            int(match.group(1))
            for key in values
            for match in [re.search(r"Band (\d+) Frequency", key)]
            if match
        }
    )
    filters: list[dict] = []
    for band_number in band_numbers:
        freq = _parse_frequency(values.get(f"Band {band_number} Frequency", ""))
        gain = _parse_number(values.get(f"Band {band_number} Gain", ""))
        q_value = _parse_number(values.get(f"Band {band_number} Q", "1")) or 1.0
        slope = _parse_number(values.get(f"Band {band_number} Slope", "1")) or 1.0
        filter_type = _normalize_filter_type(values.get(f"Band {band_number} Type", "Bell"))
        band_enable_value = values.get(f"Band {band_number} Enable", "On")
        band_enabled = _canonical_on_off(band_enable_value) == "On"
        if freq is None:
            continue
        filters.append(
            {
                "freq": freq,
                "gain": gain or 0.0,
                "q": max(q_value, 0.05),
                "slope": max(slope, 0.1),
                "type": filter_type,
                "enabled": band_enabled,
            }
        )
    return filters, overall_enable


def extract_crossover_response(values: dict[str, str], freqs: tuple[float, ...]) -> tuple[list[float], bool, str]:
    enabled = _canonical_on_off(values.get("Enable", "Off")) == "On"
    frequency = _parse_frequency(values.get("Frequency", "")) or 60.0
    type_text = values.get("Type", "BW 12")
    family, order = _parse_crossover_type(type_text)
    if not enabled:
        return [0.0 for _ in freqs], enabled, f"{type_text} at {frequency:.0f} Hz"
    response = [_crossover_magnitude_db(freq, frequency, family, order) for freq in freqs]
    return response, enabled, f"{type_text} at {frequency:.0f} Hz"


def band_response_db(band: dict, freqs: tuple[float, ...]) -> list[float]:
    coeffs = _biquad_coefficients(band)
    a0 = coeffs["a0"]
    b0 = coeffs["b0"] / a0
    b1 = coeffs["b1"] / a0
    b2 = coeffs["b2"] / a0
    a1 = coeffs["a1"] / a0
    a2 = coeffs["a2"] / a0
    response: list[float] = []
    for freq in freqs:
        omega = 2.0 * math.pi * freq / SAMPLE_RATE
        z1 = cmath.exp(-1j * omega)
        z2 = cmath.exp(-2j * omega)
        numerator = b0 + b1 * z1 + b2 * z2
        denominator = 1.0 + a1 * z1 + a2 * z2
        magnitude = abs(numerator / denominator)
        response.append(20.0 * math.log10(max(magnitude, 1e-9)))
    return response


def _plot_geometry(width: int, height: int) -> dict[str, int]:
    left = 54
    right = 18
    top = 18
    bottom = 28
    return {
        "width": width,
        "height": height,
        "left": left,
        "top": top,
        "plot_width": width - left - right,
        "plot_height": height - top - bottom,
    }


def _draw_background(canvas: tk.Canvas, width: int, height: int, enabled: bool) -> None:
    canvas.create_rectangle(0, 0, width, height, fill="#fbfbfc", outline="")
    if not enabled:
        canvas.create_rectangle(0, 0, width, height, fill="#f3f3f3", outline="", stipple="gray25")


def _draw_grid(canvas: tk.Canvas, plot: dict[str, int]) -> None:
    _draw_background(canvas, plot["width"], plot["height"], True)
    left = plot["left"]
    top = plot["top"]
    plot_width = plot["plot_width"]
    plot_height = plot["plot_height"]
    canvas.create_rectangle(left, top, left + plot_width, top + plot_height, outline="#d0d0d0")
    for db in (-24, -18, -12, -6, 0, 6, 12, 18, 24):
        y = _db_to_y(db, top, plot_height)
        color = "#a9a9a9" if db == 0 else "#e6e6e6"
        canvas.create_line(left, y, left + plot_width, y, fill=color)
        canvas.create_text(left - 8, y, text=f"{db:+.0f}", anchor="e", fill="#666666", font=("Segoe UI", 8))
    for freq in (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
        x = _freq_to_x(freq, left, plot_width)
        canvas.create_line(x, top, x, top + plot_height, fill="#ededed")
        label = f"{int(freq/1000)}k" if freq >= 1000 else str(int(freq))
        canvas.create_text(x, top + plot_height + 12, text=label, anchor="n", fill="#666666", font=("Segoe UI", 8))


def _draw_curve(
    canvas: tk.Canvas,
    plot: dict[str, int],
    response_db: list[float],
    color: str,
    *,
    width_px: int,
    stipple: str = "",
) -> None:
    points: list[float] = []
    for freq, db in zip(GRAPH_FREQS, response_db):
        points.extend((_freq_to_x(freq, plot["left"], plot["plot_width"]), _db_to_y(db, plot["top"], plot["plot_height"])))
    kwargs = {"fill": color, "width": width_px, "smooth": True}
    if stipple:
        kwargs["stipple"] = stipple
    canvas.create_line(*points, **kwargs)


def _freq_to_x(freq: float, left: int, plot_width: int) -> float:
    min_log = math.log10(20.0)
    max_log = math.log10(20000.0)
    return left + ((math.log10(freq) - min_log) / (max_log - min_log)) * plot_width


def _db_to_y(db: float, top: int, plot_height: int) -> float:
    clipped = max(-EQ_RANGE_DB, min(EQ_RANGE_DB, db))
    normalized = (EQ_RANGE_DB - clipped) / (EQ_RANGE_DB * 2.0)
    return top + normalized * plot_height


def _biquad_coefficients(band: dict) -> dict[str, float]:
    filter_type = band["type"]
    freq = max(10.0, min(band["freq"], SAMPLE_RATE / 2.5))
    gain = band["gain"]
    q_value = max(band["q"], 0.05)
    slope_value = max(band["slope"] / 6.0, 0.1)
    w0 = 2.0 * math.pi * freq / SAMPLE_RATE
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    a_gain = 10.0 ** (gain / 40.0)

    if filter_type == "low_shelf":
        alpha = sin_w0 / 2.0 * math.sqrt((a_gain + 1.0 / a_gain) * (1.0 / slope_value - 1.0) + 2.0)
        two_sqrt = 2.0 * math.sqrt(a_gain) * alpha
        return {
            "b0": a_gain * ((a_gain + 1.0) - (a_gain - 1.0) * cos_w0 + two_sqrt),
            "b1": 2.0 * a_gain * ((a_gain - 1.0) - (a_gain + 1.0) * cos_w0),
            "b2": a_gain * ((a_gain + 1.0) - (a_gain - 1.0) * cos_w0 - two_sqrt),
            "a0": (a_gain + 1.0) + (a_gain - 1.0) * cos_w0 + two_sqrt,
            "a1": -2.0 * ((a_gain - 1.0) + (a_gain + 1.0) * cos_w0),
            "a2": (a_gain + 1.0) + (a_gain - 1.0) * cos_w0 - two_sqrt,
        }
    if filter_type == "high_shelf":
        alpha = sin_w0 / 2.0 * math.sqrt((a_gain + 1.0 / a_gain) * (1.0 / slope_value - 1.0) + 2.0)
        two_sqrt = 2.0 * math.sqrt(a_gain) * alpha
        return {
            "b0": a_gain * ((a_gain + 1.0) + (a_gain - 1.0) * cos_w0 + two_sqrt),
            "b1": -2.0 * a_gain * ((a_gain - 1.0) + (a_gain + 1.0) * cos_w0),
            "b2": a_gain * ((a_gain + 1.0) + (a_gain - 1.0) * cos_w0 - two_sqrt),
            "a0": (a_gain + 1.0) - (a_gain - 1.0) * cos_w0 + two_sqrt,
            "a1": 2.0 * ((a_gain - 1.0) - (a_gain + 1.0) * cos_w0),
            "a2": (a_gain + 1.0) - (a_gain - 1.0) * cos_w0 - two_sqrt,
        }

    alpha = sin_w0 / (2.0 * q_value)
    return {
        "b0": 1.0 + alpha * a_gain,
        "b1": -2.0 * cos_w0,
        "b2": 1.0 - alpha * a_gain,
        "a0": 1.0 + alpha / a_gain,
        "a1": -2.0 * cos_w0,
        "a2": 1.0 - alpha / a_gain,
    }


def _parse_crossover_type(value: str) -> tuple[str, int]:
    text = value.strip().upper()
    match = re.search(r"(BW|LR)\s*(\d+)", text)
    if not match:
        return "BW", 12
    return match.group(1), int(match.group(2))


def _crossover_magnitude_db(freq: float, cutoff: float, family: str, order: int) -> float:
    ratio = max(cutoff / max(freq, 1e-6), 1e-9)
    if family == "LR":
        magnitude = 1.0 / (1.0 + ratio**order)
    else:
        magnitude = 1.0 / math.sqrt(1.0 + ratio ** (2 * order))
    return 20.0 * math.log10(max(magnitude, 1e-9))


def _normalize_filter_type(value: str) -> str:
    normalized = value.strip().lower()
    if "low" in normalized and "shelf" in normalized:
        return "low_shelf"
    if "high" in normalized and "shelf" in normalized:
        return "high_shelf"
    return "peaking"


def _parse_frequency(value: str) -> float | None:
    text = value.strip().lower()
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    numeric = float(match.group(0))
    if "khz" in text:
        return numeric * 1000.0
    return numeric


def _parse_number(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    return float(match.group(0))


def _canonical_on_off(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"on", "enable", "enabled", "engaged", "true", "1"}:
        return "On"
    if normalized in {"off", "disable", "disabled", "disengaged", "false", "0"}:
        return "Off"
    return value


def _format_frequency(freq: float) -> str:
    if freq >= 1000.0:
        return f"{freq / 1000.0:.2f} kHz"
    return f"{freq:.0f} Hz"
