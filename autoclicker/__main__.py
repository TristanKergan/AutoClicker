"""Application entry point: ``python -m autoclicker``.

Sets up logging, applies the dark theme, boots the click engine + key monitor
on background threads and shows the main window. Designed to run natively on a
Wayland session (niri / Hyprland / Sway / GNOME / KDE) without X11.
"""
from __future__ import annotations

import argparse
import signal
import sys

from PySide6.QtWidgets import QApplication

from .core.models import AppSettings
from .gui.main_window import MainWindow
from .gui.theme import apply_theme
from .services.settings_service import SettingsService
from .utils.logging_setup import log, setup_logging


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ZCode Auto Clicker (Wayland)")
    parser.add_argument("--start-minimized", action="store_true",
                        help="Start hidden in the system tray if available")
    parser.add_argument("--self-test", action="store_true",
                        help="Start, run briefly, then quit (used by integration tests)")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser.parse_args()


def main() -> int:
    setup_logging()
    args = _parse_args()

    if args.version:
        from . import __version__
        print(f"autoclicker {__version__}")
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("ZCode Auto Clicker")
    app.setApplicationDisplayName("ZCode Auto Clicker")
    apply_theme(app)

    settings = SettingsService().load()

    window = MainWindow(settings)
    window.setWindowIcon(window.windowIcon())
    # Ensure background threads stop before the process tears down.
    app.aboutToQuit.connect(window._shutdown)

    # Allow Ctrl-C / SIGTERM to quit cleanly.
    def _quit(*_args) -> None:
        window.close()
        app.quit()

    signal.signal(signal.SIGINT, _quit)
    signal.signal(signal.SIGTERM, _quit)
    # Keep Python's signal handling responsive inside the Qt loop.
    from PySide6.QtCore import QTimer
    QTimer(app).start(500)

    if args.start_minimized:
        if window._tray_usable():
            window.hide()
        else:
            window.showMinimized()
    else:
        window.show()

    if args.self_test:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, app.quit)

    log.info("Application started")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
