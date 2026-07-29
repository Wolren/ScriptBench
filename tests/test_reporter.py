"""Tests for reporter.py — HTML/CSV export and derived statistics."""

import csv
import re

from scriptbench.reporter import (
    _bar_chart_svg,
    _compute_derived,
    _esc,
    _fmt,
    _grouped_bar_svg,
    compute_derived,
    export_csv,
    export_html,
)
from scriptbench.runner import RunResult, ScriptSummary

# ===================================================================
# Internal helpers
# ===================================================================


class TestFmt:
    def test_none_returns_empty(self) -> None:
        assert _fmt(None) == ""

    def test_float_returns_6_decimal_places(self) -> None:
        assert _fmt(3.1415926535) == "3.141593"

    def test_int_is_str(self) -> None:
        assert _fmt(42) == "42"

    def test_string_passthrough(self) -> None:
        assert _fmt("hello") == "hello"

    def test_zero(self) -> None:
        assert _fmt(0.0) == "0.000000"


class TestEsc:
    def test_noop_for_plain_text(self) -> None:
        assert _esc("hello world") == "hello world"

    def test_escapes_ampersand(self) -> None:
        assert _esc("a & b") == "a &amp; b"

    def test_escapes_lt(self) -> None:
        assert _esc("a < b") == "a &lt; b"

    def test_escapes_gt(self) -> None:
        assert _esc("a > b") == "a &gt; b"

    def test_escapes_quote(self) -> None:
        assert _esc('say "hi"') == "say &quot;hi&quot;"

    def test_escapes_all(self) -> None:
        assert _esc('<tag attr="x&y">') == "&lt;tag attr=&quot;x&amp;y&quot;&gt;"


# ===================================================================
# _bar_chart_svg
# ===================================================================


class TestBarChartSvg:
    def test_returns_svg_string(self) -> None:
        svg = _bar_chart_svg(["a"], [1.0], "Test")
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")
        assert 'width="680"' in svg or "width" in svg

    def test_empty_labels_returns_valid_svg(self) -> None:
        svg = _bar_chart_svg([], [], "Empty")
        assert svg.startswith("<svg")
        assert "</svg>" in svg

    def test_includes_title(self) -> None:
        svg = _bar_chart_svg(["x"], [0.5], "My Chart")
        assert "My Chart" in svg

    def test_multiple_bars(self) -> None:
        svg = _bar_chart_svg(["a", "b", "c"], [1.0, 2.0, 3.0], "Multi")
        assert svg.count("<rect") == 3
        assert svg.count("</text>") >= 3

    def test_distinguishes_zero_and_none(self) -> None:
        """None values render as zero-width grey bars."""
        svg = _bar_chart_svg(["a", "b"], [1.0, None], "Mixed")
        assert '<rect' in svg
        assert "#e0e0e0" in svg  # grey for None/zero

    def test_max_val_zero_does_not_crash(self) -> None:
        """When all values are zero, max_val defaults to 1.0."""
        svg = _bar_chart_svg(["a"], [0.0], "Zero")
        assert "</svg>" in svg


# ===================================================================
# _grouped_bar_svg
# ===================================================================


class TestGroupedBarSvg:
    def test_returns_svg_string(self) -> None:
        svg = _grouped_bar_svg(
            labels=["a", "b"],
            groups={"compute": [0.5, 1.0], "save": [0.2, 0.3]},
            title="Grouped",
            colors={"compute": "blue", "save": "orange"},
        )
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_empty_labels_returns_empty_string(self) -> None:
        svg = _grouped_bar_svg(
            labels=[], groups={}, title="Empty", colors={}
        )
        assert svg == ""

    def test_includes_legend(self) -> None:
        svg = _grouped_bar_svg(
            labels=["x"],
            groups={"compute": [0.5], "save": [0.3]},
            title="Legend Test",
            colors={"compute": "#111", "save": "#222"},
        )
        assert "compute" in svg
        assert "save" in svg


# ===================================================================
# compute_derived / _compute_derived
# ===================================================================


