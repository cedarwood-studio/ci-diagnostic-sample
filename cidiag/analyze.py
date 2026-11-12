"""Build the full set of report numbers from the cached API responses."""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from statistics import median

from . import actions, fetch, flaky
from . import metrics as m
from .gh import Client


def lookup(data, dotted: str):
    """`a.b.0.c` -> data["a"]["b"][0]["c"]."""
    for part in dotted.split("."):
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def _jobs_and_prior(client: Client, repo: str, runs: list[dict]):
    jobs = {r["id"]: fetch.run_jobs(client, repo, r["id"]) for r in runs}
    prior = {
        r["id"]: fetch.prior_attempts(client, repo, r) for r in runs if r.get("run_attempt", 1) > 1
    }
    return jobs, prior


def main_branch(client: Client, cfg: dict) -> dict:
    repo = cfg["repo"]
    runs = fetch.main_runs(client, repo, cfg["workflow"], cfg["branch"], cfg["main_run_count"])
    jobs, _ = _jobs_and_prior(client, repo, runs)
    # A job that only reports on other jobs always finishes last; leave it out.
    gate = set(cfg.get("flaky", {}).get("gate_jobs", []))
    if gate:
        jobs = {rid: [j for j in items if j["name"] not in gate] for rid, items in jobs.items()}
    summary = m.duration_summary(runs, jobs)
    breakdown = m.job_breakdown(runs, jobs)
    steps = m.step_breakdown(runs, jobs)

    # The matrix changed during the window, so job-level numbers are also
    # reported for the runs that used the matrix in the current workflow file.
    anchor = runs[0] if runs else None
    if cfg.get("profile") == "flaky":
        # Half the runs here end red, and a red run can be missing jobs, so the
        # current matrix is read from the most recent run that passed.
        anchor = next((r for r in runs if r["conclusion"] == "success"), anchor)
    current_names = {j["name"] for j in jobs[anchor["id"]]} if anchor else set()
    current = [
        r
        for r in runs
        if r["conclusion"] == "success" and {j["name"] for j in jobs[r["id"]]} == current_names
    ]
    current_summary = m.duration_summary(current, jobs)
    current_breakdown = m.job_breakdown(current, jobs)
    return {
        "summary": summary,
        "jobs": breakdown,
        "steps": steps,
        "step_test": m.step_stats(runs, jobs, "Test"),
        "cancelled": m.cancelled_cost(runs, jobs),
        "queue": m.queue_summary(runs, jobs),
        "python_pairs": m.python_pairs(breakdown),
        "failing_jobs": m.failing_jobs(runs, jobs),
        "failed_runs": [
            {"run_id": r["id"], "created_at": r["created_at"], "url": r["html_url"]}
            for r in runs
            if r["conclusion"] == "failure"
        ],
        "current_matrix": {
            "summary": current_summary,
            "jobs": current_breakdown,
            "first_run": min((r["created_at"] for r in current), default=None),
            "job_count": len(current_names),
            "test_job_count": len(current_names - {"coverage"}),
            "test_mysql_last": sum(
                j["finished_last"] for j in current_breakdown if j["job"].startswith("test-mysql")
            ),
        },
        "test_mysql_last": sum(
            j["finished_last"] for j in breakdown if j["job"].startswith("test-mysql")
        ),
        "success_runs": steps["runs"],
    }


def window(client: Client, cfg: dict) -> dict:
    repo = cfg["repo"]
    scoped = cfg.get("profile") == "flaky"
    runs = fetch.window_runs(
        client, repo, cfg["window_since"], cfg["window_until"], cfg.get("window_by_day", False)
    )
    if scoped:
        jobs = fetch.scoped_jobs(client, cfg, runs)
        prior = {
            r["id"]: fetch.prior_attempts(client, repo, r)
            for r in runs
            if r.get("run_attempt", 1) > 1
        }
    else:
        jobs, prior = _jobs_and_prior(client, repo, runs)
    # Workflows GitHub generates itself (Dependabot, Copilot, code scanning
    # setup) are counted but reported apart from the repository's own files.
    own = [r for r in runs if r.get("path", "").startswith(".github/workflows/")]
    rows = m.failure_rates(own, prior)
    ci = [r for r in own if r["name"] == cfg["workflow_name"]]
    by_event = {row["event"]: row for row in rows if row["workflow"] == cfg["workflow_name"]}
    shapes = {
        event: m.failed_run_shapes([r for r in ci if r["event"] == event], jobs)
        for event in sorted({r["event"] for r in ci})
    }
    for shape in shapes.values():
        for item in [] if scoped else shape["single_job_failures"]:
            job_id = int(item["url"].rsplit("/", 1)[1])
            item["failed_tests"] = actions.failed_tests(fetch.job_log(client, repo, job_id))
    main_push = [r for r in ci if r["event"] == "push" and r["head_branch"] == cfg["branch"]]
    main_counts = Counter(r["conclusion"] for r in main_push)
    main_verdicts = main_counts["success"] + main_counts["failure"]
    pr_runs = [r for r in ci if r["event"] == "pull_request"]
    return {
        "ci_main_push": {
            "runs": len(main_push),
            "success": main_counts["success"],
            "failure": main_counts["failure"],
            "cancelled": main_counts["cancelled"],
            "verdicts": main_verdicts,
            "failure_rate": main_counts["failure"] / main_verdicts if main_verdicts else None,
        },
        "ci_push_branches": len({r["head_branch"] for r in ci if r["event"] == "push"}),
        "ci_pr_duration": m.duration_summary(
            [r for r in pr_runs if r["conclusion"] == "success"], jobs
        ),
        "ci_pr_inspectable_failures": sum(
            1
            for r in pr_runs
            if r["conclusion"] == "failure"
            and any(j.get("conclusion") == "failure" for j in jobs[r["id"]])
        ),
        "since": cfg["window_since"],
        "until": cfg["window_until"],
        "runs_all": len(runs),
        "runs_own": len(own),
        "runs_generated": len(runs) - len(own),
        "rows": rows,
        "totals": m.totals(rows),
        "ci_totals": m.totals([r for r in rows if r["workflow"] == cfg["workflow_name"]]),
        "ci_by_event": by_event,
        "flaky_candidates": m.flaky_candidates(own, jobs, prior),
        "failing_jobs": m.failing_jobs(ci, jobs),
        "failed_shapes": shapes,
        "ci_verdict_runs": sum(1 for r in ci if r["conclusion"] in ("success", "failure")),
        "ci_cancelled_cost": m.cancelled_cost(ci, jobs),
    }


