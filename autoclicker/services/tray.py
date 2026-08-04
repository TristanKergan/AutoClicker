"""System tray icon wrapper.

On Wayland the availability of a system tray depends on the compositor / a
status-notifier host (e.g. a waybar tray module). The app checks
``isSystemTrayAvailable()`` before relying on tray behaviour and degrades
gracefully (minimize to taskbar instead of hiding) when there is no tray.
"""
from __future__ import annotations

from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..utils.logging_setup import log


class TrayIcon(QSystemTrayIcon):
    def __init__(self, icon, parent=None) -> None:
        super().__init__(icon, parent)
        self.setToolTip("ZCode Auto Clicker")

        menu = QMenu()
        self.show_action = menu.addAction("Show")
        self.start_action = menu.addAction("Start")
        self.stop_action = menu.addAction("Stop")
        menu.addSeparator()
        self.quit_action = menu.addAction("Quit")
        self.setContextMenu(menu)

        self.activated.connect(self._on_activate)

    def _on_activate(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_action.triggered.emit()
