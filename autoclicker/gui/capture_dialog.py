"""'Press any key' dialog for assigning a global hotkey.

Delegates capture to the active :class:`HotkeyBackend`:

* evdev / X11 backends capture the key globally (any window) and emit
  ``key_captured(code, label)``.
* IPC backend cannot capture (the key is bound in the compositor), so the
  dialog explains how to use ``autoclickerctl`` instead.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..input.hotkey_backends import ipc_socket_path
from .components import MutedTitle


class CaptureDialog(QDialog):
    def __init__(
        self,
        backend,
        current_code: int,
        current_label: str,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign hotkey")
        self.setMinimumWidth(360)
        self._backend = backend
        self._result_code = current_code
        self._result_label = current_label

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        if backend.can_capture():
            self._build_capture_ui(backend, current_label, layout)
        else:
            self._build_ipc_ui(layout)

    # -- capture-capable backends -----------------------------------------
    def _build_capture_ui(self, backend, current_label, layout) -> None:
        layout.addWidget(MutedTitle("Press any key…"))
        hint = QLabel(
            "Focus this window and press the key or mouse button you want to use.\n"
            "Esc cancels without changing the hotkey."
        )
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        current = QLabel(f"Current: <b>{current_label}</b>")
        current.setObjectName("muted")
        layout.addWidget(current)

        cancel = QPushButton("Cancel")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.reject)
        layout.addStretch(1)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignRight)

        backend.key_captured.connect(self._on_captured)
        backend.begin_capture()

    def _on_captured(self, code: int, label: str) -> None:
        self._result_code = code
        self._result_label = label
        self.accept()

    def done(self, result: int) -> None:  # type: ignore[override]
        # Always leave capture mode, whether the user picked a key or cancelled.
        try:
            self._backend.end_capture()
        except Exception:
            pass
        super().done(result)

    # -- IPC backend (no capture) -----------------------------------------
    def _build_ipc_ui(self, layout) -> None:
        layout.addWidget(MutedTitle("IPC mode — bind in your compositor"))
        info = QLabel(
            "Global key capture is unavailable in IPC mode. Instead, bind a key in "
            "your compositor to the <b>autoclickerctl</b> helper. Copy an example "
            "for your compositor below and add it to its config, then reload it."
        )
        info.setObjectName("subtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        examples = (
            "# niri (~/.config/niri/config.kdl)\n"
            "binds {\n"
            '    "F8" { spawn "autoclickerctl" "toggle"; }\n'
            "}\n\n"
            "# Sway / Hyprland (~/.config/sway/config)\n"
            'bindsym F8 exec autoclickerctl toggle\n'
            "# Hyprland (~/.config/hypr/hyprland.conf)\n"
            "bind = , F8, exec, autoclickerctl toggle\n\n"
            f"# socket: {ipc_socket_path()}\n"
            "# commands: start | stop | toggle | pause"
        )
        box = QTextEdit()
        box.setPlainText(examples)
        box.setReadOnly(True)
        layout.addWidget(box)

        copy = QPushButton("Copy niri example")
        copy.setObjectName("ghost")
        copy.clicked.connect(lambda: self._copy(examples))
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(copy)
        row.addWidget(close)
        layout.addLayout(row)

    def _copy(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    # -- results -----------------------------------------------------------
    @property
    def result_code(self) -> int:
        return self._result_code

    @property
    def result_label(self) -> str:
        return self._result_label
