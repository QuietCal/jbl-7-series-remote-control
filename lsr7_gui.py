from __future__ import annotations

import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from lsr7_catalog import COMMON_CONTROLS, FAVORITE_BRANCHES, IDENTITY_PATHS, INPUT_HINTS, OVERVIEW_PATHS, PANEL_SECTIONS, SYSTEM_INFO_PATHS, LSR7Control, LSR7InputHint, LSR7Panel
from lsr7_eq_graph import clear_hover, draw_combined_eq_canvas, draw_eq_canvas, get_block_color, update_hover
from lsr7_network import DiscoveredSpeaker, NetworkInterface, discover_speakers, list_network_interfaces
from lsr7_storage import AppConfig, TREE_CACHE_PATH, TREE_SUMMARY_PATH, load_or_create_config, load_tree_cache, save_config
from lsr7_tree_tools import tree_stats
from lsr7_ws import LSR7WebSocketClient

APP_VERSION = "1.1"
COMBINED_EQ_PANEL_KEYS = ("user_eq", "speaker_eq_lo", "speaker_eq_hi", "room_eq", "bass_mgmt_xover")
INPUT_STATE_STYLES = {
    "loaded": {"entry": "Loaded.TEntry", "combobox": "Loaded.TCombobox", "spinbox": "Loaded.TSpinbox", "scale": "Loaded.Horizontal.TScale"},
    "dirty": {"entry": "Dirty.TEntry", "combobox": "Dirty.TCombobox", "spinbox": "Dirty.TSpinbox", "scale": "Dirty.Horizontal.TScale"},
    "applied": {"entry": "Applied.TEntry", "combobox": "Applied.TCombobox", "spinbox": "Applied.TSpinbox", "scale": "Applied.Horizontal.TScale"},
}
INPUT_STATE_COLORS = {
    "light": {
        "loaded": {"fg": "#1f6f43", "field": "#e9f7ee", "dot": "#2e8b57"},
        "dirty": {"fg": "#9a5b00", "field": "#fff3df", "dot": "#d98b00"},
        "applied": {"fg": "#0b4f9c", "field": "#e4f0ff", "dot": "#2f6fdd"},
    },
    "dark": {
        "loaded": {"fg": "#f7fff9", "field": "#416b54", "dot": "#92d4af"},
        "dirty": {"fg": "#fff8ec", "field": "#7a5722", "dot": "#efb85d"},
        "applied": {"fg": "#f3f8ff", "field": "#466892", "dot": "#88b6ff"},
    },
}
SOURCE_STATE_COLORS = {
    "fresh": "#2e8b57",
    "cached": "#d1a300",
    "error": "#c62828",
    "idle": "#9aa0a6",
}
THEME_PALETTES = {
    "light": {
        "root_bg": "#f0f0f0",
        "panel_bg": "#ffffff",
        "text": "#000000",
        "muted": "#555555",
        "accent": "#0B4F6C",
        "border": "#b8b8b8",
        "field_bg": "#ffffff",
        "field_fg": "#000000",
        "arrow_fg": "#000000",
        "button_bg": "#f0f0f0",
        "button_fg": "#000000",
        "selected_bg": "#cfe8ff",
        "selected_fg": "#000000",
        "tab_bg": "#f0f0f0",
        "tab_selected_bg": "#ffffff",
        "canvas_bg": "#fbfbfc",
        "text_bg": "#ffffff",
        "text_fg": "#000000",
        "insert_bg": "#000000",
    },
    "dark": {
        "root_bg": "#15191f",
        "panel_bg": "#1d232c",
        "text": "#e8edf3",
        "muted": "#a8b4c3",
        "accent": "#7fd0ff",
        "border": "#3a4655",
        "field_bg": "#222a35",
        "field_fg": "#f4f7fb",
        "arrow_fg": "#f4f7fb",
        "button_bg": "#2a3442",
        "button_fg": "#f4f7fb",
        "selected_bg": "#164e63",
        "selected_fg": "#f4f7fb",
        "tab_bg": "#222a35",
        "tab_selected_bg": "#2d3746",
        "canvas_bg": "#161d26",
        "text_bg": "#161d26",
        "text_fg": "#e8edf3",
        "insert_bg": "#f4f7fb",
    },
}
STATE_STYLE_PALETTES = {
    "light": {
        "loaded": {"fg": "#1f6f43", "field": "#e9f7ee", "border": "#7cc596", "trough": "#d7efdf"},
        "dirty": {"fg": "#9a5b00", "field": "#fff3df", "border": "#f0ad4e", "trough": "#ffe1b3"},
        "applied": {"fg": "#0b4f9c", "field": "#e4f0ff", "border": "#6ea8fe", "trough": "#d2e3ff"},
    },
    "dark": {
        "loaded": {"fg": "#f7fff9", "field": "#416b54", "border": "#92d4af", "trough": "#4f7a61"},
        "dirty": {"fg": "#fff8ec", "field": "#7a5722", "border": "#efb85d", "trough": "#8a662d"},
        "applied": {"fg": "#f3f8ff", "field": "#466892", "border": "#88b6ff", "trough": "#5579a6"},
    },
}
ROLE_FOREGROUND_MAP = {
    "#0B4F6C": "accent",
    "#666666": "muted",
    "#555555": "muted",
    "#444444": "muted",
}
ENUM_DISPLAY_LABELS = {
    "\\\\this\\Node\\InputMixer\\SV\\InputSensitivity": {
        "Plus4": "+4dBu",
        "Minus10": "-10dBV",
    },
}


