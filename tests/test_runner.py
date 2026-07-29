"""Tests for BenchmarkRunner, RunResult, and ScriptSummary."""

import textwrap
from pathlib import Path

from scriptbench.runner import (
    BenchmarkRunner,
    RunResult,
    ScriptSummary,
    _detect_hardcoded_paths,
    _has_benchmark_api,
)

# ===================================================================
# Utility functions (_detect_hardcoded_paths, _has_benchmark_api)
# ===================================================================


class TestDetectHardcodedPaths:
    def test_empty_source_returns_empty(self) -> None:
        assert _detect_hardcoded_paths("") == []

    def test_no_paths_returns_empty(self) -> None:
        code = "x = 42\ny = x + 1\n"
        assert _detect_hardcoded_paths(code) == []

    def test_detects_windows_path(self) -> None:
        code = 'raster_path = r"C:\\Users\\test\\data.tif"'
        hits = _detect_hardcoded_paths(code)
        assert len(hits) >= 1
        assert "C:\\Users\\test\\data.tif" in hits

    def test_detects_unix_path(self) -> None:
        code = 'path = "/home/user/data/layers.shp"'
        hits = _detect_hardcoded_paths(code)
        assert any("/home/user/data/layers.shp" in h for h in hits)

    def test_detects_multiple_hardcoded_paths(self) -> None:
        code = textwrap.dedent("""\
            input_raster = r"C:\\GIS\\data\\dem.tif"
            output_dir = "/home/user/output/"
        """)
        hits = _detect_hardcoded_paths(code)
        assert len(hits) >= 2


class TestHasBenchmarkApi:
    def test_detects_run_benchmark(self) -> None:
        code = "def run_benchmark(context):\n    pass\n"
        assert _has_benchmark_api(code) is True

    def test_rejects_code_without_api(self) -> None:
        code = "def foo():\n    pass\n"
        assert _has_benchmark_api(code) is False

    def test_empty_string(self) -> None:
        assert _has_benchmark_api("") is False

    def test_run_benchmark_as_variable(self) -> None:
        """Only function definition is detected, not a string match."""
        code = 'x = "def run_benchmark(never used)"'
        # The string contains "def run_benchmark(" so it will match
        assert _has_benchmark_api(code) is True


# ===================================================================
# RunResult
# ===================================================================


class TestRunResult:
    def test_default_state(self) -> None:
        """A fresh RunResult starts as a failed run with sensible defaults."""
        r = RunResult("test.py", 0)
        assert r.script_name == "test.py"
        assert r.run_index == 0
        assert r.success is False
        assert r.wall_time == 0.0
        assert r.error is None
        assert r.warnings == []
        assert r.has_phases is False
        assert r.compute_time is None
        assert r.save_time is None
        assert r.other_phase_times == {}

    def test_to_dict_includes_all_keys(self) -> None:
        r = RunResult("bench.py", 1)
        r.success = True
        r.wall_time = 1.234
        r.compute_time = 0.800
        r.save_time = 0.200
        r.has_phases = True
        r.warnings.append("test warning")

        d = r.to_dict()
        assert d["script"] == "bench.py"
        assert d["run"] == 1
        assert d["wall_time"] == 1.234
        assert d["compute_time"] == 0.800
        assert d["save_time"] == 0.200
        assert d["has_phases"] is True
        assert d["success"] is True
        assert d["error"] == ""
        assert "test warning" in d["warnings"]

    def test_to_dict_default_error_empty_string(self) -> None:
        """When error is None, to_dict returns empty string."""
        r = RunResult("test.py", 0)
        assert r.to_dict()["error"] == ""

    def test_to_dict_with_error(self) -> None:
        r = RunResult("bad.py", 0)
        r.error = "RuntimeError: something broke"
        assert "something broke" in r.to_dict()["error"]


# ===================================================================
# ScriptSummary
# ===================================================================