def static_checks(client: Client, cfg: dict) -> dict:
    repo = cfg["repo"]
    files = fetch.workflow_files(client, repo, cfg["workflow_ref"])
    uses, images, job_rows, assessed = [], [], [], []
    for path, text in sorted(files.items()):
        uses += actions.find_uses(path, text)
        images += actions.find_images(path, text)
        job_rows += actions.job_caches(path, text)
    seen = set()
    for use in uses:
        key = (use["action"], use["ref"])
        if not use["ref"] or key in seen:
            continue
        seen.add(key)
        owner_repo, subpath = actions.action_repo(use["action"])
        meta = fetch.action_metadata(client, owner_repo, use["ref"], subpath)
        row = actions.assess_action(use, meta)
        row["references"] = sum(1 for u in uses if (u["action"], u["ref"]) == key)
        assessed.append(row)
    pins = Counter(u["pin"] for u in uses)
    installing = [j for j in job_rows if j["installs"]]
    return {
        "ref": cfg["workflow_ref"],
        "files": sorted(files),
        "uses_total": len(uses),
        "uses_by_pin": dict(pins),
        "uses_unpinned": [u for u in uses if u["pin"] == "tag_or_branch"],
        "actions": sorted(assessed, key=lambda r: r["action"]),
        "actions_distinct": len(assessed),
        "action_repos": len({actions.action_repo(a["action"])[0] for a in assessed}),
        "actions_archived": [a["action"] for a in assessed if a["archived"]],
        "actions_deprecated_runtime": [a["action"] for a in assessed if a["runtime_deprecated"]],
        "actions_behind": [a for a in assessed if (a["majors_behind"] or 0) > 0],
        "images": images,
        "images_floating": [i for i in images if i["pin"] == "floating"],
        "jobs": job_rows,
        "jobs_installing": len(installing),
        "jobs_installing_without_cache": [j["job"] for j in installing if not j["has_cache"]],
    }


def cache_checks(client: Client, cfg: dict) -> dict:
    repo = cfg["repo"]
    runs = fetch.main_runs(client, repo, cfg["workflow"], cfg["branch"], cfg["main_run_count"])
    sample = fetch.log_sample(runs, cfg["log_run_count"])
    outcome = Counter()
    logs_read = 0
    installs = []
    for run in sample:
        for job in fetch.run_jobs(client, repo, run["id"]):
            if job["name"] == "coverage":
                continue
            text = fetch.job_log(client, repo, job["id"])
            if not text:
                outcome["log_unavailable"] += 1
                continue
            logs_read += 1
            outcome[actions.parse_log(text)["cache"]] += 1
            for step in job.get("steps", []):
                if step["name"] == "Install dependencies" and step.get("conclusion") == "success":
                    installs.append(m.seconds(step["started_at"], step["completed_at"]))
    entries = fetch.caches(client, repo)
    never_read = [
        e for e in entries if (m.seconds(e["created_at"], e["last_accessed_at"]) or 0) < 60
    ]
    looked_up = outcome["hit"] + outcome["miss"]
    return {
        "sample_runs": len(sample),
        "sample_first": min((r["created_at"] for r in sample), default=None),
        "sample_last": max((r["created_at"] for r in sample), default=None),
        "logs_read": logs_read,
        "outcome": dict(outcome),
        "hit_rate": outcome["hit"] / looked_up if looked_up else None,
        "install_median_s": median(installs) if installs else None,
        "install_p90_s": m.percentile(installs, 90),
        "entries": len(entries),
        "entries_bytes": sum(e["size_in_bytes"] for e in entries),
        "entries_on_default_branch": sum(1 for e in entries if e["ref"] == "refs/heads/main"),
        "entries_never_read": len(never_read),
        "entries_never_read_on_pr": sum(1 for e in never_read if e["ref"].startswith("refs/pull/")),
    }


