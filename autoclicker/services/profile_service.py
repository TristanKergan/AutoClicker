"""Profile storage: save / load / delete / export / import.

Profiles are stored as individual JSON files under
``~/.config/autoclicker/profiles``. A built-in ``Default`` profile is created
on first run so the UI always has something to show.
"""
from __future__ import annotations

import json
import os
import time

from ..core.models import ClickSettings, Profile
from ..utils.logging_setup import log

PROFILES_DIR = os.path.join(os.path.expanduser("~"), ".config", "autoclicker", "profiles")
DEFAULT_PROFILE = "Default"


class ProfileService:
    def __init__(self, directory: str = PROFILES_DIR) -> None:
        self.directory = directory
        os.makedirs(directory, exist_ok=True)
        self.ensure_default()

    def _path(self, name: str) -> str:
        safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in name)
        return os.path.join(self.directory, f"{safe}.json")

    def ensure_default(self) -> None:
        if DEFAULT_PROFILE not in self.list_names():
            self.save(Profile(name=DEFAULT_PROFILE))

    def list_names(self) -> list[str]:
        try:
            return sorted(p[:-5] for p in os.listdir(self.directory) if p.endswith(".json"))
        except OSError:
            return [DEFAULT_PROFILE]

    def get(self, name: str) -> Profile | None:
        try:
            with open(self._path(name), encoding="utf-8") as fh:
                return Profile.from_dict(json.load(fh))
        except (OSError, ValueError) as exc:
            log.warning("Could not load profile %s: %s", name, exc)
            return None

    def save(self, profile: Profile) -> None:
        profile.updated_at = time.time()
        if not profile.created_at:
            profile.created_at = time.time()
        try:
            with open(self._path(profile.name), "w", encoding="utf-8") as fh:
                json.dump(profile.to_dict(), fh, indent=2)
        except OSError as exc:  # pragma: no cover
            log.warning("Could not save profile %s: %s", profile.name, exc)

    def delete(self, name: str) -> None:
        if name == DEFAULT_PROFILE:
            return  # never delete the built-in default
        try:
            os.remove(self._path(name))
        except OSError:
            pass

    def export_json(self, profile: Profile) -> str:
        return json.dumps(profile.to_dict(), indent=2)

    def import_json(self, text: str) -> Profile:
        data = json.loads(text)
        profile = Profile.from_dict(data)
        # Avoid clobbering an existing name on import.
        base = profile.name or DEFAULT_PROFILE
        names = self.list_names()
        candidate = base
        i = 2
        while candidate in names:
            candidate = f"{base} {i}"
            i += 1
        profile.name = candidate
        return profile
