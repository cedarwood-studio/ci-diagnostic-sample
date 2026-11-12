"""Fill the report template from metrics.json and render it to one HTML file.

Placeholders look like `{{ main.summary.wall_median_s | min }}`. Every number
in REPORT.md comes through one of them, so the report cannot drift from the
computed results. Tables are built by the functions in TABLES.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import markdown

from .analyze import lookup

PLACEHOLDER = re.compile(r"\{\{\s*([^}|]+?)\s*(?:\|\s*([a-z0-9_]+)\s*)?\}\}")


def fmt_min(value) -> str:
    return f"{value / 60:.1f}"


def fmt_mmss(value) -> str:
    value = int(round(value))
    return f"{value // 60}:{value % 60:02d}"


def fmt_pct(value) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def fmt_int(value) -> str:
    return f"{int(round(value)):,}"


def fmt_date(value) -> str:
    return str(value)[:10]


def fmt_sha(value) -> str:
    return str(value)[:7]


def fmt_mb(value) -> str:
    return f"{value / 1e6:,.0f}"


def fmt_count(value) -> str:
    return str(len(value))


def fmt_hours(value) -> str:
    return f"{value / 60:,.1f}"


def fmt_num(value) -> str:
    """Whole numbers without a decimal, halves and the like with one."""
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.1f}"


def fmt_hmm(value) -> str:
    """Seconds as h:mm:ss, for durations that pass an hour."""
    value = int(round(value))
    return f"{value // 3600}:{value % 3600 // 60:02d}:{value % 60:02d}"


def fmt_hrs(value) -> str:
    return f"{value / 3600:,.1f}"


def fmt_counts(value) -> str:
    return ", ".join(f"{k} {n}" for k, n in sorted(value.items(), key=lambda kv: -kv[1]))


def fmt_list(value) -> str:
    return ", ".join(f"`{v}`" for v in value) if value else "none"


def fmt_attempts(value) -> str:
    """`{"2": 26, "3": 15}` -> `2 attempts in 26 runs, 3 in 15`."""
    items = sorted(value.items(), key=lambda kv: int(kv[0]))
    parts = [f"{k} in {n}" for k, n in items]
    if parts:
        k, n = items[0]
        parts[0] = f"{k} attempts in {n} runs"
    return ", ".join(parts)


FORMATS = {
    "attempts": fmt_attempts,
    "hmm": fmt_hmm,
    "hrs": fmt_hrs,
    "counts": fmt_counts,
    "list": fmt_list,
    "min": fmt_min,
    "mmss": fmt_mmss,
    "pct": fmt_pct,
    "int": fmt_int,
    "date": fmt_date,
    "sha": fmt_sha,
    "mb": fmt_mb,
    "count": fmt_count,
    "num": fmt_num,
    "job": lambda value: short_job(value),
    "hours": fmt_hours,
}


def short_job(name: str, width: int = 70) -> str:
    name = name.replace("git+https://github.com/django/django.git@", "django@")
    name = name.replace("#egg=Django", "")
    return name.replace("|", "/")


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(" --- " for _ in header) + "|"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def t_jobs(m: dict) -> str:
    rows = [
        [
            short_job(j["job"]),
            j["runs"],
            fmt_mmss(j["median_s"]),
            fmt_mmss(j["p90_s"]),
            j["finished_last"],
        ]
        for j in m["main"]["current_matrix"]["jobs"]
    ]
    return table(["Job", "Runs", "Median", "90th pct", "Finished last"], rows)


def t_steps(m: dict) -> str:
    steps = m["main"]["steps"]
    rows = [
        [r["step"], fmt_min(r["seconds"] / steps["runs"]), fmt_pct(r["share"])]
        for r in steps["rows"][:8]
    ]
    return table(["Step", "Minutes per run, all jobs", "Share of step time"], rows)


def t_rates(m: dict) -> str:
    rows = [
        [
            r["workflow"],
            r["event"],
            r["runs"],
            r["success"],
            r["failure"],
            r["cancelled"],
            r["held_for_approval"],
            fmt_pct(r["failure_rate"]),
            r["rerun_after_failure"],
        ]
        for r in m["window"]["rows"]
    ]
    return table(
        [
            "Workflow",
            "Trigger",
            "Runs",
            "Passed",
            "Failed",
            "Cancelled",
            "Held for approval",
            "Failure rate",
            "Re-run after failure",
        ],
        rows,
    )


def t_failing(m: dict) -> str:
    rows = [[r["job"], r["step"], r["failures"], r["allowed"]] for r in m["window"]["failing_jobs"]]
    return table(["Job", "Failing step", "Failures", "Of which allowed to fail"], rows)


def t_actions(m: dict) -> str:
    rows = [
        [
            a["action"],
            f"`{(a['ref'] or '')[:12]}`",
            a["version_comment"] or "",
            a["references"],
            "commit SHA" if a["pin"] == "sha" else "tag or branch",
            a["runtime"] or "",
            a["latest_release"] or "",
            "yes" if a["archived"] else "no",
        ]
        for a in m["static"]["actions"]
    ]
    return table(
        [
            "Action",
            "Ref",
            "Version comment",
            "Uses",
            "Pinned to",
            "Runtime",
            "Latest release",
            "Archived",
        ],
        rows,
    )


def t_images(m: dict) -> str:
    rows = [
        [
            f"`{i['image']}`",
            i["file"].split("/")[-1],
            i["line"],
            {"floating": "moves with every release", "tag": "version tag", "digest": "digest"}[
                i["pin"]
            ],
        ]
        for i in m["static"]["images"]
    ]
    return table(["Image", "File", "Line", "Fixed by"], rows)


def t_circleci(m: dict) -> str:
    rows = [
        [j["job"], j["runs"], j["failed"], fmt_mmss(j["median_s"]), fmt_mmss(j["p95_s"])]
        for j in m["circleci"]["jobs"]
    ]
    return table(["Job", "Runs", "Failed", "Median", "95th pct"], rows)


def t_fix_runs(m: dict) -> str:
    rows = []
    for label in ("before", "after"):
        for r in m["fix"]["arms"][label]["runs"]:
            rows.append(
                [
                    label,
                    f"[{r['run_id']}]({r['url']})",
                    r["created_at"][11:16] + " UTC",
                    r["conclusion"],
                    fmt_mmss(r["wall_s"]),
                    fmt_min(r["runner_s"]),
                    r["billed_min"],
                    fmt_int(r["queue_max_s"]),
                ]
            )
    return table(
        [
            "Arm",
            "Run",
            "Started",
            "Result",
            "Wall clock",
            "Running time (min)",
            "Runner minutes",
            "Longest queue (s)",
        ],
        rows,
    )


def t_fix_jobs(m: dict) -> str:
    def tests(value):
        return "/".join(str(v) for v in value) if value else ""

    rows = [
        [
            short_job(r["job"]) + (" **(made parallel)**" if r.get("changed") else ""),
            fmt_mmss(r["before_s"]),
            fmt_mmss(r["after_s"]) if r["after_s"] is not None else "",
            tests(r["tests_before"]),
            tests(r["tests_after"]),
        ]
        for r in m["fix"]["job_rows"]
    ]
    return table(
        ["Job", "Before (median)", "After (median)", "Tests run before", "Tests run after"], rows
    )


def t_probe(m: dict) -> str:
    rows = [
        [
            short_job(r["job"]),
            fmt_mmss(r["with_coverage_s"]),
            fmt_mmss(r["without_coverage_s"]),
            f"{r['change'] * 100:+.0f}%",
            r["tests_ran"],
        ]
        for r in m["fix"]["probe"]["rows"]
    ]
    return table(
        [
            "Job",
            "With coverage (median of baseline runs)",
            "Without coverage (one run)",
            "Change",
            "Tests run",
        ],
        rows,
    )


def t_python(m: dict) -> str:
    rows = [
        [
            short_job(r["job"]),
            f"{r['old_python']} ({r['old_runs']} runs)",
            fmt_mmss(r["old_median_s"]),
            f"{r['new_python']} ({r['new_runs']} runs)",
            fmt_mmss(r["new_median_s"]),
            f"{r['change'] * 100:+.0f}%",
        ]
        for r in m["main"]["python_pairs"]
    ]
    return table(
        [
            "Job (Python version removed)",
            "Earlier Python",
            "Median",
            "Later Python",
            "Median",
            "Change",
        ],
        rows,
    )


def cell(text, width: int = 120) -> str:
    """Text made safe for one table cell: no pipes or line breaks, cut to `width`."""
    text = " ".join(str(text).split()).replace("|", "/")
    return text if len(text) <= width else text[: width - 3].rstrip() + "..."


def links(examples: list[dict]) -> str:
    return ", ".join(f"[{e['run_id']}]({e['url']})" for e in examples)


def span(first: str, last: str) -> str:
    first, last = fmt_date(first), fmt_date(last)
    return first if first == last else f"{first} to {last}"


def platforms(counts: dict) -> str:
    return ", ".join(f"{name} {n}" for name, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def t_flaky_tests(m: dict) -> str:
    rows = [
        [
            t["rank"],
            f"`{t['test']}`",
            t["failures"],
            t["runs"],
            span(t["first"], t["last"]),
            t["main_failures"],
            platforms(t["platforms"]),
            f"`{cell(t['error'] or t['error_type'])}`",
            links(t["examples"]),
        ]
        for t in m["flaky"]["tests"]
    ]
    return table(
        [
            "#",
            "Test",
            "Failed, then passed",
            "Runs",
            "Seen",
            "Also failed on main",
            "Runner",
            "Error line",
            "Most recent job logs",
        ],
        rows,
    )


def t_flaky_timeouts(m: dict) -> str:
    rows = [
        [
            f"`{r['key'][0]}`",
            f"{r['key'][1]} min",
            r["failures"],
            r["runs"],
            span(r["first"], r["last"]),
            links(r["examples"]),
        ]
        for r in m["flaky"]["timeouts"]
    ]
    return table(
        ["Job", "Step limit", "Failed, then passed", "Runs", "Seen", "Most recent job logs"],
        rows,
    )


def t_flaky_other(m: dict) -> str:
    rows = [
        [
            f"`{cell(r['key'][0], 70)}`",
            f"`{cell(r['key'][1])}`" if r["key"][1] else "none in the log",
            r["failures"],
            r["runs"],
            span(r["first"], r["last"]),
            links(r["examples"]),
        ]
        for r in m["flaky"]["other"]
    ]
    return table(
        [
            "Failing step",
            "Error line",
            "Failed, then passed",
            "Runs",
            "Seen",
            "Most recent job logs",
        ],
        rows,
    )


def t_flaky_shared(m: dict) -> str:
    rows = [
        [
            f"`{cell(r['key'][0], 140)}`",
            r["failures"],
            str(r["tests_min"])
            if r["tests_min"] == r["tests_max"]
            else f"{r['tests_min']} to {r['tests_max']}",
            span(r["first"], r["last"]),
            links(r["examples"]),
        ]
        for r in m["flaky"]["shared"]
    ]
    return table(
        ["Error line", "Failed, then passed", "Tests it took down per job", "Seen", "Job logs"],
        rows,
    )


def t_failing_top(m: dict) -> str:
    rows = [
        [f"`{r['job']}`", f"`{cell(r['step'], 90)}`", r["failures"]]
        for r in m["window"]["failing_jobs"][:10]
    ]
    return table(["Job", "Failing step", "Failures"], rows)


def t_flake_probe(m: dict) -> str:
    def outcome(r: dict) -> str:
        if r["finished"]:
            return "finished"
        if r["step_limit"]:
            return "stopped at our step limit"
        if r["timeouts"]:
            return "pytest-timeout ended the process"
        return r["conclusion"] or ""

    rows = [
        [
            f"[{r['run_id']}]({r['url']})",
            r["platform"],
            r["step"],
            r["passed"],
            r["failed"],
            outcome(r),
            fmt_mmss(r["seconds"]) if r["seconds"] is not None else "",
        ]
        for r in m["probe"]["rows"]
    ]
    return table(
        [
            "Run and job",
            "Runner",
            "Step",
            "Passed",
            "Failed",
            "How the step ended",
            "Time",
        ],
        rows,
    )


def t_flaky_platforms(m: dict) -> str:
    rows = [
        [r["platform"], fmt_int(r["executed"]), r["failed_then_passed"], fmt_pct(r["rate"])]
        for r in m["flaky"]["platforms"]
    ]
    return table(["Runner", "Job executions", "Failed, then passed", "Share"], rows)


def t_flaky_log(m: dict) -> str:
    what = {
        "timeout": "step past its time limit",
        "shared": "one error shared by many tests",
        "other": "outside the tests",
    }
    rows = []
    for i in m["flaky"]["instances"]:
        if i["kind"] == "test":
            names = sorted({t["name"] for t in i["tests"]})
            found = ", ".join(f"`{n}`" for n in names[:3])
            found += f" and {len(names) - 3} more" if len(names) > 3 else ""
        else:
            found = what[i["kind"]]
        rows.append(
            [
                fmt_date(i["started_at"]),
                f"[{i['run_id']}]({i['url']})",
                f"{i['attempt']}, passed in {i['passed_in_attempt']}",
                f"`{i['job']}`",
                found,
            ]
        )
    return table(["Date", "Job log", "Failed in attempt", "Job", "What failed"], rows)


def t_unpinned(m: dict) -> str:
    rows = [
        [f"`{u['action']}`", f"`{u['ref']}`", u["file"].split("/")[-1], u["line"]]
        for u in m["static"]["uses_unpinned"]
    ]
    return table(["Reference", "Ref", "File", "Line"], rows)


def t_jobs_all(m: dict) -> str:
    rows = [
        [
            f"`{short_job(j['job'])}`",
            j["runs"],
            fmt_mmss(j["median_s"]),
            fmt_mmss(j["p90_s"]),
            j["finished_last"],
        ]
        for j in m["main"]["current_matrix"]["jobs"]
    ]
    return table(["Job", "Runs", "Median", "90th pct", "Finished last"], rows)


TABLES = {
    "flaky_shared": t_flaky_shared,
    "failing_top": t_failing_top,
    "flaky_probe": t_flake_probe,
    "flaky_tests": t_flaky_tests,
    "flaky_timeouts": t_flaky_timeouts,
    "flaky_other": t_flaky_other,
    "flaky_platforms": t_flaky_platforms,
    "flaky_log": t_flaky_log,
    "unpinned": t_unpinned,
    "jobs_all": t_jobs_all,
    "python": t_python,
    "probe": t_probe,
    "jobs": t_jobs,
    "steps": t_steps,
    "rates": t_rates,
    "failing": t_failing,
    "actions": t_actions,
    "images": t_images,
    "circleci": t_circleci,
    "fix_runs": t_fix_runs,
    "fix_jobs": t_fix_jobs,
}


def render_markdown(template: str, metrics: dict) -> str:
    def replace(match: re.Match) -> str:
        path, fmt = match.group(1), match.group(2)
        if path.startswith("table:"):
            return TABLES[path.split(":", 1)[1]](metrics)
        value = lookup(metrics, path)
        return FORMATS[fmt](value) if fmt else str(value)

    return PLACEHOLDER.sub(replace, template)


CSS = """
:root { --fg:#1b1f1d; --muted:#5a635f; --line:#d9ddd9; --bg:#fbfbf9; --accent:#2f5d4a;
  --code:#f0f1ee; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e6e8e5; --muted:#a3aba6; --line:#3a403c; --bg:#151816; --accent:#8fc3aa;
    --code:#20241f; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font: 16px/1.55 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 52rem; margin: 0 auto; padding: 1.25rem 1rem 4rem; }
h1 { font-size: 1.7rem; line-height: 1.2; margin: 1.2rem 0 .6rem; }
h2 { font-size: 1.3rem; margin: 2.4rem 0 .6rem; padding-top: 1rem;
  border-top: 1px solid var(--line); }
h3 { font-size: 1.08rem; margin: 1.6rem 0 .4rem; }
a { color: var(--accent); }
blockquote { margin: 1rem 0; padding: .7rem 1rem; border-left: 4px solid var(--accent);
  background: var(--code); }
blockquote p { margin: 0; }
code { background: var(--code); padding: .1em .3em; border-radius: 3px; font-size: .9em;
  overflow-wrap: anywhere; }
pre { background: var(--code); padding: .8rem; border-radius: 4px; overflow-x: auto; }
pre code { padding: 0; background: none; overflow-wrap: normal; }
.table-wrap { overflow-x: auto; margin: 1rem 0; }
table { border-collapse: collapse; font-size: .9rem; min-width: 100%;
  font-variant-numeric: tabular-nums; }
th, td { border-bottom: 1px solid var(--line); padding: .35rem .6rem; text-align: left;
  vertical-align: top; }
th { color: var(--muted); font-weight: 600; white-space: nowrap; }
li { margin: .25rem 0; }
"""


def render_html(markdown_text: str, title: str) -> str:
    body = markdown.markdown(markdown_text, extensions=["tables", "fenced_code"])
    body = body.replace("<table>", '<div class="table-wrap"><table>')
    body = body.replace("</table>", "</table></div>")
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex">\n'
        f"<title>{html.escape(title)}</title>\n<style>{CSS}</style>\n</head>\n"
        f"<body>\n<main>\n{body}\n</main>\n</body>\n</html>\n"
    )


def write_report(template_path: Path, metrics: dict, out: Path) -> None:
    text = render_markdown(template_path.read_text(), metrics)
    (out / "REPORT.md").write_text(text)
    title = text.splitlines()[0].lstrip("# ").strip()
    (out / "report.html").write_text(render_html(text, title))