def circleci(client: Client, cfg: dict) -> dict | None:
    if not cfg.get("circleci"):
        return None
    data = fetch.circleci(
        client, cfg["circleci"]["slug"], cfg["circleci"]["workflow"], cfg["branch"]
    )
    name = cfg["circleci"]["workflow"]
    wf = next(i for i in data["workflows"]["items"] if i["name"] == name)
    config = fetch.repo_file(client, cfg["repo"], ".circleci/config.yml", cfg["workflow_ref"]) or ""
    orbs = []
    in_orbs = False
    for line in config.splitlines():
        if line.startswith("orbs:"):
            in_orbs = True
            continue
        if in_orbs:
            if not line.startswith(" "):
                break
            if ":" in line:
                ref = line.split(":", 1)[1].strip()
                version = ref.partition("@")[2]
                exact = version.count(".") == 2 and version.replace(".", "").isdigit()
                orbs.append({"orb": ref, "pin": "exact" if exact else "floating"})
    return {
        "workflow": name,
        "window_start": wf["window_start"],
        "window_end": wf["window_end"],
        "total_runs": wf["metrics"]["total_runs"],
        "failed_runs": wf["metrics"]["failed_runs"],
        "success_rate": wf["metrics"]["success_rate"],
        "median_s": wf["metrics"]["duration_metrics"]["median"],
        "p95_s": wf["metrics"]["duration_metrics"]["p95"],
        "jobs": [
            {
                "job": i["name"],
                "runs": i["metrics"]["total_runs"],
                "failed": i["metrics"]["failed_runs"],
                "median_s": i["metrics"]["duration_metrics"]["median"],
                "p95_s": i["metrics"]["duration_metrics"]["p95"],
            }
            for i in data["jobs"]["items"]
        ],
        "orbs": orbs,
        "orbs_floating": [o["orb"] for o in orbs if o["pin"] == "floating"],
    }


def fix(client: Client, cfg: dict) -> dict | None:
    spec = cfg.get("fix")
    if not spec or not all(arm["run_ids"] for arm in spec["arms"]):
        return None
    repo = spec["repo"]
    out = {"repo": repo, "arms": {}}
    for arm in spec["arms"]:
        runs, jobs, tests = [], {}, {}
        for run_id in arm["run_ids"]:
            run = client.get(f"repos/{repo}/actions/runs/{run_id}")
            runs.append(run)
            jobs[run_id] = fetch.run_jobs(client, repo, run_id)
            for job in jobs[run_id]:
                parsed = actions.parse_log(fetch.job_log(client, repo, job["id"]))
                if parsed["tests_ran"] is not None:
                    tests.setdefault(job["name"], set()).add(parsed["tests_ran"])
        per_run = []
        for run in runs:
            final = m.final_attempt_jobs(jobs[run["id"]])
            per_run.append(
                {
                    "run_id": run["id"],
                    "url": run["html_url"],
                    "sha": run["head_sha"],
                    "conclusion": run["conclusion"],
                    "created_at": run["created_at"],
                    "wall_s": m.run_wall_seconds(final),
                    "runner_s": sum(m.job_seconds(j) for j in final),
                    "billed_min": sum(m.billed_minutes(j) for j in final),
                    "queue_max_s": max(
                        (m.seconds(j["created_at"], j["started_at"]) or 0)
                        for j in final
                        if j["name"] != "coverage"
                    ),
                }
            )
        out["arms"][arm["label"]] = {
            "branch": arm["branch"],
            "runs": per_run,
            "n": len(per_run),
            "all_success": all(r["conclusion"] == "success" for r in per_run),
            "summary": m.duration_summary(runs, jobs),
            "jobs": {row["job"]: row for row in m.job_breakdown(runs, jobs)},
            "tests_ran": {name: sorted(counts) for name, counts in sorted(tests.items())},
        }
    before, after = out["arms"]["before"], out["arms"]["after"]
    out["wall_saved_s"] = before["summary"]["wall_median_s"] - after["summary"]["wall_median_s"]
    out["wall_saved_share"] = out["wall_saved_s"] / before["summary"]["wall_median_s"]
    out["billed_saved_min"] = (
        before["summary"]["billed_median_min"] - after["summary"]["billed_median_min"]
    )
    out["billed_saved_share"] = out["billed_saved_min"] / before["summary"]["billed_median_min"]
    out["runner_saved_s"] = (
        before["summary"]["runner_median_s"] - after["summary"]["runner_median_s"]
    )
    longest = max(after["jobs"].values(), key=lambda row: row["median_s"])
    out["after_longest"] = {"job": longest["job"], "median_s": longest["median_s"]}
    out["ranges_overlap"] = (
        "don't overlap"
        if after["summary"]["wall_max_s"] < before["summary"]["wall_min_s"]
        else "overlap"
    )

    # The fix adds `--parallel` to matrix entries, and GitHub puts matrix values
    # in the job name, so jobs are matched across arms with that value removed.
    def key(name: str) -> str:
        return name.replace(", --parallel", "")

    after_jobs = {key(name): (name, row) for name, row in after["jobs"].items()}
    after_tests = {key(name): counts for name, counts in after["tests_ran"].items()}
    before_tests = {key(name): counts for name, counts in before["tests_ran"].items()}
    out["tests_match"] = (
        "Every job reported the same number of tests before and after."
        if before_tests == after_tests
        else "Test counts differ between before and after in at least one job."
    )
    out["job_rows"] = [
        {
            "job": name,
            "before_s": row["median_s"],
            "after_s": after_jobs[key(name)][1]["median_s"] if key(name) in after_jobs else None,
            "changed": key(name) in after_jobs and after_jobs[key(name)][0] != name,
            "tests_before": before["tests_ran"].get(name),
            "tests_after": after_tests.get(key(name)),
        }
        for name, row in before["jobs"].items()
    ]
    probe = spec.get("probe")
    if probe and probe.get("run_ids"):
        run_id = probe["run_ids"][0]
        run = client.get(f"repos/{repo}/actions/runs/{run_id}")
        rows = []
        for job in fetch.run_jobs(client, repo, run_id):
            if not job["name"].startswith(probe["job_prefix"]):
                continue
            base = before["jobs"].get(job["name"])
            parsed = actions.parse_log(fetch.job_log(client, repo, job["id"]))
            secs = m.job_seconds(job)
            rows.append(
                {
                    "job": job["name"],
                    "conclusion": job["conclusion"],
                    "with_coverage_s": base["median_s"] if base else None,
                    "without_coverage_s": secs,
                    "change": (secs - base["median_s"]) / base["median_s"] if base else None,
                    "tests_ran": parsed["tests_ran"],
                }
            )
        rows.sort(key=lambda r: r["change"])
        out["probe"] = {
            "branch": probe["branch"],
            "run_id": run_id,
            "url": run["html_url"],
            "conclusion": run["conclusion"],
            "rows": rows,
        }
    return out