class LSR7ControllerApp:
    def __init__(self) -> None:
        self.config = load_or_create_config()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.protocol_queue: queue.Queue[str] = queue.Queue()
        self.latest_tree: dict[str, dict] = {}
        self.path_to_tree_id: dict[str, str] = {}
        self.current_branch_path = "\\\\this\\Node"
        self.interfaces: list[NetworkInterface] = []
        self.interface_map: dict[str, NetworkInterface] = {}
        self.discovered_speakers: list[DiscoveredSpeaker] = []
        self.discovered_speaker_map: dict[str, DiscoveredSpeaker] = {}
        self.panel_value_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.panel_source_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.panel_input_vars: dict[str, dict[str, tk.StringVar]] = {}
        self.panel_input_hints: dict[str, dict[str, LSR7InputHint | None]] = {}
        self.panel_graph_canvases: dict[str, tk.Canvas] = {}
        self.combined_graph_canvas: tk.Canvas | None = None
        self.combined_visibility_vars: dict[str, tk.BooleanVar] = {}
        self.control_inputs: dict[str, tk.StringVar] = {}
        self.control_current_text: dict[str, tk.StringVar] = {}
        self.control_scale_vars: dict[str, tk.DoubleVar] = {}
        self.control_input_widgets: dict[str, tk.Widget] = {}
        self.control_input_markers: dict[str, ttk.Label] = {}
        self.control_apply_buttons: dict[str, ttk.Button] = {}
        self.control_undo_buttons: dict[str, ttk.Button] = {}
        self.control_input_baselines: dict[str, str] = {}
        self.control_input_last_seen: dict[str, str] = {}
        self.control_input_states: dict[str, str] = {}
        self.panel_input_widgets: dict[str, dict[str, tk.Widget]] = {}
        self.panel_input_markers: dict[str, dict[str, ttk.Label]] = {}
        self.panel_apply_buttons: dict[str, dict[str, ttk.Button]] = {}
        self.panel_undo_buttons: dict[str, dict[str, ttk.Button]] = {}
        self.panel_input_baselines: dict[str, dict[str, str]] = {}
        self.panel_input_last_seen: dict[str, dict[str, str]] = {}
        self.panel_input_states: dict[str, dict[str, str]] = {}
        self.color_chip_canvases: list[tk.Canvas] = []
        self.instant_update_jobs: dict[str, str] = {}
        self.instant_update_flash_job: str | None = None
        self.status_blink_job: str | None = None
        self.status_blink_visible = True
        self._instant_restore_confirm_writes = bool(self.config.confirm_writes)
        self._instant_restore_auto_refresh = bool(self.config.auto_refresh_after_write)
        self._suspend_dirty_tracking = False
        self._suspend_history_tracking = False
        self.undo_history: list[dict[str, str]] = []
        self.redo_history: list[dict[str, str]] = []
        self.slider_targets: set[str] = set()
        self.slider_drag_start_values: dict[str, str] = {}

        self.root = tk.Tk()
        self.root.title(f"JBL 7 Series Speaker Controller v{APP_VERSION}")
        self.root.geometry("1560x980")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.style = ttk.Style(self.root)
        self.default_theme_name = self.style.theme_use()

        self.host_var = tk.StringVar(value=self.config.speaker_host)
        self.theme_mode = self.config.theme_mode if self.config.theme_mode in THEME_PALETTES else "light"
        self.theme_button_var = tk.StringVar()
        self.interface_var = tk.StringVar(value=self.config.network_interface)
        self.discovered_speaker_var = tk.StringVar(value="")
        self.snapshot_root_var = tk.StringVar(value=self.config.snapshot_root)
        self.branch_root_var = tk.StringVar(value="\\\\this\\Node")
        self.status_var = tk.StringVar(value="Idle")
        self.status_detail_var = tk.StringVar(value="No operations yet.")
        self.confirm_writes_var = tk.BooleanVar(value=self.config.confirm_writes)
        self.auto_refresh_var = tk.BooleanVar(value=self.config.auto_refresh_after_write)
        self.instant_update_var = tk.BooleanVar(value=self.config.instant_update)
        self.debug_protocol_var = tk.BooleanVar(value=self.config.debug_protocol)
        self.protocol_notes_var = tk.StringVar(value=self.config.notes)

        self.identity_vars = {label: tk.StringVar(value="") for label in IDENTITY_PATHS}
        self.overview_vars = {label: tk.StringVar(value="") for label in OVERVIEW_PATHS}
        self.overview_source_vars = {label: tk.StringVar(value="") for label in OVERVIEW_PATHS}
        self.system_info_vars = {label: tk.StringVar(value="") for label in SYSTEM_INFO_PATHS}
        self.system_info_source_vars = {label: tk.StringVar(value="") for label in SYSTEM_INFO_PATHS}
        self.overview_source_labels: dict[str, ttk.Label] = {}
        self.system_info_source_labels: dict[str, ttk.Label] = {}
        self.panel_source_labels: dict[str, dict[str, ttk.Label]] = {}

        self.selected_path_var = tk.StringVar(value="No node selected")
        self.path_value_text_var = tk.StringVar(value="")
        self.path_value_percent_var = tk.StringVar(value="")
        self.path_value_float_var = tk.StringVar(value="")
        self.path_min_var = tk.StringVar(value="")
        self.path_max_var = tk.StringVar(value="")
        self.path_type_var = tk.StringVar(value="")
        self.path_enabled_var = tk.StringVar(value="")
        self.path_sensor_var = tk.StringVar(value="")
        self.write_text_var = tk.StringVar(value="")
        self.write_percent_var = tk.StringVar(value="")
        self.explorer_status_var = tk.StringVar(value="Explorer idle")
        self.top_level_status_var = tk.StringVar(value="Top-level branches not loaded")
        self.tree_cache_stats_var = tk.StringVar(value="No cached tree loaded")
        self.debug_summary_var = tk.StringVar(value="Protocol trace off")
        self.protocol_event_count = 0
        self._auto_refresh_inflight = False

        self._configure_styles()
        self._build_ui()
        self._apply_theme(self.theme_mode)
        self._bind_shortcuts()
        self._load_interfaces()
        cached = load_tree_cache()
        if cached and isinstance(cached.get("tree"), dict):
            self._populate_tree(cached["tree"], self.current_branch_path)
            self._load_cached_panels(cached)
            self._update_tree_cache_stats(cached["tree"], source=f"startup cache {cached.get('host', '?')}")
            self._load_top_level_branches(cached)
        self._poll_logs()

    def _panel_by_key(self, key: str) -> LSR7Panel:
        return next(panel for panel in PANEL_SECTIONS if panel.key == key)

    def _build_color_chip(self, parent, color: str, *, size: int = 12):
        try:
            background = parent.cget("background")
        except tk.TclError:
            background = self.root.tk.call("ttk::style", "lookup", "TFrame", "-background") or "#f0f0f0"
        chip = tk.Canvas(parent, width=size, height=size, highlightthickness=0, background=background)
        chip.create_rectangle(1, 1, size - 1, size - 1, fill=color, outline="")
        self.color_chip_canvases.append(chip)
        return chip

    def _input_state_colors(self, state: str) -> dict[str, str]:
        return INPUT_STATE_COLORS[self.theme_mode][state]

    def _configure_styles(self) -> None:
        theme = THEME_PALETTES[self.theme_mode]
        palette = STATE_STYLE_PALETTES[self.theme_mode]
        self.style.theme_use("clam" if self.theme_mode == "dark" else self.default_theme_name)
        self.style.configure(".", background=theme["root_bg"], foreground=theme["text"])
        self.style.configure("TFrame", background=theme["root_bg"])
        self.style.configure("TLabel", background=theme["root_bg"], foreground=theme["text"])
        self.style.configure("TLabelframe", background=theme["panel_bg"], bordercolor=theme["border"], relief="solid")
        self.style.configure("TLabelframe.Label", background=theme["panel_bg"], foreground=theme["text"])
        self.style.configure("TButton", background=theme["button_bg"], foreground=theme["button_fg"], bordercolor=theme["border"], focuscolor=theme["selected_bg"])
        self.style.map("TButton", background=[("active", theme["selected_bg"])], foreground=[("active", theme["button_fg"])])
        self.style.configure("TCheckbutton", background=theme["root_bg"], foreground=theme["text"])
        self.style.map("TCheckbutton", background=[("active", theme["root_bg"])], foreground=[("active", theme["text"])])
        self.style.configure("TEntry", fieldbackground=theme["field_bg"], foreground=theme["field_fg"], bordercolor=theme["border"])
        self.style.configure("TCombobox", fieldbackground=theme["field_bg"], foreground=theme["field_fg"], bordercolor=theme["border"], arrowsize=14, arrowcolor=theme["arrow_fg"])
        self.style.map("TCombobox", fieldbackground=[("readonly", theme["field_bg"]), ("!disabled", theme["field_bg"])], foreground=[("readonly", theme["field_fg"]), ("!disabled", theme["field_fg"])])
        self.style.configure("TSpinbox", fieldbackground=theme["field_bg"], foreground=theme["field_fg"], bordercolor=theme["border"], arrowcolor=theme["arrow_fg"])
        self.style.configure("Horizontal.TScrollbar", background=theme["button_bg"], troughcolor=theme["panel_bg"], bordercolor=theme["border"])
        self.style.configure("Vertical.TScrollbar", background=theme["button_bg"], troughcolor=theme["panel_bg"], bordercolor=theme["border"])
        self.style.configure("Treeview", background=theme["field_bg"], fieldbackground=theme["field_bg"], foreground=theme["field_fg"], bordercolor=theme["border"])
        self.style.map("Treeview", background=[("selected", theme["selected_bg"])], foreground=[("selected", theme["selected_fg"])])
        self.style.configure("Treeview.Heading", background=theme["button_bg"], foreground=theme["text"], bordercolor=theme["border"])
        self.style.configure("TNotebook", background=theme["root_bg"], bordercolor=theme["border"])
        self.style.configure("TNotebook.Tab", background=theme["tab_bg"], foreground=theme["text"], bordercolor=theme["border"], padding=(8, 4))
        self.style.map("TNotebook.Tab", background=[("selected", theme["tab_selected_bg"])], foreground=[("selected", theme["text"])])
        self.style.configure("TPanedwindow", background=theme["root_bg"])
        for state, colors in palette.items():
            self.style.configure(INPUT_STATE_STYLES[state]["entry"], foreground=colors["fg"], fieldbackground=colors["field"], bordercolor=colors["border"])
            self.style.configure(INPUT_STATE_STYLES[state]["combobox"], foreground=colors["fg"], fieldbackground=colors["field"], bordercolor=colors["border"], arrowsize=14, arrowcolor=theme["arrow_fg"])
            self.style.map(
                INPUT_STATE_STYLES[state]["combobox"],
                fieldbackground=[
                    ("readonly", colors["field"]),
                    ("focus", colors["field"]),
                    ("!disabled", colors["field"]),
                ],
                foreground=[
                    ("readonly", colors["fg"]),
                    ("focus", colors["fg"]),
                    ("!disabled", colors["fg"]),
                ],
            )
            self.style.configure(INPUT_STATE_STYLES[state]["spinbox"], foreground=colors["fg"], fieldbackground=colors["field"], bordercolor=colors["border"], arrowsize=12, arrowcolor=theme["arrow_fg"])
            self.style.configure(INPUT_STATE_STYLES[state]["scale"], troughcolor=colors["trough"], background=colors["border"])
        self.style.configure("Pending.TButton", foreground=palette["dirty"]["fg"], bordercolor=palette["dirty"]["border"])
        self.style.map(
            "Pending.TButton",
            foreground=[("!disabled", palette["dirty"]["fg"])],
            background=[("!disabled", palette["dirty"]["field"])],
        )
        self.style.configure("Instant.TCheckbutton", background=theme["root_bg"], foreground=theme["text"])
        self.style.map(
            "Instant.TCheckbutton",
            background=[("selected", theme["root_bg"]), ("active", theme["root_bg"])],
            foreground=[("selected", theme["text"]), ("active", theme["text"])],
        )
        self.style.configure("InstantFlash.TCheckbutton", background=theme["root_bg"], foreground=theme["accent"])
        self.style.map(
            "InstantFlash.TCheckbutton",
            background=[("selected", theme["root_bg"]), ("active", theme["root_bg"])],
            foreground=[("selected", theme["accent"]), ("active", theme["accent"])],
        )

    def _apply_theme(self, theme_mode: str) -> None:
        self.theme_mode = theme_mode if theme_mode in THEME_PALETTES else "light"
        palette = THEME_PALETTES[self.theme_mode]
        self.theme_button_var.set("Light Theme" if self.theme_mode == "dark" else "Dark Theme")
        self._configure_styles()
        self.root.configure(background=palette["root_bg"])
        self._apply_theme_to_widget(self.root)
        for canvas in self.panel_graph_canvases.values():
            canvas.configure(background=palette["canvas_bg"])
        if self.combined_graph_canvas:
            self.combined_graph_canvas.configure(background=palette["canvas_bg"])
        for canvas in self.color_chip_canvases:
            try:
                canvas.configure(background=palette["panel_bg"])
            except tk.TclError:
                pass
        try:
            self.log_text.configure(background=palette["text_bg"], foreground=palette["text_fg"], insertbackground=palette["insert_bg"], selectbackground=palette["selected_bg"], selectforeground=palette["selected_fg"])
            self.protocol_text.configure(background=palette["text_bg"], foreground=palette["text_fg"], insertbackground=palette["insert_bg"], selectbackground=palette["selected_bg"], selectforeground=palette["selected_fg"])
            self.favorites_list.configure(background=palette["field_bg"], foreground=palette["field_fg"], selectbackground=palette["selected_bg"], selectforeground=palette["selected_fg"], highlightbackground=palette["border"], highlightcolor=palette["border"])
        except AttributeError:
            pass
        for panel_key in list(self.panel_graph_canvases):
            self._redraw_panel_graph(panel_key)
        if self.combined_graph_canvas:
            self._redraw_combined_graph()
        if getattr(self, "instant_update_var", None) and self.instant_update_var.get():
            self._flash_instant_update_indicator()
        elif getattr(self, "instant_update_check", None):
            try:
                self.instant_update_check.configure(style="Instant.TCheckbutton")
            except tk.TclError:
                pass

    def _apply_theme_to_widget(self, widget) -> None:
        palette = THEME_PALETTES[self.theme_mode]
        try:
            klass = widget.winfo_class()
        except tk.TclError:
            return
        try:
            foreground = str(widget.cget("foreground"))
        except tk.TclError:
            foreground = ""
        if klass in {"Frame", "Labelframe", "TFrame", "TLabelframe"}:
            try:
                widget.configure(background=palette["panel_bg"] if klass in {"Labelframe", "TLabelframe"} else palette["root_bg"])
            except tk.TclError:
                pass
        elif klass in {"Label", "TLabel"}:
            role = ROLE_FOREGROUND_MAP.get(foreground)
            try:
                widget.configure(background=palette["root_bg"], foreground=palette[role] if role else palette["text"])
            except tk.TclError:
                pass
        elif klass in {"TCheckbutton", "Checkbutton"}:
            role = ROLE_FOREGROUND_MAP.get(foreground)
            try:
                widget.configure(background=palette["root_bg"], foreground=palette[role] if role else palette["text"])
            except tk.TclError:
                pass
        elif klass == "Text":
            widget.configure(background=palette["text_bg"], foreground=palette["text_fg"], insertbackground=palette["insert_bg"], selectbackground=palette["selected_bg"], selectforeground=palette["selected_fg"])
        elif klass == "Listbox":
            widget.configure(background=palette["field_bg"], foreground=palette["field_fg"], selectbackground=palette["selected_bg"], selectforeground=palette["selected_fg"])
        elif klass == "Canvas":
            widget.configure(background=palette["panel_bg"], highlightbackground=palette["border"])
        for child in widget.winfo_children():
            self._apply_theme_to_widget(child)

    def _toggle_theme(self) -> None:
        self._apply_theme("dark" if self.theme_mode == "light" else "light")
        self._save_runtime_config()

    def _set_source_indicator(self, label_widget: ttk.Label, variable: tk.StringVar, state: str) -> None:
        variable.set("●")
        label_widget.configure(foreground=SOURCE_STATE_COLORS[state])

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(9, weight=1)

        ttk.Label(top, text="Speaker IP").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.host_var, width=18).grid(row=0, column=1, sticky="w", padx=(6, 12))
        ttk.Button(top, textvariable=self.theme_button_var, command=self._toggle_theme).grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(8, 0))
        ttk.Button(top, text="Refresh Speaker", command=self.refresh_overview).grid(row=0, column=2, sticky="w")
        ttk.Label(top, text="Interface").grid(row=0, column=3, sticky="w", padx=(18, 0))
        self.interface_combo = ttk.Combobox(top, textvariable=self.interface_var, state="readonly", width=30)
        self.interface_combo.grid(row=0, column=4, sticky="w", padx=(6, 8))
        self.interface_combo.bind("<<ComboboxSelected>>", self._on_interface_selected)
        ttk.Button(top, text="Discover Speakers", command=self.discover_speakers_on_interface).grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Label(top, text="Discovered").grid(row=1, column=3, sticky="w", padx=(18, 0), pady=(8, 0))
        self.discovered_combo = ttk.Combobox(top, textvariable=self.discovered_speaker_var, state="readonly", width=24)
        self.discovered_combo.grid(row=1, column=4, sticky="w", padx=(6, 12), pady=(8, 0))
        self.discovered_combo.bind("<<ComboboxSelected>>", self._on_discovered_speaker_selected)
        status_frame = ttk.LabelFrame(top, text="Status", padding=(10, 6))
        status_frame.grid(row=0, column=7, rowspan=2, columnspan=3, sticky="nsew", padx=(12, 0))
        status_frame.columnconfigure(0, weight=1)
        self.status_summary_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            foreground="#0B4F6C",
            font=("Segoe UI", 10, "bold"),
            wraplength=980,
            justify="left",
        )
        self.status_summary_label.grid(row=0, column=0, sticky="w")
        ttk.Label(
            status_frame,
            textvariable=self.status_detail_var,
            foreground="#666666",
            wraplength=980,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        write_options = ttk.Frame(top)
        write_options.grid(row=2, column=7, columnspan=3, sticky="e", pady=(8, 0))
        self.confirm_writes_check = ttk.Checkbutton(write_options, text="Confirm writes", variable=self.confirm_writes_var)
        self.confirm_writes_check.grid(row=0, column=0, sticky="w")
        self.auto_refresh_check = ttk.Checkbutton(write_options, text="Refresh after write", variable=self.auto_refresh_var)
        self.auto_refresh_check.grid(row=0, column=1, sticky="w", padx=(14, 0))
        self.instant_update_check = ttk.Checkbutton(
            write_options,
            text="Instant-Update",
            variable=self.instant_update_var,
            style="Instant.TCheckbutton",
            command=self._on_instant_update_toggle,
        )
        self.instant_update_check.grid(row=0, column=2, sticky="w", padx=(14, 0))
        self._sync_instant_update_controls()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.overview_tab = ttk.Frame(self.notebook, padding=10)
        self.user_eq_tab = ttk.Frame(self.notebook, padding=10)
        self.bass_mgmt_tab = ttk.Frame(self.notebook, padding=10)
        self.speaker_eq_lo_tab = ttk.Frame(self.notebook, padding=10)
        self.speaker_eq_hi_tab = ttk.Frame(self.notebook, padding=10)
        self.room_eq_tab = ttk.Frame(self.notebook, padding=10)
        self.room_delay_tab = ttk.Frame(self.notebook, padding=10)
        self.speaker_trim_tab = ttk.Frame(self.notebook, padding=10)
        self.meters_tab = ttk.Frame(self.notebook, padding=10)
        self.combined_eq_tab = ttk.Frame(self.notebook, padding=10)
        self.explorer_tab = ttk.Frame(self.notebook, padding=10)
        self.diagnostics_tab = ttk.Frame(self.notebook, padding=10)

        for tab, label in [
            (self.overview_tab, "Overview"),
            (self.room_delay_tab, "Delay"),
            (self.speaker_trim_tab, "SpeakerTrim"),
            (self.speaker_eq_lo_tab, "SpeakerEQ_Lo"),
            (self.speaker_eq_hi_tab, "SpeakerEQ_Hi"),
            (self.bass_mgmt_tab, "BassMgmtXover"),
            (self.room_eq_tab, "RoomEQ"),
            (self.user_eq_tab, "UserEQ"),
            (self.combined_eq_tab, "Combined EQ"),
            (self.meters_tab, "Meters"),
            (self.explorer_tab, "Live Browser"),
            (self.diagnostics_tab, "Diagnostics"),
        ]:
            self.notebook.add(tab, text=label)

        self._build_overview_tab(self.overview_tab)
        self._build_panel_tab(self.user_eq_tab, "user_eq")
        self._build_panel_tab(self.bass_mgmt_tab, "bass_mgmt_xover")
        self._build_panel_tab(self.speaker_eq_lo_tab, "speaker_eq_lo")
        self._build_panel_tab(self.speaker_eq_hi_tab, "speaker_eq_hi")
        self._build_panel_tab(self.room_eq_tab, "room_eq")
        self._build_panel_tab(self.room_delay_tab, "room_delay")
        self._build_panel_tab(self.speaker_trim_tab, "speaker_trim")
        self._build_panel_tab(self.meters_tab, "meters")
        self._build_combined_eq_tab(self.combined_eq_tab)
        self._build_explorer_tab(self.explorer_tab)
        self._build_diagnostics_tab(self.diagnostics_tab)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _build_overview_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=2)
        parent.columnconfigure(1, weight=3)
        parent.columnconfigure(2, weight=3)
        identity = ttk.LabelFrame(parent, text="Speaker Identity", padding=10)
        identity.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        identity.columnconfigure(1, weight=1)
        for row, label in enumerate(IDENTITY_PATHS):
            ttk.Label(identity, text=label).grid(row=row, column=0, sticky="w", pady=(0, 6))
            ttk.Entry(identity, textvariable=self.identity_vars[label], state="readonly").grid(row=row, column=1, sticky="ew", pady=(0, 6))
        ttk.Button(identity, text="Probe Identity", command=self.probe_speaker).grid(row=len(IDENTITY_PATHS), column=0, pady=(8, 0), sticky="w")

        status = ttk.LabelFrame(parent, text="Current Speaker State", padding=10)
        status.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
        status.columnconfigure(1, weight=1)
        for row, label in enumerate(OVERVIEW_PATHS):
            ttk.Label(status, text=label).grid(row=row, column=0, sticky="w", pady=(0, 6))
            ttk.Entry(status, textvariable=self.overview_vars[label], state="readonly").grid(row=row, column=1, sticky="ew", pady=(0, 6))
            source_label = ttk.Label(status, textvariable=self.overview_source_vars[label], foreground=SOURCE_STATE_COLORS["idle"])
            source_label.grid(row=row, column=2, sticky="w", padx=(8, 0))
            self.overview_source_labels[label] = source_label
        ttk.Button(status, text="Refresh State", command=self.refresh_overview).grid(row=len(OVERVIEW_PATHS), column=0, pady=(8, 0), sticky="w")

        quick = ttk.LabelFrame(parent, text="Quick Actions", padding=10)
        quick.grid(row=0, column=2, sticky="nsew", padx=(8, 0), pady=(0, 8))
        self._build_quick_controls_grid(quick, compact=True)

    def _build_quick_controls_grid(self, parent: ttk.Frame, *, compact: bool = False) -> None:
        action_button_width = 7
        undo_button_width = 7
        apply_all_button_width = 10
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=1)
        parent.columnconfigure(3, weight=1)
        ttk.Label(parent, text="Control").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="Current").grid(row=0, column=1, sticky="w")
        ttk.Label(parent, text="New Value").grid(row=0, column=2, sticky="w")
        ttk.Label(parent, text="Action").grid(row=0, column=3, sticky="w")
        ttk.Button(parent, text="Apply All", width=apply_all_button_width, command=self.apply_all_quick_controls).grid(row=1, column=3, sticky="w", pady=(6, 6))

        for row, control in enumerate(COMMON_CONTROLS, start=2):
            current_text_var = tk.StringVar(value="")
            input_var = tk.StringVar(value="")
            self.control_current_text[control.key] = current_text_var
            self.control_inputs[control.key] = input_var
            hint = self._input_hint_for_path(control.path)

            ttk.Label(parent, text=control.label).grid(row=row, column=0, sticky="nw", pady=(6, 0))
            ttk.Label(parent, textvariable=current_text_var, width=20, anchor="w").grid(row=row, column=1, sticky="w", pady=(6, 0))
            input_wrap = ttk.Frame(parent)
            input_wrap.columnconfigure(1, weight=1)
            marker = ttk.Label(input_wrap, text="●", foreground=self._input_state_colors("loaded")["dot"])
            marker.grid(row=0, column=0, sticky="nw", padx=(0, 6))
            input_widget = self._build_input_widget(input_wrap, row, 2, input_var, hint, path=control.path, target=("control", control.key))
            input_widget.grid(row=0, column=1, sticky="ew")
            input_wrap.grid(row=row, column=2, sticky="ew", padx=(8, 8), pady=(6, 0))
            self.control_input_widgets[control.key] = input_wrap
            self.control_input_markers[control.key] = marker
            self._bind_input_tracking(input_var, lambda _name="", _index="", _mode="", key=control.key: self._on_control_input_changed(key))
            self._bind_widget_dirty_events(input_wrap, lambda _event=None, key=control.key: self._on_control_input_changed(key))
            self._set_control_input_state(control.key, "loaded")
            action_wrap = ttk.Frame(parent)
            action_wrap.grid(row=row, column=3, sticky="w", pady=(6, 0))
            apply_button = ttk.Button(action_wrap, text="Apply", width=action_button_width, command=lambda selected=control: self.write_common_control(selected))
            apply_button.grid(row=0, column=0, sticky="w")
            undo_button = ttk.Button(action_wrap, text="Undo", width=undo_button_width, command=lambda selected_key=control.key: self.undo_target(selected_key))
            undo_button.grid(row=0, column=1, sticky="w", padx=(6, 0))
            self.control_apply_buttons[control.key] = apply_button
            self.control_undo_buttons[control.key] = undo_button
            self._refresh_target_undo_button(("control", control.key))
            if not compact:
                ttk.Label(parent, text=control.description, wraplength=1160, justify="left", foreground="#555555").grid(row=row + 1, column=0, columnspan=4, sticky="w", pady=(0, 2))
        footer_row = len(COMMON_CONTROLS) + 2
        ttk.Button(parent, text="Refresh Quick Actions", command=self.refresh_common_controls).grid(row=footer_row, column=0, sticky="w", pady=(10, 0))

    def _build_panel_tab(self, parent: ttk.Frame, panel_key: str) -> None:
        panel = self._panel_by_key(panel_key)
        action_button_width = 7
        undo_button_width = 7
        apply_all_button_width = 10
        parent.columnconfigure(0, weight=1)
        has_graph = bool(panel.graph_mode)
        parent.rowconfigure(2 if has_graph else 1, weight=1)
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(1, weight=1)
        title_wrap = ttk.Frame(header)
        title_wrap.grid(row=0, column=0, sticky="w")
        if has_graph:
            self._build_color_chip(title_wrap, get_block_color(panel.label)).grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Label(title_wrap, text=panel.label, font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w")
        ttk.Label(
            header,
            text="Use Reload This Tab to pull the current values from the speaker.",
            foreground="#555555",
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Button(header, text="Reload This Tab", command=lambda key=panel_key: self.refresh_panel(key)).grid(row=0, column=2, sticky="e")
        ttk.Button(header, text="Load Cached Values", command=lambda key=panel_key: self.load_cached_panel(key)).grid(row=0, column=3, sticky="e", padx=(8, 0))

        outer_row = 1
        if has_graph:
            graph_frame = ttk.LabelFrame(parent, text=f"{panel.label} Response", padding=8)
            graph_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
            graph_frame.columnconfigure(0, weight=1)
            legend = ttk.Frame(graph_frame)
            legend.grid(row=0, column=0, sticky="w", pady=(0, 6))
            self._build_color_chip(legend, get_block_color(panel.label)).grid(row=0, column=0, sticky="w", padx=(0, 6))
            ttk.Label(legend, text=f"{panel.label} native response color", foreground="#444444").grid(row=0, column=1, sticky="w")
            graph_canvas = tk.Canvas(graph_frame, height=260, highlightthickness=0, background="#fbfbfc")
            graph_canvas.grid(row=1, column=0, sticky="ew")
            graph_canvas.bind("<Configure>", lambda _event, key=panel_key: self._redraw_panel_graph(key))
            graph_canvas.bind("<Motion>", lambda event, canvas=graph_canvas: update_hover(canvas, event.x, event.y))
            graph_canvas.bind("<Leave>", lambda _event, canvas=graph_canvas: clear_hover(canvas))
            ttk.Label(
                graph_frame,
                text="This graph redraws when the tab reloads or when a value on this tab is applied. Interactive editing can be layered onto this canvas later.",
                foreground="#666666",
                wraplength=1180,
                justify="left",
            ).grid(row=2, column=0, sticky="w", pady=(8, 0))
            self.panel_graph_canvases[panel_key] = graph_canvas
            outer_row = 2

        outer = ttk.LabelFrame(parent, text=panel.label, padding=10)
        outer.grid(row=outer_row, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        frame = ttk.Frame(canvas)
        frame.columnconfigure(1, weight=1, minsize=280)
        frame.columnconfigure(3, weight=1, minsize=360)
        canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw")

        def on_frame_configure(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event) -> None:
            canvas.itemconfigure(canvas_window, width=event.width)

        frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        ttk.Label(frame, text="Parameter").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, text="Current").grid(row=0, column=1, sticky="w")
        ttk.Label(frame, text="Source").grid(row=0, column=2, sticky="w")
        ttk.Label(frame, text="New Value").grid(row=0, column=3, sticky="w")
        ttk.Label(frame, text="Action").grid(row=0, column=4, sticky="w")
        ttk.Button(frame, text="Apply All", width=apply_all_button_width, command=lambda key=panel_key: self.apply_pending_panel_values(key)).grid(row=1, column=4, sticky="w", pady=(6, 6))

        value_vars: dict[str, tk.StringVar] = {}
        source_vars: dict[str, tk.StringVar] = {}
        input_vars: dict[str, tk.StringVar] = {}
        input_hints: dict[str, LSR7InputHint | None] = {}
        input_widgets: dict[str, tk.Widget] = {}
        source_widgets: dict[str, ttk.Label] = {}
        current_row = 2
        previous_band: str | None = None
        for label, _ in panel.paths.items():
            band_match = re.match(r"Band (\d+)\s+", label)
            current_band = band_match.group(1) if band_match else None
            if panel.graph_mode == "peq" and current_band and previous_band and current_band != previous_band:
                ttk.Separator(frame, orient="horizontal").grid(row=current_row, column=0, columnspan=5, sticky="ew", pady=(6, 10))
                current_row += 1
            row = current_row
            value_vars[label] = tk.StringVar(value="")
            source_vars[label] = tk.StringVar(value="")
            input_vars[label] = tk.StringVar(value="")
            if panel.graph_mode == "peq" and "Gain" in label:
                input_vars[label].set("0.0")
            hint = self._input_hint_for_path(panel.paths[label])
            input_hints[label] = hint
            is_readonly_eq_type = panel.graph_mode == "peq" and label.endswith("Type")
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="nw", pady=(0, 6))
            ttk.Entry(frame, textvariable=value_vars[label], state="readonly", width=34).grid(row=row, column=1, sticky="new", pady=(0, 6))
            source_label = ttk.Label(frame, textvariable=source_vars[label], foreground=SOURCE_STATE_COLORS["idle"])
            source_label.grid(row=row, column=2, sticky="nw", padx=(12, 16))
            source_widgets[label] = source_label
            if is_readonly_eq_type:
                input_widgets[label] = ttk.Frame(frame)
                self.panel_input_markers.setdefault(panel_key, {})[label] = ttk.Label(frame, text="")
            else:
                input_wrap = ttk.Frame(frame)
                input_wrap.columnconfigure(1, weight=1)
                marker = ttk.Label(input_wrap, text="●", foreground=self._input_state_colors("loaded")["dot"])
                marker.grid(row=0, column=0, sticky="nw", padx=(0, 6))
                input_widget = self._build_input_widget(input_wrap, row, 3, input_vars[label], hint, path=panel.paths[label], target=(panel_key, label))
                input_widget.grid(row=0, column=1, sticky="ew")
                input_wrap.grid(row=row, column=3, sticky="new", padx=(8, 8), pady=(0, 6))
                input_widgets[label] = input_wrap
                self.panel_input_markers.setdefault(panel_key, {})[label] = marker
                self._bind_input_tracking(input_vars[label], lambda _name="", _index="", _mode="", key=panel_key, item=label: self._on_panel_input_changed(key, item))
                self._bind_widget_dirty_events(input_wrap, lambda _event=None, key=panel_key, item=label: self._on_panel_input_changed(key, item))
                self._set_panel_input_state(panel_key, label, "loaded")
                action_wrap = ttk.Frame(frame)
                action_wrap.grid(row=row, column=4, sticky="nw", pady=(0, 6))
                apply_button = ttk.Button(action_wrap, text="Apply", width=action_button_width, command=lambda key=panel_key, item=label: self.write_panel_value(key, item))
                apply_button.grid(row=0, column=0, sticky="w")
                undo_button = ttk.Button(action_wrap, text="Undo", width=undo_button_width, command=lambda key=panel_key, item=label: self.undo_target((key, item)))
                undo_button.grid(row=0, column=1, sticky="w", padx=(6, 0))
                self.panel_apply_buttons.setdefault(panel_key, {})[label] = apply_button
                self.panel_undo_buttons.setdefault(panel_key, {})[label] = undo_button
                self._refresh_target_undo_button((panel_key, label))
            previous_band = current_band or previous_band
            current_row += 1
        ttk.Label(
            frame,
            text=panel.description + " Enter the exact value you want and click Apply on that row.",
            wraplength=1180,
            justify="left",
            foreground="#555555",
        ).grid(row=current_row, column=0, columnspan=5, sticky="w", pady=(10, 0))
        self.panel_value_vars[panel_key] = value_vars
        self.panel_source_vars[panel_key] = source_vars
        self.panel_input_vars[panel_key] = input_vars
        self.panel_input_hints[panel_key] = input_hints
        self.panel_input_widgets[panel_key] = input_widgets
        self.panel_source_labels[panel_key] = source_widgets
        self.panel_input_baselines[panel_key] = {}
        self.panel_input_states[panel_key] = {}

    def _build_combined_eq_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="Combined EQ", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Overlay the major EQ blocks and the bass-management crossover into one combined response view.",
            foreground="#555555",
        ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Button(header, text="Reload Combined Sources", command=self.refresh_combined_eq).grid(row=0, column=2, sticky="e")
        ttk.Button(header, text="Load Cached Sources", command=self.load_cached_combined_eq).grid(row=0, column=3, sticky="e", padx=(8, 0))

        body = ttk.Frame(parent)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)

        controls = ttk.LabelFrame(body, text="Visible Functions", padding=8)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for column, panel_key in enumerate(COMBINED_EQ_PANEL_KEYS):
            label = self._panel_by_key(panel_key).label
            variable = tk.BooleanVar(value=True)
            self.combined_visibility_vars[panel_key] = variable
            block = ttk.Frame(controls)
            block.grid(row=0, column=column, sticky="w", padx=(0, 14))
            self._build_color_chip(block, get_block_color(label)).grid(row=0, column=0, sticky="w", padx=(0, 4))
            ttk.Checkbutton(
                block,
                text=label,
                variable=variable,
                command=self._redraw_combined_graph,
            ).grid(row=0, column=1, sticky="w")

        graph_frame = ttk.LabelFrame(body, text="Merged Response", padding=8)
        graph_frame.grid(row=1, column=0, sticky="nsew")
        graph_frame.columnconfigure(0, weight=1)
        graph_frame.rowconfigure(0, weight=1)
        self.combined_graph_canvas = tk.Canvas(graph_frame, height=340, highlightthickness=0, background="#fbfbfc")
        self.combined_graph_canvas.grid(row=0, column=0, sticky="nsew")
        self.combined_graph_canvas.bind("<Configure>", lambda _event: self._redraw_combined_graph())
        self.combined_graph_canvas.bind("<Motion>", lambda event: update_hover(self.combined_graph_canvas, event.x, event.y))
        self.combined_graph_canvas.bind("<Leave>", lambda _event: clear_hover(self.combined_graph_canvas))
        ttk.Label(
            graph_frame,
            text="The checkboxes only affect what is shown on this graph. They do not change any speaker settings.",
            foreground="#666666",
            wraplength=1180,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

    def _build_explorer_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=2)
        parent.columnconfigure(1, weight=3)
        parent.rowconfigure(1, weight=1)

        intro = ttk.LabelFrame(parent, text="Live Branch Browser", padding=8)
        intro.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        intro.columnconfigure(0, weight=1)
        ttk.Label(
            intro,
            text=(
                "Browse one branch level at a time from the live speaker. "
                "Double-click a node to drill down. Use Read Selected for the current node details."
            ),
            wraplength=1180,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        controls = ttk.Frame(parent)
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(controls, text="Current Branch").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.branch_root_var, width=32).grid(row=0, column=1, sticky="w", padx=(6, 12))
        ttk.Button(controls, text="Open Branch", command=self.open_selected_branch).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(controls, text="Open Cached Branch", command=self.load_cached_tree).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(controls, text="Up One Level", command=self.go_up_branch).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(controls, text="Read Selected", command=self.read_selected_path).grid(row=0, column=5, padx=(0, 8))
        ttk.Button(controls, text="Pull Snapshot", command=self.pull_snapshot).grid(row=0, column=6, padx=(0, 8))
        ttk.Label(controls, textvariable=self.explorer_status_var, foreground="#0B4F6C").grid(row=0, column=7, sticky="w", padx=(12, 0))
        ttk.Label(controls, textvariable=self.tree_cache_stats_var, foreground="#666666").grid(row=1, column=0, columnspan=8, sticky="w", pady=(6, 0))

        favorites = ttk.LabelFrame(parent, text="Top-Level Branches", padding=8)
        favorites.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        favorites.columnconfigure(0, weight=1)
        favorites.rowconfigure(1, weight=1)
        ttk.Label(favorites, text="Double-click a branch to open it live.").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.favorites_list = tk.Listbox(favorites, height=16)
        self.favorites_list.grid(row=1, column=0, sticky="nsew")
        self.favorites_list.bind("<Double-Button-1>", self._apply_favorite_root)
        ttk.Button(favorites, text="Refresh Top-Level Branches", command=self.refresh_top_level_branches).grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Label(favorites, textvariable=self.top_level_status_var, foreground="#666666").grid(row=3, column=0, sticky="w", pady=(6, 0))

        tree_frame = ttk.LabelFrame(parent, text="Current Branch Contents", padding=8)
        tree_frame.grid(row=2, column=1, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("kind",), show="tree headings")
        self.tree.heading("#0", text="Current Branch Level")
        self.tree.heading("kind", text="Kind")
        self.tree.column("#0", width=430, anchor="w")
        self.tree.column("kind", width=100, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-Button-1>", self._drill_selected_path)
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scroll.set)

        details = ttk.LabelFrame(parent, text="Selected Path", padding=8)
        details.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        ttk.Label(details, text="Path").grid(row=0, column=0, sticky="nw")
        ttk.Label(details, textvariable=self.selected_path_var, wraplength=1120).grid(row=0, column=1, columnspan=3, sticky="w")
        for row, (label, variable) in enumerate(
            [("Text", self.path_value_text_var), ("Percent", self.path_value_percent_var), ("Float", self.path_value_float_var), ("Min", self.path_min_var), ("Max", self.path_max_var), ("Type", self.path_type_var), ("Enabled", self.path_enabled_var), ("Sensor", self.path_sensor_var)],
            start=1,
        ):
            ttk.Label(details, text=label).grid(row=row, column=0, sticky="w", pady=(6, 0))
            ttk.Entry(details, textvariable=variable, state="readonly").grid(row=row, column=1, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Separator(details, orient="horizontal").grid(row=9, column=0, columnspan=4, sticky="ew", pady=10)
        ttk.Label(details, text="Write Text").grid(row=10, column=0, sticky="w")
        ttk.Entry(details, textvariable=self.write_text_var).grid(row=10, column=1, sticky="ew")
        ttk.Button(details, text="Apply Text", command=self.write_selected_text).grid(row=10, column=2, sticky="w", padx=(8, 0))
        ttk.Label(details, text="Write Percent").grid(row=11, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(details, textvariable=self.write_percent_var).grid(row=11, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(details, text="Apply Percent", command=self.write_selected_percent).grid(row=11, column=2, sticky="w", padx=(8, 0), pady=(8, 0))

    def _build_diagnostics_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        ttk.Label(parent, text="Live app events, protocol tracing, snapshot tools, and documentation shortcuts.").grid(row=0, column=0, sticky="w", pady=(0, 8))

        controls = ttk.LabelFrame(parent, text="Diagnostics Controls", padding=8)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        controls.columnconfigure(4, weight=1)
        ttk.Checkbutton(controls, text="Verbose protocol debug", variable=self.debug_protocol_var, command=self._on_debug_toggle).grid(row=0, column=0, sticky="w")
        ttk.Label(controls, textvariable=self.debug_summary_var, foreground="#0B4F6C").grid(row=0, column=1, columnspan=2, sticky="w", padx=(12, 0))
        ttk.Label(controls, text="Snapshot export root").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(controls, textvariable=self.snapshot_root_var, width=28).grid(row=1, column=1, sticky="w", padx=(8, 8), pady=(10, 0))
        ttk.Button(controls, text="Export Snapshot Now", command=self.pull_snapshot).grid(row=1, column=2, sticky="w", pady=(10, 0))
        ttk.Button(controls, text="Refresh System Info", command=self.refresh_system_info).grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        info = ttk.LabelFrame(parent, text="System Info", padding=8)
        info.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        info.columnconfigure(1, weight=1)
        for row, label in enumerate(SYSTEM_INFO_PATHS):
            ttk.Label(info, text=label).grid(row=row, column=0, sticky="w", pady=(0, 4))
            ttk.Entry(info, textvariable=self.system_info_vars[label], state="readonly").grid(row=row, column=1, sticky="ew", pady=(0, 4))
            ttk.Label(info, textvariable=self.system_info_source_vars[label], foreground="#666666").grid(row=row, column=2, sticky="w", padx=(8, 0))
        ttk.Label(info, text="Use verbose protocol debug during discovery, reads, writes, and retries to see raw traffic as it happens.", foreground="#666666", wraplength=1160, justify="left").grid(
            row=len(SYSTEM_INFO_PATHS), column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        panes = ttk.Panedwindow(parent, orient="vertical")
        panes.grid(row=3, column=0, sticky="nsew")
        parent.rowconfigure(3, weight=1)

        events_frame = ttk.LabelFrame(panes, text="App Events", padding=8)
        events_frame.columnconfigure(0, weight=1)
        events_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(events_frame, wrap="word", height=12)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.configure(state="disabled")
        log_scroll = ttk.Scrollbar(events_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        protocol_frame = ttk.LabelFrame(panes, text="Realtime Protocol Trace", padding=8)
        protocol_frame.columnconfigure(0, weight=1)
        protocol_frame.rowconfigure(0, weight=1)
        self.protocol_text = tk.Text(protocol_frame, wrap="word", height=18)
        self.protocol_text.grid(row=0, column=0, sticky="nsew")
        self.protocol_text.configure(state="disabled")
        protocol_scroll = ttk.Scrollbar(protocol_frame, orient="vertical", command=self.protocol_text.yview)
        protocol_scroll.grid(row=0, column=1, sticky="ns")
        self.protocol_text.configure(yscrollcommand=protocol_scroll.set)

        panes.add(events_frame, weight=1)
        panes.add(protocol_frame, weight=2)
        actions = ttk.Frame(parent)
        actions.grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Button(actions, text="Clear Log", command=self.clear_log).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Clear Protocol Trace", command=self.clear_protocol_trace).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Show Project Status", command=lambda: self.show_text_file("PROJECT_STATUS.md")).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="Show Protocol Notes", command=lambda: self.show_text_file("LSR7_WEBSOCKET_PROTOCOL.md")).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(actions, text="Show Path Map", command=lambda: self.show_text_file("LSR7_MAPPED_PATHS.md")).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(actions, text="Show Tree Summary", command=lambda: self.show_text_file(str(TREE_SUMMARY_PATH))).grid(row=0, column=5, padx=(0, 8))

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _append_protocol(self, message: str) -> None:
        self.protocol_text.configure(state="normal")
        self.protocol_text.insert("end", message + "\n")
        self.protocol_text.see("end")
        self.protocol_text.configure(state="disabled")

    def _enqueue_log(self, message: str) -> None:
        self.log_queue.put(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _enqueue_protocol(self, message: str) -> None:
        self.protocol_queue.put(f"[{time.strftime('%H:%M:%S')}] {message}")

    def _poll_logs(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(message)
        while True:
            try:
                message = self.protocol_queue.get_nowait()
            except queue.Empty:
                break
            self.protocol_event_count += 1
            if self.debug_protocol_var.get():
                self.debug_summary_var.set(f"Verbose trace active: {self.protocol_event_count} events captured")
            self._append_protocol(message)
        self.root.after(200, self._poll_logs)

    def _set_status(self, summary: str, detail: str | None = None) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.status_var.set(summary)
        self.status_detail_var.set(detail or f"Updated {timestamp}")
        self._update_status_blink(summary)

    def _update_status_blink(self, summary: str) -> None:
        is_refreshing = "refreshing" in summary.lower()
        if is_refreshing:
            if not self.status_blink_job:
                self.status_blink_visible = True
                self._blink_status_summary()
            return
        if self.status_blink_job:
            try:
                self.root.after_cancel(self.status_blink_job)
            except tk.TclError:
                pass
            self.status_blink_job = None
        self.status_blink_visible = True
        try:
            self.status_summary_label.configure(foreground="#0B4F6C")
        except tk.TclError:
            pass

    def _blink_status_summary(self) -> None:
        try:
            color = "#0B4F6C" if self.status_blink_visible else "#9ecfe3"
            self.status_summary_label.configure(foreground=color)
        except tk.TclError:
            self.status_blink_job = None
            return
        self.status_blink_visible = not self.status_blink_visible
        self.status_blink_job = self.root.after(350, self._blink_status_summary)

    def _on_debug_toggle(self) -> None:
        enabled = bool(self.debug_protocol_var.get())
        self._save_runtime_config()
        state = "enabled" if enabled else "disabled"
        self.debug_summary_var.set(f"Verbose protocol tracing {state}")
        self._enqueue_log(f"Verbose protocol tracing {state}")
        self._enqueue_protocol(f"[control] Verbose protocol tracing {state}")
        self._set_status("Diagnostics updated", f"Verbose protocol tracing {state} at {time.strftime('%H:%M:%S')}")

    def _protocol_debug(self, event: str, message: str) -> None:
        if not self.debug_protocol_var.get():
            return
        self._enqueue_protocol(f"[{event}] {message}")

    def _host(self) -> str:
        return self.host_var.get().strip()

    def _load_interfaces(self) -> None:
        self.interfaces = list_network_interfaces()
        self.interface_map = {item.display_name: item for item in self.interfaces}
        values = list(self.interface_map.keys())
        self.interface_combo["values"] = values
        if values:
            if self.interface_var.get() not in self.interface_map:
                self.interface_var.set(values[0])
            self.top_level_status_var.set(f"{len(values)} local interfaces available")
            self._set_status("Interfaces ready", f"{len(values)} local interfaces available for discovery")

    def _on_interface_selected(self, _event=None) -> None:
        self._save_runtime_config()

    def _on_discovered_speaker_selected(self, _event=None) -> None:
        selected = self.discovered_speaker_map.get(self.discovered_speaker_var.get())
        if selected:
            self.host_var.set(selected.host)
            self._set_status(f"Selected speaker {selected.host}", f"Discovery list selection updated at {time.strftime('%H:%M:%S')}")

    def discover_speakers_on_interface(self) -> None:
        selected_name = self.interface_var.get().strip()
        interface = self.interface_map.get(selected_name)
        if not interface:
            messagebox.showinfo("Interface Required", "Select a local network interface first.")
            return
        self._save_runtime_config()
        def worker() -> None:
            speakers = discover_speakers(interface)
            def update() -> None:
                self.discovered_speakers = speakers
                self.discovered_speaker_map = {speaker.display_name: speaker for speaker in speakers}
                values = list(self.discovered_speaker_map.keys())
                self.discovered_combo["values"] = values
                if values:
                    self.discovered_speaker_var.set(values[0])
                    self.host_var.set(self.discovered_speaker_map[values[0]].host)
                self._set_status(
                    f"Found {len(speakers)} speaker(s)",
                    f"Discovery completed on {interface.display_name} at {time.strftime('%H:%M:%S')}",
                )
            self.root.after(0, update)
            self._enqueue_log(f"Discovery complete on {interface.display_name}: {len(speakers)} speakers")
        self._run_in_thread(f"Discovering speakers on {interface.display_name}", worker)

    def _save_runtime_config(self) -> None:
        self.config = AppConfig(
            speaker_host=self._host(),
            network_interface=self.interface_var.get().strip(),
            snapshot_root=self.snapshot_root_var.get().strip() or "\\\\this",
            theme_mode=self.theme_mode,
            confirm_writes=bool(self.confirm_writes_var.get()),
            auto_refresh_after_write=bool(self.auto_refresh_var.get()),
            instant_update=bool(self.instant_update_var.get()),
            debug_protocol=bool(self.debug_protocol_var.get()),
            notes=self.protocol_notes_var.get(),
        )
        save_config(self.config)

    def _run_in_thread(self, label: str, worker, on_error=None) -> None:
        self._set_status(label, f"Started at {time.strftime('%H:%M:%S')} on host {self._host() or '?'}")
        def runner() -> None:
            try:
                worker()
            except Exception as exc:
                message = f"{label} failed: {exc}"
                self._enqueue_log(message)
                self._enqueue_protocol(f"[error] {message}")
                def update_error(message=message):
                    if on_error:
                        on_error()
                    self._set_status("Operation failed", message)
                self.root.after(0, update_error)
            else:
                self.root.after(0, lambda label=label: self._mark_request_complete(label))
        threading.Thread(target=runner, daemon=True).start()

    def _mark_request_complete(self, label: str) -> None:
        current_summary = self.status_var.get().strip()
        current_detail = self.status_detail_var.get().strip()
        timestamp = time.strftime("%H:%M:%S")
        if current_summary == "Operation failed":
            return
        if current_summary == label:
            self._set_status("Ready", f"{label} completed and socket closed at {timestamp}")
            return
        if "completed and socket closed" in current_detail.lower():
            return
        self.status_detail_var.set(f"{current_detail} Completed and socket closed at {timestamp}".strip())

    def _with_client(self, action):
        host = self._host()
        if not host:
            raise ValueError("Enter a speaker IP first.")
        with LSR7WebSocketClient(host, debug_hook=self._protocol_debug) as client:
            return action(client)

    def _is_enable_path(self, path: str) -> bool:
        tail = path.rsplit("\\", 1)[-1]
        return tail in {"Enable", "Enabled"} or tail.endswith("_Enable") or tail.endswith("_Enabled")

    def _canonical_on_off(self, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"on", "enable", "enabled", "engaged", "true", "1"}:
            return "On"
        if normalized in {"off", "disable", "disabled", "disengaged", "false", "0"}:
            return "Off"
        return value

    def _enable_write_value(self, path: str, raw: str) -> str:
        desired = self._canonical_on_off(raw)
        if desired not in {"On", "Off"}:
            return raw
        snapshot = self._cached_snapshot_for_path(self.latest_tree, path)
        min_text = (snapshot.get("min_text") or "").strip()
        max_text = (snapshot.get("max_text") or "").strip()
        current = (snapshot.get("value_text") or "").strip()
        candidates = {min_text, max_text, current}
        if {"Disabled", "Enabled"} & candidates:
            return "Enabled" if desired == "On" else "Disabled"
        if {"Disable", "Enable"} & candidates:
            return "Enable" if desired == "On" else "Disable"
        if {"Disengaged", "Engaged"} & candidates:
            return "Engaged" if desired == "On" else "Disengaged"
        return desired

    def _input_hint_for_path(self, path: str) -> LSR7InputHint | None:
        hint = INPUT_HINTS.get(path)
        if hint:
            return hint
        snapshot = self._cached_snapshot_for_path(self.latest_tree, path)
        if self._is_enable_path(path):
            return LSR7InputHint("enum", ("Off", "On"))
        min_text = self._canonical_on_off(snapshot.get("min_text") or "")
        max_text = self._canonical_on_off(snapshot.get("max_text") or "")
        if min_text == "Off" and max_text == "On":
            return LSR7InputHint("enum", ("Off", "On"))
        if snapshot.get("min_text") == "Off" and snapshot.get("max_text") == "On":
            return LSR7InputHint("enum", ("Off", "On"))
        return None

    def _bind_input_tracking(self, variable: tk.StringVar, callback) -> None:
        variable.trace_add("write", callback)

    def _enum_display_value(self, path: str, value: str) -> str:
        mapping = ENUM_DISPLAY_LABELS.get(path)
        if not mapping:
            return value
        return mapping.get(value, value)

    def _enum_backend_value(self, path: str, value: str) -> str:
        mapping = ENUM_DISPLAY_LABELS.get(path)
        if not mapping:
            return value
        reverse = {display: backend for backend, display in mapping.items()}
        return reverse.get(value, value)

    def _enum_display_choices(self, path: str, hint: LSR7InputHint) -> list[str]:
        return [self._enum_display_value(path, choice) for choice in hint.choices]

    def _bind_widget_dirty_events(self, widget: tk.Widget, callback) -> None:
        try:
            klass = widget.winfo_class()
        except tk.TclError:
            return
        if klass == "TCombobox":
            widget.bind("<<ComboboxSelected>>", callback, add="+")
            widget.bind("<KeyRelease>", callback, add="+")
        elif klass in {"TSpinbox", "TEntry"}:
            widget.bind("<KeyRelease>", callback, add="+")
            widget.bind("<<Increment>>", callback, add="+")
            widget.bind("<<Decrement>>", callback, add="+")
        else:
            for child in widget.winfo_children():
                self._bind_widget_dirty_events(child, callback)

    def _set_variable_safely(self, variable: tk.StringVar, value: str) -> None:
        self._suspend_dirty_tracking = True
        try:
            variable.set(value)
        finally:
            self._suspend_dirty_tracking = False

    def _bind_shortcuts(self) -> None:
        self.root.bind_all("<Control-z>", self._on_global_undo, add="+")
        self.root.bind_all("<Control-y>", self._on_global_redo, add="+")
        self.root.bind_all("<Control-Shift-Z>", self._on_global_redo, add="+")

    def _target_key(self, target) -> str:
        return "|".join(self._normalize_target(target))

    def _normalize_target(self, target) -> tuple[str, ...]:
        if isinstance(target, tuple):
            if len(target) == 3 and target[0] == "panel":
                return target
            if len(target) == 2 and target[0] == "control":
                return target
            if len(target) == 2:
                return ("panel", target[0], target[1])
        if isinstance(target, str):
            return ("control", target)
        raise ValueError(f"Unsupported target {target!r}")

    def _record_history(self, target, old_value: str, new_value: str) -> None:
        normalized = self._normalize_target(target)
        if self._suspend_history_tracking or old_value == new_value:
            return
        self.undo_history.append({"target": "|".join(normalized), "old": old_value, "new": new_value})
        self.redo_history.clear()
        self._refresh_target_undo_button(normalized)

    def _target_has_undo(self, target) -> bool:
        normalized = "|".join(self._normalize_target(target))
        return any(entry["target"] == normalized for entry in self.undo_history)

    def _refresh_target_undo_button(self, target) -> None:
        normalized = self._normalize_target(target)
        has_undo = self._target_has_undo(normalized)
        if normalized[0] == "control":
            button = self.control_undo_buttons.get(normalized[1])
        else:
            button = self.panel_undo_buttons.get(normalized[1], {}).get(normalized[2])
        if button:
            button.configure(state="normal" if has_undo else "disabled")

    def _refresh_all_undo_buttons(self) -> None:
        for key in self.control_undo_buttons:
            self._refresh_target_undo_button(("control", key))
        for panel_key, buttons in self.panel_undo_buttons.items():
            for label in buttons:
                self._refresh_target_undo_button((panel_key, label))

    def _begin_slider_history(self, target, current_value: str) -> None:
        self.slider_drag_start_values[self._target_key(target)] = current_value

    def _commit_slider_history(self, target, current_value: str) -> None:
        target_key = self._target_key(target)
        start_value = self.slider_drag_start_values.pop(target_key, None)
        if start_value is None:
            start_value = current_value
        self._record_history(target, start_value, current_value)
        normalized = self._normalize_target(target)
        if normalized[0] == "control":
            self.control_input_last_seen[normalized[1]] = current_value
        else:
            self.panel_input_last_seen.setdefault(normalized[1], {})[normalized[2]] = current_value

    def _apply_history_value(self, target, value: str) -> None:
        normalized = self._normalize_target(target)
        self._suspend_history_tracking = True
        try:
            if normalized[0] == "control":
                key = normalized[1]
                self._set_variable_safely(self.control_inputs[key], value)
                self.control_input_last_seen[key] = value
                self._on_control_input_changed(key)
            else:
                panel_key, label = normalized[1], normalized[2]
                self._set_variable_safely(self.panel_input_vars[panel_key][label], value)
                self.panel_input_last_seen.setdefault(panel_key, {})[label] = value
                self._on_panel_input_changed(panel_key, label)
        finally:
            self._suspend_history_tracking = False

    def _move_history_entry(self, source: list[dict[str, str]], destination: list[dict[str, str]], index: int, *, use_old: bool) -> None:
        entry = source.pop(index)
        target = tuple(entry["target"].split("|"))
        destination.append(entry)
        self._apply_history_value(target, entry["old"] if use_old else entry["new"])
        self._refresh_all_undo_buttons()

    def undo_target(self, target) -> None:
        normalized = "|".join(self._normalize_target(target))
        for index in range(len(self.undo_history) - 1, -1, -1):
            if self.undo_history[index]["target"] == normalized:
                self._move_history_entry(self.undo_history, self.redo_history, index, use_old=True)
                return

    def _on_global_undo(self, _event=None):
        if not self.undo_history:
            return "break"
        self._move_history_entry(self.undo_history, self.redo_history, len(self.undo_history) - 1, use_old=True)
        return "break"

    def _on_global_redo(self, _event=None):
        if not self.redo_history:
            return "break"
        self._move_history_entry(self.redo_history, self.undo_history, len(self.redo_history) - 1, use_old=False)
        return "break"

    def _apply_input_state(self, widget: tk.Widget, state: str) -> None:
        style_names = INPUT_STATE_STYLES[state]
        colors = self._input_state_colors(state)
        try:
            klass = widget.winfo_class()
        except tk.TclError:
            return
        if klass == "TCombobox":
            widget.configure(style=style_names["combobox"])
            try:
                widget.configure(foreground=colors["fg"])
            except tk.TclError:
                pass
            try:
                widget.selection_clear()
            except tk.TclError:
                pass
        elif klass == "TSpinbox":
            widget.configure(style=style_names["spinbox"])
            try:
                widget.configure(foreground=colors["fg"])
            except tk.TclError:
                pass
        elif klass == "TEntry":
            widget.configure(style=style_names["entry"])
            try:
                widget.configure(foreground=colors["fg"])
            except tk.TclError:
                pass
        elif klass == "TScale":
            widget.configure(style=style_names["scale"])
        elif klass == "TLabel" and str(widget.cget("text")).strip() == "●":
            widget.configure(foreground=colors["dot"])
        else:
            for child in widget.winfo_children():
                self._apply_input_state(child, state)
        try:
            widget.update_idletasks()
        except tk.TclError:
            pass

    def _set_control_input_state(self, key: str, state: str) -> None:
        self.control_input_states[key] = state
        widget = self.control_input_widgets.get(key)
        if widget:
            self._apply_input_state(widget, state)
        marker = self.control_input_markers.get(key)
        if marker:
            self._apply_input_state(marker, state)
        button = self.control_apply_buttons.get(key)
        if button:
            button.configure(style="Pending.TButton" if state == "dirty" else "TButton")

    def _set_panel_input_state(self, panel_key: str, label: str, state: str) -> None:
        self.panel_input_states.setdefault(panel_key, {})[label] = state
        widget = self.panel_input_widgets.get(panel_key, {}).get(label)
        if widget:
            self._apply_input_state(widget, state)
        marker = self.panel_input_markers.get(panel_key, {}).get(label)
        if marker:
            self._apply_input_state(marker, state)
        button = self.panel_apply_buttons.get(panel_key, {}).get(label)
        if button:
            button.configure(style="Pending.TButton" if state == "dirty" else "TButton")

    def _on_control_input_changed(self, key: str) -> None:
        if self._suspend_dirty_tracking:
            return
        current = self.control_inputs[key].get().strip()
        if self._target_key(("control", key)) not in self.slider_targets:
            previous = self.control_input_last_seen.get(key, current)
            self._record_history(("control", key), previous, current)
            self.control_input_last_seen[key] = current
        baseline = self.control_input_baselines.get(key, "").strip()
        state = "loaded" if current == baseline else "dirty"
        self._set_control_input_state(key, state)
        if state == "dirty":
            self._schedule_instant_control_write(key)
        else:
            self._cancel_instant_update_job(f"control:{key}")

    def _on_panel_input_changed(self, panel_key: str, label: str) -> None:
        if self._suspend_dirty_tracking:
            return
        current = self.panel_input_vars[panel_key][label].get().strip()
        if self._target_key((panel_key, label)) not in self.slider_targets:
            previous = self.panel_input_last_seen.get(panel_key, {}).get(label, current)
            self._record_history((panel_key, label), previous, current)
            self.panel_input_last_seen.setdefault(panel_key, {})[label] = current
        baseline = self.panel_input_baselines.get(panel_key, {}).get(label, "").strip()
        state = "loaded" if current == baseline else "dirty"
        self._set_panel_input_state(panel_key, label, state)
        job_key = f"panel:{panel_key}:{label}"
        if state == "dirty":
            self._schedule_instant_panel_write(panel_key, label)
        else:
            self._cancel_instant_update_job(job_key)

    def _cancel_instant_update_job(self, job_key: str) -> None:
        after_id = self.instant_update_jobs.pop(job_key, None)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass

    def _schedule_instant_control_write(self, key: str) -> None:
        if not self.instant_update_var.get():
            return
        job_key = f"control:{key}"
        self._cancel_instant_update_job(job_key)
        after_id = self.root.after(350, lambda selected_key=key: self._perform_instant_control_write(selected_key))
        self.instant_update_jobs[job_key] = after_id

    def _schedule_instant_panel_write(self, panel_key: str, label: str) -> None:
        if not self.instant_update_var.get():
            return
        job_key = f"panel:{panel_key}:{label}"
        self._cancel_instant_update_job(job_key)
        after_id = self.root.after(350, lambda selected_panel=panel_key, selected_label=label: self._perform_instant_panel_write(selected_panel, selected_label))
        self.instant_update_jobs[job_key] = after_id

    def _perform_instant_control_write(self, key: str) -> None:
        self.instant_update_jobs.pop(f"control:{key}", None)
        if not self.instant_update_var.get():
            return
        control = next((item for item in COMMON_CONTROLS if item.key == key), None)
        if not control:
            return
        if self.control_input_states.get(key) != "dirty":
            return
        self.write_common_control(control, auto_refresh=False, instant=True)

    def _perform_instant_panel_write(self, panel_key: str, label: str) -> None:
        self.instant_update_jobs.pop(f"panel:{panel_key}:{label}", None)
        if not self.instant_update_var.get():
            return
        if self.panel_input_states.get(panel_key, {}).get(label) != "dirty":
            return
        self.write_panel_value(panel_key, label, auto_refresh=False, instant=True)

    def _flash_instant_update_indicator(self, cycles: int = 6) -> None:
        if self.instant_update_flash_job:
            try:
                self.root.after_cancel(self.instant_update_flash_job)
            except tk.TclError:
                pass
            self.instant_update_flash_job = None

        def step(remaining: int, flash_on: bool) -> None:
            try:
                self.instant_update_check.configure(style="InstantFlash.TCheckbutton" if flash_on else "Instant.TCheckbutton")
            except tk.TclError:
                return
            if self.instant_update_var.get():
                self.instant_update_flash_job = self.root.after(220, lambda: step(remaining, not flash_on))
                return
            if remaining <= 0:
                self.instant_update_check.configure(style="Instant.TCheckbutton")
                self.instant_update_flash_job = None
                return
            self.instant_update_flash_job = self.root.after(220, lambda: step(remaining - 1, not flash_on))

        step(cycles, True)

    def _on_instant_update_toggle(self) -> None:
        enabled = bool(self.instant_update_var.get())
        if enabled:
            self._instant_restore_confirm_writes = bool(self.confirm_writes_var.get())
            self._instant_restore_auto_refresh = bool(self.auto_refresh_var.get())
            self.confirm_writes_var.set(False)
            self.auto_refresh_var.set(False)
        else:
            self.confirm_writes_var.set(self._instant_restore_confirm_writes)
            self.auto_refresh_var.set(self._instant_restore_auto_refresh)
        self._sync_instant_update_controls()
        self._save_runtime_config()
        self._flash_instant_update_indicator()
        state = "enabled" if enabled else "disabled"
        self._set_status("Instant-Update changed", f"Instant-Update {state} at {time.strftime('%H:%M:%S')}")
        if not enabled:
            for job_key in list(self.instant_update_jobs):
                self._cancel_instant_update_job(job_key)
            try:
                self.instant_update_check.configure(style="Instant.TCheckbutton")
            except tk.TclError:
                pass
        else:
            self.instant_update_var.set(True)

    def _sync_instant_update_controls(self) -> None:
        disabled = bool(self.instant_update_var.get())
        try:
            self.confirm_writes_check.configure(state="disabled" if disabled else "normal")
            self.auto_refresh_check.configure(state="disabled" if disabled else "normal")
        except tk.TclError:
            pass

    def _load_control_input_value(self, key: str, value: str, *, state: str = "loaded") -> None:
        self.control_input_baselines[key] = value
        self._set_variable_safely(self.control_inputs[key], value)
        self.control_input_last_seen[key] = value
        self._set_control_input_state(key, state)

    def _load_panel_input_value(self, panel_key: str, label: str, value: str, *, state: str = "loaded") -> None:
        self.panel_input_baselines.setdefault(panel_key, {})[label] = value
        self._set_variable_safely(self.panel_input_vars[panel_key][label], value)
        self.panel_input_last_seen.setdefault(panel_key, {})[label] = value
        self._set_panel_input_state(panel_key, label, state)

    def _set_control_values(self, data: dict[str, str], *, state: str = "loaded", preserve_pending: bool = True) -> None:
        pending_values: dict[str, str] = {}
        if preserve_pending:
            for key, input_state in self.control_input_states.items():
                if input_state == "dirty":
                    pending_values[key] = self.control_inputs[key].get()
        for key, display_value in data.items():
            self.control_current_text[key].set(display_value)
            if key in pending_values and state == "loaded":
                self.control_input_baselines[key] = display_value
                if pending_values[key].strip() == display_value.strip():
                    self._load_control_input_value(key, display_value, state="loaded")
                else:
                    self._set_variable_safely(self.control_inputs[key], pending_values[key])
                    self._set_control_input_state(key, "dirty")
            else:
                self._load_control_input_value(key, display_value, state=state)

    def _build_input_widget(self, parent, row: int, column: int, variable: tk.StringVar, hint: LSR7InputHint | None, *, path: str | None = None, target=None):
        if hint and hint.input_kind == "enum" and hint.choices:
            choices = self._enum_display_choices(path, hint) if path else list(hint.choices)
            widget = ttk.Combobox(parent, textvariable=variable, values=choices, state="normal")
            widget.configure(height=12)
            return widget
        uses_slider = (
            hint
            and hint.minimum is not None
            and hint.maximum is not None
            and (
                hint.input_kind in {"numeric_db", "numeric_ms"}
                or (hint.input_kind == "numeric_plain" and path and path.endswith("_Q"))
            )
        )
        if uses_slider:
            wrapper = ttk.Frame(parent)
            wrapper.columnconfigure(0, weight=1)
            if target is not None:
                self.slider_targets.add(self._target_key(target))
            initial_value = hint.minimum if hint.minimum is not None else 0.0
            existing_text = variable.get().strip()
            if existing_text:
                candidate = existing_text
                if hint.suffix and candidate.lower().endswith(hint.suffix.lower()):
                    candidate = candidate[: -len(hint.suffix)].strip()
                try:
                    initial_value = float(candidate)
                except ValueError:
                    initial_value = hint.minimum if hint.minimum is not None else 0.0
            elif hint.input_kind == "numeric_db" and hint.minimum <= 0.0 <= hint.maximum:
                initial_value = 0.0
            initial_value = min(max(initial_value, hint.minimum), hint.maximum)
            scale_var = tk.DoubleVar(value=initial_value)
            key = f"{id(variable)}:{row}:{column}"
            self.control_scale_vars[key] = scale_var

            def format_value(number: float) -> str:
                return f"{number:.{hint.decimals}f}"

            def on_scale(raw: str) -> None:
                number = round(float(raw), hint.decimals)
                variable.set(format_value(number))

            def on_entry(*_args) -> None:
                text = variable.get().strip()
                if not text:
                    return
                if hint.suffix and text.lower().endswith(hint.suffix.lower()):
                    text = text[: -len(hint.suffix)].strip()
                try:
                    number = float(text)
                except ValueError:
                    return
                number = min(max(number, hint.minimum), hint.maximum)
                scale_var.set(number)

            scale = ttk.Scale(wrapper, from_=hint.minimum, to=hint.maximum, variable=scale_var, command=on_scale)
            scale.grid(row=0, column=0, sticky="ew")
            if target is not None:
                scale.bind("<ButtonPress-1>", lambda _event, selected_target=target, selected_var=variable: self._begin_slider_history(selected_target, selected_var.get().strip()), add="+")
                scale.bind("<ButtonRelease-1>", lambda _event, selected_target=target, selected_var=variable: self._commit_slider_history(selected_target, selected_var.get().strip()), add="+")
            entry = ttk.Spinbox(
                wrapper,
                textvariable=variable,
                from_=hint.minimum,
                to=hint.maximum,
                increment=hint.step or 1.0,
                format=f"%.{hint.decimals}f",
                width=8,
            )
            entry.grid(row=0, column=1, sticky="w", padx=(8, 0))
            ttk.Label(wrapper, text=f"{hint.minimum:.{hint.decimals}f} to {hint.maximum:.{hint.decimals}f}{hint.suffix}").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))
            variable.trace_add("write", on_entry)
            variable.set(format_value(initial_value))
            return wrapper
        if hint and hint.input_kind in {"numeric_db", "numeric_ms", "numeric_plain"} and hint.minimum is not None and hint.maximum is not None:
            return ttk.Spinbox(
                parent,
                textvariable=variable,
                from_=hint.minimum,
                to=hint.maximum,
                increment=hint.step or 1.0,
                format=f"%.{hint.decimals}f",
                width=12,
            )
        return ttk.Entry(parent, textvariable=variable)

    def _parse_numeric_input(self, raw: str, hint: LSR7InputHint) -> float:
        text = raw.strip()
        if hint.suffix and text.lower().endswith(hint.suffix.lower()):
            text = text[: -len(hint.suffix)].strip()
        if not text:
            raise ValueError("Missing numeric value")
        text = text.replace(",", "")
        numeric_match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", text)
        if numeric_match:
            text = numeric_match.group(0)
        numeric = float(text)
        if hint.minimum is not None and numeric < hint.minimum - 1e-9:
            raise ValueError(f"Below minimum {hint.minimum}")
        if hint.maximum is not None and numeric > hint.maximum + 1e-9:
            raise ValueError(f"Above maximum {hint.maximum}")
        if hint.step and hint.input_kind != "numeric_ms":
            base = hint.minimum or 0.0
            units = round((numeric - base) / hint.step)
            snapped = base + (units * hint.step)
            tolerance = max(1e-6, abs(hint.step) / 1000.0)
            if abs(numeric - snapped) > tolerance:
                raise ValueError(f"Invalid step {hint.step}")
            numeric = snapped
        return round(numeric, hint.decimals)

    def _normalize_write_value(self, path: str, value: str, hint: LSR7InputHint | None) -> tuple[str, str]:
        raw = value.strip()
        if self._is_enable_path(path):
            return self._enable_write_value(path, raw), "text"
        if not hint:
            return raw, "text"
        if hint.input_kind == "enum":
            raw = self._enum_backend_value(path, raw)
            if hint.choices == ("Off", "On"):
                return self._enable_write_value(path, raw), "text"
            return raw, "text"
        if hint.input_kind == "numeric_db":
            numeric = self._parse_numeric_input(raw, hint)
            return f"{numeric:.{hint.decimals}f}dB", "text"
        if hint.input_kind == "numeric_ms":
            numeric = self._parse_numeric_input(raw, hint)
            return f"{numeric:.{hint.decimals}f}ms", "text"
        if hint.input_kind == "numeric_plain":
            numeric = self._parse_numeric_input(raw, hint)
            return f"{numeric:.{hint.decimals}f}", "text"
        return raw, "text"

    def _display_value_for_path(self, path: str, payload) -> str:
        hint = self._input_hint_for_path(path)
        snapshot = payload if isinstance(payload, dict) else {"value_text": payload}
        value_text = snapshot.get("value_text") or ""
        value_float = snapshot.get("value_float")
        if self._is_enable_path(path):
            return self._canonical_on_off(value_text)
        if hint and hint.input_kind == "numeric_ms":
            if value_float not in (None, ""):
                try:
                    milliseconds = float(value_float) * 1000.0
                    return f"{milliseconds:.{hint.decimals}f}ms"
                except ValueError:
                    pass
            return value_text.split("/", 1)[0] if "/" in value_text else value_text
        if hint and hint.input_kind == "numeric_db":
            if value_float not in (None, ""):
                try:
                    return f"{float(value_float):.1f}dB"
                except ValueError:
                    pass
        if hint and hint.input_kind == "numeric_plain":
            if value_float not in (None, ""):
                try:
                    return f"{float(value_float):.{hint.decimals}f}"
                except ValueError:
                    pass
        if hint and hint.input_kind == "enum" and hint.choices == ("Off", "On"):
            return self._canonical_on_off(value_text)
        if hint and hint.input_kind == "enum":
            return self._enum_display_value(path, value_text)
        return value_text

    def _display_system_info_value(self, label: str, value: str | None) -> str:
        text = value or ""
        if label == "Configuration State" and not text:
            return "Unavailable"
        return text

    def _set_overview_source_state(self, state: str) -> None:
        for label, variable in self.overview_source_vars.items():
            widget = self.overview_source_labels.get(label)
            if widget:
                self._set_source_indicator(widget, variable, state)

    def _set_system_source_state(self, state: str) -> None:
        for label, variable in self.system_info_source_vars.items():
            widget = self.system_info_source_labels.get(label)
            if widget:
                self._set_source_indicator(widget, variable, state)

    def _set_panel_source_state(self, panel_key: str, state: str) -> None:
        for label, variable in self.panel_source_vars.get(panel_key, {}).items():
            widget = self.panel_source_labels.get(panel_key, {}).get(label)
            if widget:
                self._set_source_indicator(widget, variable, state)

    def _confirm_write(self, path: str, value: str, mode: str) -> bool:
        if not self.confirm_writes_var.get():
            return True
        return messagebox.askyesno("Confirm Write", f"Apply {mode} write?\n\nPath: {path}\nValue: {value}")

    def _set_panel_values(self, panel_key: str, data: dict[str, str | None], source: str, *, preserve_pending: bool = True) -> None:
        pending_values: dict[str, str] = {}
        if preserve_pending:
            for label, state in self.panel_input_states.get(panel_key, {}).items():
                if state == "dirty":
                    pending_values[label] = self.panel_input_vars[panel_key][label].get()
        for label, value in data.items():
            if label in self.panel_value_vars[panel_key]:
                display = "" if value is None else str(value)
                self.panel_value_vars[panel_key][label].set(display)
                if label in pending_values and source == "live":
                    self.panel_input_baselines.setdefault(panel_key, {})[label] = display
                    if pending_values[label].strip() == display.strip():
                        self._load_panel_input_value(panel_key, label, display, state="loaded")
                    else:
                        self._set_variable_safely(self.panel_input_vars[panel_key][label], pending_values[label])
                        self._set_panel_input_state(panel_key, label, "dirty")
                else:
                    self._load_panel_input_value(panel_key, label, display, state="loaded")
        self._set_panel_source_state(panel_key, "fresh" if source == "live" else "cached")
        self._redraw_panel_graph(panel_key)
        if panel_key in COMBINED_EQ_PANEL_KEYS:
            self._redraw_combined_graph()

    def _redraw_panel_graph(self, panel_key: str) -> None:
        canvas = self.panel_graph_canvases.get(panel_key)
        if not canvas:
            return
        panel = self._panel_by_key(panel_key)
        values = {label: variable.get() for label, variable in self.panel_value_vars.get(panel_key, {}).items()}
        draw_eq_canvas(canvas, values, panel.graph_mode, panel.label)

    def _redraw_combined_graph(self) -> None:
        if not self.combined_graph_canvas:
            return
        blocks = {
            self._panel_by_key(panel_key).label: {
                label: variable.get()
                for label, variable in self.panel_value_vars.get(panel_key, {}).items()
            }
            for panel_key in COMBINED_EQ_PANEL_KEYS
        }
        visibility = {
            self._panel_by_key(panel_key).label: variable.get()
            for panel_key, variable in self.combined_visibility_vars.items()
        }
        draw_combined_eq_canvas(self.combined_graph_canvas, blocks, visibility)

    def _cached_snapshot_for_path(self, tree: dict[str, dict], path: str) -> dict:
        entry = tree.get(path, {})
        if isinstance(entry, dict):
            snapshot = entry.get("snapshot")
            if isinstance(snapshot, dict):
                return snapshot
            if "value_text" in entry or "value_percent" in entry or "value_float" in entry:
                return entry
        return {"path": path}

    def _load_cached_panels(self, cached: dict) -> None:
        tree = cached.get("tree", {})
        self.latest_tree = tree
        for panel in PANEL_SECTIONS:
            data = {label: self._display_value_for_path(path, self._cached_snapshot_for_path(tree, path)) for label, path in panel.paths.items()}
            self._set_panel_values(panel.key, data, "cached")
        for label, path in OVERVIEW_PATHS.items():
            self.overview_vars[label].set(self._display_value_for_path(path, self._cached_snapshot_for_path(tree, path)))
        self._set_overview_source_state("cached")
        for control in COMMON_CONTROLS:
            snapshot = self._cached_snapshot_for_path(tree, control.path)
            display_value = self._display_value_for_path(control.path, snapshot)
            self._set_control_values({control.key: display_value}, state="loaded", preserve_pending=False)
        for label, path in SYSTEM_INFO_PATHS.items():
            self.system_info_vars[label].set(self._display_system_info_value(label, self._cached_snapshot_for_path(tree, path).get("value_text")))
        self._set_system_source_state("cached")

    def _load_top_level_branches(self, cached: dict | None = None) -> None:
        self.favorites_list.delete(0, "end")
        branches: list[str] = []
        preferred_order = [
            "\\\\this\\Node\\UserEQ",
            "\\\\this\\Node\\BassMgmtXover",
            "\\\\this\\Node\\SpeakerEQ_Lo",
            "\\\\this\\Node\\SpeakerEQ_Hi",
            "\\\\this\\Node\\RoomEQ",
            "\\\\this\\Node\\RoomDelay",
            "\\\\this\\Node\\SpeakerTrim",
            "\\\\this\\Node\\AnalogInputMeter",
            "\\\\this\\Node\\AES1InputMeter",
            "\\\\this\\Node\\AES2InputMeter",
            "\\\\this\\Node\\OutputHiMeter",
            "\\\\this\\Node\\OutputLoMeter",
            "\\\\this\\Node\\ChannelInputMeter",
        ]
        if cached and isinstance(cached.get("tree"), dict):
            tree = cached["tree"]
            if "\\\\this\\Node" in tree:
                for child in tree["\\\\this\\Node"].get("children", []):
                    if child and child != "*":
                        branches.append(f"\\\\this\\Node\\{child}")
            if "\\\\this" in tree and "Presets" in tree["\\\\this"].get("children", []):
                branches.append("\\\\this\\Presets")
        if not branches:
            branches = FAVORITE_BRANCHES
        ordered = [path for path in preferred_order if path in branches]
        remaining = [path for path in branches if path not in ordered]
        branches = ordered + sorted(remaining)
        for path in branches:
            self.favorites_list.insert("end", path)
        self.top_level_status_var.set(f"{len(branches)} top-level branches loaded")

    def probe_speaker(self) -> None:
        self._save_runtime_config()
        def worker() -> None:
            identity = self._with_client(lambda client: client.get_identity())
            def update() -> None:
                self.identity_vars["Class Name"].set(identity.get("class_name") or "")
                self.identity_vars["Instance Name"].set(identity.get("instance_name") or "")
                self.identity_vars["Software Version"].set(identity.get("software_version") or "")
                self._set_status(
                    f"Connected to {self._host()}",
                    f"class={identity.get('class_name') or '?'} version={identity.get('software_version') or '?'}",
                )
                self.refresh_top_level_branches()
            self.root.after(0, update)
            self._enqueue_log(f"Probe ok host={self._host()} class={identity.get('class_name')!r} instance={identity.get('instance_name')!r} version={identity.get('software_version')!r}")
        self._run_in_thread("Probing speaker", worker)

    def refresh_overview(self) -> None:
        self._save_runtime_config()
        def worker() -> None:
            identity, overview = self._with_client(lambda client: (client.get_identity(), {label: client.read_path(path) for label, path in OVERVIEW_PATHS.items()}))
            def update() -> None:
                self.identity_vars["Class Name"].set(identity.get("class_name") or "")
                self.identity_vars["Instance Name"].set(identity.get("instance_name") or "")
                self.identity_vars["Software Version"].set(identity.get("software_version") or "")
                for label, snapshot in overview.items():
                    self.overview_vars[label].set(self._display_value_for_path(OVERVIEW_PATHS[label], snapshot))
                self._set_overview_source_state("fresh")
                self._set_status(f"Overview refreshed for {self._host()}", f"Identity and current-state fields updated at {time.strftime('%H:%M:%S')}")
            self.root.after(0, update)
            self._enqueue_log(f"Overview refreshed for {self._host()}")
        def fail() -> None:
            self._set_overview_source_state("error")
        self._run_in_thread("Refreshing overview", worker, on_error=fail)

    def refresh_common_controls(self) -> None:
        self._save_runtime_config()
        def worker() -> None:
            snapshots = self._with_client(lambda client: {control.key: client.read_path(control.path) for control in COMMON_CONTROLS})
            def update() -> None:
                display_values: dict[str, str] = {}
                for control in COMMON_CONTROLS:
                    snapshot = snapshots.get(control.key, {})
                    display_value = self._display_value_for_path(control.path, snapshot)
                    display_values[control.key] = display_value
                self._set_control_values(display_values, state="loaded", preserve_pending=True)
                self._set_status(f"Quick actions refreshed from {self._host()}", f"{len(COMMON_CONTROLS)} controls updated live")
            self.root.after(0, update)
        self._run_in_thread("Refreshing common controls", worker)

    def refresh_system_info(self) -> None:
        self._save_runtime_config()
        def worker() -> None:
            data = self._with_client(lambda client: client.read_many(SYSTEM_INFO_PATHS))
            def update() -> None:
                for label, value in data.items():
                    self.system_info_vars[label].set(self._display_system_info_value(label, value))
                self._set_system_source_state("fresh")
                self._set_status(f"System info refreshed from {self._host()}", f"{len(data)} metadata fields updated live")
            self.root.after(0, update)
            self._enqueue_log(f"Refreshed system info from {self._host()}")
        def fail() -> None:
            self._set_system_source_state("error")
        self._run_in_thread("Refreshing system info", worker, on_error=fail)

    def refresh_panel(self, panel_key: str) -> None:
        panel = self._panel_by_key(panel_key)
        self._save_runtime_config()
        def worker() -> None:
            snapshots = self._with_client(lambda client: {label: client.read_path(path) for label, path in panel.paths.items()})
            data = {label: self._display_value_for_path(panel.paths[label], snapshot) for label, snapshot in snapshots.items()}
            def update() -> None:
                self._set_panel_values(panel_key, data, "live")
                self._set_status(f"{panel.label} refreshed from {self._host()}", f"{len(data)} values updated live at {time.strftime('%H:%M:%S')}")
            self.root.after(0, update)
            self._enqueue_log(f"Refreshed panel {panel.label} from {self._host()}")
        def fail() -> None:
            self._set_panel_source_state(panel_key, "error")
        self._run_in_thread(f"Refreshing {panel.label}", worker, on_error=fail)

    def refresh_top_level_branches(self) -> None:
        self._save_runtime_config()
        def worker() -> None:
            branches = self._with_client(
                lambda client: [f"\\\\this\\Node\\{child}" for child in (client.list_children("\\\\this\\Node")) if child and child != "*"] + ["\\\\this\\Presets"]
            )
            def update() -> None:
                self.favorites_list.delete(0, "end")
                cached_payload = {"tree": {"\\\\this\\Node": {"children": [path.split("\\")[-1] for path in branches if path.startswith("\\\\this\\Node\\")]}, "\\\\this": {"children": ["Node", "Presets"]}}}
                self._load_top_level_branches(cached_payload)
                self.top_level_status_var.set(f"{len(branches)} top-level branches loaded live")
                self._set_status(f"Loaded top-level branches from {self._host()}", f"{len(branches)} branches available for browsing")
            self.root.after(0, update)
            self._enqueue_log(f"Loaded top-level branches from {self._host()}")
        self._run_in_thread("Loading top-level branches", worker)

    def load_cached_panel(self, panel_key: str) -> None:
        cached = load_tree_cache()
        if not cached:
            messagebox.showinfo("No Cache", f"No cached tree found at {TREE_CACHE_PATH}.")
            return
        panel = self._panel_by_key(panel_key)
        tree = cached.get("tree", {})
        data = {label: self._display_value_for_path(path, self._cached_snapshot_for_path(tree, path)) for label, path in panel.paths.items()}
        self._set_panel_values(panel_key, data, "cached")
        self._enqueue_log(f"Loaded cached values for {panel.label}")

    def apply_pending_panel_values(self, panel_key: str) -> None:
        pending = [
            label
            for label, state in self.panel_input_states.get(panel_key, {}).items()
            if state == "dirty"
        ]
        if not pending:
            messagebox.showinfo("No Pending Changes", "There are no pending values to apply on this tab.")
            return
        panel = self._panel_by_key(panel_key)
        normalized: list[tuple[str, str, str]] = []
        for label in pending:
            path = panel.paths[label]
            raw_value = self.panel_input_vars[panel_key][label].get().strip()
            hint = self.panel_input_hints.get(panel_key, {}).get(label)
            try:
                normalized_value, normalized_mode = self._normalize_write_value(path, raw_value, hint)
            except ValueError:
                messagebox.showerror("Invalid Value", f"Couldn't parse {label}.")
                return
            normalized.append((label, normalized_value, normalized_mode))
        summary = "\n".join(f"{label}: {value}" for label, value, _mode in normalized)
        if self.confirm_writes_var.get():
            if not messagebox.askyesno("Confirm Pending Writes", f"Apply all {len(normalized)} pending value(s)?\n\n{summary}"):
                return
        self._save_runtime_config()

        def worker() -> None:
            def apply(client: LSR7WebSocketClient):
                results: dict[str, dict] = {}
                for label, normalized_value, _mode in normalized:
                    path = panel.paths[label]
                    client.write_text_and_confirm(path, normalized_value)
                    results[label] = client.read_path(path)
                return results

            snapshots = self._with_client(apply)

            def update() -> None:
                for label, snapshot in snapshots.items():
                    path = panel.paths[label]
                    display_value = self._display_value_for_path(path, snapshot)
                    self.panel_value_vars[panel_key][label].set(display_value)
                    self._load_panel_input_value(panel_key, label, display_value, state="applied")
                self._set_panel_source_state(panel_key, "fresh")
                self._redraw_panel_graph(panel_key)
                self._set_status(f"Applied all {len(normalized)} pending value(s)", f"{panel.label} pending changes saved at {time.strftime('%H:%M:%S')}")

            self.root.after(0, update)
            self._enqueue_log(f"Applied {len(normalized)} pending values on {panel.label}")
            if self.auto_refresh_var.get():
                self.root.after(0, lambda: self.refresh_panel(panel_key))

        self._run_in_thread(f"Applying pending {panel.label} values", worker)

    def refresh_combined_eq(self) -> None:
        self._save_runtime_config()
        combined_panels = [self._panel_by_key(panel_key) for panel_key in COMBINED_EQ_PANEL_KEYS]

        def worker() -> None:
            def fetch(client: LSR7WebSocketClient):
                return {
                    panel.key: {label: client.read_path(path) for label, path in panel.paths.items()}
                    for panel in combined_panels
                }

            snapshots_by_panel = self._with_client(fetch)

            def update() -> None:
                for panel in combined_panels:
                    data = {
                        label: self._display_value_for_path(panel.paths[label], snapshot)
                        for label, snapshot in snapshots_by_panel[panel.key].items()
                    }
                    self._set_panel_values(panel.key, data, "live")
                self._set_status(f"Combined EQ refreshed from {self._host()}", f"{len(combined_panels)} source blocks re-read live")

            self.root.after(0, update)
            self._enqueue_log(f"Refreshed combined EQ sources from {self._host()}")

        self._run_in_thread("Refreshing combined EQ", worker)

    def load_cached_combined_eq(self) -> None:
        cached = load_tree_cache()
        if not cached:
            messagebox.showinfo("No Cache", f"No cached tree found at {TREE_CACHE_PATH}.")
            return
        tree = cached.get("tree", {})
        for panel_key in COMBINED_EQ_PANEL_KEYS:
            panel = self._panel_by_key(panel_key)
            data = {
                label: self._display_value_for_path(path, self._cached_snapshot_for_path(tree, path))
                for label, path in panel.paths.items()
            }
            self._set_panel_values(panel.key, data, "cached")
        self._enqueue_log("Loaded cached combined EQ sources")

    def write_panel_value(self, panel_key: str, label: str, *, auto_refresh: bool | None = None, instant: bool = False) -> None:
        panel = self._panel_by_key(panel_key)
        path = panel.paths[label]
        value = self.panel_input_vars[panel_key][label].get().strip()
        if not value:
            messagebox.showinfo("Value Required", f"Enter a new value for {label}.")
            return
        hint = self.panel_input_hints.get(panel_key, {}).get(label)
        try:
            normalized_value, normalized_mode = self._normalize_write_value(path, value, hint)
        except ValueError:
            messagebox.showerror("Invalid Value", f"Couldn't parse {label}.")
            return
        if not self._confirm_write(path, normalized_value, normalized_mode):
            return
        self._cancel_instant_update_job(f"panel:{panel_key}:{label}")
        self._save_runtime_config()
        def worker() -> None:
            snapshot = self._with_client(lambda client: client.write_text_and_confirm(path, normalized_value))
            def update() -> None:
                display_value = self._display_value_for_path(path, snapshot)
                self.panel_value_vars[panel_key][label].set(display_value)
                self.panel_source_vars[panel_key][label].set("live")
                self._load_panel_input_value(panel_key, label, display_value, state="applied")
                self._redraw_panel_graph(panel_key)
                self._set_status(f"Wrote {label}", f"{path} <= {normalized_value}")
            self.root.after(0, update)
            self._enqueue_log(f"Panel write ok path={path} value={normalized_value!r}")
            if auto_refresh is None:
                should_refresh = self.auto_refresh_var.get() and not instant and not self.instant_update_var.get()
            else:
                should_refresh = auto_refresh
            if should_refresh:
                self.root.after(0, lambda: self.refresh_panel(panel_key))
        thread_label = f"Instant update {label}" if instant else f"Writing {label}"
        self._run_in_thread(thread_label, worker)

    def write_common_control(self, control: LSR7Control, *, auto_refresh: bool | None = None, instant: bool = False) -> None:
        value = self.control_inputs[control.key].get().strip()
        if not value:
            messagebox.showinfo("Value Required", f"Enter a new value for {control.label}.")
            return
        hint = self._input_hint_for_path(control.path)
        try:
            normalized_value, normalized_mode = self._normalize_write_value(control.path, value, hint)
        except ValueError:
            messagebox.showerror("Invalid Value", f"Couldn't parse {control.label}.")
            return
        if not self._confirm_write(control.path, normalized_value, normalized_mode):
            return
        self._cancel_instant_update_job(f"control:{control.key}")
        self._save_runtime_config()
        def worker() -> None:
            def apply(client: LSR7WebSocketClient) -> dict:
                if normalized_mode == "percent":
                    return client.write_percent_and_confirm(control.path, float(normalized_value))
                return client.write_text_and_confirm(control.path, normalized_value)
            snapshot = self._with_client(apply)
            def update() -> None:
                display_value = self._display_value_for_path(control.path, snapshot)
                self._set_control_values({control.key: display_value}, state="applied", preserve_pending=True)
                self._set_status(f"Wrote {control.label}", f"{control.path} <= {normalized_value}")
            self.root.after(0, update)
            self._enqueue_log(f"Write ok path={control.path} value={normalized_value!r} mode={normalized_mode}")
            if auto_refresh is None:
                should_refresh = self.auto_refresh_var.get() and not instant and not self.instant_update_var.get()
            else:
                should_refresh = auto_refresh
            if should_refresh:
                self.root.after(0, self.refresh_common_controls)
        thread_label = f"Instant update {control.label}" if instant else f"Writing {control.label}"
        self._run_in_thread(thread_label, worker)

    def apply_all_quick_controls(self) -> None:
        pending = [
            control for control in COMMON_CONTROLS
            if self.control_input_states.get(control.key) == "dirty"
        ]
        if not pending:
            messagebox.showinfo("No Pending Changes", "There are no pending values to apply in Quick Actions.")
            return

        normalized: list[tuple[LSR7Control, str, str]] = []
        for control in pending:
            raw_value = self.control_inputs[control.key].get().strip()
            hint = self._input_hint_for_path(control.path)
            try:
                normalized_value, normalized_mode = self._normalize_write_value(control.path, raw_value, hint)
            except ValueError:
                messagebox.showerror("Invalid Value", f"Couldn't parse {control.label}.")
                return
            normalized.append((control, normalized_value, normalized_mode))

        summary = "\n".join(f"{control.label}: {value}" for control, value, _mode in normalized)
        if self.confirm_writes_var.get():
            if not messagebox.askyesno("Confirm Pending Writes", f"Apply all {len(normalized)} pending quick action value(s)?\n\n{summary}"):
                return

        self._save_runtime_config()

        def worker() -> None:
            def apply(client: LSR7WebSocketClient):
                results: dict[str, dict] = {}
                for control, normalized_value, normalized_mode in normalized:
                    if normalized_mode == "percent":
                        client.write_percent_and_confirm(control.path, float(normalized_value))
                    else:
                        client.write_text_and_confirm(control.path, normalized_value)
                    results[control.key] = client.read_path(control.path)
                return results

            snapshots = self._with_client(apply)

            def update() -> None:
                display_values: dict[str, str] = {}
                for control, _normalized_value, _normalized_mode in normalized:
                    snapshot = snapshots[control.key]
                    display_value = self._display_value_for_path(control.path, snapshot)
                    display_values[control.key] = display_value
                self._set_control_values(display_values, state="applied", preserve_pending=True)
                self._set_status(f"Applied all {len(normalized)} quick action value(s)", f"Quick actions saved at {time.strftime('%H:%M:%S')}")

            self.root.after(0, update)
            self._enqueue_log(f"Applied {len(normalized)} pending quick action values")
            if self.auto_refresh_var.get():
                self.root.after(0, self.refresh_common_controls)

        self._run_in_thread("Applying all quick action values", worker)

    def _apply_favorite_root(self, _event=None) -> None:
        path = self._selected_top_level_branch()
        if path:
            self.branch_root_var.set(path)
            self.load_tree()

    def open_selected_branch(self) -> None:
        selected_tree_path = self._selected_path()
        if selected_tree_path and selected_tree_path != self.current_branch_path:
            node = self.latest_tree.get(selected_tree_path, {})
            if node.get("kind") == "node":
                self.branch_root_var.set(selected_tree_path)
                self.load_tree()
                return

        selected_top_level = self._selected_top_level_branch()
        if selected_top_level:
            self.branch_root_var.set(selected_top_level)
            self.load_tree()
            return

        self.load_tree()

    def load_tree(self) -> None:
        self._save_runtime_config()
        root_path = self.branch_root_var.get().strip() or "\\\\this\\Node"
        def worker() -> None:
            result = self._with_client(lambda client: self._read_branch_level(client, root_path))
            self.root.after(0, lambda: self._populate_tree(result, root_path))
            self._enqueue_log(f"Loaded branch level host={self._host()} root={root_path} nodes={len(result)}")
        self._run_in_thread(f"Loading {root_path}", worker)

    def load_cached_tree(self) -> None:
        payload = load_tree_cache()
        if not payload:
            messagebox.showinfo("No Cache", f"No cached tree found at {TREE_CACHE_PATH}.")
            return
        tree = payload.get("tree", {})
        root_path = self.branch_root_var.get().strip() or "\\\\this\\Node"
        self._populate_tree(tree, root_path)
        self._load_cached_panels(payload)
        self._update_tree_cache_stats(tree, source=f"cache {payload.get('host', '?')}")
        self.explorer_status_var.set(f"Loaded cached tree from {TREE_CACHE_PATH.name}")
        self._enqueue_log(f"Loaded cached tree from {TREE_CACHE_PATH.resolve()}")

    def go_up_branch(self) -> None:
        current = self.branch_root_var.get().strip() or "\\\\this\\Node"
        if current in {"\\\\this", "\\\\this\\Node"}:
            self.branch_root_var.set("\\\\this\\Node")
        else:
            parent = current.rsplit("\\", 1)[0]
            self.branch_root_var.set(parent if parent else "\\\\this\\Node")
        self.load_tree()

    def read_selected_path(self) -> None:
        path = self._selected_path()
        if not path:
            messagebox.showinfo("Selection Required", "Select a path in the tree first.")
            return
        def worker() -> None:
            snapshot = self._with_client(lambda client: client.read_path(path))
            self.root.after(0, lambda: self._display_snapshot(snapshot))
            self.root.after(0, lambda: self.explorer_status_var.set(f"Read {path}"))
            self._enqueue_log(f"Read path={path}")
        self._run_in_thread(f"Reading {path}", worker)

    def pull_snapshot(self) -> None:
        self._save_runtime_config()
        root_path = self.snapshot_root_var.get().strip() or "\\\\this"
        def worker() -> None:
            output_path = Path(f"lsr7_snapshot_{time.strftime('%Y%m%d_%H%M%S')}.json")
            self._with_client(lambda client: client.export_configuration(output_path, root=root_path))
            self.root.after(0, lambda: self.explorer_status_var.set(f"Snapshot exported to {output_path.name}"))
            self.root.after(0, lambda: self._set_status(f"Snapshot exported to {output_path.name}", f"Snapshot root {root_path}"))
            self._enqueue_log(f"Snapshot exported to {output_path.resolve()}")
        self._run_in_thread(f"Snapshotting {root_path}", worker)

    def write_selected_text(self) -> None:
        path = self._selected_path()
        value = self.write_text_var.get().strip()
        if not path or not value:
            messagebox.showinfo("Selection Required", "Select a path and enter a text value first.")
            return
        if not self._confirm_write(path, value, "text"):
            return
        def worker() -> None:
            snapshot = self._with_client(lambda client: client.write_text_and_confirm(path, value))
            self.root.after(0, lambda: self._display_snapshot(snapshot))
            self.root.after(0, lambda: self.explorer_status_var.set(f"Text write ok for {path}"))
            self._enqueue_log(f"Text write ok path={path} value={value!r}")
        self._run_in_thread(f"Writing {path}", worker)

    def write_selected_percent(self) -> None:
        path = self._selected_path()
        value = self.write_percent_var.get().strip()
        if not path or not value:
            messagebox.showinfo("Selection Required", "Select a path and enter a percent value first.")
            return
        try:
            numeric = float(value)
        except ValueError:
            messagebox.showerror("Invalid Percent", "Percent must be numeric.")
            return
        if not self._confirm_write(path, value, "percent"):
            return
        def worker() -> None:
            snapshot = self._with_client(lambda client: client.write_percent_and_confirm(path, numeric))
            self.root.after(0, lambda: self._display_snapshot(snapshot))
            self.root.after(0, lambda: self.explorer_status_var.set(f"Percent write ok for {path}"))
            self._enqueue_log(f"Percent write ok path={path} value={numeric}")
        self._run_in_thread(f"Writing {path}", worker)

    def _read_branch_level(self, client: LSR7WebSocketClient, root_path: str) -> dict[str, dict]:
        tree: dict[str, dict] = {}
        children = client.try_list_children(root_path) or []
        clean_children = [child for child in children if child and child != "*"]
        tree[root_path] = {"kind": "node", "children": clean_children}
        for child in clean_children:
            path = f"{root_path}\\{child}"
            child_children = client.try_list_children(path)
            if child_children:
                clean = [item for item in child_children if item]
                if set(clean).issubset({"$", "f", "%", "r", "*", "Min", "Max", "Sensor", "Enabled", "Type", "AT", "EN"}):
                    tree[path] = {"kind": "parameter", "snapshot": client.get_parameter_snapshot(path).as_dict()}
                else:
                    tree[path] = {"kind": "node", "children": [item for item in clean if item != "*"]}
            else:
                tree[path] = client.read_path(path)
                if "kind" not in tree[path]:
                    tree[path]["kind"] = "parameter" if tree[path].get("value_text") is not None else "node"
        return tree

    def _populate_tree(self, tree: dict[str, dict], root_path: str) -> None:
        self.latest_tree = tree
        self.current_branch_path = root_path
        self.branch_root_var.set(root_path)
        self.path_to_tree_id = {}
        self.tree.delete(*self.tree.get_children())
        root_entry = tree.get(root_path, {"kind": "node", "children": []})
        root_id = self.tree.insert("", "end", text=root_path, values=(root_entry.get("kind", "node"),), open=True)
        self.path_to_tree_id[root_path] = root_id
        child_paths = [path for path in tree.keys() if path != root_path and path.rsplit("\\", 1)[0] == root_path]
        for path in sorted(child_paths):
            self.path_to_tree_id[path] = self.tree.insert(root_id, "end", text=path.split("\\")[-1], values=(tree[path].get("kind", "node"),))
        self.explorer_status_var.set(f"Loaded {len(child_paths)} items from {root_path}")
        self._set_status(f"Loaded branch {root_path}", f"{len(child_paths)} item(s) shown in the live browser")

    def _selected_path(self) -> str | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return self._path_for_tree_id(selection[0])

    def _path_for_tree_id(self, selected_id: str) -> str | None:
        for path, tree_id in self.path_to_tree_id.items():
            if tree_id == selected_id:
                return path
        return None

    def _selected_top_level_branch(self) -> str | None:
        selection = self.favorites_list.curselection()
        if not selection:
            return None
        return self.favorites_list.get(selection[0])

    def _on_tree_select(self, _event=None) -> None:
        path = self._selected_path()
        if not path:
            return
        self._display_snapshot(self._cached_snapshot_for_path(self.latest_tree, path))

    def _drill_selected_path(self, _event=None) -> None:
        row_id = self.tree.identify_row(_event.y) if _event is not None else None
        if row_id:
            self.tree.selection_set(row_id)
            path = self._path_for_tree_id(row_id)
        else:
            path = self._selected_path()
        if not path or path == self.current_branch_path:
            return
        node = self.latest_tree.get(path, {})
        if node.get("kind") == "node":
            self.branch_root_var.set(path)
            self.load_tree()
        else:
            self.read_selected_path()

    def _display_snapshot(self, snapshot: dict) -> None:
        path = snapshot.get("path", "")
        self.selected_path_var.set(path)
        self.path_value_text_var.set(self._display_value_for_path(path, snapshot))
        self.path_value_percent_var.set(snapshot.get("value_percent") or "")
        self.path_value_float_var.set(snapshot.get("value_float") or "")
        self.path_min_var.set(snapshot.get("min_text") or "")
        self.path_max_var.set(snapshot.get("max_text") or "")
        self.path_type_var.set(snapshot.get("type_name") or "")
        self.path_enabled_var.set(self._canonical_on_off(snapshot.get("enabled") or ""))
        self.path_sensor_var.set(snapshot.get("is_sensor") or "")

    def _update_tree_cache_stats(self, tree: dict[str, dict], source: str) -> None:
        stats = tree_stats(tree)
        self.tree_cache_stats_var.set(
            f"{source}: {stats['node_count']} nodes, {stats['kind_counts'].get('parameter', 0)} parameters, "
            f"SV={stats['family_counts'].get('SV', 0)} AT={stats['family_counts'].get('AT', 0)} DA={stats['family_counts'].get('DA', 0)}"
        )

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def clear_protocol_trace(self) -> None:
        self.protocol_text.configure(state="normal")
        self.protocol_text.delete("1.0", "end")
        self.protocol_text.configure(state="disabled")
        self.protocol_event_count = 0
        self.debug_summary_var.set("Protocol trace cleared")

    def _on_tab_changed(self, _event=None) -> None:
        if self._auto_refresh_inflight:
            return
        self._auto_refresh_inflight = True
        try:
            selected = self.notebook.select()
            if selected == str(self.overview_tab):
                self.refresh_overview()
                self.refresh_common_controls()
                self.refresh_system_info()
            elif selected == str(self.user_eq_tab):
                self.refresh_panel("user_eq")
            elif selected == str(self.bass_mgmt_tab):
                self.refresh_panel("bass_mgmt_xover")
            elif selected == str(self.speaker_eq_lo_tab):
                self.refresh_panel("speaker_eq_lo")
            elif selected == str(self.speaker_eq_hi_tab):
                self.refresh_panel("speaker_eq_hi")
            elif selected == str(self.room_eq_tab):
                self.refresh_panel("room_eq")
            elif selected == str(self.room_delay_tab):
                self.refresh_panel("room_delay")
            elif selected == str(self.speaker_trim_tab):
                self.refresh_panel("speaker_trim")
            elif selected == str(self.meters_tab):
                self.refresh_panel("meters")
            elif selected == str(self.combined_eq_tab):
                self.refresh_combined_eq()
            elif selected == str(self.explorer_tab):
                self.load_tree()
            elif selected == str(self.diagnostics_tab):
                self.refresh_system_info()
        finally:
            self.root.after(250, self._clear_auto_refresh_flag)

    def _clear_auto_refresh_flag(self) -> None:
        self._auto_refresh_inflight = False

    def show_text_file(self, filename: str) -> None:
        path = Path(filename)
        if not path.exists():
            self._enqueue_log(f"Missing documentation file: {filename}")
            return
        self._append_log(f"\n===== {filename} =====\n")
        self._append_log(path.read_text(encoding="utf-8"))

    def on_close(self) -> None:
        self._save_runtime_config()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = LSR7ControllerApp()
    app.run()


if __name__ == "__main__":
    main()