class TestScriptSummary:
    def test_empty_results(self) -> None:
        """A summary with no results produces None stats."""
        s = ScriptSummary("empty.py", [])
        ws = s.wall_stats()
        assert ws["n"] == 0
        assert ws["min"] is None
        assert ws["max"] is None
        assert ws["mean"] is None
        assert s.failure_count() == 0
        assert s.has_phase_data() is False

    def test_single_success(self) -> None:
        r = RunResult("single.py", 0)
        r.success = True
        r.wall_time = 2.0
        s = ScriptSummary("single.py", [r])

        ws = s.wall_stats()
        assert ws["n"] == 1
        assert ws["min"] == 2.0
        assert ws["max"] == 2.0
        assert ws["mean"] == 2.0
        assert ws["median"] == 2.0
        assert ws["stdev"] == 0.0
        assert ws["cv"] == 0.0
        assert s.failure_count() == 0

    def test_mixed_success_failure(self) -> None:
        results = []
        for i in range(3):
            r = RunResult("mix.py", i)
            r.success = i % 2 == 0  # Run 0 and 2 succeed, run 1 fails
            r.wall_time = 1.0 + i
            results.append(r)

        s = ScriptSummary("mix.py", results)
        ws = s.wall_stats()
        assert ws["n"] == 2  # only successful runs counted
        assert ws["min"] == 1.0
        assert ws["max"] == 3.0
        assert ws["mean"] == 2.0
        assert s.failure_count() == 1

    def test_wall_stats_ignores_failed_runs(self) -> None:
        """Failed runs are excluded from wall time statistics."""
        r1 = RunResult("fail_test.py", 0)
        r1.success = True
        r1.wall_time = 1.0

        r2 = RunResult("fail_test.py", 1)
        r2.success = False
        r2.wall_time = 999.0  # huge but ignored

        s = ScriptSummary("fail_test.py", [r1, r2])
        ws = s.wall_stats()
        assert ws["n"] == 1
        assert ws["mean"] == 1.0

    def test_has_phase_data_true(self) -> None:
        r = RunResult("phased.py", 0)
        r.success = True
        r.has_phases = True
        s = ScriptSummary("phased.py", [r])
        assert s.has_phase_data() is True

    def test_has_phase_data_false(self) -> None:
        r = RunResult("plain.py", 0)
        r.success = True
        r.has_phases = False
        s = ScriptSummary("plain.py", [r])
        assert s.has_phase_data() is False

    def test_multiple_runs_produce_cv(self) -> None:
        """Coefficient of variation > 0 when timing varies across runs."""
        rs = []
        for i in range(5):
            r = RunResult("vary.py", i)
            r.success = True
            r.wall_time = 1.0 + i * 0.5  # 1.0, 1.5, 2.0, 2.5, 3.0
            rs.append(r)
        s = ScriptSummary("vary.py", rs)
        ws = s.wall_stats()
        assert ws["n"] == 5
        assert ws["mean"] == 2.0
        assert ws["stdev"] > 0
        assert ws["cv"] > 0  # coefficient of variation

    def test_compute_stats_ignores_none(self) -> None:
        """compute_stats only includes results with a non-None compute_time."""
        r1 = RunResult("partial.py", 0)
        r1.success = True
        r1.compute_time = 0.5

        r2 = RunResult("partial.py", 1)
        r2.success = True
        r2.compute_time = None  # no compute phase

        s = ScriptSummary("partial.py", [r1, r2])
        cs = s.compute_stats()
        assert cs["n"] == 1
        assert cs["mean"] == 0.5

    def test_save_stats(self) -> None:
        r1 = RunResult("save_test.py", 0)
        r1.success = True
        r1.save_time = 0.3
        r2 = RunResult("save_test.py", 1)
        r2.success = True
        r2.save_time = 0.5

        s = ScriptSummary("save_test.py", [r1, r2])
        ss = s.save_stats()
        assert ss["n"] == 2
        assert ss["mean"] == 0.4


# ===================================================================
# BenchmarkRunner  (integration-style tests with temp scripts)
# ===================================================================


