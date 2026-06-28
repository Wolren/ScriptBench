"""
reporter.py  --  generate HTML benchmark reports and CSV statistics.

The HTML report is self-contained: all charts are inline SVG produced from
Python standard library data only (no external JS/CSS dependencies that
could break inside QGIS's bundled Python environment).
"""

import csv
from datetime import datetime
from typing import Any, Optional

from .runner import ScriptSummary


def compute_derived(
    summaries: list[ScriptSummary],
) -> list[dict[str, Any]]:
    return _compute_derived(summaries)


# --------------------------------------------------------------------------
# CSV export
# --------------------------------------------------------------------------


def export_csv(summaries: list[ScriptSummary], output_path: str) -> None:
    rows = []
    for s in summaries:
        ws = s.wall_stats()
        cs = s.compute_stats()
        ss = s.save_stats()
        rows.append(
            {
                "script": s.script_name,
                "runs": ws["n"],
                "failures": s.failure_count(),
                "wall_mean": _fmt(ws["mean"]),
                "wall_min": _fmt(ws["min"]),
                "wall_max": _fmt(ws["max"]),
                "wall_median": _fmt(ws["median"]),
                "wall_stdev": _fmt(ws["stdev"]),
                "wall_cv_pct": _fmt(ws["cv"]),
                "compute_mean": _fmt(cs["mean"]),
                "save_mean": _fmt(ss["mean"]),
                "has_phases": s.has_phase_data(),
                "warnings": "; ".join(s.warnings),
            }
        )

    if not rows:
        return

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


# --------------------------------------------------------------------------
# Derived comparison metrics
# --------------------------------------------------------------------------


def _compute_derived(summaries: list[ScriptSummary]) -> list[dict[str, Any]]:
    rows = []
    valid = [s for s in summaries if s.wall_stats()["mean"] is not None]
    if not valid:
        return rows
    fastest_mean = min(s.wall_stats()["mean"] for s in valid)

    for s in summaries:
        ws = s.wall_stats()
        cs = s.compute_stats()
        ss = s.save_stats()
        mean = ws["mean"]
        speedup = (mean / fastest_mean) if (mean and fastest_mean > 0) else None
        compute_share = None
        save_share = None
        if mean and cs["mean"]:
            compute_share = cs["mean"] / mean * 100
        if mean and ss["mean"]:
            save_share = ss["mean"] / mean * 100
        rows.append(
            {
                "script": s.script_name,
                "wall_mean": mean,
                "wall_min": ws["min"],
                "wall_median": ws["median"],
                "wall_stdev": ws["stdev"],
                "wall_cv": ws["cv"],
                "compute_mean": cs["mean"],
                "save_mean": ss["mean"],
                "compute_share_pct": compute_share,
                "save_share_pct": save_share,
                "speedup_vs_fastest": speedup,
                "failures": s.failure_count(),
                "runs": ws["n"],
                "has_phases": s.has_phase_data(),
                "warnings": s.warnings,
            }
        )
    rows.sort(key=lambda r: r["wall_mean"] or 1e9)
    return rows


# --------------------------------------------------------------------------
# Inline SVG chart helpers
# --------------------------------------------------------------------------


