"""Dark theme: palette + stylesheet for a modern, flat look."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Palette
BG = "#1b1b22"
PANEL = "#23232c"
PANEL2 = "#2b2b36"
CARD = "#20202a"
BORDER = "#34343f"
TEXT = "#e7e7ee"
MUTED = "#9a9aab"
ACCENT = "#7c6cff"     # violet
ACCENT_HOVER = "#8f80ff"
BLUE = "#4f8cff"
GREEN = "#3ddc84"
RED = "#ff5c7c"
AMBER = "#ffb454"

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-family: 'Inter', 'Segoe UI', 'Noto Sans', sans-serif;
    font-size: 13px;
}}
QFrame#card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#title {{ font-size: 15px; font-weight: 600; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 12px; }}
QLabel#muted {{ color: {MUTED}; font-size: 12px; }}
QLabel#big {{ font-size: 22px; font-weight: 700; }}
QLabel#statlabel {{ color: {MUTED}; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }}

QPushButton {{
    background: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 16px;
    color: {TEXT};
}}
QPushButton:hover {{ background: #34343f; }}
QPushButton:pressed {{ background: #3c3c49; }}
QPushButton:disabled {{ color: {MUTED}; background: {PANEL}; }}

QPushButton#primary {{ background: {ACCENT}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#danger {{ background: {RED}; border: none; font-weight: 600; }}
QPushButton#danger:hover {{ background: #ff7488; }}
QPushButton#ghost {{ background: transparent; border: 1px solid {BORDER}; }}

QComboBox {{
    background: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 12px;
}}
QComboBox:hover {{ border: 1px solid {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    selection-background-color: {ACCENT};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QSpinBox, QDoubleSpinBox {{
    background: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 12px;
}}
QSpinBox:hover, QDoubleSpinBox:hover {{ border: 1px solid {ACCENT}; }}

QSlider::groove:horizontal {{
    height: 6px; border-radius: 3px; background: {BORDER};
}}
QSlider::handle:horizontal {{
    width: 16px; height: 16px; margin: -5px 0; border-radius: 8px;
    background: {ACCENT};
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT_HOVER}; }}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 12px;
    margin-top: 12px; padding: 14px 12px 10px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 14px; padding: 0 6px;
    color: {MUTED}; font-size: 12px;
}}

QMenu {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; }}

QScrollArea {{ border: none; }}
QStatusBar {{ background: {PANEL}; color: {MUTED}; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL2))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL2))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
