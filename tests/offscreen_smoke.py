"""Headless integration smoke test (QT_QPA_PLATFORM=offscreen).

Boots the real MainWindow, exercises the click engine thread, profiles and the
virtual uinput device, then quits. No display server required.

Run with:  QT_QPA_PLATFORM=offscreen python tests/offscreen_smoke.py
"""
from __future__ import annotations

import os
import sys
import time

# Make the package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from autoclicker.core.models import AppSettings, ClickSettings, Profile
from autoclicker.gui.main_window import MainWindow
from autoclicker.gui.theme import apply_theme
from autoclicker.input.virtual_device import CLICK_BUTTONS, VirtualMouse, VirtualDeviceError
from autoclicker.services.profile_service import ProfileService
from autoclicker.utils.logging_setup import log


def test_virtual_device() -> None:
    """A real uinput device can be created and a click emitted."""
    try:
        with VirtualMouse() as vm:
            vm.click(CLICK_BUTTONS["left"])
            vm.click(CLICK_BUTTONS["right"])
        log.info("virtual device: OK")
        return True
    except VirtualDeviceError as exc:
        log.warning("virtual device unavailable: %s", exc)
        return False


def test_profiles() -> None:
    svc = ProfileService()
    names = svc.list_names()
    assert "Default" in names, f"Default profile missing: {names}"
    p = Profile(name="__smoke__", settings=ClickSettings(interval_value=250, interval_unit="ms"))
    svc.save(p)
    assert "__smoke__" in svc.list_names()
    loaded = svc.get("__smoke__")
    assert loaded is not None and loaded.settings.interval_value == 250
    svc.delete("__smoke__")
    assert "__smoke__" not in svc.list_names()
    log.info("profiles: OK")


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)

    states: list[bool] = []
    window = MainWindow(AppSettings())

    engine = window.engine
    assert engine.isRunning(), "click engine thread did not start"
    assert window.backend is not None
    log.info("engine thread running: OK")

    window.show()

    device_ok = test_virtual_device()
    test_profiles()

    # Drive a start/stop cycle through the real signal path. Use a long interval
    # so the test does not inject real clicks at the pointer.
    window.engine.set_settings(ClickSettings(interval_value=30, interval_unit="sec"))
    engine.stateChanged.connect(states.append)
    window.start_clicking()
    QTimer.singleShot(300, window.stop_clicking)
    QTimer.singleShot(700, lambda: (app.quit(), None))

    code = app.exec()
    assert any(states), "engine never reported Running after start_clicking()"
    assert states[-1] is False, "engine did not report Stopped after stop_clicking()"
    log.info("start/stop cycle: OK (states=%s)", states)

    # Clean shutdown.
    window.engine.stop_engine()
    window.backend.stop()
    log.info("shutdown: OK; device_available=%s", device_ok)
    return code


if __name__ == "__main__":
    sys.exit(main())
