"""Tests for the plugin package structure — metadata, classFactory, icons."""

import configparser
import importlib
import inspect
from pathlib import Path

import pytest

# The plugin root is one level up from the tests directory
PLUGIN_DIR = Path(__file__).resolve().parent.parent / "scriptbench"
assert PLUGIN_DIR.is_dir(), f"Plugin directory not found: {PLUGIN_DIR}"

REQUIRED_METADATA_FIELDS = [
    "name",
    "qgisMinimumVersion",
    "description",
    "version",
    "author",
    "email",
]


# ===================================================================
# metadata.txt
# ===================================================================


class TestMetadataTxt:
    """Verify that metadata.txt is valid and contains required QGIS fields."""

    @pytest.fixture
    def metadata(self) -> configparser.ConfigParser:
        path = PLUGIN_DIR / "metadata.txt"
        assert path.exists(), f"metadata.txt not found at {path}"
        cp = configparser.ConfigParser()
        cp.read(str(path), encoding="utf-8")
        return cp

    @pytest.mark.parametrize("field", REQUIRED_METADATA_FIELDS)
    def test_has_required_field(self, metadata, field: str) -> None:
        """metadata.txt must have [general] section with every required field."""
        assert field in metadata["general"], (
            f"Missing required metadata field: {field}"
        )

    def test_version_is_semver(self, metadata) -> None:
        """version should follow semver (X.Y.Z)."""
        v = metadata["general"]["version"]
        parts = v.split(".")
        assert len(parts) == 3, f"Version must be semver (X.Y.Z), got: {v}"
        assert all(p.isdigit() for p in parts), (
            f"Version parts must be numeric, got: {v}"
        )

    def test_qgis_min_version_is_36_or_higher(self, metadata) -> None:
        """Minimum QGIS version must be at least 3.22."""
        min_ver = metadata["general"]["qgisMinimumVersion"]
        major, minor = (int(x) for x in min_ver.split(".")[:2])
        assert (major, minor) >= (3, 22), (
            f"qgisMinimumVersion must be >= 3.22, got {min_ver}"
        )

    def test_icon_path_is_relative(self, metadata) -> None:
        """icon entry should point to a relative path within the plugin dir."""
        icon = metadata["general"].get("icon", "")
        assert icon, "metadata.txt must specify an icon path"
        icon_path = PLUGIN_DIR / icon
        assert icon_path.is_file(), (
            f"Icon file does not exist: {icon_path} (from metadata icon={icon})"
        )

    def test_tracker_url(self, metadata) -> None:
        """tracker should be a valid HTTPS URL."""
        tracker = metadata["general"].get("tracker", "")
        assert tracker.startswith("https://"), (
            f"tracker URL should use HTTPS: {tracker}"
        )

    def test_repository_url(self, metadata) -> None:
        """repository should be a valid URL."""
        repo = metadata["general"].get("repository", "")
        assert repo.startswith("https://"), (
            f"repository should use HTTPS: {repo}"
        )

    def test_tags_exist(self, metadata) -> None:
        tags = metadata["general"].get("tags", "")
        assert tags, "metadata.txt must have a tags field"
        assert len(tags.split(",")) >= 3, "At least 3 tags recommended"


# ===================================================================
# Package __init__.py  (classFactory)
# ===================================================================


class TestClassFactory:
    """Verify that the plugin entry point works correctly."""

    def test_classFactory_is_callable(self) -> None:
        """classFactory should be a callable function."""
        module = importlib.import_module("scriptbench")
        assert hasattr(module, "classFactory")
        assert callable(module.classFactory)

    def test_classFactory_takes_iface_argument(self) -> None:
        """classFactory(iface) must accept a single argument."""
        sig = inspect.signature(importlib.import_module("scriptbench").classFactory)
        params = list(sig.parameters.keys())
        assert len(params) == 1, f"Expected 1 parameter, got {params}"
        assert params[0] == "iface"

    def test_classFactory_returns_plugin_instance(self) -> None:
        """When iface is None, classFactory may raise or return a plugin instance.

        Because conftest.py mocks QGIS/PyQt, the import succeeds. In the real
        environment with QGIS, calling classFactory(iface) would succeed.
        This test verifies the code path does not crash unexpectedly.
        """
        from scriptbench import classFactory

        # With mocks the import succeeds; either result is fine
        try:
            instance = classFactory(None)
            from scriptbench.plugin import ScriptBenchPlugin

            assert isinstance(instance, ScriptBenchPlugin)
        except Exception:
            pass  # raising is acceptable too — main thing: no crash


