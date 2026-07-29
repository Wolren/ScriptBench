"""Tests for suite_manager.py — Suite model and SuiteManager persistence."""

import json
from pathlib import Path

import pytest

from scriptbench.suite_manager import (
    DEFAULT_SETTINGS,
    Suite,
    SuiteManager,
)

# ===================================================================
# DEFAULT_SETTINGS
# ===================================================================


class TestDefaultSettings:
    def test_all_expected_keys_present(self) -> None:
        """DEFAULT_SETTINGS must contain all keys the UI and Suite depend on."""
        expected = {
            "repeats",
            "warmups",
            "save_output",
            "profile_runs",
            "preserve_temp",
            "file_filter",
        }
        assert set(DEFAULT_SETTINGS.keys()) == expected

    def test_repeats_is_positive(self) -> None:
        assert isinstance(DEFAULT_SETTINGS["repeats"], int)
        assert DEFAULT_SETTINGS["repeats"] >= 1

    def test_warmups_is_non_negative(self) -> None:
        assert isinstance(DEFAULT_SETTINGS["warmups"], int)
        assert DEFAULT_SETTINGS["warmups"] >= 0

    def test_save_output_defaults_false(self) -> None:
        assert DEFAULT_SETTINGS["save_output"] is False

    def test_profile_runs_defaults_false(self) -> None:
        assert DEFAULT_SETTINGS["profile_runs"] is False

    def test_preserve_temp_defaults_false(self) -> None:
        assert DEFAULT_SETTINGS["preserve_temp"] is False

    def test_file_filter_defaults_star_py(self) -> None:
        assert DEFAULT_SETTINGS["file_filter"] == "*.py"


# ===================================================================
# Suite model
# ===================================================================


class TestSuiteInit:
    def test_minimal_construction(self) -> None:
        """Suite can be created with just name and folder."""
        s = Suite(name="my-suite", folder="/tmp/scripts")
        assert s.name == "my-suite"
        assert s.folder == "/tmp/scripts"
        assert s.description == ""
        assert s.settings == DEFAULT_SETTINGS

    def test_custom_settings_override_defaults(self) -> None:
        s = Suite(
            name="fast",
            folder="/tmp/py",
            settings={"repeats": 10, "warmups": 3},
        )
        assert s.settings["repeats"] == 10
        assert s.settings["warmups"] == 3
        # Non-overridden keys stay at defaults
        assert s.settings["file_filter"] == "*.py"

    def test_empty_settings_uses_defaults(self) -> None:
        s = Suite(name="s", folder="/tmp", settings={})
        assert s.settings == DEFAULT_SETTINGS

    def test_with_description(self) -> None:
        s = Suite(name="s", folder="/tmp", description="my benchmarks")
        assert s.description == "my benchmarks"


class TestSuiteSerialization:
    def test_to_dict_returns_expected_keys(self) -> None:
        s = Suite(name="s1", folder="/a/b", description="desc")
        d = s.to_dict()
        assert set(d.keys()) == {"name", "folder", "settings", "description"}
        assert d["name"] == "s1"
        assert d["folder"] == "/a/b"
        assert d["description"] == "desc"

    def test_to_dict_settings_are_complete(self) -> None:
        s = Suite(name="s", folder="/x")
        d = s.to_dict()
        assert d["settings"] == DEFAULT_SETTINGS

    def test_from_dict_round_trip(self) -> None:
        original = Suite(
            name="roundtrip",
            folder="/tmp/scripts",
            settings={"repeats": 7, "warmups": 2, "profile_runs": True},
            description="testing round-trip",
        )
        d = original.to_dict()
        restored = Suite.from_dict(d)

        assert restored.name == original.name
        assert restored.folder == original.folder
        assert restored.description == original.description
        assert restored.settings["repeats"] == 7
        assert restored.settings["warmups"] == 2
        assert restored.settings["profile_runs"] is True
        assert restored.settings["file_filter"] == "*.py"  # default

    def test_from_dict_missing_keys_use_defaults(self) -> None:
        restored = Suite.from_dict({})
        assert restored.name == "unnamed"
        assert restored.folder == ""
        assert restored.description == ""
        assert restored.settings == DEFAULT_SETTINGS

    def test_json_serializable(self) -> None:
        """to_dict output must be JSON-serializable."""
        s = Suite(name="json-test", folder="/tmp")
        json_str = json.dumps(s.to_dict())
        assert "json-test" in json_str
        assert "/tmp" in json_str

    def test_from_dict_handles_partial_settings(self) -> None:
        d = {
            "name": "partial",
            "folder": "/p",
            "settings": {"repeats": 3},
            "description": "",
        }
        s = Suite.from_dict(d)
        assert s.settings["repeats"] == 3
        assert s.settings["warmups"] == 1  # default
        assert s.settings["file_filter"] == "*.py"


