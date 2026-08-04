"""Virtual mouse device built directly on the Linux ``uinput`` interface.

No external programs (xdotool / ydotool) and no shell commands are used — we
talk to the kernel via ``ctypes``. The compositor sees the device as a real
mouse, so emitted button events become clicks at the current pointer position.
"""
from __future__ import annotations

import fcntl
import os
import struct

from ..utils.logging_setup import log

# uinput ioctls (from <linux/uinput.h>)
UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_RELBIT = 0x40045566
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502

# input-event-codes.h
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
SYN_REPORT = 0

BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112

# Friendly name -> button code used for *clicking*.
CLICK_BUTTONS: dict[str, int] = {
    "left": BTN_LEFT,
    "right": BTN_RIGHT,
    "middle": BTN_MIDDLE,
}

_UINPUT_DEV = "/dev/uinput"


class VirtualDeviceError(RuntimeError):
    """Raised when the virtual input device cannot be created."""


class VirtualMouse:
    """A virtual mouse that injects button events through ``uinput``."""

    def __init__(self, name: str = "ZCode Autoclicker") -> None:
        self._name = name
        self._fd: int | None = None
        try:
            self._fd = os.open(_UINPUT_DEV, os.O_WRONLY)
        except OSError as exc:
            raise VirtualDeviceError(
                f"Cannot open {_UINPUT_DEV}: {exc}\n"
                "Add your user to the 'uinput' group or run as root."
            ) from exc

        try:
            for code in CLICK_BUTTONS.values():
                fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_KEY)
                fcntl.ioctl(self._fd, UI_SET_KEYBIT, code)
            fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_REL)
            fcntl.ioctl(self._fd, UI_SET_RELBIT, 0)  # REL_X
            fcntl.ioctl(self._fd, UI_SET_RELBIT, 1)  # REL_Y

            name_b = (name.encode("utf-8") + b"\x00")[:80]
            dev = struct.pack(
                "<80sHHHHI256i",
                name_b, 0, 0, 0, 0, 0, *([0] * 256),
            )
            os.write(self._fd, dev)
            fcntl.ioctl(self._fd, UI_DEV_CREATE)
        except OSError as exc:
            self._safe_close()
            raise VirtualDeviceError(f"Failed to create uinput device: {exc}") from exc

        # Give the kernel a moment to register the device.
        import time

        time.sleep(0.05)
        log.info("Virtual mouse device '%s' created", name)

    # -- public API ---------------------------------------------------------
    def press(self, btn: int) -> None:
        self._emit(EV_KEY, btn, 1)
        self._emit(EV_SYN, SYN_REPORT, 0)

    def release(self, btn: int) -> None:
        self._emit(EV_KEY, btn, 0)
        self._emit(EV_SYN, SYN_REPORT, 0)

    def click(self, btn: int, double: bool = False) -> None:
        """Perform a single (or double) click at the current pointer position."""
        self.press(btn)
        self.release(btn)
        if double:
            import time

            time.sleep(0.05)
            self.press(btn)
            self.release(btn)

    def close(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.ioctl(self._fd, UI_DEV_DESTROY)
        except OSError as exc:  # pragma: no cover
            log.warning("uinput destroy ioctl failed: %s", exc)
        self._safe_close()
        log.info("Virtual mouse device '%s' destroyed", self._name)

    # -- internals ----------------------------------------------------------
    def _emit(self, etype: int, code: int, value: int) -> None:
        if self._fd is None:
            return
        buf = struct.pack("<qqHHi", 0, 0, etype, code, value)
        try:
            os.write(self._fd, buf)
        except OSError as exc:  # pragma: no cover
            log.error("uinput write failed: %s", exc)

    def _safe_close(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

    def __enter__(self) -> "VirtualMouse":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