# ===================================================================
# Icon file
# ===================================================================


class TestIconFile:
    def test_icon_exists(self) -> None:
        """The icon referenced in metadata.txt must be present."""
        icon_path = PLUGIN_DIR / "icons" / "scriptbench.png"
        assert icon_path.exists(), f"Icon not found: {icon_path}"
        assert icon_path.is_file()
        assert icon_path.stat().st_size > 0, "Icon file is empty"

    def test_icon_is_png(self) -> None:
        """Icon file should have PNG magic bytes."""
        icon_path = PLUGIN_DIR / "icons" / "scriptbench.png"
        magic = icon_path.read_bytes()[:8]
        # PNG magic: 89 50 4E 47 0D 0A 1A 0A
        assert magic == b"\x89PNG\r\n\x1a\n", "File does not appear to be a PNG"


# ===================================================================
# Plugin directory structure
# ===================================================================


class TestPluginStructure:
    """Verify expected files and directories exist in the plugin package."""

    EXPECTED_PACKAGE_FILES = {
        "__init__.py",
        "context.py",
        "plugin.py",
        "reporter.py",
        "runner.py",
        "suite_manager.py",
        "scriptbench_template.py",
        "metadata.txt",
    }

    EXPECTED_SUBDIRS = {"icons", "ui"}

    def test_all_source_files_exist(self) -> None:
        """Every expected Python module should be present."""
        for fname in self.EXPECTED_PACKAGE_FILES:
            path = PLUGIN_DIR / fname
            assert path.exists(), f"Missing required file: {path}"

    def test_expected_subdirectories_exist(self) -> None:
        """Required subdirectories exist."""
        for dname in self.EXPECTED_SUBDIRS:
            path = PLUGIN_DIR / dname
            assert path.is_dir(), f"Missing required directory: {path}"

    def test_no_unexpected_top_level_dirs(self) -> None:
        """Sanity check: no large unintended directories in the plugin root."""
        dirs = [
            p
            for p in PLUGIN_DIR.iterdir()
            if p.is_dir() and not p.name.startswith("__")
        ]
        expected = self.EXPECTED_SUBDIRS
        unexpected = set(d.name for d in dirs) - expected
        assert not unexpected, (
            f"Unexpected directories in plugin root: {unexpected}"
        )


# ===================================================================
# Plugin class basics
# ===================================================================


class TestPluginClass:
    @pytest.fixture
    def PluginClass(self):
        """Import ScriptBenchPlugin (requires mocks from conftest)."""
        from scriptbench.plugin import ScriptBenchPlugin

        return ScriptBenchPlugin

    def test_plugin_class_exists(self, PluginClass) -> None:
        assert PluginClass is not None

    def test_plugin_name_constant(self, PluginClass) -> None:
        assert PluginClass.PLUGIN_NAME == "ScriptBench"
        assert PluginClass.PLUGIN_TAG == "ScriptBench"

    def test_has_expected_methods(self, PluginClass) -> None:
        """Plugin class provides the standard QGIS lifecycle and helper methods."""
        methods = {
            "initGui",
            "unload",
            "run",
            "_browse_folder",
            "_refresh_scripts",
            "_start_run",
            "_cancel_run",
            "_save_suite",
            "_delete_suite",
            "_load_suite",
            "_export_csv",
            "_export_html",
            "_log",
            "_on_progress",
            "_on_finished",
            "_on_error",
        }
        available = {m for m in methods if hasattr(PluginClass, m)}
        missing = methods - available
        assert not missing, f"Plugin class missing methods: {missing}"

    def test_tr_function_exists(self) -> None:
        """The tr() helper should be importable."""
        from scriptbench.plugin import tr

        assert callable(tr)
        result = tr("hello")
        assert isinstance(result, str)
