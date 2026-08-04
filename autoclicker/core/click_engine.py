"""Click engine.

Runs the actual clicking loop on a dedicated thread so the GUI never blocks.
Communication with the GUI is one-directional signalling; commands from the
GUI (start/stop/toggle/hold) flip a small amount of shared, lock-protected
state and wake the loop. Timing uses an interruptible wait so a "stop" or
"release" is honoured promptly instead of busy-waiting.
"""
from __future__ import annotations

import random
import threading
import time
from collections import deque

from PySide6.QtCore import QThread, Signal

from ..input.virtual_device import CLICK_BUTTONS, VirtualDeviceError, VirtualMouse
from ..utils.logging_setup import log


class ClickEngine(QThread):
    """Emits mouse clicks through a virtual uinput device."""

    clicked = Signal(int)        # cumulative click count
    stateChanged = Signal(bool)  # True while clicking
    error = Signal(str)
    started = Signal()
    stopped = Signal()

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        from ..core.models import ClickSettings

        self._settings = ClickSettings()
        self._device: VirtualMouse | None = None
        self._active = False
        self._stop = False
        self._total = 0
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()
        self._wake = threading.Event()

    # -- public API (called from GUI thread) --------------------------------
    def set_settings(self, settings) -> None:
        with self._lock:
            self._settings = settings

    def set_active(self, active: bool) -> None:
        with self._lock:
            if self._active == active:
                return
            self._active = active
        self.stateChanged.emit(active)
        self._wake.set()

    def toggle(self) -> None:
        with self._lock:
            self._active = not self._active
            active = self._active
        self.stateChanged.emit(active)
        self._wake.set()

    def set_holding(self, holding: bool) -> None:
        self.set_active(holding)

    def stop_engine(self) -> None:
        with self._lock:
            self._stop = True
        self._wake.set()
        self.wait()

    # -- runtime ------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 - QThread entry point
        self.started.emit()
        log.info("Click engine thread started")

        while True:
            with self._lock:
                if self._stop:
                    break
                active = self._active
                settings = self._settings

            if active:
                if not self._ensure_device():
                    # Device creation failed; stop clicking and surface it.
                    self.stateChanged.emit(False)
                    with self._lock:
                        self._active = False
                    self._wake.clear()
                    self._wake.wait(0.06)
                    continue
                self._do_click(settings)
                interval = settings.interval_seconds()
                if settings.randomize:
                    jitter = settings.randomize_pct / 100.0
                    interval *= 1.0 + random.uniform(-jitter, jitter)
                interval = max(0.001, interval)
                self._wake.clear()
                self._wake.wait(interval)
            else:
                self._wake.clear()
                self._wake.wait(0.06)

        if self._device is not None:
            self._device.close()
        self.stopped.emit()
        log.info("Click engine thread stopped (total=%d)", self._total)

    # -- internals ----------------------------------------------------------
    def _ensure_device(self) -> bool:
        """Create the virtual device on first use. Returns True on success."""
        if self._device is not None:
            return True
        try:
            self._device = VirtualMouse()
        except VirtualDeviceError as exc:
            log.error("Click engine cannot create device: %s", exc)
            self.error.emit(str(exc))
            self._device = None
            return False
        return True

    def _do_click(self, settings) -> None:
        if self._device is None:
            return
        btn = CLICK_BUTTONS.get(settings.button, CLICK_BUTTONS["left"])
        double = settings.click_type == "double"

        self._device.press(btn)
        self._stamp()
        self._device.release(btn)
        if double:
            time.sleep(0.05)
            self._device.press(btn)
            self._stamp()
            self._device.release(btn)

        with self._lock:
            self._total += 2 if double else 1
        self.clicked.emit(self._total)

    def _stamp(self) -> None:
        now = time.monotonic()
        with self._lock:
            self._stamps.append(now)

    def cps(self) -> float:
        """Measured clicks-per-second over the last 1 second window."""
        now = time.monotonic()
        with self._lock:
            while self._stamps and now - self._stamps[0] > 1.0:
                self._stamps.popleft()
            return float(len(self._stamps))

    def total_clicks(self) -> int:
        with self._lock:
            return self._total
