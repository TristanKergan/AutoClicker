"""Application settings dialog (autostart, tray, background, autosave, backend)."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ..core.models import AppSettings
from ..utils.platform import detect_compositor
from .components import Card, ToggleSwitch

BACKEND_CHOICES = ["Auto", "Evdev", "IPC", "X11"]


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("App settings")
        self.setMinimumWidth(440)
        self._settings = settings

        info = detect_compositor()
        compositor_line = (
            f"Session: {info['compositor'].title()} "
            f"({'Wayland' if info['wayland'] else 'X11' if info['x11'] else 'unknown'})"
        )

        self._start_system = self._row("Start with system", settings.start_with_system,
                                       "Add a .desktop file to ~/.config/autostart")
        self._minimize_tray = self._row("Minimize to tray", settings.minimize_to_tray)
        self._close_tray = self._row("Close to tray", settings.close_to_tray,
                                     "Keep running in the tray when the window is closed")
        self._background = self._row("Run in background", settings.run_in_background,
                                     "Lower priority / no foreground focus when clicking")
        self._autosave = self._row("Autosave", settings.autosave,
                                   "Save settings and the active profile on change")
        self._start_min = self._row("Start minimized", settings.start_minimized)

        behaviour = Card(title="Behaviour")
        for switch, label in (
            self._start_system,
            self._minimize_tray,
            self._close_tray,
            self._background,
            self._autosave,
            self._start_min,
        ):
            behaviour.card_layout().addWidget(self._labeled(switch, label))

        note = QLabel(compositor_line)
        note.setObjectName("subtitle")
        behaviour.card_layout().addWidget(note)

        # Hotkey backend selector.
        backend_card = Card(title="Global hotkey backend")
        backend_layout = QVBoxLayout()
        self._backend_box = QComboBox()
        self._backend_box.addItems(BACKEND_CHOICES)
        self._backend_box.setCurrentText(settings.hotkey_backend.title())
        backend_layout.addWidget(self._labeled_combo(self._backend_box,
                                  "Backend (Auto picks the best for this session)"))
        be_note = QLabel(
            "IPC mode needs no special permissions: bind a compositor key to "
            "'autoclickerctl toggle'. Evdev needs the 'input' group."
        )
        be_note.setObjectName("subtitle")
        be_note.setWordWrap(True)
        backend_layout.addWidget(be_note)
        backend_card.card_layout().addLayout(backend_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(behaviour)
        layout.addWidget(backend_card)
        layout.addWidget(buttons)

    # -- helpers -------------------------------------------------------------
    def _row(self, text: str, checked: bool, tooltip: str = "") -> tuple[ToggleSwitch, str]:
        switch = ToggleSwitch()
        switch.setChecked(checked)
        if tooltip:
            switch.setToolTip(tooltip)
        return switch, text

    def _labeled(self, switch: ToggleSwitch, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("label")
        label.mousePressEvent = lambda _e: switch.setChecked(not switch.isChecked())  # type: ignore[assignment]
        return label

    def _labeled_combo(self, combo: QComboBox, text: str) -> QWidget:
        row = Card()
        rl = QVBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        rl.addWidget(QLabel(text))
        rl.addWidget(combo)
        return row

    # -- result --------------------------------------------------------------
    def apply(self) -> AppSettings:
        self._settings.start_with_system = self._start_system[0].isChecked()
        self._settings.minimize_to_tray = self._minimize_tray[0].isChecked()
        self._settings.close_to_tray = self._close_tray[0].isChecked()
        self._settings.run_in_background = self._background[0].isChecked()
        self._settings.autosave = self._autosave[0].isChecked()
        self._settings.start_minimized = self._start_min[0].isChecked()
        self._settings.hotkey_backend = self._backend_box.currentText().lower()
        return self._settings
