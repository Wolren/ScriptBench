"""
scriptbench_template.py
-----------------------
Template for a ScriptBench-compatible PyQGIS script.

Two modes of operation:

1. Benchmarked via ScriptBench
   - ScriptBench detects the `run_benchmark(context)` function and calls it.
   - The `context` object provides:
       context.output_dir  -- isolated temp directory for this run
       context.temp_dir    -- same as output_dir by default
       context.save_output -- False by default (outputs go to temp and are deleted)
       context.phase(name) -- mark the start of a named timing phase
                              Standard phase names: "setup", "compute", "save"
   - SAVE_OUTPUT is also injected as a global bool.

2. Run standalone in QGIS Python console or as a saved script
   - The __main__ guard at the bottom provides sensible defaults.
   - Output paths are taken from HARDCODED_OUTPUT_DIR when not benchmarked.

Benchmark-compatible phase contract
------------------------------------
    context.phase("setup")    -- layer lookup, path building, etc.
    context.phase("compute")  -- the actual algorithm / processing calls
    context.phase("save")     -- file writes (redirected to temp when benchmarking)

Phases are optional.  If you omit them, ScriptBench records only total wall time.
"""

import os

import processing
from qgis.core import QgsPointXY, QgsProject

# ---------------------------------------------------------------------------
# Hardcoded defaults used only when NOT running under ScriptBench
# ---------------------------------------------------------------------------
HARDCODED_OUTPUT_DIR = r"C:\temp\my_script_output"

# ScriptBench injects these globals before calling run_benchmark():
#   SAVE_OUTPUT  (bool)
#   OUTPUT_DIR   (str)
#   TEMP_DIR     (str)
#   BENCH_CONTEXT (BenchmarkContext)
# Your script should NOT rely on them existing when run standalone.


# ---------------------------------------------------------------------------
# Main benchmark entry point (called by ScriptBench)
# ---------------------------------------------------------------------------

def run_benchmark(context):
    """
    Required signature: run_benchmark(context)
    ScriptBench passes a BenchmarkContext instance.
    """
    context.phase("setup")

    raster = QgsProject.instance().mapLayersByName("clc_wlkp")[0]
    points = QgsProject.instance().mapLayersByName("points2")[0]
    ext = raster.extent()
    buffer_m = 10000

    out_dir = context.output_dir
    os.makedirs(out_dir, exist_ok=True)

    context.phase("compute")

    features = list(points.getFeatures())

    context.phase("save")

    for f in features:
        p = f.geometry().asPoint()
        x_min, x_max = p.x() - buffer_m, p.x() + buffer_m
        y_min, y_max = p.y() - buffer_m, p.y() + buffer_m

        if not (ext.contains(QgsPointXY(x_min, y_min)) and ext.contains(QgsPointXY(x_max, y_max))):
            continue

        if context.save_output:
            out_path = os.path.join(out_dir, f"clc_bufor_{f.id()}.tif")
        else:
            # redirect to temp so nothing persists after the benchmark
            out_path = os.path.join(context.temp_dir, f"clc_bufor_{f.id()}.tif")

        processing.run(
            "gdal:cliprasterbyextent",
            {
                "INPUT": raster,
                "PROJWIN": f"{x_min},{x_max},{y_min},{y_max}",
                "OVERCRS": False,
                "NODATA": None,
                "ALPHA_BAND": False,
                "CROP_TO_CUTLINE": False,
                "KEEP_RESOLUTION": True,
                "DATA_TYPE": 0,
                "OUTPUT": out_path,
            },
        )


# ---------------------------------------------------------------------------
# Standalone execution (not benchmarked)
# ---------------------------------------------------------------------------

class _StandaloneContext:
    """Minimal stub so the same function body runs standalone."""
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.temp_dir = output_dir
        self.save_output = True
    def phase(self, name: str):
        pass


if __name__ == "__main__" or not globals().get("BENCH_CONTEXT"):
    # Running standalone: use hardcoded path and save outputs normally.
    _ctx = _StandaloneContext(HARDCODED_OUTPUT_DIR)
    run_benchmark(_ctx)
