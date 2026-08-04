"""Diagnostics page — shows exactly why each hotkey backend is (un)available.

No silent failures: every capability is probed and displayed, and the reason a
backend is unavailable is shown verbatim.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..input.hotkey_backends import backend_unavailable_reason, collect_diagnostics
from .components import Card


class DiagnosticsDialog(QDialog):
    def __init__(self, current_backend: str, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnostics")
        self.setMinimumWidth(480)

        data = collect_diagnostics()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        summary = Card()
        s = summary.card_layout()
        self._row(s, "Session", data["session"].upper())
        self._row(s, "Compositor", data["compositor"].title())
        self._row(s, "/dev/input readable", _ok(data["input_readable"]))
        self._row(s, "/dev/uinput writable", _ok(data["uinput_writable"]))
        self._row(s, "IPC available", _ok(data["ipc_available"]))
        self._row(s, "IPC socket", data["ipc_path"])
        self._row(s, "Current backend", current_backend)
        root.addWidget(summary)

        backends = Card(title="Backends")
        b = backends.card_layout()
        for name in ("evdev", "ipc", "x11", "windows"):
            info = data["backends"][name]
            status = _ok(info["available"])
            reason = info["reason"] or "—"
            self._row(b, f"{name}", f"{status}   {reason}")
        root.addWidget(backends)

        hint = QLabel(
            "Если ни один бэкенд не активен: на Wayland без группы 'input' "
            "используйте IPC (бинд композитора → autoclickerctl), либо добавьте "
            "пользователя в группу 'input' для evdev."
        )
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        root.addWidget(hint)

    @staticmethod
    def _row(layout, label: str, value: str) -> None:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 2, 0, 2)
        l = QLabel(label)
        l.setObjectName("muted")
        v = QLabel(str(value))
        v.setWordWrap(True)
        hl.addWidget(l)
        hl.addWidget(v, stretch=1)
        layout.addWidget(row)


def _ok(flag: bool) -> str:
    return "✔ yes" if flag else "✘ no"
