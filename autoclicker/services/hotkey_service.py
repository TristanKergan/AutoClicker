"""Hotkey service: maps backend events to click-engine actions.

The service knows *nothing* about how a hotkey is detected. It only consumes
the :class:`HotkeyBackend` interface:

* ``activated``  -> toggle (toggle/continuous) or press (hold)
* ``deactivated`` -> release (hold mode)

Mode and the bound key come from the settings callback, so the same service
works for every backend (evdev, IPC, X11, Windows).
"""
from __future__ import annotations

from PySide6.QtCore import QObject

from ..core.models import ClickSettings
from ..input.hotkey_backends import HotkeyBackend


class HotkeyService(QObject):
    def __init__(
        self,
        engine,
        backend: HotkeyBackend,
        get_settings,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._get_settings = get_settings
        self._backend: HotkeyBackend | None = None
        self.set_backend(backend)

    def set_backend(self, backend: HotkeyBackend) -> None:
        """Swap the active backend (e.g. when the user changes the mode)."""
        if self._backend is not None:
            try:
                self._backend.activated.disconnect(self._on_activated)
                self._backend.deactivated.disconnect(self._on_deactivated)
            except (TypeError, RuntimeError):
                pass
        self._backend = backend
        backend.activated.connect(self._on_activated)
        backend.deactivated.connect(self._on_deactivated)

    def sync_hotkey(self) -> None:
        """Push the currently-bound key to the backend."""
        if self._backend is not None:
            self._backend.set_hotkey(self._get_settings().hotkey_code)

    def _on_activated(self) -> None:
        settings: ClickSettings = self._get_settings()
        if settings.mode in ("toggle", "continuous"):
            self._engine.toggle()
        elif settings.mode == "hold":
            self._engine.set_active(True)

    def _on_deactivated(self) -> None:
        if self._get_settings().mode == "hold":
            self._engine.set_active(False)
