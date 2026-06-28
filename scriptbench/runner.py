"""
runner.py  --  benchmark engine for ScriptBench.
"""

import cProfile
import io
import pstats
import shutil
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

from .context import BenchmarkContext


class RunResult:
    def __init__(self, script_name: str, run_index: int):
        self.script_name = script_name
        self.run_index = run_index
        self.wall_time: float = 0.0
        self.compute_time: Optional[float] = None
        self.save_time: Optional[float] = None
        self.other_phase_times: dict[str, float] = {}
        self.has_phases: bool = False
        self.success: bool = False
        self.error: Optional[str] = None
        self.warnings: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "script": self.script_name,
            "run": self.run_index,
            "wall_time": self.wall_time,
            "compute_time": self.compute_time,
            "save_time": self.save_time,
            "has_phases": self.has_phases,
            "success": self.success,
            "error": self.error or "",
            "warnings": "; ".join(self.warnings),
        }


class ScriptSummary:
    def __init__(self, script_name: str, results: list[RunResult]):
        self.script_name = script_name
        self.results = results
        self.warnings: list[str] = []

    def _wall_times(self) -> list[float]:
        return [r.wall_time for r in self.results if r.success]

    def _compute_times(self) -> list[float]:
        return [
            r.compute_time
            for r in self.results
            if r.success and r.compute_time is not None
        ]

    def _save_times(self) -> list[float]:
        return [
            r.save_time for r in self.results if r.success and r.save_time is not None
        ]

    def _stats(self, values: list[float]) -> dict[str, Any]:
        if not values:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "stdev": None,
                "cv": None,
                "n": 0,
            }
        import statistics

        n = len(values)
        mean = statistics.mean(values)
        median = statistics.median(values)
        mn = min(values)
        mx = max(values)
        stdev = statistics.stdev(values) if n > 1 else 0.0
        cv = (stdev / mean * 100) if mean > 0 else 0.0
        return {
            "min": mn,
            "max": mx,
            "mean": mean,
            "median": median,
            "stdev": stdev,
            "cv": cv,
            "n": n,
        }

    def wall_stats(self) -> dict[str, Any]:
        return self._stats(self._wall_times())

    def compute_stats(self) -> dict[str, Any]:
        return self._stats(self._compute_times())

    def save_stats(self) -> dict[str, Any]:
        return self._stats(self._save_times())

    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)

    def has_phase_data(self) -> bool:
        return any(r.has_phases for r in self.results if r.success)


def _detect_hardcoded_paths(source: str) -> list[str]:
    import re

    hits = []
    patterns = [
        r"""['"]((?:[A-Za-z]:\\|/(?:home|Users|var|mnt|data))[^'"]{3,})['"']""",
        r"""r['"]((?:[A-Za-z]:\\|/(?:home|Users|var|mnt|data))[^'"]{3,})['"']""",
    ]
    for pat in patterns:
        for m in re.finditer(pat, source):
            hits.append(m.group(1))
    return list(set(hits))


def _has_benchmark_api(source: str) -> bool:
    return "def run_benchmark(" in source


def _start_profiling() -> cProfile.Profile:
    pr = cProfile.Profile()
    pr.enable()
    return pr


def _stop_profiling(pr: cProfile.Profile) -> str:
    pr.disable()
    buf = io.StringIO()
    ps = pstats.Stats(pr, stream=buf).sort_stats("cumulative")
    ps.print_stats(20)
    return buf.getvalue()


