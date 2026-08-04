"""Reusable GUI components: an animated toggle switch and a card frame."""
from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, Qt, Signal, QPoint
from PySide6.QtGui import QColor, QPainter, QIcon
from PySide6.QtWidgets import QLabel, QFrame, QWidget, QVBoxLayout, QHBoxLayout

from .theme import ACCENT, BORDER, MUTED


class ToggleSwitch(QWidget):
    """A small animated on/off switch."""

    toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = False
        self._position = 0.0
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # -- properties ---------------------------------------------------------
    def _get_position(self) -> float:
        return self._position

    def _set_position(self, value: float) -> None:
        self._position = value
        self.update()

    position = Property(float, _get_position, _set_position)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        if value == self._checked:
            return
        self._checked = value
        self._animate()
        self.toggled.emit(value)

    # -- interaction --------------------------------------------------------
    def mousePressEvent(self, _event) -> None:  # noqa: D401
        self.setChecked(not self._checked)

    def _animate(self) -> None:
        anim = QPropertyAnimation(self, b"position", self)
        anim.setDuration(160)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(self._position)
        anim.setEndValue(1.0 if self._checked else 0.0)
        anim.start()

    # -- painting -----------------------------------------------------------
    def paintEvent(self, _event) -> None:  # noqa: D401
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        radius = h / 2
        track = QColor(ACCENT) if self._checked else QColor(BORDER)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), radius, radius)

        handle = h - 6
        x = 3 + self._position * (self.width() - handle - 6)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(int(x), 3, handle, handle)
        painter.end()


class Card(QFrame):
    """A rounded panel used to group related controls."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(10)
        if title:
            label = MutedTitle(title)
            self._layout.addWidget(label)

    def addRow(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def card_layout(self) -> QVBoxLayout:
        return self._layout


class MutedTitle(QLabel):
    """A small muted section heading used inside cards."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("title")


class StatCard(QFrame):
    """A compact statistic tile (label on top, big value below)."""

    def __init__(self, label: str, value: str = "0", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._label = QLabel(label)
        self._label.setObjectName("statlabel")
        self._value = QLabel(value)
        self._value.setObjectName("big")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class IconHelper:
    """Draws simple themed icons (no external asset files required)."""

    @staticmethod
    def app_icon() -> "QIcon":  # noqa: D401
        from PySide6.QtGui import QColor, QPainter, QPixmap

        size = 64
        pix = QPixmap(size, size)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # round background
        painter.setBrush(QColor(ACCENT))
        painter.setPen(QColor(0, 0, 0, 0))
        painter.drawRoundedRect(2, 2, size - 4, size - 4, 16, 16)
        # cursor arrow
        painter.setBrush(QColor("#ffffff"))
        painter.drawPolygon([
            QPoint(20, 16),
            QPoint(44, 30),
            QPoint(34, 32),
            QPoint(36, 46),
            QPoint(30, 48),
            QPoint(28, 34),
            QPoint(18, 42),
        ])
        painter.end()
        return QIcon(pix)
