"""Pure functions that turn cached run and job records into the report's numbers.

Definitions used throughout:

* A run's wall-clock time is the latest job `completed_at` minus the earliest
  job `created_at`, over the jobs of the run's final attempt. This is the time
  a person waits for a verdict.
* A job's runner time is `completed_at - started_at`. Billed minutes round each
  job up to a whole minute, the way GitHub bills private repositories.
* Queue time is `started_at - created_at` for a job.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median


def ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def seconds(start: str | None, end: str | None) -> float | None:
    a, b = ts(start), ts(end)
    if a is None or b is None:
        return None
    return max((b - a).total_seconds(), 0.0)


def percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile; no interpolation, so it is always an observed value."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def final_attempt_jobs(jobs: list[dict]) -> list[dict]:
    if not jobs:
        return []
    last = max(j.get("run_attempt", 1) for j in jobs)
    return [j for j in jobs if j.get("run_attempt", 1) == last]


def job_seconds(job: dict) -> float:
    return seconds(job.get("started_at"), job.get("completed_at")) or 0.0


def billed_minutes(job: dict) -> int:
    """Whole minutes a private repository would be billed for this job."""
    if job.get("conclusion") == "skipped":
        return 0
    secs = job_seconds(job)
    return math.ceil(secs / 60) if secs > 0 else 0


def run_wall_seconds(jobs: list[dict]) -> float | None:
    jobs = [j for j in final_attempt_jobs(jobs) if j.get("completed_at")]
    if not jobs:
        return None
    start = min(ts(j["created_at"]) for j in jobs)
    end = max(ts(j["completed_at"]) for j in jobs)
    return (end - start).total_seconds()


def duration_summary(runs: list[dict], jobs_by_run: dict[int, list[dict]]) -> dict:
    """Wall-clock and runner-time statistics for runs that reached a verdict."""
    verdict = [r for r in runs if r["conclusion"] in ("success", "failure")]
    walls, runner, billed = [], [], []
    for run in verdict:
        jobs = final_attempt_jobs(jobs_by_run.get(run["id"], []))
        wall = run_wall_seconds(jobs)
        if wall is None:
            continue
        walls.append(wall)
        runner.append(sum(job_seconds(j) for j in jobs))
        billed.append(sum(billed_minutes(j) for j in jobs))
    success_walls = [
        run_wall_seconds(jobs_by_run.get(r["id"], []))
        for r in verdict
        if r["conclusion"] == "success"
    ]
    success_walls = [w for w in success_walls if w is not None]
    return {
        "runs_total": len(runs),
        "runs_with_verdict": len(walls),
        "conclusions": dict(Counter(r["conclusion"] for r in runs)),
        "first_run": min(r["created_at"] for r in runs) if runs else None,
        "last_run": max(r["created_at"] for r in runs) if runs else None,
        "wall_median_s": median(walls) if walls else None,
        "wall_p90_s": percentile(walls, 90),
        "wall_min_s": min(walls) if walls else None,
        "wall_max_s": max(walls) if walls else None,
        "wall_median_success_s": median(success_walls) if success_walls else None,
        "runner_median_s": median(runner) if runner else None,
        "billed_median_min": median(billed) if billed else None,
        "billed_total_min": sum(billed),
    }


def base_job_name(name: str) -> str:
    """`test-mysql (3.12, Django>=5.2,<5.3, false)` -> `test-mysql`."""
    return name.split(" (")[0]


def job_breakdown(runs: list[dict], jobs_by_run: dict[int, list[dict]]) -> list[dict]:
    """Per matrix job: median duration, queue time and how often it finishes last."""
    success = [r for r in runs if r["conclusion"] == "success"]
    durations, queues, last = defaultdict(list), defaultdict(list), Counter()
    for run in success:
        jobs = [
            j
            for j in final_attempt_jobs(jobs_by_run.get(run["id"], []))
            if j.get("conclusion") == "success"
        ]
        if not jobs:
            continue
        for job in jobs:
            durations[job["name"]].append(job_seconds(job))
            queues[job["name"]].append(seconds(job["created_at"], job["started_at"]) or 0.0)
        # The job that sets the run's finish time, ignoring jobs that only
        # wait on others (those with a `needs` gate start late by design).
        test_jobs = [j for j in jobs if j["name"] != "coverage"]
        if test_jobs:
            last[max(test_jobs, key=lambda j: ts(j["completed_at"]))["name"]] += 1
    rows = []
    for name, values in durations.items():
        rows.append(
            {
                "job": name,
                "runs": len(values),
                "median_s": median(values),
                "p90_s": percentile(values, 90),
                "queue_median_s": median(queues[name]),
                "finished_last": last.get(name, 0),
            }
        )
    rows.sort(key=lambda r: -r["median_s"])
    return rows


def normalize_step(name: str) -> str:
    name = re.sub(r"@[0-9a-f]{40}", "", name)
    name = re.sub(r"Set up Python [0-9.]+", "Set up Python", name)
    # A report path that differs per matrix job would split one step into many.
    name = re.sub(r"\s+--junit-xml=\S+", "", name)
    return name


def step_breakdown(runs: list[dict], jobs_by_run: dict[int, list[dict]]) -> dict:
    """Share of runner time by step name, over successful runs."""
    success = [r for r in runs if r["conclusion"] == "success"]
    totals: Counter = Counter()
    job_total = 0.0
    for run in success:
        for job in final_attempt_jobs(jobs_by_run.get(run["id"], [])):
            if job.get("conclusion") != "success":
                continue
            job_total += job_seconds(job)
            for step in job.get("steps", []):
                secs = seconds(step.get("started_at"), step.get("completed_at")) or 0.0
                totals[normalize_step(step["name"])] += secs
    step_total = sum(totals.values())
    rows = [
        {"step": name, "seconds": secs, "share": secs / step_total if step_total else 0.0}
        for name, secs in totals.most_common()
    ]
    return {
        "runs": len(success),
        "job_seconds": job_total,
        "step_seconds": step_total,
        "rows": rows,
    }


def step_stats(
    runs: list[dict], jobs_by_run: dict[int, list[dict]], step_name: str
) -> dict[str, dict]:
    """Per job: median and p90 duration of one named step, over successful jobs."""
    values = defaultdict(list)
    for run in runs:
        for job in final_attempt_jobs(jobs_by_run.get(run["id"], [])):
            if job.get("conclusion") != "success":
                continue
            for step in job.get("steps", []):
                if normalize_step(step["name"]) == step_name:
                    secs = seconds(step.get("started_at"), step.get("completed_at"))
                    if secs is not None:
                        values[job["name"]].append(secs)
    return {
        name: {"n": len(v), "median_s": median(v), "p90_s": percentile(v, 90), "max_s": max(v)}
        for name, v in values.items()
    }


def cancelled_cost(runs: list[dict], jobs_by_run: dict[int, list[dict]]) -> dict:
    """Runner time used by runs that were cancelled before a verdict."""
    cancelled = [r for r in runs if r["conclusion"] == "cancelled"]
    secs = 0.0
    billed = 0
    for run in cancelled:
        for job in jobs_by_run.get(run["id"], []):
            secs += job_seconds(job)
            billed += billed_minutes(job)
    return {"runs": len(cancelled), "runner_seconds": secs, "billed_min": billed}


def superseded_runs(runs: list[dict], jobs_by_run: dict[int, list[dict]]) -> dict:
    """Pull-request runs that were still running when a newer commit started a new run.

    Runs are grouped by head branch and ordered by creation time. A run is
    superseded if the next run on the branch is for a different commit and was
    created before this one finished. `billed_min_after` is the running time of
    its jobs after that moment, in whole minutes per job: what cancelling
    superseded runs would have saved.
    """
    by_branch: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        if run["event"] == "pull_request" and run.get("head_branch"):
            by_branch[run["head_branch"]].append(run)
    count, billed = 0, 0
    for items in by_branch.values():
        items.sort(key=lambda r: r["created_at"])
        for older, newer in zip(items, items[1:], strict=False):
            if older["head_sha"] == newer["head_sha"] or older.get("run_attempt", 1) > 1:
                continue
            jobs = [j for j in jobs_by_run.get(older["id"], []) if j.get("completed_at")]
            if not jobs or max(ts(j["completed_at"]) for j in jobs) <= ts(newer["created_at"]):
                continue
            count += 1
            for job in jobs:
                start = max(ts(job["started_at"]), ts(newer["created_at"]))
                secs = (ts(job["completed_at"]) - start).total_seconds()
                if job.get("conclusion") != "skipped" and secs > 0:
                    billed += math.ceil(secs / 60)
    return {"runs": count, "billed_min_after": billed}


def rerun_kind(run: dict, prior: list[dict]) -> str | None:
    """Why a run has more than one attempt.

    `after_failure`: an earlier attempt failed or timed out, and someone ran it again.
    `after_approval`: the earlier attempt was held for maintainer approval
    (`action_required`), so the second attempt is the first real execution.
    `other`: anything else, for example a re-run of a cancelled attempt.
    """
    if run.get("run_attempt", 1) <= 1:
        return None
    conclusions = {a.get("conclusion") for a in prior}
    if conclusions & {"failure", "timed_out"}:
        return "after_failure"
    if conclusions and conclusions <= {"action_required"}:
        return "after_approval"
    return "other"


def failure_rates(runs: list[dict], prior_by_run: dict[int, list[dict]]) -> list[dict]:
    """Per workflow and trigger: conclusions, failure rate and re-run rate.

    Failure rate = failure / (success + failure). Cancelled runs and runs held
    for approval never reached a verdict and are left out of the denominator.
    Re-run rate = runs re-run after a failed attempt / runs that executed
    (success + failure + cancelled).
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for run in runs:
        groups[(run["name"], run["event"])].append(run)
    rows = []
    for (name, event), items in groups.items():
        counts = Counter(r["conclusion"] for r in items)
        kinds = Counter(rerun_kind(r, prior_by_run.get(r["id"], [])) for r in items)
        verdicts = counts["success"] + counts["failure"]
        executed = verdicts + counts["cancelled"]
        rows.append(
            {
                "workflow": name,
                "event": event,
                "runs": len(items),
                "success": counts["success"],
                "failure": counts["failure"],
                "cancelled": counts["cancelled"],
                "held_for_approval": counts["action_required"],
                "other": len(items) - executed - counts["action_required"],
                "failure_rate": counts["failure"] / verdicts if verdicts else None,
                "rerun_after_failure": kinds["after_failure"],
                "rerun_after_approval": kinds["after_approval"],
                "rerun_other": kinds["other"],
                "rerun_rate": kinds["after_failure"] / executed if executed else None,
            }
        )
    rows.sort(key=lambda r: (-r["runs"], r["workflow"], r["event"]))
    return rows


