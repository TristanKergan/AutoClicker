"""Platform / compositor detection and capability checks.

Wayland compositors expose different levels of global-hotkey support. We probe
what we can so the UI can show an honest, compositor-specific message instead of
failing mysteriously.
"""
from __future__ import annotations

import os


def detect_compositor() -> dict:
    """Return a dict describing the current session.

    Keys: ``wayland`` (bool), ``x11`` (bool), ``compositor`` (str name),
    ``desktop`` (raw XDG_CURRENT_DESKTOP + DESKTOP_SESSION).
    """
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    x11 = bool(os.environ.get("DISPLAY")) and not wayland
    raw = f"{os.environ.get('XDG_CURRENT_DESKTOP', '')} {os.environ.get('DESKTOP_SESSION', '')}".strip().lower()

    name = "unknown"
    for candidate in ("niri", "hyprland", "sway", "gnome", "kde", "plasma", "weston", "labwc"):
        if candidate in raw:
            name = candidate
            break
    if name == "unknown" and wayland:
        name = "wayland"

    return {
        "wayland": wayland,
        "x11": x11,
        "compositor": name,
        "desktop": raw,
    }


def running_as_root() -> bool:
    return os.geteuid() == 0


def _in_group(gid_name: str) -> bool:
    import grp

    try:
        gid = grp.getgrnam(gid_name).gr_gid
    except KeyError:
        return False
    return gid in os.getgroups()


def can_read_input_devices() -> bool:
    """Best-effort check: can we open at least one ``/dev/input/event*``?

    Returns True when global hotkeys are expected to work (root, or the user is
    in the ``input`` group). This is optimistic — a compositor may still grab
    the keyboard — but it is a good first signal for the UI.
    """
    if running_as_root():
        return True
    if _in_group("input"):
        return True
    try:
        import glob

        for path in glob.glob("/dev/input/event*"):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            os.close(fd)
            return True
    except OSError:  # pragma: no cover
        pass
    return False


def can_create_virtual_device() -> bool:
    """Can we open ``/dev/uinput`` to inject clicks?"""
    try:
        fd = os.open("/dev/uinput", os.O_WRONLY)
    except OSError:
        return False
    os.close(fd)
    return True
