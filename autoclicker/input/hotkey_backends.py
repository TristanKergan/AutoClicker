"""Cross-platform global hotkey backends.

The application talks to hotkeys only through the :class:`HotkeyBackend`
interface. Concrete backends implement the same contract but use completely
different mechanisms:

* :class:`EvdevBackend` — reads ``/dev/input/event*`` directly (Linux, needs
  read access to input devices). Works regardless of the focused window.
* :class:`WaylandIPCBackend` — a Unix-domain socket server. A companion CLI
  (``autoclickerctl``) sends ``start`` / ``stop`` / ``toggle`` / ``pause``.
  This is the recommended Wayland fallback because it needs **no** special
  group membership: the user binds a compositor key to ``autoclickerctl``.
* :class:`X11Backend` — real ``XGrabKey`` via ctypes on X11 sessions.
* :class:`WindowsBackend` — ``RegisterHotKey`` via ctypes (Win32 only; the
  architecture is ready, the code path simply never runs off Windows).
* :class:`DummyBackend` — always unavailable; used as a safe fallback.

A backend is chosen automatically from the platform and the available
capabilities (see :func:`create_backend`), or forced by the user in the
settings (Auto / Evdev / IPC / X11).

No polling, no busy-loops: every backend blocks on its source (evdev
``read``, IPC ``accept``/``recv``, X11 ``XNextEvent``). Threads are always
joined on :meth:`HotkeyBackend.stop`.
"""
from __future__ import annotations

import ctypes
import glob
import os
import select
import socket
import struct
import sys
import threading

from PySide6.QtCore import QObject, Signal

from ..input.key_codes import code_to_label
from ..utils.logging_setup import log
from ..utils.platform import can_create_virtual_device, can_read_input_devices, detect_compositor

# --------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------
EV_KEY = 0x01
_EVENT_SIZE = 24  # struct input_event on 64-bit Linux
# On Xorg backed by evdev the X keycode equals the Linux keycode + this offset.
EVDEV_X_OFFSET = 8