KINDS = ("test", "shared", "timeout", "other")
RETRY_RE = re.compile(r"--reruns[ =]\d+|nick-fields/retry|retry-action|--retries[ =]\d+")


def error_groups(instances: list[dict], groups: dict[str, list[str]]) -> dict:
    """Failed-then-passed executions whose errors contain one of a group's phrases.

    The phrases come from the sample's configuration. They let the report add
    up failures that share an outside cause (a download, say) across the tests,
    shared-error and other categories.
    """
    out = {}
    for name, phrases in groups.items():
        hits = []
        for item in instances:
            lines = [item["error"]] + [s["error"] for s in item["shared"]]
            lines += [t["error"] for t in item["tests"]]
            if any(p in line for p in phrases for line in lines):
                hits.append(item)
        out[name] = len(hits)
        out[f"{name}_runs"] = len({i["run_id"] for i in hits})
        out[f"{name}_days"] = len({i["started_at"][:10] for i in hits})
        out[f"{name}_first"] = min((i["started_at"] for i in hits), default=None)
        out[f"{name}_last"] = max((i["started_at"] for i in hits), default=None)
    return out


def flaky_checks(client: Client, cfg: dict) -> dict:
    """Jobs that failed and then passed on the same commit, and what their logs name."""
    repo = cfg["repo"]
    spec = cfg.get("flaky", {})
    gate = set(spec.get("gate_jobs", []))
    runs = fetch.window_runs(
        client, repo, cfg["window_since"], cfg["window_until"], cfg.get("window_by_day", False)
    )
    runs = [r for r in runs if r.get("path", "").startswith(".github/workflows/")]
    jobs = fetch.scoped_jobs(client, cfg, runs)
    prior = {
        r["id"]: fetch.prior_attempts(client, repo, r) for r in runs if r.get("run_attempt", 1) > 1
    }
    ci = [r for r in runs if r["name"] == cfg["workflow_name"]]
    kinds = {r["id"]: m.rerun_kind(r, prior.get(r["id"], [])) for r in ci}
    rerun = [r for r in ci if kinds[r["id"]] == "after_failure"]
    final = Counter(r["conclusion"] for r in rerun)
    verdicts = [r for r in ci if r["conclusion"] in ("success", "failure")]
    # Runs with a failed attempt: the final one, or an earlier one that was re-run.
    any_failed = [
        r for r in ci if r["conclusion"] == "failure" or kinds[r["id"]] == "after_failure"
    ]
    any_failed_verdicts = [r for r in any_failed if r["conclusion"] in ("success", "failure")]

    instances = flaky.failed_then_passed(ci, jobs, prior, gate)
    main_runs = fetch.main_runs(client, repo, cfg["workflow"], cfg["branch"], cfg["main_run_count"])
    main_jobs = {r["id"]: fetch.run_jobs(client, repo, r["id"]) for r in main_runs}
    main_failed_jobs = flaky.failed_final_jobs(main_runs, main_jobs, gate)
    slim = ("id", "file", "name", "error_type", "error", "step")
    for item in instances + main_failed_jobs:
        job_id = item["job_id"] if "job_id" in item else item["id"]
        text = fetch.job_log(client, repo, job_id, failures=True)
        item["parsed"] = flaky.summarize(flaky.parse_failures(text))
    flaky.resolve_files(
        [i["parsed"]["tests"] for i in instances + main_failed_jobs],
        fetch.repo_paths(client, repo, cfg["workflow_ref"], "tests/"),
    )
    for item in instances:
        parsed = item.pop("parsed")
        item["kind"] = parsed["kind"]
        item["platform"] = flaky.platform(item["job"])
        item["tests"] = [{k: t[k] for k in slim} for t in parsed["tests"]]
        item["shared"] = parsed["shared"]
        item["timeouts"] = parsed["timeouts"]
        item["error"] = parsed["error"]
        item["command"] = flaky.normalize_command(item["failed_step"])
    by_kind = Counter(i["kind"] for i in instances)
    named = [i for i in instances if i["kind"] == "test"]
    tests = flaky.rank_tests(named)
    for row in tests:
        only = {i["run_id"] for i in named if {t["id"] for t in i["tests"]} == {row["test"]}}
        row["runs_cleared"] = sum(
            1
            for run_id in only
            if all(
                i["kind"] == "test" and {t["id"] for t in i["tests"]} == {row["test"]}
                for i in instances
                if i["run_id"] == run_id
            )
        )
    timeouts = [i for i in instances if i["kind"] == "timeout"]
    recent_from = str(date.fromisoformat(cfg["window_until"]) - timedelta(days=6))
    shared_rows = flaky.group_counts(
        [{**i, "shared_error": sh} for i in instances for sh in i["shared"]],
        lambda i: (i["shared_error"]["error"],),
    )
    for row in shared_rows:
        counts = [
            sh["tests"] for i in instances for sh in i["shared"] if sh["error"] == row["key"][0]
        ]
        row["tests_min"], row["tests_max"] = min(counts), max(counts)

    # How often a job execution fails and later passes, by platform.
    executed: Counter = Counter()
    for run in ci:
        for job in flaky.executed_jobs(run, jobs[run["id"]], prior.get(run["id"], [])):
            if job["name"] not in gate and job.get("conclusion") in ("success", "failure"):
                executed[flaky.platform(job["name"])] += 1
    flaked = Counter(i["platform"] for i in instances)
    platforms = [
        {
            "platform": name,
            "executed": executed[name],
            "failed_then_passed": flaked[name],
            "rate": flaked[name] / executed[name] if executed[name] else None,
        }
        for name in sorted(executed, key=lambda n: -flaked[n])
    ]

    # The main branch: failed runs there were not re-run, so there is no
    # second attempt to compare. What can be said is whether the tests they
    # name are the same tests that failed and then passed elsewhere.
    known = {t["test"] for t in tests}
    on_main: Counter = Counter()
    main_kinds: Counter = Counter()
    run_tests: dict[int, set] = {}
    run_kinds: dict[int, set] = {}
    for job in main_failed_jobs:
        parsed = job["parsed"]
        main_kinds[parsed["kind"]] += 1
        run_kinds.setdefault(job["run_id"], set()).add(parsed["kind"])
        names = {t["id"] for t in parsed["tests"]}
        run_tests.setdefault(job["run_id"], set()).update(names)
        for name in names:
            on_main[name] += 1
    for row in tests:
        row["main_failures"] = on_main.get(row["test"], 0)

    # The job matrix as of the most recent run, and how runs on it have gone.
    def matrix(run: dict) -> frozenset:
        return frozenset(j["name"] for j in main_jobs[run["id"]] if " (" in j["name"])

    latest = [r for r in main_runs if matrix(r) == matrix(main_runs[0])] if main_runs else []
    latest_ids = {r["id"] for r in latest}
    latest_failed = [j for j in main_failed_jobs if j["run_id"] in latest_ids]
    latest_matrix = {
        "first_run": min((r["created_at"] for r in latest), default=None),
        "runs": len(latest),
        "conclusions": {
            k: sum(1 for r in latest if r["conclusion"] == k)
            for k in ("success", "failure", "cancelled")
        },
        "failed_jobs": len(latest_failed),
        "failed_jobs_by_kind": {
            k: sum(1 for j in latest_failed if j["parsed"]["kind"] == k) for k in KINDS
        },
        "failed_jobs_by_platform": dict(Counter(flaky.platform(j["name"]) for j in latest_failed)),
        "runs_with_timeout": sum(1 for rid in latest_ids if "timeout" in run_kinds.get(rid, set())),
        "timeout_jobs_windows": sum(
            1
            for j in latest_failed
            if j["parsed"]["kind"] == "timeout" and flaky.platform(j["name"]) == "windows"
        ),
        "timeout_jobs": sum(1 for j in latest_failed if j["parsed"]["kind"] == "timeout"),
    }
    main_failed = [r for r in main_runs if r["conclusion"] == "failure"]
    only_known = [
        rid
        for rid, kinds_seen in run_kinds.items()
        if kinds_seen == {"test"} and run_tests[rid] <= known
    ]
    main_other_tests = Counter({k: v for k, v in on_main.items() if k not in known})
    main = {
        "failed_runs": len(main_failed),
        "failed_runs_rerun": sum(1 for r in main_failed if r.get("run_attempt", 1) > 1),
        "runs_rerun": sum(1 for r in main_runs if r.get("run_attempt", 1) > 1),
        "failed_runs_with_jobs": len(run_kinds),
        "failed_jobs": sum(main_kinds.values()),
        "failed_jobs_by_kind": {k: main_kinds[k] for k in KINDS},
        "runs_naming_a_test": sum(1 for names in run_tests.values() if names),
        "runs_naming_a_known_test": sum(1 for names in run_tests.values() if names & known),
        "runs_only_known_tests": len(only_known),
        "runs_with_timeout": sum(1 for k in run_kinds.values() if "timeout" in k),
        "known_test_failures": sum(v for k, v in on_main.items() if k in known),
        "other_tests": [
            {"test": name, "failures": n} for name, n in main_other_tests.most_common(10)
        ],
        "other_tests_distinct": len(main_other_tests),
        "latest_matrix": latest_matrix,
    }

    files = fetch.workflow_files(client, repo, cfg["workflow_ref"])
    retries = [
        {"file": path.split("/")[-1], "line": number, "text": line.strip()[:160]}
        for path, text in sorted(files.items())
        for number, line in enumerate(text.splitlines(), start=1)
        if RETRY_RE.search(line)
    ]
    return {
        "ci_runs": len(ci),
        "ci_verdicts": len(verdicts),
        "any_attempt_failed": len(any_failed),
        "any_attempt_failed_verdicts": len(any_failed_verdicts),
        "any_attempt_failed_no_verdict": len(any_failed) - len(any_failed_verdicts),
        "any_attempt_failed_rate": len(any_failed_verdicts) / len(verdicts) if verdicts else None,
        "final_failure_rate": sum(1 for r in verdicts if r["conclusion"] == "failure")
        / len(verdicts)
        if verdicts
        else None,
        "rerun_runs": len(rerun),
        "rerun_share_of_failed": len(rerun) / len(any_failed) if any_failed else None,
        "rerun_final": {k: final[k] for k in ("success", "failure", "cancelled")},
        "rerun_by_event": dict(Counter(r["event"] for r in rerun)),
        "rerun_attempts_max": max((r["run_attempt"] for r in rerun), default=None),
        "approval_reruns": sum(1 for r in ci if kinds[r["id"]] == "after_approval"),
        "attempt_gt1": sum(1 for r in ci if r.get("run_attempt", 1) > 1),
        "gate_jobs": sorted(gate),
        "instances": instances,
        "instance_count": len(instances),
        "instance_runs": len({i["run_id"] for i in instances}),
        "first_instance": min((i["started_at"] for i in instances), default=None),
        "last_instance": max((i["started_at"] for i in instances), default=None),
        "by_kind": {k: by_kind[k] for k in KINDS},
        "tests": tests,
        "tests_distinct": len(tests),
        "tests_repeat": sum(1 for t in tests if t["failures"] > 1),
        "tests_once": sum(1 for t in tests if t["failures"] == 1),
        "tests_top_share": tests[0]["failures"] / len(named) if tests and named else None,
        "top2_failures": sum(t["failures"] for t in tests[:2]),
        "timeouts": flaky.group_counts(timeouts, lambda i: (i["job"], i["timeouts"][0]["minutes"])),
        "timeouts_by_platform": dict(Counter(i["platform"] for i in timeouts)),
        "timeouts_windows": sum(1 for i in timeouts if i["platform"] == "windows"),
        "timeouts_recent_from": recent_from,
        "timeouts_recent": sum(1 for i in timeouts if i["started_at"][:10] >= recent_from),
        "timeouts_first": min((i["started_at"] for i in timeouts), default=None),
        "other": flaky.group_counts(
            [i for i in instances if i["kind"] == "other"],
            lambda i: (i["command"], i["error"]),
        ),
        "shared": shared_rows,
        "pr_first_pass": m.duration_summary(
            [
                r
                for r in ci
                if r["event"] == "pull_request"
                and r["conclusion"] == "success"
                and r.get("run_attempt", 1) == 1
            ],
            jobs,
        ),
        "platforms": platforms,
        "cost": flaky.rerun_cost(ci, jobs, prior),
        "retries_configured": retries,
        "platform_rates": {r["platform"]: r["rate"] for r in platforms},
        "downloads": error_groups(instances, spec.get("error_groups", {})),
        "superseded": m.superseded_runs(ci, jobs),
        "cancels_superseded": any(
            "cancel-in-progress" in text
            for path, text in files.items()
            if path.endswith(cfg["workflow"])
        ),
        "main": main,
    }


