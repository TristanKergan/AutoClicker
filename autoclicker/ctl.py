"""``autoclickerctl`` — companion CLI for the IPC hotkey backend.

Sends a single command to a running ZCode Auto Clicker instance over its
Unix-domain socket. Bind it from your compositor, e.g. niri:

    binds {
        "F8" { spawn "autoclickerctl" "toggle"; }
    }

Commands: start | stop | toggle | pause
"""
from __future__ import annotations

import argparse
import socket
import sys

from .input.hotkey_backends import ipc_socket_path

VALID = {"start", "stop", "toggle", "pause"}


def send_command(cmd: str) -> int:
    path = ipc_socket_path()
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(path)
            sock.sendall((cmd + "\n").encode("utf-8"))
    except OSError as exc:
        print(f"autoclickerctl: cannot reach autoclicker at {path}: {exc}", file=sys.stderr)
        print("Is the app running with the IPC hotkey backend enabled?", file=sys.stderr)
        return 1
    print(f"sent: {cmd}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Control ZCode Auto Clicker via IPC")
    parser.add_argument("command", choices=sorted(VALID), help="Command to send")
    args = parser.parse_args()
    return send_command(args.command)


if __name__ == "__main__":
    sys.exit(main())
