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
from typing import Dict, List, Optional


def _suites_dir() -> Path:
    try:
        from qgis.core import QgsApplication

        base = Path(QgsApplication.qgisSettingsDirPath())
    except Exception:
        base = Path.home() / ".qgis3"
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
    def __init__(
        self,
        name: str,
        folder: str,
        settings: Optional[Dict] = None,
        description: str = "",
    ):
        self.name = name
        self.folder = folder
        self.settings: Dict = {**DEFAULT_SETTINGS, **(settings or {})}
        self.description = description

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "folder": self.folder,
            "settings": self.settings,
            "description": self.description,
        }

    @staticmethod
    def from_dict(d: Dict) -> "Suite":
        return Suite(
            name=d.get("name", "unnamed"),
            folder=d.get("folder", ""),
            settings=d.get("settings", {}),
            description=d.get("description", ""),
        )

    def resolve_scripts(self) -> List[str]:
        """Return sorted list of .py file paths matching the filter in folder."""
        folder = Path(self.folder)
        if not folder.is_dir():
            return []
        pattern = self.settings.get("file_filter", "*.py")
        return sorted(str(p) for p in folder.glob(pattern) if p.is_file())


class SuiteManager:
    def list_suites(self) -> List[str]:
        d = _suites_dir()
        return sorted(p.stem for p in d.glob("*.json"))

    def load(self, name: str) -> Optional["Suite"]:
        path = _suites_dir() / f"{name}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return Suite.from_dict(json.load(fh))
        except (json.JSONDecodeError, OSError) as exc:
            from qgis.core import QgsMessageLog

            QgsMessageLog.logMessage(
                f"Failed to load suite '{name}': {exc}", "ScriptBench", level=2
            )
            return None

    def save(self, suite: Suite) -> None:
        path = _suites_dir() / f"{suite.name}.json"
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(suite.to_dict(), fh, indent=2)
        except OSError as exc:
            from qgis.core import QgsMessageLog

            QgsMessageLog.logMessage(
                f"Failed to save suite '{suite.name}': {exc}",
                "ScriptBench",
                level=2,
            )
            raise

    def delete(self, name: str) -> None:
        path = _suites_dir() / f"{name}.json"
        if path.exists():
            path.unlink()