def cache_checks_flaky(client: Client, cfg: dict) -> dict:
    """Cache hits read from job logs, for a pipeline with a uv cache and a Rust build cache."""
    repo = cfg["repo"]
    spec = cfg.get("cache", {})
    runs = fetch.main_runs(client, repo, cfg["workflow"], cfg["branch"], cfg["main_run_count"])
    sample = fetch.log_sample(runs, cfg["log_run_count"])
    uv, rust = Counter(), Counter()
    build = {"full": [], "other": []}
    logs_read = reruns_in_job = jobs_with_reruns = 0
    for run in sample:
        for job in m.final_attempt_jobs(fetch.run_jobs(client, repo, run["id"])):
            text = fetch.job_log(client, repo, job["id"], failures=True)
            if not text:
                continue
            logs_read += 1
            parsed = flaky.parse_failures(text)
            reruns_in_job += parsed["reruns_in_job"]
            jobs_with_reruns += 1 if parsed["reruns_in_job"] else 0
            state = actions.parse_log(text)["cache"]
            if state != "none":
                uv[state] += 1
            restored = actions.rust_cache(text)
            if restored:
                rust[restored] += 1
                for step in job.get("steps", []):
                    if (
                        step["name"] == spec.get("build_step")
                        and step.get("conclusion") == "success"
                    ):
                        secs = m.seconds(step["started_at"], step["completed_at"])
                        build["full" if restored == "full" else "other"].append(secs)
    entries = fetch.caches(client, repo)
    never_read = [
        e for e in entries if (m.seconds(e["created_at"], e["last_accessed_at"]) or 0) < 60
    ]
    return {
        "sample_runs": len(sample),
        "sample_first": min((r["created_at"] for r in sample), default=None),
        "sample_last": max((r["created_at"] for r in sample), default=None),
        "logs_read": logs_read,
        "uv": {k: uv[k] for k in ("hit", "miss")},
        "uv_lookups": uv["hit"] + uv["miss"],
        "uv_hit_rate": uv["hit"] / (uv["hit"] + uv["miss"]) if uv else None,
        "rust": {k: rust[k] for k in ("full", "partial", "miss")},
        "rust_lookups": sum(rust.values()),
        "rust_full_rate": rust["full"] / sum(rust.values()) if rust else None,
        "build_step": spec.get("build_step"),
        "build_full_n": len(build["full"]),
        "build_full_median_s": median(build["full"]) if build["full"] else None,
        "build_other_n": len(build["other"]),
        "build_other_median_s": median(build["other"]) if build["other"] else None,
        "build_saving_s": median(build["other"]) - median(build["full"])
        if build["other"] and build["full"]
        else None,
        "reruns_in_job": reruns_in_job,
        "jobs_with_reruns": jobs_with_reruns,
        "entries": len(entries),
        "entries_bytes": sum(e["size_in_bytes"] for e in entries),
        "entries_never_read": len(never_read),
        "entries_never_read_on_pr": sum(1 for e in never_read if e["ref"].startswith("refs/pull/")),
    }