class BenchmarkRunner:
    def __init__(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self._progress = progress_callback or (lambda msg: None)

    def run_suite(
        self,
        script_paths: list[str],
        repeats: int = 5,
        warmups: int = 1,
        save_output: bool = False,
        profile_runs: bool = False,
        preserve_temp: bool = False,
    ) -> list[ScriptSummary]:
        summaries = []
        for sp in script_paths:
            summary = self._run_script(
                sp, repeats, warmups, save_output, profile_runs, preserve_temp
            )
            summaries.append(summary)
        return summaries

    def _run_script(
        self,
        script_path: str,
        repeats: int,
        warmups: int,
        save_output: bool,
        profile_runs: bool,
        preserve_temp: bool,
    ) -> ScriptSummary:
        name = Path(script_path).name
        self._progress(f"Starting: {name}")

        try:
            with open(script_path, encoding="utf-8") as fh:
                source = fh.read()
        except Exception as exc:
            s = ScriptSummary(name, [])
            s.warnings.append(f"Could not read script: {exc}")
            return s

        warnings = []
        hard_paths = _detect_hardcoded_paths(source)
        if hard_paths:
            warnings.append(
                f"Hardcoded paths detected (will still run): {', '.join(hard_paths[:3])}"
            )
        uses_api = _has_benchmark_api(source)

        all_results: list[RunResult] = []
        total_runs = warmups + repeats

        for i in range(total_runs):
            is_warmup = i < warmups
            run_label = (
                f"warmup {i + 1}" if is_warmup else f"run {i - warmups + 1}/{repeats}"
            )
            self._progress(f"  {name}: {run_label}")

            tmp_dir = tempfile.mkdtemp(prefix="scriptbench_")
            try:
                result = self._exec_one(
                    name=name,
                    source=source,
                    run_index=i,
                    temp_dir=tmp_dir,
                    save_output=save_output,
                    uses_api=uses_api,
                    profile=(profile_runs and not is_warmup),
                )
                result.warnings.extend(warnings)
            finally:
                if not preserve_temp:
                    shutil.rmtree(tmp_dir, ignore_errors=True)

            if not is_warmup:
                all_results.append(result)

        summary = ScriptSummary(name, all_results)
        summary.warnings = warnings
        self._progress(f"  {name}: done ({len(all_results)} measured runs)")
        return summary

    def _exec_one(
        self,
        name: str,
        source: str,
        run_index: int,
        temp_dir: str,
        save_output: bool,
        uses_api: bool,
        profile: bool,
    ) -> RunResult:
        result = RunResult(name, run_index)
        ctx = BenchmarkContext(
            output_dir=temp_dir, temp_dir=temp_dir, save_output=save_output
        )

        ns: dict[str, Any] = {
            "__name__": "__scriptbench__",
            "__file__": name,
            "SAVE_OUTPUT": save_output,
            "OUTPUT_DIR": temp_dir,
            "TEMP_DIR": temp_dir,
            "BENCH_CONTEXT": ctx,
        }
        try:
            import processing
            from qgis.core import QgsApplication, QgsProject

            ns["QgsProject"] = QgsProject
            ns["QgsApplication"] = QgsApplication
            ns["processing"] = processing
        except ImportError:
            pass

        try:
            code = compile(source, name, "exec")
        except SyntaxError as exc:
            result.success = False
            result.error = f"SyntaxError: {exc}"
            return result

        ctx._start()
        t0 = time.perf_counter()

        try:
            if uses_api:
                exec(code, ns)
                if "run_benchmark" in ns and callable(ns["run_benchmark"]):
                    if profile:
                        pr = _start_profiling()
                    ns["run_benchmark"](ctx)
                    if profile:
                        result.warnings.append("PROFILE:\n" + _stop_profiling(pr))
                else:
                    result.warnings.append(
                        "run_benchmark not found after exec; fell back to full-file timing."
                    )
                    if profile:
                        pr = _start_profiling()
                    exec(code, ns)
                    if profile:
                        result.warnings.append("PROFILE:\n" + _stop_profiling(pr))
            else:
                if profile:
                    pr = _start_profiling()
                exec(code, ns)
                if profile:
                    result.warnings.append("PROFILE:\n" + _stop_profiling(pr))

            result.success = True
        except Exception:
            result.success = False
            result.error = traceback.format_exc()

        ctx._stop()
        result.wall_time = time.perf_counter() - t0

        if ctx.has_phases():
            result.has_phases = True
            result.compute_time = ctx.compute_time()
            result.save_time = ctx.save_time()
            pt = ctx.phase_times()
            result.other_phase_times = {
                k: v for k, v in pt.items() if k not in ("compute", "save")
            }
        else:
            result.has_phases = False

        return result
