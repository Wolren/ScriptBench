"""
pytest configuration and shared fixtures for ScriptBench tests.

Mock all QGIS/PyQt imports so tests can run outside the QGIS application.
The scriptbench package imports from ``qgis.core``, ``qgis.PyQt`` etc. at the
top level; we inject lightweight stubs into ``sys.modules`` *before* any test
module imports from scriptbench.
"""

# ── QGIS/PyQt stubs injected before the test session sees scriptbench ──
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# 1.  Build qgis.core stub
# ---------------------------------------------------------------------------
_qgis_core = MagicMock()

# QgsMessageLog.logMessage is called throughout the plugin
_qgis_core.QgsMessageLog.logMessage = MagicMock()

# QgsProject / QgsApplication (used in suite_manager as fallback)
_qgis_core.QgsProject = MagicMock()
_qgis_core.QgsApplication = MagicMock()
_qgis_core.QgsApplication.qgisSettingsDirPath = MagicMock(
    return_value=str(Path.home() / ".qgis3")
)

sys.modules["qgis"] = MagicMock()
sys.modules["qgis.core"] = _qgis_core

# ---------------------------------------------------------------------------
# 2.  Build qgis.PyQt stubs  --  everything QGIS GUI code depends on these
# ---------------------------------------------------------------------------
_qt_core = MagicMock()
_qt_core.QCoreApplication.translate = MagicMock(side_effect=lambda ctx, msg: msg)
_qt_core.Qt = MagicMock()

_qt_gui = MagicMock()
_qt_gui.QIcon = MagicMock()

_qt_widgets = MagicMock()
_qt_widgets.QAction = MagicMock
_qt_widgets.QFileDialog = MagicMock
_qt_widgets.QMessageBox = MagicMock
_qt_widgets.QMessageBox.StandardButton = MagicMock()
_qt_widgets.QApplication = MagicMock
_qt_widgets.QTableWidgetItem = MagicMock
_qt_widgets.QWidget = MagicMock

sys.modules["qgis.PyQt"] = MagicMock()
sys.modules["qgis.PyQt.QtCore"] = _qt_core
sys.modules["qgis.PyQt.QtGui"] = _qt_gui
sys.modules["qgis.PyQt.QtWidgets"] = _qt_widgets

# ---------------------------------------------------------------------------
# 3.  Mock processing module (imported optionally inside _exec_one)
# ---------------------------------------------------------------------------
sys.modules["processing"] = MagicMock()

# ---------------------------------------------------------------------------
# Now it is safe to import the actual ScriptBench modules
# ---------------------------------------------------------------------------
import pytest  # noqa: E402

from scriptbench.runner import RunResult, ScriptSummary  # noqa: E402


# ---------------------------------------------------------------------------
# 4.  Helper: create a temporary script file with given content
# ---------------------------------------------------------------------------
@pytest.fixture
def temp_script(tmp_path: Path) -> Path:
    """Return a factory that writes a .py script into *tmp_path*.

    Usage::

        script = temp_script(\"\"\"
        def run_benchmark(context):
            context.phase(\"compute\")
            total = sum(range(100_000))
            context.phase(\"save\")
        \"\"\")
    """

    def _make(content: str, name: str = "test_script.py") -> Path:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    return _make


# ---------------------------------------------------------------------------
# 5.  Fixture: ScriptSummary with known data  (for reporter tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_summaries() -> list[ScriptSummary]:
    """Return a pair of ScriptSummary objects with deterministic timing data."""
    # --- Script A: 3 successful runs with phases ---
    a_results = []
    for i in range(3):
        r = RunResult("script_a.py", i)
        r.success = True
        r.wall_time = 0.5 + i * 0.1  # 0.5, 0.6, 0.7
        r.has_phases = True
        r.compute_time = 0.3 + i * 0.05  # 0.3, 0.35, 0.4
        r.save_time = 0.1 + i * 0.02  # 0.1, 0.12, 0.14
        r.other_phase_times = {"setup": 0.1}
        a_results.append(r)

    # --- Script B: 2 success + 1 failure, no phases ---
    b_results = []
    for i in range(2):
        r = RunResult("script_b.py", i)
        r.success = True
        r.wall_time = 1.0 + i * 0.2  # 1.0, 1.2
        r.has_phases = False
        r.compute_time = None
        r.save_time = None
        b_results.append(r)

    r_fail = RunResult("script_b.py", 2)
    r_fail.success = False
    r_fail.error = "ZeroDivisionError: division by zero"
    r_fail.wall_time = 0.0
    r_fail.has_phases = False
    b_results.append(r_fail)

    sa = ScriptSummary("script_a.py", a_results)
    sb = ScriptSummary("script_b.py", b_results)

    return [sa, sb]


# ---------------------------------------------------------------------------
# 6.  Fixture: empty summary list edge-case
# ---------------------------------------------------------------------------
@pytest.fixture
def empty_summaries() -> list[ScriptSummary]:
    return []


# ---------------------------------------------------------------------------
# 7.  Fixture: a single-output ScriptSummary (one success, edge values)
# ---------------------------------------------------------------------------
@pytest.fixture
def single_run_summary() -> ScriptSummary:
    r = RunResult("single.py", 0)
    r.success = True
    r.wall_time = 0.123456
    r.has_phases = True
    r.compute_time = 0.100000
    r.save_time = 0.023456
    return ScriptSummary("single.py", [r])
