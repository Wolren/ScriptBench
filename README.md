<div align="center">

![ScriptBench](scriptbench/icons/scriptbench.png)

# ScriptBench

Benchmark and compare PyQGIS scripts with phase-split timing, suite management, and self-contained HTML reports.

[![License][license-badge]][license-url]
[![Last commit][commit-badge]][commits-url]
[![Issues][issues-badge]][issues-url]
[![Code size][size-badge]][repo-url]
[![Python][python-badge]][pyproject-url]
[![QGIS][qgis-badge]][qgis-url]
[![CI][ci-badge]][ci-url]
[![OpenSSF Scorecard][scorecard-badge]][scorecard-url]

</div>

## Problem

Measuring PyQGIS script performance manually is inconsistent. Ad-hoc timing with `time.time()` ignores warm-up effects, conflates compute and save phases, and produces results that are hard to compare across runs or script versions. ScriptBench provides a repeatable framework for benchmarking PyQGIS scripts with configurable warm-ups, phase-split timing, and structured output.

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

1. Download the latest `scriptbench.zip` from the [releases page](https://github.com/Wolren/ScriptBench/releases)
2. In QGIS: **Plugins > Manage and Install Plugins > Install from ZIP**
3. Select the downloaded ZIP file
4. Enable ScriptBench in the **Installed** tab

### From source

Copy the `scriptbench/` folder into your QGIS profile's `python/plugins/` directory, or create a symlink:

- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

## Usage

1. Click the **ScriptBench** toolbar icon or find it under **Plugins > ScriptBench**
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

Scripts without `run_benchmark` are timed as a single block (wall time only). A template is available at `scriptbench/scriptbench_template.py`.

## Tech stack

| Tool | Purpose |
|------|---------|
| Python 3.9+ | Core language and runtime |
| QGIS 3.22+ | GIS platform (PyQt/PySide) |
| setuptools | Build and packaging |
| ruff | Linting |
| pytest | Unit testing |
| GitHub Actions | CI pipeline |

## Compatibility

| QGIS version | Qt | Python | Status |
|---|---|---|---|
| 3.22 LTR | Qt5 | 3.9+ | Tested in CI |
| 3.x stable | Qt5/Qt6 | 3.9+ | Tested in CI |
| 4.2 | Qt6 | 3.12+ | Tested in CI |
| 4.x latest | Qt6 | 3.12+ | Tested in CI |

## Limitations

- **QGIS dependency** - ScriptBench runs inside QGIS's Python environment and cannot be used standalone. Scripts under test must be compatible with the host QGIS version.
- **Phase timing requires the API** - compute/save phase-split data is only collected for scripts that implement the `run_benchmark(context)` function. Scripts without it report total wall time only.
- **Single-machine execution** - all benchmarks run on the local machine. There is no distributed or remote execution mode.
- **cProfile only** - profiling uses Python's built-in cProfile. Memory profiling, GPU timing, and line-level profiling are not supported.
- **Static HTML reports** - reports are fully self-contained but static. They include inline SVG charts with no interactive filtering or sorting.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

GPL-3.0 - see [LICENSE](LICENSE).

[license-badge]: https://img.shields.io/github/license/Wolren/ScriptBench
[license-url]: LICENSE
[commit-badge]: https://img.shields.io/github/last-commit/Wolren/ScriptBench
[commits-url]: https://github.com/Wolren/ScriptBench/commits
[issues-badge]: https://img.shields.io/github/issues/Wolren/ScriptBench
[issues-url]: https://github.com/Wolren/ScriptBench/issues
[size-badge]: https://img.shields.io/github/languages/code-size/Wolren/ScriptBench
[repo-url]: https://github.com/Wolren/ScriptBench
[python-badge]: https://img.shields.io/badge/Python-3.9+-blue?logo=python
[pyproject-url]: pyproject.toml
[qgis-badge]: https://img.shields.io/badge/QGIS-3.22+-green
[qgis-url]: https://qgis.org
[ci-badge]: https://github.com/Wolren/ScriptBench/actions/workflows/ci.yml/badge.svg
[ci-url]: https://github.com/Wolren/ScriptBench/actions/workflows/ci.yml
[scorecard-badge]: https://api.securityscorecards.dev/projects/github.com/Wolren/ScriptBench/badge
[scorecard-url]: https://securityscorecards.dev/viewer/?uri=github.com/Wolren/ScriptBench