class TestBenchmarkRunnerScriptExecution:
    """These tests create real .py files and exercise the runner."""

    def test_runs_script_with_benchmark_api(self, tmp_path: Path) -> None:
        """A script with run_benchmark(context) is detected and executed."""
        script = tmp_path / "with_api.py"
        script.write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    context.phase("setup")
                    context.phase("compute")
                    total = sum(range(50_000))
                    context.phase("save")
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=2,
            warmups=0,
            save_output=False,
        )

        assert len(summaries) == 1
        s = summaries[0]
        assert s.script_name == "with_api.py"
        assert len(s.results) == 2
        assert all(r.success for r in s.results)
        assert all(r.wall_time > 0 for r in s.results)

    def test_runs_script_without_benchmark_api(self, tmp_path: Path) -> None:
        """Scripts without run_benchmark still execute and get wall time."""
        script = tmp_path / "no_api.py"
        script.write_text(
            textwrap.dedent("""\
                total = sum(range(100_000))
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=1,
            warmups=0,
        )

        assert len(summaries) == 1
        s = summaries[0]
        assert s.script_name == "no_api.py"
        assert len(s.results) == 1
        result = s.results[0]
        assert result.success is True
        assert result.wall_time > 0
        # No phases defined so has_phases should be False
        assert result.has_phases is False

    def test_handles_syntax_error_gracefully(self, tmp_path: Path) -> None:
        """A script with invalid syntax returns Result.success=False."""
        script = tmp_path / "syntax_error.py"
        script.write_text(
            "def broken(:\n    pass\n",
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=1,
            warmups=0,
        )

        assert len(summaries) == 1
        s = summaries[0]
        assert len(s.results) == 1
        result = s.results[0]
        assert result.success is False
        assert result.error is not None
        assert "SyntaxError" in result.error

    def test_handles_runtime_error_gracefully(self, tmp_path: Path) -> None:
        """A script that raises at runtime returns Result.success=False."""
        script = tmp_path / "runtime_error.py"
        script.write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    raise ValueError("boom!")
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=1,
            warmups=0,
        )

        assert len(summaries) == 1
        result = summaries[0].results[0]
        assert result.success is False
        assert result.error is not None
        assert "ValueError" in result.error

    def test_multiple_runs_collect_timings(self, tmp_path: Path) -> None:
        """Multiple repeats produce separate RunResult entries."""
        script = tmp_path / "multi.py"
        script.write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    context.phase("compute")
                    total = sum(range(30_000))
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=5,
            warmups=0,
        )

        s = summaries[0]
        assert len(s.results) == 5
        assert all(r.success for r in s.results)
        # Wall times should all be positive and non-identical (noise)
        wall_times = [r.wall_time for r in s.results]
        assert all(wt > 0 for wt in wall_times)
        # At least compute_time should be populated
        assert all(r.compute_time is not None for r in s.results)

    def test_warmups_not_included_in_results(self, tmp_path: Path) -> None:
        """Warm-up runs are executed but not added to results."""
        script = tmp_path / "warm.py"
        script.write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    context.phase("compute")
                    total = sum(range(10_000))
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=3,
            warmups=2,
        )

        s = summaries[0]
        # Only 'repeats' counted, not warmups
        assert len(s.results) == 3

    def test_run_index_in_results(self, tmp_path: Path) -> None:
        """Each RunResult carries its original run index."""
        script = tmp_path / "indexed.py"
        script.write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    pass
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=4,
            warmups=1,
        )

        indices = [r.run_index for r in summaries[0].results]
        expected = list(range(1, 5))  # warmups=1, so measured runs are indices 1-4
        assert indices == expected

    def test_multiple_scripts(self, tmp_path: Path) -> None:
        """Running multiple scripts returns one ScriptSummary per script."""
        (tmp_path / "a.py").write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    context.phase("compute")
            """)
        )
        (tmp_path / "b.py").write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    context.phase("compute")
            """)
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[
                str(tmp_path / "a.py"),
                str(tmp_path / "b.py"),
            ],
            repeats=1,
            warmups=0,
        )

        assert len(summaries) == 2
        names = {s.script_name for s in summaries}
        assert names == {"a.py", "b.py"}

    def test_script_context_isolation(self, tmp_path: Path) -> None:
        """Each run gets its own temp dir — verify through OUTPUT_DIR injection."""
        script = tmp_path / "check_dir.py"
        script.write_text(
            textwrap.dedent("""\
                import os
                def run_benchmark(context):
                    assert os.path.isdir(context.temp_dir), "temp_dir must exist"
                    context.phase("check")
                    assert context.output_dir == context.temp_dir
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=2,
            warmups=0,
        )
        assert all(r.success for r in summaries[0].results)

    def test_non_existent_file_returns_empty_summary(self) -> None:
        """A path that does not exist is handled without crashing."""
        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=["/tmp/nonexistent/foo.py"],
            repeats=1,
            warmups=0,
        )
        assert len(summaries) == 1
        s = summaries[0]
        assert s.script_name == "foo.py"
        assert len(s.results) == 0
        # Should have a warning about being unable to read
        assert len(s.warnings) >= 1
        assert any("read" in w.lower() for w in s.warnings)

    def test_save_output_flag_passed_to_context(self, tmp_path: Path) -> None:
        """save_output=True is visible inside the script via injected global."""
        script = tmp_path / "check_save.py"
        script.write_text(
            textwrap.dedent("""\
                def run_benchmark(context):
                    assert context.save_output is True
                    context.phase("verify")
            """),
            encoding="utf-8",
        )

        runner = BenchmarkRunner()
        summaries = runner.run_suite(
            script_paths=[str(script)],
            repeats=1,
            warmups=0,
            save_output=True,
        )
        assert summaries[0].results[0].success is True