def probe_checks(client: Client, cfg: dict) -> dict | None:
    """One test run many times on a fork: what each step showed, per runner."""
    spec = cfg.get("probe")
    if not spec or not spec.get("run_ids"):
        return None
    repo = spec["repo"]
    rows, runs = [], []
    errors: Counter = Counter()
    for run_id in spec["run_ids"]:
        run = client.get(f"repos/{repo}/actions/runs/{run_id}")
        runs.append(
            {
                "run_id": run_id,
                "url": run["html_url"],
                "sha": run["head_sha"],
                "conclusion": run["conclusion"],
                "created_at": run["created_at"],
            }
        )
        for job in m.final_attempt_jobs(fetch.run_jobs(client, repo, run_id)):
            text = fetch.job_log(client, repo, job["id"], probe=True)
            parsed = flaky.parse_probe(text)
            errors.update(t["error"] for t in flaky.parse_failures(text)["tests"])
            for step in job.get("steps", []):
                marker = spec["steps"].get(step["name"])
                seen = next((p for p in parsed if marker and marker in p["command"]), None)
                if not seen:
                    continue
                results = seen["results"]
                finished = results is not None
                rows.append(
                    {
                        "run_id": run_id,
                        "platform": flaky.platform(job["name"]),
                        "step": step["name"],
                        "kind": spec["kinds"][step["name"]],
                        "items": seen["items"],
                        "finished": finished,
                        "passed": results.get("passed", 0) if finished else seen["dots"],
                        "failed": (results.get("failed", 0) + results.get("error", 0))
                        if finished
                        else seen["fails"],
                        "timeouts": seen["timeouts"],
                        "method": seen["method"],
                        "step_limit": seen["step_limit"],
                        "conclusion": step.get("conclusion"),
                        "seconds": m.seconds(step.get("started_at"), step.get("completed_at")),
                        "url": f"{run['html_url']}/job/{job['id']}",
                    }
                )
    order = ("serial", "parallel", "file")
    rows.sort(key=lambda r: (r["run_id"], r["platform"], order.index(r["kind"])))

    def total(kind: str, key: str, platform: str | None = None) -> int:
        return sum(
            r[key]
            for r in rows
            if r["kind"] == kind and r["finished"] and platform in (None, r["platform"])
        )

    alone = [r for r in rows if r["kind"] in ("serial", "parallel")]
    return {
        "repo": repo,
        "branch": spec["branch"],
        "test": spec["test"],
        "runs": runs,
        "rows": rows,
        "steps_alone": len(alone),
        "steps_alone_finished": sum(1 for r in alone if r["finished"]),
        "steps_alone_with_failure": sum(
            1 for r in alone if r["failed"] or r["timeouts"] or not r["finished"]
        ),
        "finished_passed": sum(r["passed"] for r in alone if r["finished"]),
        "finished_failed": sum(r["failed"] for r in alone if r["finished"]),
        "finished_total": sum(r["passed"] + r["failed"] for r in alone if r["finished"]),
        "errors_total": sum(errors.values()),
        "file_passed": total("file", "passed"),
        "file_failed": total("file", "failed"),
        "file_steps": sum(1 for r in rows if r["kind"] == "file"),
        "windows_alone": sum(1 for r in alone if r["platform"] == "windows"),
        "windows_alone_finished": sum(
            1 for r in alone if r["platform"] == "windows" and r["finished"]
        ),
        "windows_ended_by_timeout": sum(
            1
            for r in alone
            if r["platform"] == "windows"
            and not r["finished"]
            and not r["step_limit"]
            and r["timeouts"]
        ),
        "windows_step_limit": sum(
            1 for r in alone if r["platform"] == "windows" and r["step_limit"]
        ),
        "methods": {r["platform"]: r["method"] for r in rows if r["method"]},
        "errors": [{"error": e, "count": n} for e, n in errors.most_common()],
        "timeouts_seen": sum(r["timeouts"] for r in alone),
    }


