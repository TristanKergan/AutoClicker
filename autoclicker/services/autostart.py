"""XDG autostart management (``~/.config/autostart/autoclicker.desktop``)."""
from __future__ import annotations

import os

APP_NAME = "autoclicker"


class AutostartManager:
    def __init__(self, app_name: str = APP_NAME) -> None:
        self.directory = os.path.join(os.path.expanduser("~"), ".config", "autostart")
        self.path = os.path.join(self.directory, f"{app_name}.desktop")

    def is_enabled(self) -> bool:
        return os.path.exists(self.path)

    def enable(self, exec_command: str) -> None:
        os.makedirs(self.directory, exist_ok=True)
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=ZCode Auto Clicker\n"
            "Comment=Wayland-native autoclicker\n"
            f"Exec={exec_command}\n"
            "Hidden=false\n"
            "NoDisplay=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(content)

    def disable(self) -> None:
        try:
            os.remove(self.path)
        except OSError:
            pass
