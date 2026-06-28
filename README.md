[![CI](https://github.com/Wolren/ScriptBench/actions/workflows/ci.yml/badge.svg)](https://github.com/Wolren/ScriptBench/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/Wolren/ScriptBench/badge)](https://securityscorecards.dev/viewer/?uri=github.com/Wolren/ScriptBench)
[![Socket](https://img.shields.io/badge/Socket-Supply%20Chain%20Security-333?logo=socketdotdev)](https://socket.dev)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![QGIS 3.22+](https://img.shields.io/badge/QGIS-3.22+-green)](https://qgis.org)
[![Qt](https://img.shields.io/badge/Qt-5.x_|_6.x-green)](https://www.qt.io/)

# ScriptBench

**Benchmark and compare PyQGIS scripts** - with phase-split timing, suite management, and self-contained HTML reports.

## Features

- **Run PyQGIS scripts** multiple times from any folder, with configurable repeats and warm-ups
- **Phase-split timing** - scripts that implement `run_benchmark(context)` can report compute vs save phase durations independently
- **Suite management** - save and reload named benchmark suites (script folder, filter, and all settings)
- **Self-contained HTML reports** - inline SVG charts, summary table, per-script run details, and warning annotations
- **CSV export** - raw statistics for external analysis
- **cProfile support** - optional profiling of one run per script (results shown inline in the HTML report)
- **Isolated workspace** - each run executes in a temporary directory; outputs are discarded by default
- **Hardcoded-path detection** - static analysis warns when absolute paths appear in script source

## Installation

### From ZIP (QGIS Plugin Manager)

1. Download the latest `scriptbench.zip` from the [releases page](https://github.com/Wolren/scriptbench/releases)
2. In QGIS: **Plugins → Manage and Install Plugins → Install from ZIP**
3. Select the downloaded ZIP file
4. Enable ScriptBench in **Installed** tab

### From source

```bash
git clone https://github.com/Wolren/scriptbench.git
cd scriptbench
```

Then copy the `scriptbench/` folder into your QGIS profile's `python/plugins/` directory, or create a symlink:

- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

## Usage

1. Click the **ScriptBench** toolbar icon or find it under **Plugins → ScriptBench**
2. **Script folder** - select a folder containing `.py` PyQGIS scripts
3. **File filter** - use a glob pattern (default `*.py`)
4. **Repeats / Warm-ups** - number of measured runs and unmeasured warm-up runs
5. Click **Run benchmark**
6. View results in the **Results** tab or export as CSV / HTML

### Writing benchmarkable scripts

ScriptBench looks for a function named `run_benchmark(context)` in each script:

```python
def run_benchmark(context):
    context.phase("setup")
    layer = QgsProject.instance().mapLayersByName("my_layer")[0]

    context.phase("compute")
    # ... heavy processing ...

    context.phase("save")
    # ... file output to context.output_dir ...
```

Scripts without `run_benchmark` are timed as a single block (wall time only). A
template is available at `scriptbench/scriptbench_template.py`.

## Project structure

```
scriptbench/
├── __init__.py           # classFactory entry point
├── metadata.txt          # QGIS plugin metadata
├── plugin.py             # Main plugin class (GUI, orchestration)
├── runner.py             # Benchmark engine (exec, timing, profiling)
├── reporter.py           # CSV / HTML report generation
├── context.py            # BenchmarkContext passed to scripts
├── suite_manager.py      # Suite JSON persistence
├── ui/
│   ├── dialog.py         # UI loader (qgis.PyQt shim)
│   └── main_dialog.ui    # Qt Designer form
├── icons/
│   └── scriptbench.png   # Plugin icon
└── i18n/                 # Translation files
```

## Compatibility

| QGIS version | Qt      | Python   | Status |
|-------------|---------|----------|--------|
| 3.16 - 3.34 | Qt5     | 3.9      | ✓      |
| 3.40+       | Qt6     | 3.12+    | ✓      |

## License

GPL-3.0 - see `LICENSE`.