def build_flaky(client: Client, cfg: dict) -> dict:
    """The numbers for a report whose main subject is flaky checks."""
    data = {
        "config": cfg,
        "main": main_branch(client, cfg),
        "window": window(client, cfg),
        "static": static_checks(client, cfg),
        "caches": cache_checks_flaky(client, cfg),
        "flaky": flaky_checks(client, cfg),
        "probe": probe_checks(client, cfg),
    }
    data["main"]["windows_last"] = sum(
        j["finished_last"] for j in data["main"]["current_matrix"]["jobs"] if "windows" in j["job"]
    )
    return data


def build(client: Client, cfg: dict) -> dict:
    if cfg.get("profile") == "flaky":
        return build_flaky(client, cfg)
    data = {
        "config": cfg,
        "main": main_branch(client, cfg),
        "window": window(client, cfg),
        "static": static_checks(client, cfg),
        "caches": cache_checks(client, cfg),
        "circleci": circleci(client, cfg),
        "fix": fix(client, cfg),
    }
    data["ranking"] = ranking(data)
    return data


def ranking(data: dict) -> dict:
    """The arithmetic behind the ranked list, so the report only quotes it."""
    win, main, fixed = data["window"], data["main"], data["fix"]
    verdict_runs = win["ci_verdict_runs"]
    out = {"window_days": 30, "ci_verdict_runs": verdict_runs}
    if fixed:
        out["fix_billed_min_per_30d"] = fixed["billed_saved_min"] * verdict_runs
        out["fix_wait_min_per_30d"] = fixed["wall_saved_s"] * verdict_runs / 60
    # Cancelled runs on the main branch: what they used, and what it would
    # cost to let each one finish instead.
    cancelled = main["cancelled"]
    typical = main["current_matrix"]["summary"]["billed_median_min"]
    used_each = cancelled["billed_min"] / cancelled["runs"] if cancelled["runs"] else 0
    out["main_cancelled_share"] = cancelled["runs"] / main["summary"]["runs_total"]
    out["main_cancelled_used_each_min"] = used_each
    out["main_cancelled_finish_extra_min"] = cancelled["runs"] * (typical - used_each)
    out["window_cancelled_runs"] = win["ci_cancelled_cost"]["runs"]
    out["window_cancelled_billed_min"] = win["ci_cancelled_cost"]["billed_min"]
    # Queue waits: the most that removing every wait above the threshold could save.
    queue = main["queue"]
    out["queue_share"] = queue["runs_over_threshold"] / queue["runs"] if queue["runs"] else None
    # Jobs still on Python 3.13 or older, and what a drop like the one seen
    # on the two jobs that moved to 3.14 would be worth. An estimate only.
    pairs = [p for p in main["python_pairs"] if p["new_python"] == "3.14"]
    if pairs:
        drop = min(abs(p["change"]) for p in pairs)
        older = [
            j
            for j in main["current_matrix"]["jobs"]
            if any(f"({v}," in j["job"] for v in ("3.11", "3.12", "3.13"))
        ]
        out["py314_smallest_drop"] = drop
        out["py314_largest_drop"] = max(abs(p["change"]) for p in pairs)
        out["py_older_jobs"] = len(older)
        out["py_older_runner_s"] = sum(j["median_s"] for j in older)
        out["py_older_estimate_s"] = drop * out["py_older_runner_s"]
    if fixed and fixed.get("probe"):
        older_rows = [r for r in fixed["probe"]["rows"] if "(3.14," not in r["job"]]
        newer_rows = [r for r in fixed["probe"]["rows"] if "(3.14," in r["job"]]
        out["coverage_min_drop"] = min(abs(r["change"]) for r in older_rows)
        out["coverage_max_drop"] = max(abs(r["change"]) for r in older_rows)
        out["coverage_314_drop"] = abs(newer_rows[0]["change"]) if newer_rows else None
        out["coverage_jobs_probed"] = len(older_rows)
        out["coverage_estimate_s"] = out["coverage_min_drop"] * out.get("py_older_runner_s", 0)
    return out
