"""Persistence of application settings (JSON under ``~/.config``)."""
from __future__ import annotations

import json
import os

from ..core.models import AppSettings
from ..utils.logging_setup import log

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "autoclicker")


class SettingsService:
    def __init__(self, directory: str = CONFIG_DIR) -> None:
        self.directory = directory
        self.path = os.path.join(directory, "settings.json")
        os.makedirs(directory, exist_ok=True)

    def load(self) -> AppSettings:
        try:
            with open(self.path, encoding="utf-8") as fh:
                return AppSettings.from_dict(json.load(fh))
        except (OSError, ValueError) as exc:
            log.info("Using default settings (%s)", exc)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(settings.to_dict(), fh, indent=2)
        except OSError as exc:  # pragma: no cover - permissions
            log.warning("Could not save settings: %s", exc)