def _bar_chart_svg(
    labels: list[str],
    values: list[Optional[float]],
    title: str,
    color: str = "#4a90d9",
    unit: str = "s",
    width: int = 680,
    height: int = 300,
) -> str:
    clean = [(label, v if v is not None else 0.0) for label, v in zip(labels, values)]
    max_val = max(v for _, v in clean) if clean else 1.0
    if max_val == 0:
        max_val = 1.0
    margin_left = 160
    margin_right = 20
    margin_top = 40
    margin_bottom = 40
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom
    bar_h = max(12, chart_h // max(len(clean), 1) - 6)
    gap = max(4, (chart_h - bar_h * len(clean)) // max(len(clean) + 1, 1))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="font-family:sans-serif;font-size:12px;">'
    ]
    # title
    parts.append(
        f'<text x="{width // 2}" y="20" text-anchor="middle" '
        f'font-size="14" font-weight="bold" fill="#222">{_esc(title)}</text>'
    )

    for i, (label, val) in enumerate(clean):
        y = margin_top + gap + i * (bar_h + gap)
        bar_w = int(val / max_val * chart_w)
        # bar
        fill = color if val > 0 else "#e0e0e0"
        parts.append(
            f'<rect x="{margin_left}" y="{y}" width="{bar_w}" height="{bar_h}" '
            f'fill="{fill}" rx="3"/>'
        )
        # label
        parts.append(
            f'<text x="{margin_left - 6}" y="{y + bar_h // 2 + 4}" '
            f'text-anchor="end" fill="#333">{_esc(label[:28])}</text>'
        )
        # value
        if val > 0:
            val_str = f"{val:.3f}{unit}"
            parts.append(
                f'<text x="{margin_left + bar_w + 4}" y="{y + bar_h // 2 + 4}" '
                f'fill="#555">{val_str}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def _grouped_bar_svg(
    labels: list[str],
    groups: dict[str, list[Optional[float]]],
    title: str,
    colors: dict[str, str],
    unit: str = "s",
    width: int = 680,
    height: int = 320,
) -> str:
    """Grouped horizontal bar chart. groups = {group_name: [values per label]}"""
    n_scripts = len(labels)
    n_groups = len(groups)
    if n_scripts == 0 or n_groups == 0:
        return ""

    all_vals = [v for vals in groups.values() for v in vals if v is not None]
    max_val = max(all_vals) if all_vals else 1.0
    if max_val == 0:
        max_val = 1.0

    margin_left = 160
    margin_right = 120
    margin_top = 50
    margin_bottom = 30
    chart_w = width - margin_left - margin_right
    chart_h = height - margin_top - margin_bottom

    group_block = chart_h // n_scripts
    bar_h = max(8, group_block // (n_groups + 1))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="font-family:sans-serif;font-size:11px;">'
    ]
    parts.append(
        f'<text x="{width // 2}" y="22" text-anchor="middle" '
        f'font-size="13" font-weight="bold" fill="#222">{_esc(title)}</text>'
    )

    gnames = list(groups.keys())
    for si, label in enumerate(labels):
        block_top = margin_top + si * group_block
        # script label
        parts.append(
            f'<text x="{margin_left - 6}" y="{block_top + group_block // 2 + 4}" '
            f'text-anchor="end" fill="#333">{_esc(label[:28])}</text>'
        )
        for gi, gname in enumerate(gnames):
            val = groups[gname][si]
            if val is None:
                continue
            y = block_top + gi * (bar_h + 2) + 4
            bar_w = int(val / max_val * chart_w)
            col = colors.get(gname, "#888")
            parts.append(
                f'<rect x="{margin_left}" y="{y}" width="{bar_w}" height="{bar_h}" '
                f'fill="{col}" rx="2"/>'
            )
            if val > 0:
                parts.append(
                    f'<text x="{margin_left + bar_w + 3}" y="{y + bar_h - 1}" '
                    f'fill="#555">{val:.3f}{unit}</text>'
                )

    # legend
    lx = width - margin_right + 10
    for gi, gname in enumerate(gnames):
        col = colors.get(gname, "#888")
        ly = margin_top + gi * 20
        parts.append(
            f'<rect x="{lx}" y="{ly}" width="14" height="12" fill="{col}" rx="2"/>'
        )
        parts.append(
            f'<text x="{lx + 18}" y="{ly + 10}" fill="#333">{_esc(gname)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# --------------------------------------------------------------------------
# HTML report
# --------------------------------------------------------------------------

_CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f6fa;color:#222;margin:0;padding:0}
.wrap{max-width:900px;margin:0 auto;padding:32px 24px}
h1{font-size:1.6rem;color:#1a2533;margin-bottom:4px}
.meta{color:#666;font-size:0.85rem;margin-bottom:32px}
h2{font-size:1.15rem;color:#2a3a55;border-bottom:2px solid #d0d8e8;padding-bottom:6px;margin-top:40px}
h3{font-size:1rem;color:#3a4a6a;margin-top:28px}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:0.88rem}
th{background:#2a3a55;color:#fff;padding:8px 10px;text-align:left;white-space:nowrap}
td{padding:7px 10px;border-bottom:1px solid #e2e6f0;vertical-align:top}
tr:nth-child(even) td{background:#f0f3fa}
tr.fastest td{background:#eaf7ee}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:0.78rem;font-weight:600}
.badge-ok{background:#d4edda;color:#155724}
.badge-fail{background:#f8d7da;color:#721c24}
.badge-warn{background:#fff3cd;color:#856404}
.badge-nophase{background:#e2e3e5;color:#383d41}
.warn-box{background:#fffbe6;border-left:4px solid #f0ad4e;padding:8px 14px;
          margin:8px 0;font-size:0.83rem;border-radius:0 4px 4px 0}
.chart-wrap{margin:20px 0;overflow-x:auto}
.toc a{color:#2a3a55;text-decoration:none;display:block;padding:2px 0}
.toc a:hover{text-decoration:underline}
footer{margin-top:48px;color:#aaa;font-size:0.78rem;text-align:center}
"""


def export_html(
    summaries: list[ScriptSummary],
    output_path: str,
    suite_name: str = "",
    repeats: int = 0,
    warmups: int = 0,
) -> None:
    rows = _compute_derived(summaries)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = f"ScriptBench Report — {suite_name}" if suite_name else "ScriptBench Report"

    def _s(v, fmt=".3f", suffix="s"):
        if v is None:
            return '<span style="color:#aaa">—</span>'
        return f"{v:{fmt}}{suffix}"

    def _badge(s: ScriptSummary) -> str:
        if s.failure_count() == len(s.results) and s.results:
            return '<span class="badge badge-fail">all failed</span>'
        if s.failure_count() > 0:
            return f'<span class="badge badge-warn">{s.failure_count()} fail</span>'
        return '<span class="badge badge-ok">ok</span>'

    # ---------- charts ----------
    labels = [r["script"] for r in rows]
    wall_means = [r["wall_mean"] for r in rows]
    compute_means = [r["compute_mean"] for r in rows]
    save_means = [r["save_mean"] for r in rows]

    chart_wall = _bar_chart_svg(
        labels, wall_means, "Mean wall-clock time per script", "#4a7fc1"
    )

    has_any_phases = any(r["has_phases"] for r in rows)
    chart_phase = ""
    if has_any_phases:
        chart_phase = _grouped_bar_svg(
            labels,
            {"compute": compute_means, "save": save_means},
            "Compute vs save phase time",
            {"compute": "#4a7fc1", "save": "#e07b4a"},
        )

    cv_vals = [r["wall_cv"] for r in rows]
    chart_cv = _bar_chart_svg(
        labels, cv_vals, "Coefficient of variation (wall time)", "#7bbf72", unit="%"
    )

    speedups = [r["speedup_vs_fastest"] for r in rows]
    chart_speedup = _bar_chart_svg(
        labels, speedups, "Slowdown vs fastest (1.0 = fastest)", "#c17a4a", unit="x"
    )

    # ---------- summary table ----------
    summary_rows_html = []
    for idx, r in enumerate(rows):
        tr_class = ' class="fastest"' if idx == 0 and r["wall_mean"] is not None else ""
        s_obj = next((s for s in summaries if s.script_name == r["script"]), None)
        badge = _badge(s_obj) if s_obj else ""
        phase_badge = (
            '<span class="badge badge-ok">yes</span>'
            if r["has_phases"]
            else '<span class="badge badge-nophase">no</span>'
        )
        speedup_str = (
            f"{r['speedup_vs_fastest']:.2f}x"
            if r["speedup_vs_fastest"] is not None
            else "—"
        )
        summary_rows_html.append(f"""
        <tr{tr_class}>
          <td><a href="#detail-{_esc(r["script"])}">{_esc(r["script"])}</a></td>
          <td>{_s(r["wall_mean"])}</td>
          <td>{_s(r["wall_min"])}</td>
          <td>{_s(r["wall_median"])}</td>
          <td>{_s(r["wall_stdev"])}</td>
          <td>{_s(r["wall_cv"], ".1f", "%")}</td>
          <td>{_s(r["compute_mean"])}</td>
          <td>{_s(r["save_mean"])}</td>
          <td>{speedup_str}</td>
          <td>{r["failures"]}/{r["runs"]}</td>
          <td>{badge}</td>
          <td>{phase_badge}</td>
        </tr>""")

    # ---------- per-script detail ----------
    detail_sections = []
    for r in rows:
        s_obj = next((s for s in summaries if s.script_name == r["script"]), None)
        if s_obj is None:
            continue
        warn_html = ""
        if s_obj.warnings:
            for w in s_obj.warnings[:5]:
                if w.startswith("PROFILE:"):
                    warn_html += f'<details><summary>cProfile output</summary><pre style="font-size:0.78rem;overflow-x:auto">{_esc(w[8:])}</pre></details>'
                else:
                    warn_html += f'<div class="warn-box">{_esc(w)}</div>'

        per_run_rows = "".join(
            f"<tr><td>{res.run_index}</td>"
            f"<td>{_s(res.wall_time)}</td>"
            f"<td>{_s(res.compute_time)}</td>"
            f"<td>{_s(res.save_time)}</td>"
            f"<td>{'yes' if res.success else '<span style=color:red>FAIL</span>'}</td>"
            f"<td style='font-size:0.78rem;color:#c00'>{_esc(res.error or '')[:120]}</td></tr>"
            for res in s_obj.results
        )

        detail_sections.append(f"""
        <h3 id="detail-{_esc(r["script"])}">{_esc(r["script"])}</h3>
        {warn_html}
        <table>
          <tr><th>Run</th><th>Wall</th><th>Compute</th><th>Save</th><th>Status</th><th>Error</th></tr>
          {per_run_rows}
        </table>""")

    toc_links = "".join(
        f'<a href="#detail-{_esc(r["script"])}">{_esc(r["script"])}</a>' for r in rows
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>{_esc(title)}</h1>
  <div class="meta">Generated: {now} &nbsp;|&nbsp; Suite: {_esc(suite_name or "—")}
  &nbsp;|&nbsp; Repeats: {repeats} &nbsp;|&nbsp; Warm-ups: {warmups}
  &nbsp;|&nbsp; Scripts: {len(summaries)}</div>

  <h2>Quick navigation</h2>
  <div class="toc">{toc_links}</div>

  <h2>Comparison overview</h2>
  <div class="chart-wrap">{chart_wall}</div>
  {'<div class="chart-wrap">' + chart_phase + "</div>" if chart_phase else ""}
  <div class="chart-wrap">{chart_speedup}</div>
  <div class="chart-wrap">{chart_cv}</div>

  <h2>Summary table</h2>
  <p style="font-size:0.82rem;color:#555">Rows sorted fastest to slowest by mean wall time.
  Highlighted row is the fastest. Phase times available only for scripts that implement
  the <code>run_benchmark(context)</code> API.</p>
  <table>
    <tr>
      <th>Script</th>
      <th>Mean</th><th>Min</th><th>Median</th><th>Stdev</th><th>CV</th>
      <th>Compute mean</th><th>Save mean</th>
      <th>Slowdown</th><th>Fail/Runs</th><th>Status</th><th>Phases</th>
    </tr>
    {"".join(summary_rows_html)}
  </table>

  <h2>Per-script details</h2>
  {"".join(detail_sections)}

  <footer>ScriptBench &mdash; QGIS benchmark plugin</footer>
</div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)
