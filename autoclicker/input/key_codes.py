"""Linux keycode <-> human label mapping.

Used both for the hotkey capture dialog and for the global key monitor. Values
follow ``linux/input-event-codes.h``.
"""
from __future__ import annotations

# name (upper-case) -> Linux keycode
KEY_NAME_TO_CODE: dict[str, int] = {
    # Function keys
    "F1": 59, "F2": 60, "F3": 61, "F4": 62, "F5": 63, "F6": 64,
    "F7": 65, "F8": 66, "F9": 67, "F10": 68, "F11": 87, "F12": 88,
    # Editing / navigation
    "ESC": 1, "BACKSPACE": 14, "TAB": 15, "ENTER": 28, "SPACE": 57,
    "CAPSLOCK": 58, "NUMLOCK": 69, "SCROLLLOCK": 70,
    "INSERT": 110, "DELETE": 111, "HOME": 102, "END": 107,
    "PAGEUP": 104, "PAGEDOWN": 109, "PRINT": 99, "PAUSE": 119,
    "UP": 103, "DOWN": 108, "LEFT": 105, "RIGHT": 106,
    # Modifiers
    "LCTRL": 29, "RCTRL": 97, "LALT": 56, "RALT": 100,
    "LSHIFT": 42, "RSHIFT": 54, "LSUPER": 125, "RSUPER": 126,
    "CTRL": 29, "ALT": 56, "SHIFT": 42, "SUPER": 125,
    # Letters
    "A": 30, "B": 48, "C": 46, "D": 32, "E": 18, "F": 33, "G": 34,
    "H": 35, "I": 23, "J": 36, "K": 37, "L": 38, "M": 50, "N": 49,
    "O": 24, "P": 25, "Q": 16, "R": 19, "S": 31, "T": 20, "U": 22,
    "V": 47, "W": 17, "X": 45, "Y": 21, "Z": 44,
    # Digits
    "0": 11, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6,
    "6": 7, "7": 8, "8": 9, "9": 10,
    # Mouse side buttons (BTN_SIDE / BTN_EXTRA)
    "MOUSE4": 275, "MOUSE5": 276,
}

# Friendly labels for codes we know (everything else falls back to its name).
_CODE_TO_LABEL: dict[int, str] = {
    1: "Esc", 14: "Backspace", 15: "Tab", 28: "Enter", 57: "Space",
    58: "Caps Lock", 59: "F1", 60: "F2", 61: "F3", 62: "F4", 63: "F5",
    64: "F6", 65: "F7", 66: "F8", 67: "F9", 68: "F10", 87: "F11",
    88: "F12", 69: "Num Lock", 70: "Scroll Lock", 99: "Print",
    119: "Pause", 110: "Insert", 111: "Delete", 102: "Home", 107: "End",
    104: "Page Up", 109: "Page Down", 103: "Up", 108: "Down",
    105: "Left", 106: "Right", 29: "Left Ctrl", 97: "Right Ctrl",
    56: "Left Alt", 100: "Right Alt", 42: "Left Shift", 54: "Right Shift",
    125: "Left Super", 126: "Right Super", 275: "Mouse 4", 276: "Mouse 5",
    30: "A", 48: "B", 46: "C", 32: "D", 18: "E", 33: "F", 34: "G",
    35: "H", 23: "I", 36: "J", 37: "K", 38: "L", 50: "M", 49: "N",
    24: "O", 25: "P", 16: "Q", 19: "R", 31: "S", 20: "T", 22: "U",
    47: "V", 17: "W", 45: "X", 21: "Y", 44: "Z",
    11: "0", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7",
    9: "8", 10: "9",
}

# Qt::Key -> Linux keycode (used only as a fallback when global capture is
# unavailable and we capture a key press inside the dialog window).
_QT_TO_LINUX: dict[int, int] = {
    32: 57,  # Space
}
# Build the rest from Qt's Key enum dynamically if available.
try:  # pragma: no cover - depends on PySide6 being importable
    from PySide6.QtCore import Qt

    # Single-char keys (letters + digits) come straight from our master map.
    for _name, _code in KEY_NAME_TO_CODE.items():
        if len(_name) == 1 and _name.isalnum():
            _qt_key = getattr(Qt, f"Key_{_name}", None)
            if _qt_key is not None:
                _QT_TO_LINUX[_qt_key] = _code
    _QT_TO_LINUX[Qt.Key_F1] = 59
    _QT_TO_LINUX[Qt.Key_F2] = 60
    _QT_TO_LINUX[Qt.Key_F3] = 61
    _QT_TO_LINUX[Qt.Key_F4] = 62
    _QT_TO_LINUX[Qt.Key_F5] = 63
    _QT_TO_LINUX[Qt.Key_F6] = 64
    _QT_TO_LINUX[Qt.Key_F7] = 65
    _QT_TO_LINUX[Qt.Key_F8] = 66
    _QT_TO_LINUX[Qt.Key_F9] = 67
    _QT_TO_LINUX[Qt.Key_F10] = 68
    _QT_TO_LINUX[Qt.Key_F11] = 87
    _QT_TO_LINUX[Qt.Key_F12] = 88
    _QT_TO_LINUX[Qt.Key_Escape] = 1
    _QT_TO_LINUX[Qt.Key_Tab] = 15
    _QT_TO_LINUX[Qt.Key_Enter] = 28
    _QT_TO_LINUX[Qt.Key_Return] = 28
    _QT_TO_LINUX[Qt.Key_Backspace] = 14
    _QT_TO_LINUX[Qt.Key_Delete] = 111
    _QT_TO_LINUX[Qt.Key_Home] = 102
    _QT_TO_LINUX[Qt.Key_End] = 107
    _QT_TO_LINUX[Qt.Key_PageUp] = 104
    _QT_TO_LINUX[Qt.Key_PageDown] = 109
    _QT_TO_LINUX[Qt.Key_Up] = 103
    _QT_TO_LINUX[Qt.Key_Down] = 108
    _QT_TO_LINUX[Qt.Key_Left] = 105
    _QT_TO_LINUX[Qt.Key_Right] = 106
    _QT_TO_LINUX[Qt.Key_Control] = 29
    _QT_TO_LINUX[Qt.Key_Alt] = 56
    _QT_TO_LINUX[Qt.Key_Shift] = 42
    _QT_TO_LINUX[Qt.Key_Meta] = 125
except Exception:  # pragma: no cover
    pass


def code_to_label(code: int) -> str:
    return _CODE_TO_LABEL.get(code, f"Key{code}")


def name_to_code(name: str) -> int:
    key = name.upper().strip()
    if key in KEY_NAME_TO_CODE:
        return KEY_NAME_TO_CODE[key]
    if key.startswith("KEY_"):
        base = key[4:]
        if base in KEY_NAME_TO_CODE:
            return KEY_NAME_TO_CODE[base]
    raise KeyError(f"Unknown key: {name}")


def qt_key_to_code(qt_key: int) -> int | None:
    return _QT_TO_LINUX.get(qt_key)
