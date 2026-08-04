"""Data models for click settings, profiles, and application settings.

Plain ``dataclass`` objects with explicit (de)serialization so the JSON files
stay stable and human-readable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..input.virtual_device import CLICK_BUTTONS
from ..utils.timeutil import to_seconds

# Allowed enum-like values (kept as strings for clarity in the UI).
CLICK_BUTTONS_NAMES = list(CLICK_BUTTONS.keys())  # left, right, middle
CLICK_TYPES = ["single", "double"]
MODES = ["continuous", "toggle", "hold"]
INTERVAL_UNITS = ["ms", "sec", "min", "hour"]


@dataclass
class ClickSettings:
    interval_value: float = 100.0
    interval_unit: str = "ms"          # ms | sec | min | hour
    button: str = "left"               # left | right | middle
    click_type: str = "single"         # single | double
    mode: str = "toggle"                # continuous | toggle | hold
    hotkey_code: int = 66              # KEY_F8
    hotkey_label: str = "F8"
    randomize: bool = False
    randomize_pct: float = 10.0

    def interval_seconds(self) -> float:
        return to_seconds(self.interval_value, self.interval_unit)

    def interval_ms(self) -> float:
        return self.interval_seconds() * 1000.0

    def to_dict(self) -> dict:
        return {
            "interval_value": self.interval_value,
            "interval_unit": self.interval_unit,
            "button": self.button,
            "click_type": self.click_type,
            "mode": self.mode,
            "hotkey_code": self.hotkey_code,
            "hotkey_label": self.hotkey_label,
            "randomize": self.randomize,
            "randomize_pct": self.randomize_pct,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClickSettings":
        return cls(
            interval_value=float(data.get("interval_value", 100.0)),
            interval_unit=str(data.get("interval_unit", "ms")),
            button=str(data.get("button", "left")),
            click_type=str(data.get("click_type", "single")),
            mode=str(data.get("mode", "toggle")),
            hotkey_code=int(data.get("hotkey_code", 66)),
            hotkey_label=str(data.get("hotkey_label", "F8")),
            randomize=bool(data.get("randomize", False)),
            randomize_pct=float(data.get("randomize_pct", 10.0)),
        )


@dataclass
class Profile:
    name: str = "Default"
    settings: ClickSettings = field(default_factory=ClickSettings)
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        now = time.time()
        return cls(
            name=str(data.get("name", "Default")),
            settings=ClickSettings.from_dict(data.get("settings", {})),
            created_at=float(data.get("created_at", now)),
            updated_at=float(data.get("updated_at", now)),
        )


@dataclass
class AppSettings:
    start_with_system: bool = False
    minimize_to_tray: bool = False
    close_to_tray: bool = True
    run_in_background: bool = False
    autosave: bool = True
    last_profile: str = "Default"
    start_minimized: bool = False
    theme: str = "dark"
    hotkey_backend: str = "auto"   # auto | evdev | ipc | x11

    def to_dict(self) -> dict:
        return {
            "start_with_system": self.start_with_system,
            "minimize_to_tray": self.minimize_to_tray,
            "close_to_tray": self.close_to_tray,
            "run_in_background": self.run_in_background,
            "autosave": self.autosave,
            "last_profile": self.last_profile,
            "start_minimized": self.start_minimized,
            "theme": self.theme,
            "hotkey_backend": self.hotkey_backend,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        return cls(
            start_with_system=bool(data.get("start_with_system", False)),
            minimize_to_tray=bool(data.get("minimize_to_tray", False)),
            close_to_tray=bool(data.get("close_to_tray", True)),
            run_in_background=bool(data.get("run_in_background", False)),
            autosave=bool(data.get("autosave", True)),
            last_profile=str(data.get("last_profile", "Default")),
            start_minimized=bool(data.get("start_minimized", False)),
            theme=str(data.get("theme", "dark")),
            hotkey_backend=str(data.get("hotkey_backend", "auto")),
        )