def totals(rows: list[dict]) -> dict:
    keys = (
        "runs",
        "success",
        "failure",
        "cancelled",
        "held_for_approval",
        "rerun_after_failure",
        "rerun_after_approval",
        "rerun_other",
    )
    out = {k: sum(r[k] for r in rows) for k in keys}
    verdicts = out["success"] + out["failure"]
    executed = verdicts + out["cancelled"]
    out["failure_rate"] = out["failure"] / verdicts if verdicts else None
    out["rerun_rate"] = out["rerun_after_failure"] / executed if executed else None
    return out


def all_attempt_jobs(jobs: list[dict], prior: list[dict]) -> list[dict]:
    """Jobs from every attempt of a run, without duplicates."""
    seen, out = set(), []
    for job in [j for a in prior for j in a.get("jobs", [])] + list(jobs):
        if job["id"] not in seen:
            seen.add(job["id"])
            out.append(job)
    return out


def flaky_candidates(
    runs: list[dict], jobs_by_run: dict[int, list[dict]], prior_by_run: dict[int, list[dict]]
) -> list[dict]:
    """Jobs that failed and then passed on the same commit, with no code change.

    A job that fails in attempt N and succeeds in a later attempt of the same
    run ran against the same commit both times, so the difference is not the
    code. This is the strongest flakiness signal the run history holds.
    """
    out = []
    for run in runs:
        by_name: dict[str, dict[int, str]] = defaultdict(dict)
        failed_step: dict[str, str] = {}
        jobs = all_attempt_jobs(jobs_by_run.get(run["id"], []), prior_by_run.get(run["id"], []))
        for job in jobs:
            by_name[job["name"]][job.get("run_attempt", 1)] = job.get("conclusion")
            if job.get("conclusion") == "failure":
                steps = [
                    s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"
                ]
                failed_step[job["name"]] = steps[0] if steps else ""
        for name, attempts in by_name.items():
            ordered = [attempts[k] for k in sorted(attempts)]
            for i, conclusion in enumerate(ordered[:-1]):
                if conclusion == "failure" and "success" in ordered[i + 1 :]:
                    out.append(
                        {
                            "run_id": run["id"],
                            "workflow": run["name"],
                            "event": run["event"],
                            "branch": run.get("head_branch"),
                            "job": name,
                            "failed_step": failed_step.get(name, ""),
                            "attempts": len(ordered),
                            "url": run.get("html_url"),
                        }
                    )
                    break
    return out