class HotkeyBackend(QObject):
    """Common interface implemented by every backend.

    Signals
    -------
    activated:
        The bound hotkey was pressed (or an IPC ``start`` / ``toggle`` arrived).
    deactivated:
        The bound hotkey was released (or an IPC ``stop`` / ``pause`` arrived).
        Used by *hold* mode.
    status_changed:
        Emitted with ``True`` once the backend is listening, ``False`` if it
        could not start or was stopped.
    key_captured:
        Emitted by ``begin_capture`` with ``(code, label)`` for the next key.
    capture_started:
        Emitted when capture mode begins.
    """

    activated = Signal()
    deactivated = Signal()
    status_changed = Signal(bool)
    key_captured = Signal(int, str)
    capture_started = Signal()

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._hotkey_code = 0
        self._stop = False

    # -- interface (subclasses override) ----------------------------------
    def start(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def stop(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def set_hotkey(self, code: int) -> None:
        self._hotkey_code = code

    def begin_capture(self) -> None:
        """Enter capture mode. Default: unsupported."""

    def end_capture(self) -> None:
        """Leave capture mode (e.g. when the dialog is cancelled)."""

    def can_capture(self) -> bool:
        return False

    def name(self) -> str:
        return "base"

    @staticmethod
    def is_available() -> bool:
        return False

    # -- helpers -----------------------------------------------------------
    def _set_status(self, ok: bool) -> None:
        self.status_changed.emit(ok)


# --------------------------------------------------------------------------
# Linux evdev backend
# --------------------------------------------------------------------------
class EvdevBackend(HotkeyBackend):
    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._fds: list[int] = []
        self._threads: list[threading.Thread] = []
        self._capture = False

    def name(self) -> str:
        return "evdev"

    @staticmethod
    def is_available() -> bool:
        return can_read_input_devices()

    def can_capture(self) -> bool:
        return True

    def start(self) -> None:
        self._stop = False
        opened = 0
        for path in sorted(glob.glob("/dev/input/event*")):
            try:
                fd = os.open(path, os.O_RDONLY)
            except OSError:
                continue
            self._fds.append(fd)
            t = threading.Thread(target=self._reader, args=(fd,), daemon=True)
            t.start()
            self._threads.append(t)
            opened += 1
        log.info("EvdevBackend opened %d input device(s)", opened)
        self._set_status(opened > 0)

    def stop(self) -> None:
        self._stop = True
        for fd in list(self._fds):
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds.clear()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()

    def begin_capture(self) -> None:
        self._capture = True
        self.capture_started.emit()

    def end_capture(self) -> None:
        self._capture = False

    def _reader(self, fd: int) -> None:
        while not self._stop:
            try:
                data = os.read(fd, _EVENT_SIZE)
            except OSError:
                break
            if len(data) < _EVENT_SIZE:
                continue
            _, _, etype, code, value = struct.unpack("<qqHHi", data)
            if etype != EV_KEY:
                continue
            if value == 1:  # press
                if self._capture:
                    self._capture = False
                    self.key_captured.emit(code, code_to_label(code))
                    continue
                if code == self._hotkey_code:
                    self.activated.emit()
            elif value == 0:  # release
                if code == self._hotkey_code:
                    self.deactivated.emit()


# --------------------------------------------------------------------------
# Wayland IPC backend (Unix socket server)
# --------------------------------------------------------------------------
def ipc_socket_path() -> str:
    """Stable socket path shared by the server and ``autoclickerctl``."""
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        base = runtime
    else:
        base = os.path.join(os.path.expanduser("~"), ".cache", "autoclicker")
        os.makedirs(base, exist_ok=True)
    return os.path.join(base, "autoclicker.sock")


class WaylandIPCBackend(HotkeyBackend):
    def __init__(self, parent: object | None = None, socket_path: str | None = None) -> None:
        super().__init__(parent)
        self.socket_path = socket_path or ipc_socket_path()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def name(self) -> str:
        return "ipc"

    @staticmethod
    def is_available() -> bool:
        # Unix-domain sockets are a Linux/Unix feature; on Windows a named pipe
        # would be needed (out of scope). Availability is otherwise gated only
        # by the filesystem, handled in start().
        return sys.platform != "win32"

    def can_capture(self) -> bool:
        return False

    def start(self) -> None:
        self._stop = False
        try:
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(self.socket_path)
            sock.listen(8)
            sock.settimeout(0.5)  # bounds the stop() wake-up time
            self._sock = sock
        except OSError as exc:
            log.error("IPC backend cannot create socket %s: %s", self.socket_path, exc)
            self._set_status(False)
            return
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        log.info("IPC backend listening on %s", self.socket_path)
        self._set_status(True)

    def stop(self) -> None:
        self._stop = True
        # Closing the listening socket unblocks accept() immediately on Linux.
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        try:
            os.unlink(self.socket_path)
        except OSError:
            pass
        self._set_status(False)

    def _serve(self) -> None:
        assert self._sock is not None
        while not self._stop:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(1.0)
            data = b""
            while len(data) < 64:
                chunk = conn.recv(64)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data or b" " in data:
                    break
        except OSError:
            data = b""
        finally:
            try:
                conn.close()
            except OSError:
                pass
        self._dispatch(data.decode("utf-8", "replace").strip().lower())

    def _dispatch(self, cmd: str) -> None:
        if cmd in ("toggle", "start"):
            self.activated.emit()
        elif cmd in ("stop", "pause"):
            self.deactivated.emit()
        else:
            log.debug("IPC backend ignored unknown command: %r", cmd)


# --------------------------------------------------------------------------
# X11 backend (real XGrabKey via ctypes)
# --------------------------------------------------------------------------
class X11Backend(HotkeyBackend):
    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._display = None
        self._lib = None
        self._thread: threading.Thread | None = None

    def name(self) -> str:
        return "x11"

    @staticmethod
    def is_available() -> bool:
        if detect_compositor()["wayland"]:
            return False
        if not os.environ.get("DISPLAY"):
            return False
        try:
            ctypes.CDLL("libX11.so.6")
            return True
        except OSError:
            return False

    def can_capture(self) -> bool:
        return self.is_available()

    def start(self) -> None:
        self._stop = False
        try:
            lib = ctypes.CDLL("libX11.so.6")
            lib.XOpenDisplay.restype = ctypes.c_void_p
            lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            display = lib.XOpenDisplay(None)
            if not display:
                self._set_status(False)
                return
            self._lib = lib
            self._display = display
            self._grab()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self._set_status(True)
        except OSError as exc:  # pragma: no cover - no X11 in CI
            log.error("X11 backend failed: %s", exc)
            self._set_status(False)

    def _grab(self) -> None:
        lib = self._lib
        lib.XDefaultRootWindow.restype = ctypes.c_void_p
        lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        lib.XGrabKey.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_uint,
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ]
        lib.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        root = lib.XDefaultRootWindow(self._display)
        keycode = self._hotkey_code + EVDEV_X_OFFSET
        # Grab with and without the common lock modifiers (NumLock/CapsLock).
        for mods in (0, 1, 2, 3, 4, 5, 0x80, 0x10, 0x80 | 0x10):
            lib.XGrabKey(self._display, keycode, mods, root, True, 0, 0)
        lib.XSync(self._display, 0)

    def _loop(self) -> None:  # pragma: no cover - no X11 in CI
        lib = self._lib
        lib.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.XPending.argtypes = [ctypes.c_void_p]
        lib.XPending.restype = ctypes.c_int
        lib.XConnectionNumber.argtypes = [ctypes.c_void_p]
        lib.XConnectionNumber.restype = ctypes.c_int
        ev = ctypes.create_string_buffer(192)
        keycode = self._hotkey_code + EVDEV_X_OFFSET
        conn_fd = lib.XConnectionNumber(self._display)
        # Block on the X connection fd (interruptible) instead of a bare
        # XNextEvent, so stop() can actually terminate the thread promptly.
        while not self._stop:
            try:
                readable, _, _ = select.select([conn_fd], [], [], 0.2)
            except OSError:
                break
            if not readable:
                continue
            while lib.XPending(self._display):
                lib.XNextEvent(self._display, ev)
                etype = struct.unpack_from("i", ev, 0)[0]
                if etype in (2, 3):  # KeyPress / KeyRelease
                    kc = struct.unpack_from("i", ev, 76)[0]
                    if kc == keycode:
                        (self.activated if etype == 2 else self.deactivated).emit()

    def stop(self) -> None:
        self._stop = True
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._display is not None and self._lib is not None:
            try:
                self._lib.XCloseDisplay(self._display)
            except OSError:
                pass
            self._display = None
        self._set_status(False)


# --------------------------------------------------------------------------
# Windows backend (RegisterHotKey via ctypes; Win32 only)
# --------------------------------------------------------------------------
class WindowsBackend(HotkeyBackend):
    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._thread: threading.Thread | None = None

    def name(self) -> str:
        return "windows"

    @staticmethod
    def is_available() -> bool:
        return sys.platform == "win32"

    def can_capture(self) -> bool:
        return sys.platform == "win32"

    def start(self) -> None:
        self._stop = False
        if sys.platform != "win32":
            self._set_status(False)
            return
        # Real implementation runs only on Windows; the path below is executed
        # there. On other platforms we simply report unavailable.
        try:  # pragma: no cover - Windows only
            import ctypes.wintypes  # noqa: F401

            user32 = ctypes.windll.user32
            if not user32.RegisterHotKey(0, 1, 0, self._hotkey_code):
                self._set_status(False)
                return
            self._thread = threading.Thread(target=self._pump, daemon=True)
            self._thread.start()
            self._set_status(True)
        except Exception as exc:  # pragma: no cover
            log.error("Windows backend failed: %s", exc)
            self._set_status(False)

    def _pump(self) -> None:  # pragma: no cover - Windows only
        import ctypes.wintypes

        msg = ctypes.wintypes.MSG()
        user32 = ctypes.windll.user32
        while not self._stop and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            if msg.message == 0x0312:  # WM_HOTKEY
                self.activated.emit()

    def stop(self) -> None:
        self._stop = True
        if sys.platform == "win32":  # pragma: no cover
            try:
                ctypes.windll.user32.UnregisterHotKey(0, 1)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._set_status(False)


# --------------------------------------------------------------------------
# Dummy backend (always unavailable; safe fallback)
# --------------------------------------------------------------------------
class DummyBackend(HotkeyBackend):
    def name(self) -> str:
        return "dummy"

    @staticmethod
    def is_available() -> bool:
        return False

    def start(self) -> None:
        self._set_status(False)

    def stop(self) -> None:
        pass


# --------------------------------------------------------------------------
# Factory + diagnostics
# --------------------------------------------------------------------------
def _auto_backend() -> HotkeyBackend:
    info = detect_compositor()
    if info["wayland"]:
        if EvdevBackend.is_available():
            return EvdevBackend()
        return WaylandIPCBackend()
    if not info["wayland"] and os.environ.get("DISPLAY"):
        if X11Backend.is_available():
            return X11Backend()
        return DummyBackend()
    # Unknown / headless: IPC still works as a control channel.
    return WaylandIPCBackend()


def create_backend(mode: str) -> HotkeyBackend:
    """Return a backend for ``mode`` (auto/evdev/ipc/x11/windows).

    Explicit modes that are unavailable still return the backend instance; the
    GUI shows it as unavailable rather than silently switching backends.
    """
    mode = (mode or "auto").lower()
    if mode == "auto":
        return _auto_backend()
    if mode == "evdev":
        return EvdevBackend()
    if mode == "ipc":
        return WaylandIPCBackend()
    if mode == "x11":
        return X11Backend()
    if mode == "windows":
        return WindowsBackend()
    return DummyBackend()


def backend_unavailable_reason(name: str) -> str:
    """Human-readable reason a given backend cannot be used right now."""
    info = detect_compositor()
    if name == "evdev":
        if EvdevBackend.is_available():
            return ""
        return ("Нет доступа к /dev/input/event* — нужна группа 'input' или запуск "
                "от root. Добавьте пользователя в группу input.")
    if name == "ipc":
        return ""
    if name == "x11":
        if info["wayland"]:
            return "Сессия Wayland — XGrabKey неприменим."
        if not os.environ.get("DISPLAY"):
            return "Переменная DISPLAY не задана (не X11 сессия)."
        return "libX11.so.6 недоступна."
    if name == "windows":
        if sys.platform == "win32":
            return ""
        return "Приложение запущено не на Windows."
    return "Бэкенд недоступен."


def collect_diagnostics() -> dict:
    """Snapshot used by the Diagnostics page (no silent failures)."""
    info = detect_compositor()
    ipc = WaylandIPCBackend()
    backends = {}
    for name in ("evdev", "ipc", "x11", "windows"):
        available = {
            "evdev": EvdevBackend.is_available(),
            "ipc": True,
            "x11": X11Backend.is_available(),
            "windows": WindowsBackend.is_available(),
        }[name]
        backends[name] = {"available": available, "reason": backend_unavailable_reason(name)}
    return {
        "session": "wayland" if info["wayland"] else ("x11" if info["x11"] else "unknown"),
        "compositor": info["compositor"],
        "input_readable": can_read_input_devices(),
        "uinput_writable": can_create_virtual_device(),
        "ipc_available": True,
        "ipc_path": ipc.socket_path,
        "backends": backends,
    }