class TestComputeDerived:
    def test_empty_summaries_returns_empty(self, empty_summaries) -> None:
        assert _compute_derived(empty_summaries) == []

    def test_all_failures_returns_empty(self) -> None:
        """When every ScriptSummary has mean=None, result is empty."""
        r = RunResult("fail.py", 0)
        r.success = False
        s = ScriptSummary("fail.py", [r])
        result = _compute_derived([s])
        assert result == []

    def test_two_scripts_correctly_identifies_fastest(
        self, sample_summaries
    ) -> None:
        """The fastest script (smallest mean) is identified correctly."""
        rows = compute_derived(sample_summaries)
        assert len(rows) == 2
        # fastest is script_a with mean=0.6
        assert rows[0]["script"] == "script_a.py"
        assert rows[1]["script"] == "script_b.py"

    def test_speedup_vs_fastest(self, sample_summaries) -> None:
        rows = compute_derived(sample_summaries)
        # script_a is fastest -> speedup = 1.0
        assert rows[0]["speedup_vs_fastest"] == 1.0
        # script_b mean=1.1 / script_a mean=0.6 ≈ 1.833
        assert rows[1]["speedup_vs_fastest"] is not None
        assert abs(rows[1]["speedup_vs_fastest"] - (1.1 / 0.6)) < 0.01

    def test_compute_share_pct(self, sample_summaries) -> None:
        rows = compute_derived(sample_summaries)
        # script_a: compute_mean=0.35 / wall_mean=0.6 * 100 ≈ 58.33%
        assert rows[0]["compute_share_pct"] is not None
        assert abs(rows[0]["compute_share_pct"] - (0.35 / 0.6 * 100)) < 0.5

    def test_save_share_pct(self, sample_summaries) -> None:
        rows = compute_derived(sample_summaries)
        # script_a: save_mean=0.12 / wall_mean=0.6 * 100 ≈ 20%
        assert rows[0]["save_share_pct"] is not None
        assert abs(rows[0]["save_share_pct"] - (0.12 / 0.6 * 100)) < 0.5

    def test_has_phases_reflected(self, sample_summaries) -> None:
        rows = compute_derived(sample_summaries)
        assert rows[0]["has_phases"] is True   # script_a
        assert rows[1]["has_phases"] is False  # script_b

    def test_failures_counted(self, sample_summaries) -> None:
        rows = compute_derived(sample_summaries)
        # script_b has 1 failure out of 3 runs
        assert rows[1]["failures"] == 1
        assert rows[1]["runs"] == 2  # only successful runs counted for n

    def test_single_result_works(self, single_run_summary) -> None:
        rows = compute_derived([single_run_summary])
        assert len(rows) == 1
        assert rows[0]["wall_mean"] == 0.123456
        assert rows[0]["wall_min"] == 0.123456
        assert rows[0]["wall_median"] == 0.123456
        assert rows[0]["wall_stdev"] == 0.0
        assert rows[0]["wall_cv"] == 0.0

    def test_sorted_by_mean(self) -> None:
        """Rows are sorted ascending by wall_mean."""
        r1 = RunResult("slow.py", 0)
        r1.success = True
        r1.wall_time = 5.0

        r2 = RunResult("fast.py", 0)
        r2.success = True
        r2.wall_time = 1.0

        s1 = ScriptSummary("slow.py", [r1])
        s2 = ScriptSummary("fast.py", [r2])
        rows = compute_derived([s1, s2])
        assert rows[0]["script"] == "fast.py"
        assert rows[1]["script"] == "slow.py"


# ===================================================================
# export_csv
# ===================================================================


class TestExportCsv:
    def test_writes_csv_file(self, sample_summaries, tmp_path) -> None:
        """export_csv writes a valid CSV to the given path."""
        out = tmp_path / "report.csv"
        export_csv(sample_summaries, str(out))

        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "script" in content
        assert "script_a.py" in content
        assert "script_b.py" in content

    def test_csv_has_expected_columns(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.csv"
        export_csv(sample_summaries, str(out))

        with open(out, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        assert len(rows) == 2
        expected_keys = {
            "script", "runs", "failures", "wall_mean", "wall_min",
            "wall_max", "wall_median", "wall_stdev", "wall_cv_pct",
            "compute_mean", "save_mean", "has_phases", "warnings",
        }
        assert set(rows[0].keys()) == expected_keys

    def test_csv_empty_summaries_does_not_write_file(
        self, empty_summaries, tmp_path
    ) -> None:
        """export_csv with no summaries does not create a file."""
        out = tmp_path / "empty.csv"
        export_csv(empty_summaries, str(out))
        # The function returns early when rows are empty
        assert not out.exists()

    def test_csv_numeric_values(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.csv"
        export_csv(sample_summaries, str(out))

        with open(out, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        # script_a wall_mean ≈ 0.6
        wall_mean_a = float(rows[0]["wall_mean"])
        assert abs(wall_mean_a - 0.6) < 0.01
        assert rows[0]["has_phases"] == "True"

    def test_csv_failures(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.csv"
        export_csv(sample_summaries, str(out))

        with open(out, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        # script_b has 1 failure
        b_row = next(r for r in rows if r["script"] == "script_b.py")
        assert int(b_row["failures"]) == 1


# ===================================================================
# export_html
# ===================================================================


class TestExportHtml:
    def test_writes_html_file(self, sample_summaries, tmp_path) -> None:
        """export_html writes a valid HTML file."""
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out), suite_name="test-suite")

        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert content.startswith("<!DOCTYPE html>")
        assert "</html>" in content

    def test_contains_suite_name(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out), suite_name="my-suite")

        content = out.read_text(encoding="utf-8")
        assert "my-suite" in content

    def test_contains_script_names(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out))

        content = out.read_text(encoding="utf-8")
        assert "script_a.py" in content
        assert "script_b.py" in content

    def test_contains_inline_svg(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out))

        content = out.read_text(encoding="utf-8")
        # Should have at least one inline SVG chart
        assert "<svg" in content

    def test_contains_table(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out))

        content = out.read_text(encoding="utf-8")
        assert "<table" in content
        assert "<th>Mean</th>" in content
        assert "<th>Min</th>" in content

    def test_empty_summaries_does_not_crash(
        self, empty_summaries, tmp_path
    ) -> None:
        out = tmp_path / "empty.html"
        export_html(empty_summaries, str(out))
        content = out.read_text(encoding="utf-8")
        assert "</html>" in content

    def test_contains_timestamp(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out))
        content = out.read_text(encoding="utf-8")
        # Should contain a date/time pattern
        assert re.search(r"\d{4}-\d{2}-\d{2}", content) is not None

    def test_contains_runs_info(self, sample_summaries, tmp_path) -> None:
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out), repeats=3, warmups=1)

        content = out.read_text(encoding="utf-8")
        assert "Repeats: 3" in content
        assert "Warm-ups: 1" in content

    def test_shows_failure_badges(self, sample_summaries, tmp_path) -> None:
        """Script with failures gets a warning/fail badge."""
        out = tmp_path / "report.html"
        export_html(sample_summaries, str(out))

        content = out.read_text(encoding="utf-8")
        # script_b has 1 failure -> should appear as warning
        assert "badge" in content
