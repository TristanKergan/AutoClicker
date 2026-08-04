"""ZCode Auto Clicker — a Wayland-native autoclicker with a PySide6 GUI.

The application injects mouse clicks through a virtual ``uinput`` device and
reads an optional global hotkey straight from the Linux input layer, so it
works on Wayland compositors without X11 or any external helper program.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
