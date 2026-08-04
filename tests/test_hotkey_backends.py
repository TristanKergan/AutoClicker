"""Per-backend unit/integration tests for the global hotkey system.

These run without a display server or special device permissions:

* EvdevBackend  -- exercised with a synthetic pipe fed via monkeypatched
                   ``/dev/input/event*`` so we can inject real ``input_event``
                   packets and assert the decode/dispatch logic.
* WaylandIPCBackend -- real Unix socket + the ``autoclickerctl`` client.
* X11Backend / WindowsBackend / DummyBackend -- availability + safe start/stop.
* Factory + diagnostics -- ``create_backend``, ``collect_diagnostics``,
  ``backend_unavailable_reason``.

Run directly:  QT_QPA_PLATFORM=offscreen python tests/test_hotkey_backends.py
"""
from __future__ import annotations

import os
import socket
import struct
import sys
import tempfile
import threading
import unittest
from unittest import mock

# Make the package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication, Qt

from autoclicker.input.hotkey_backends import (
    DummyBackend,
    EvdevBackend,
    WaylandIPCBackend,
    WindowsBackend,
    X11Backend,
    backend_unavailable_reason,
    create_backend,
    collect_diagnostics,
)
from autoclicker.ctl import send_command


# A QCoreApplication must outlive every QObject so PySide6 can tear down cleanly
# (without it, the interpreter segfaults on exit with live signals/threads).
_app = QCoreApplication.instance() or QCoreApplication(sys.argv)

EV_KEY = 0x01
_EVENT = struct.Struct("<qqHHi")


def _key_packet(code: int, value: int, etype: int = EV_KEY) -> bytes:
    # tv_sec, tv_usec, type, code, value
    return _EVENT.pack(0, 0, etype, code, value)


class _SignalWatcher:
    """Connects a DirectConnection and records the first emission.

    DirectConnection runs the slot in the *emitter* thread, so delivery is
    deterministic and no event loop is required. Useful for signals emitted
    synchronously inside ``start()`` (connect *before* calling start) and for
    signals emitted later on a backend thread (connect, trigger, then ``wait``).
    """

    def __init__(self, signal):
        self._ev = threading.Event()
        self._args = None
        self._signal = signal
        self._slot = self._make_slot()
        signal.connect(self._slot, Qt.DirectConnection)

    def _make_slot(self):
        def slot(*args):
            self._args = args
            self._ev.set()
        return slot

    def wait(self, timeout: float = 2.0) -> bool:
        return self._ev.wait(timeout)

    def close(self) -> None:
        try:
            self._signal.disconnect(self._slot)
        except Exception:
            pass

    @property
    def args(self):
        return self._args


def _wait_signal(signal, timeout: float = 2.0):
    """Wait for a Qt signal (post-start emission). Returns ``(fired, args)``."""
    w = _SignalWatcher(signal)
    fired = w.wait(timeout)
    args = w.args
    w.close()
    return fired, args



class DummyBackendTests(unittest.TestCase):
    def test_always_unavailable(self):
        b = DummyBackend()
        self.assertEqual(b.name(), "dummy")
        self.assertFalse(b.is_available())
        self.assertFalse(b.can_capture())

    def test_start_emits_false_stop_safe(self):
        b = DummyBackend()
        watch = _SignalWatcher(b.status_changed)
        b.start()
        self.assertTrue(watch.wait())
        self.assertFalse(watch.args[0])
        b.stop()  # must not raise
        watch.close()


class EvdevBackendTests(unittest.TestCase):
    def _patch_devices(self, read_fd):
        # Point /dev/input/event* at our synthetic readable fd.
        patcher_glob = mock.patch(
            "autoclicker.input.hotkey_backends.glob.glob", return_value=["/dev/input/eventSYNTH"]
        )
        patcher_open = mock.patch(
            "autoclicker.input.hotkey_backends.os.open", return_value=read_fd
        )
        patcher_glob.start()
        patcher_open.start()
        self.addCleanup(patcher_glob.stop)
        self.addCleanup(patcher_open.stop)

    def test_capture_emits_key(self):
        r, w = os.pipe()
        self._patch_devices(r)
        b = EvdevBackend()
        b.begin_capture()
        b.start()
        try:
            os.write(w, _key_packet(30, 1))  # KEY_A press
            fired, args = _wait_signal(b.key_captured)
            self.assertTrue(fired, "key_captured was not emitted")
            self.assertEqual(args, (30, "A"))
        finally:
            b.stop()
            os.close(w)

    def test_hotkey_press_and_release(self):
        r, w = os.pipe()
        self._patch_devices(r)
        b = EvdevBackend()
        b.set_hotkey(66)  # F8
        b.start()
        try:
            os.write(w, _key_packet(66, 1))
            fired, _ = _wait_signal(b.activated)
            self.assertTrue(fired, "activated was not emitted for hotkey")

            os.write(w, _key_packet(66, 0))
            fired, _ = _wait_signal(b.deactivated)
            self.assertTrue(fired, "deactivated was not emitted for hotkey release")
        finally:
            b.stop()
            os.close(w)

    def test_no_devices_reports_unavailable(self):
        with mock.patch(
            "autoclicker.input.hotkey_backends.glob.glob", return_value=[]
        ):
            b = EvdevBackend()
            watch = _SignalWatcher(b.status_changed)
            b.start()
            self.assertTrue(watch.wait())
            self.assertFalse(watch.args[0])
            b.stop()
            watch.close()

    def test_is_available_returns_bool(self):
        self.assertIsInstance(EvdevBackend.is_available(), bool)

    def test_capture_cancel_resets_state(self):
        b = EvdevBackend()
        b.begin_capture()
        # Simulate the dialog being cancelled (done()) without a key press.
        b.end_capture()
        # A subsequent key press must NOT be swallowed by stale capture state;
        # a real hotkey press should now trigger activated, not key_captured.
        r, w = os.pipe()
        self._patch_devices(r)
        b.set_hotkey(66)
        b.start()
        try:
            os.write(w, _key_packet(66, 1))
            fired, _ = _wait_signal(b.activated)
            self.assertTrue(fired, "hotkey not activated after capture cancelled")
        finally:
            b.stop()
            os.close(w)


class WaylandIPCBackendTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="autoclicker-ipc-")
        self.sock = os.path.join(self._dir, "test.sock")

    def tearDown(self):
        try:
            os.unlink(self.sock)
        except OSError:
            pass
        try:
            os.rmdir(self._dir)
        except OSError:
            pass

    def test_toggle_via_socket(self):
        b = WaylandIPCBackend(socket_path=self.sock)
        watch = _SignalWatcher(b.status_changed)
        b.start()
        self.assertTrue(watch.wait())
        self.assertTrue(os.path.exists(self.sock))

        # Connect a raw client and send 'toggle'.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as cli:
            cli.connect(self.sock)
            cli.sendall(b"toggle\n")
        fired, _ = _wait_signal(b.activated)
        self.assertTrue(fired, "activated not emitted for 'toggle'")

        # 'pause' -> deactivated (hold mode release).
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as cli:
            cli.connect(self.sock)
            cli.sendall(b"pause\n")
        fired, _ = _wait_signal(b.deactivated)
        self.assertTrue(fired, "deactivated not emitted for 'pause'")

        b.stop()
        watch.close()
        self.assertFalse(os.path.exists(self.sock))

    def test_ctl_client_end_to_end(self):
        b = WaylandIPCBackend(socket_path=self.sock)
        b.start()
        try:
            with mock.patch(
                "autoclicker.ctl.ipc_socket_path", return_value=self.sock
            ):
                rc = send_command("start")  # uses the real autoclickerctl path
            self.assertEqual(rc, 0)
            fired, _ = _wait_signal(b.activated)
            self.assertTrue(fired, "activated not emitted via autoclickerctl")
        finally:
            b.stop()

    def test_capture_unsupported(self):
        b = WaylandIPCBackend(socket_path=self.sock)
        self.assertFalse(b.can_capture())

    def test_unknown_command_ignored(self):
        b = WaylandIPCBackend(socket_path=self.sock)
        b.start()
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as cli:
                cli.connect(self.sock)
                cli.sendall(b"frobnicate\n")
            # Give the server a moment; if it were to crash the thread dies.
            b2 = WaylandIPCBackend(socket_path=self.sock + ".x")
            # sanity: a second backend can still start on its own socket
            b2.start()
            self.assertTrue(os.path.exists(self.sock))
            b2.stop()
        finally:
            b.stop()


class X11WindowsBackendTests(unittest.TestCase):
    def test_x11_safe_lifecycle(self):
        b = X11Backend()
        self.assertEqual(b.name(), "x11")
        self.assertIsInstance(b.is_available(), bool)
        b.start()  # no DISPLAY / no X11 -> status False, no thread leaked
        b.stop()

    def test_windows_safe_lifecycle(self):
        b = WindowsBackend()
        self.assertEqual(b.name(), "windows")
        self.assertEqual(b.is_available(), sys.platform == "win32")
        b.start()
        b.stop()


class FactoryAndDiagnosticsTests(unittest.TestCase):
    def test_create_backend_returns_correct_classes(self):
        self.assertIsInstance(create_backend("evdev"), EvdevBackend)
        self.assertIsInstance(create_backend("ipc"), WaylandIPCBackend)
        self.assertIsInstance(create_backend("x11"), X11Backend)
        self.assertIsInstance(create_backend("windows"), WindowsBackend)
        self.assertIsInstance(create_backend("auto"), (EvdevBackend, WaylandIPCBackend, X11Backend, DummyBackend, WindowsBackend))
        # Unknown mode falls back to Dummy.
        self.assertIsInstance(create_backend("bogus"), DummyBackend)

    def test_unavailable_reason_strings(self):
        for name in ("evdev", "ipc", "x11", "windows"):
            reason = backend_unavailable_reason(name)
            self.assertIsInstance(reason, str)

    def test_collect_diagnostics_shape(self):
        data = collect_diagnostics()
        for key in ("session", "compositor", "input_readable", "uinput_writable",
                    "ipc_available", "ipc_path", "backends"):
            self.assertIn(key, data)
        for name in ("evdev", "ipc", "x11", "windows"):
            self.assertIn(name, data["backends"])
            self.assertIn("available", data["backends"][name])
            self.assertIn("reason", data["backends"][name])


if __name__ == "__main__":
    unittest.main(verbosity=2)
