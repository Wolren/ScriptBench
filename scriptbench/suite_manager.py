"""
suite_manager.py  --  load, save, and manage benchmark suites as JSON.

A suite is a named collection of:
  - a script folder path
  - a file selection filter (all / glob pattern)
  - benchmark settings (repeats, warmups, save_output, profile, preserve_temp)
  - optional description

Suites are stored in the QGIS user profile directory under scriptbench/suites/.
"""

import json
import os
from pathlib import Path


def _suites_dir() -> Path:
    try:
        from qgis.core import QgsApplication
        profile_dir = QgsApplication.qgisUserDatabaseFilePath()
        base = Path(profile_dir).parent
    except Exception:
        base = Path.home() / ".qgis2"
    d = base / "scriptbench" / "suites"
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULT_SETTINGS = {
    "repeats": 5,
    "warmups": 1,
    "save_output": False,
    "profile_runs": False,
    "preserve_temp": False,
    "file_filter": "*.py",
}


class Suite:
    def __init__(self, name: str, folder: str, settings: dict | None = None, description: str = ""):
        self.name = name
        self.folder = folder
        self.settings: dict = {**DEFAULT_SETTINGS, **(settings or {})}
        self.description = description

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "folder": self.folder,
            "settings": self.settings,
            "description": self.description,
        }

    @staticmethod
    def from_dict(d: dict) -> "Suite":
        return Suite(
            name=d.get("name", "unnamed"),
            folder=d.get("folder", ""),
            settings=d.get("settings", {}),
            description=d.get("description", ""),
        )

    def resolve_scripts(self) -> list[str]:
        """Return sorted list of .py file paths matching the filter in folder."""
        folder = Path(self.folder)
        if not folder.is_dir():
            return []
        pattern = self.settings.get("file_filter", "*.py")
        return sorted(str(p) for p in folder.glob(pattern) if p.is_file())


class SuiteManager:

    def list_suites(self) -> list[str]:
        d = _suites_dir()
        return sorted(p.stem for p in d.glob("*.json"))

    def load(self, name: str) -> Suite | None:
        path = _suites_dir() / f"{name}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return Suite.from_dict(json.load(fh))

    def save(self, suite: Suite) -> None:
        path = _suites_dir() / f"{suite.name}.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(suite.to_dict(), fh, indent=2)

    def delete(self, name: str) -> None:
        path = _suites_dir() / f"{name}.json"
        if path.exists():
            path.unlink()