class TestSuiteResolveScripts:
    def test_non_existent_folder_returns_empty(self) -> None:
        s = Suite(name="bad", folder="/tmp/non_existent_xyz")
        assert s.resolve_scripts() == []

    def test_returns_matching_py_files(self, tmp_path: Path) -> None:
        """resolve_scripts returns sorted .py files matching the filter."""
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")  # should not match

        s = Suite(name="test", folder=str(tmp_path))
        scripts = s.resolve_scripts()
        assert len(scripts) == 2
        assert all(p.endswith(".py") for p in scripts)

    def test_custom_filter(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("")
        (tmp_path / "a_test.py").write_text("")
        (tmp_path / "b.txt").write_text("")

        s = Suite(
            name="filtered",
            folder=str(tmp_path),
            settings={"file_filter": "*_test.py"},
        )
        scripts = s.resolve_scripts()
        assert len(scripts) == 1
        assert "_test.py" in scripts[0]


# ===================================================================
# SuiteManager persistence
# ===================================================================


class TestSuiteManager:
    """Tests that use monkeypatch to redirect _suites_dir to tmp_path."""

    @pytest.fixture
    def manager(self, tmp_path: Path, monkeypatch) -> SuiteManager:
        """Return a SuiteManager whose _suites_dir points at tmp_path."""

        def _fake_suites_dir() -> Path:
            return tmp_path

        monkeypatch.setattr(
            "scriptbench.suite_manager._suites_dir", _fake_suites_dir
        )
        return SuiteManager()

    @pytest.fixture
    def saved_suite(self, manager: SuiteManager) -> Suite:
        s = Suite(
            name="integration-test",
            folder="/tmp/scripts",
            settings={"repeats": 10, "warmups": 2},
            description="integration test suite",
        )
        manager.save(s)
        return s

    def test_save_creates_json_file(self, manager: SuiteManager, tmp_path: Path) -> None:
        s = Suite(name="save-test", folder="/tmp")
        manager.save(s)
        expected = tmp_path / "save-test.json"
        assert expected.exists()
        assert expected.read_text(encoding="utf-8").startswith("{")

    def test_load_returns_suite(self, manager: SuiteManager, saved_suite: Suite) -> None:
        loaded = manager.load("integration-test")
        assert loaded is not None
        assert loaded.name == "integration-test"
        assert loaded.folder == "/tmp/scripts"
        assert loaded.settings["repeats"] == 10
        assert loaded.description == "integration test suite"

    def test_load_nonexistent_returns_none(self, manager: SuiteManager) -> None:
        assert manager.load("does-not-exist") is None

    def test_list_suites(self, manager: SuiteManager, tmp_path: Path) -> None:
        # Create two suite files
        (tmp_path / "alpha.json").write_text(
            json.dumps({"name": "alpha", "folder": "/a", "settings": {}, "description": ""})
        )
        (tmp_path / "beta.json").write_text(
            json.dumps({"name": "beta", "folder": "/b", "settings": {}, "description": ""})
        )
        names = manager.list_suites()
        assert names == ["alpha", "beta"]

    def test_list_suites_empty(self, manager: SuiteManager) -> None:
        assert manager.list_suites() == []

    def test_delete_removes_file(self, manager: SuiteManager, saved_suite: Suite) -> None:
        manager.delete("integration-test")
        assert manager.load("integration-test") is None
        # list should be empty
        assert "integration-test" not in manager.list_suites()

    def test_delete_nonexistent_does_not_raise(self, manager: SuiteManager) -> None:
        # Should not raise an exception
        manager.delete("i-do-not-exist")

    def test_save_then_list_includes_suite(
        self, manager: SuiteManager, saved_suite: Suite
    ) -> None:
        names = manager.list_suites()
        assert "integration-test" in names

    def test_save_overwrites_existing(self, manager: SuiteManager) -> None:
        s1 = Suite(name="overwrite", folder="/v1")
        manager.save(s1)
        s2 = Suite(name="overwrite", folder="/v2")
        manager.save(s2)

        loaded = manager.load("overwrite")
        assert loaded is not None
        assert loaded.folder == "/v2"

    def test_json_content_structure(self, manager: SuiteManager, tmp_path: Path) -> None:
        s = Suite(
            name="struct-check",
            folder="/tmp/py",
            settings={"repeats": 3},
            description="check",
        )
        manager.save(s)

        raw = (tmp_path / "struct-check.json").read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["name"] == "struct-check"
        assert data["folder"] == "/tmp/py"
        assert "settings" in data
        assert "description" in data