def failing_jobs(runs: list[dict], jobs_by_run: dict[int, list[dict]]) -> list[dict]:
    """Which jobs and steps fail, over the final attempt of every run.

    `allowed` counts failures in runs that still concluded `success`: the job
    is marked continue-on-error, so its failure does not fail the run.
    """
    counts: Counter = Counter()
    allowed: Counter = Counter()
    for run in runs:
        for job in final_attempt_jobs(jobs_by_run.get(run["id"], [])):
            if job.get("conclusion") != "failure":
                continue
            steps = [s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"]
            key = (
                run["name"],
                base_job_name(job["name"]),
                normalize_step(steps[0]) if steps else "",
            )
            counts[key] += 1
            if run["conclusion"] == "success":
                allowed[key] += 1
    return [
        {"workflow": w, "job": j, "step": s, "failures": n, "allowed": allowed[(w, j, s)]}
        for (w, j, s), n in counts.most_common()
    ]


def failed_run_shapes(runs: list[dict], jobs_by_run: dict[int, list[dict]]) -> dict:
    """For failed runs: how many test jobs failed together.

    A failure in most of the matrix at once points at the commit. A failure in
    a single job while the same tests pass elsewhere is worth a closer look.
    """
    shapes = Counter()
    single = []
    for run in runs:
        if run["conclusion"] != "failure":
            continue
        jobs = final_attempt_jobs(jobs_by_run.get(run["id"], []))
        failed = [j for j in jobs if j.get("conclusion") == "failure"]
        if len(failed) == 1:
            shapes["one_job"] += 1
            single.append(
                {
                    "run_id": run["id"],
                    "job": failed[0]["name"],
                    "event": run["event"],
                    "url": failed[0].get("html_url"),
                }
            )
        elif len(failed) > 1:
            shapes["several_jobs"] += 1
        else:
            shapes["no_failed_job"] += 1
    return {"shapes": dict(shapes), "single_job_failures": single}


def queue_summary(
    runs: list[dict], jobs_by_run: dict[int, list[dict]], threshold: float = 60
) -> dict:
    """How much of the wall-clock tail is waiting for a runner rather than running.

    For each successful run: the longest wait any test job had between being
    created and starting. The `coverage` job is left out because it waits on
    the other jobs by design.
    """
    waits, slowest = [], None
    walls_waited, walls_prompt = [], []
    for run in runs:
        if run["conclusion"] != "success":
            continue
        jobs = [
            j
            for j in final_attempt_jobs(jobs_by_run.get(run["id"], []))
            if j["name"] != "coverage" and j.get("started_at")
        ]
        if not jobs:
            continue
        wait = max(seconds(j["created_at"], j["started_at"]) or 0.0 for j in jobs)
        waits.append(wait)
        wall = run_wall_seconds(jobs_by_run[run["id"]])
        (walls_waited if wait > threshold else walls_prompt).append(wall)
        if slowest is None or wall > slowest["wall_s"]:
            slowest = {
                "run_id": run["id"],
                "wall_s": wall,
                "queue_s": wait,
                "url": run.get("html_url"),
            }
    return {
        "wall_median_waited_s": median(walls_waited) if walls_waited else None,
        "wall_median_prompt_s": median(walls_prompt) if walls_prompt else None,
        "runs": len(waits),
        "threshold_s": threshold,
        "runs_over_threshold": sum(1 for w in waits if w > threshold),
        "median_s": median(waits) if waits else None,
        "p90_s": percentile(waits, 90),
        "max_s": max(waits) if waits else None,
        "slowest_run": slowest,
    }


def python_pairs(job_rows: list[dict]) -> list[dict]:
    """Matrix jobs that ran on two Python versions with nothing else changed.

    Job names look like `test-mysql (3.12, Django>=6.1,<6.2, ...)`. Two rows
    whose names match after the first field is removed differ only in the
    Python version, so their medians can be compared directly.
    """
    groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for row in job_rows:
        match = re.match(r"^(.*? \()([0-9.]+), (.*)$", row["job"])
        if match:
            groups[match.group(1) + match.group(3)].append((match.group(2), row))
    out = []
    for key, items in groups.items():
        if len(items) != 2:
            continue
        (old_py, old), (new_py, new) = sorted(
            items, key=lambda i: tuple(int(p) for p in i[0].split("."))
        )
        out.append(
            {
                "job": key,
                "old_python": old_py,
                "new_python": new_py,
                "old_runs": old["runs"],
                "new_runs": new["runs"],
                "old_median_s": old["median_s"],
                "new_median_s": new["median_s"],
                "change": (new["median_s"] - old["median_s"]) / old["median_s"],
            }
        )
    out.sort(key=lambda r: r["change"])
    return out
