"""Flaky-test evidence: jobs that failed and then passed on the same commit.

A re-run executes the same commit again. When a job fails in one attempt and
passes in a later attempt of the same run, the code did not change between
the two, so something else decided the result: timing, a shared resource, the
network, the runner. That is evidence of a flaky check. It is not proof: one
pass after one failure says the failure is not deterministic, and nothing more.

GitHub lists every job in every attempt. A job that was not re-run appears
again in the later attempt as a copy, with a new id and its original start
time. Counting those copies would count one failure several times, so a job
only counts in the attempt it started in.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import median

from . import metrics as m
from .actions import (
    FAIL_SECTION_RE,
    SECTION_RE,
    TABLE_LINE_RE,
    TABLE_ROW_RE,
    TEST_HEADER_RE,
    log_body,
)

# pytest-pretty cuts long cells with an ellipsis; some Windows consoles print
# it as the Unicode replacement character.
ELLIPSIS = "\u2026\ufffd"

TIMEOUT_RE = re.compile(
    r"^##\[error\]The (?:action|operation) '?(.*?)'? has timed out after (\d+) minutes"
)
RUN_RE = re.compile(r"^##\[group\]Run (.*)$")
RERUN_RE = re.compile(r"^\s+(\d+) rerun$")
SETUP_PREFIX_RE = re.compile(r"^ERROR at (setup|teardown) of ")


def attempt_starts(run: dict, prior: list[dict]) -> dict[int, str]:
    """When each attempt of a run started, keyed by attempt number."""
    starts = {a["attempt"]: a.get("run_started_at") for a in prior}
    starts[run.get("run_attempt", 1)] = run.get("run_started_at")
    return starts


def executed(job: dict, starts: dict[int, str]) -> bool:
    """True if the job ran in the attempt it is listed under, false for a copy."""
    start = starts.get(job.get("run_attempt", 1))
    if not start or not job.get("started_at"):
        return False
    return m.ts(job["started_at"]) >= m.ts(start)


def executed_jobs(run: dict, jobs: list[dict], prior: list[dict]) -> list[dict]:
    """Every job execution of a run across its attempts, copies removed."""
    starts = attempt_starts(run, prior)
    return [j for j in m.all_attempt_jobs(jobs, prior) if executed(j, starts)]


def failed_then_passed(
    runs: list[dict],
    jobs_by_run: dict[int, list[dict]],
    prior_by_run: dict[int, list[dict]],
    gate_jobs: set[str] = frozenset(),
) -> list[dict]:
    """Each job execution that failed and whose job later passed in the same run.

    `gate_jobs` are jobs that only report the result of other jobs. They fail
    whenever anything else fails, so they are left out.
    """
    out = []
    for run in runs:
        if run.get("run_attempt", 1) <= 1:
            continue
        by_name: dict[str, list[dict]] = defaultdict(list)
        for job in executed_jobs(
            run, jobs_by_run.get(run["id"], []), prior_by_run.get(run["id"], [])
        ):
            by_name[job["name"]].append(job)
        for name, items in by_name.items():
            if name in gate_jobs:
                continue
            items.sort(key=lambda j: j.get("run_attempt", 1))
            passed = [j.get("run_attempt", 1) for j in items if j.get("conclusion") == "success"]
            for job in items:
                attempt = job.get("run_attempt", 1)
                if job.get("conclusion") != "failure" or not any(p > attempt for p in passed):
                    continue
                steps = [
                    s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"
                ]
                out.append(
                    {
                        "run_id": run["id"],
                        "run_url": run.get("html_url"),
                        "workflow": run["name"],
                        "event": run["event"],
                        "job_id": job["id"],
                        "job": name,
                        "attempt": attempt,
                        "passed_in_attempt": min(p for p in passed if p > attempt),
                        "failed_step": steps[0] if steps else "",
                        "started_at": job.get("started_at"),
                        "url": f"{run.get('html_url')}/job/{job['id']}",
                    }
                )
    out.sort(key=lambda i: (i["started_at"] or "", i["job_id"]))
    return out


def failed_final_jobs(
    runs: list[dict], jobs_by_run: dict[int, list[dict]], gate_jobs: set[str] = frozenset()
) -> list[dict]:
    """Failed jobs in the final attempt of runs that ended red, gate jobs left out."""
    out = []
    for run in runs:
        if run["conclusion"] != "failure":
            continue
        for job in m.final_attempt_jobs(jobs_by_run.get(run["id"], [])):
            if job.get("conclusion") == "failure" and job["name"] not in gate_jobs:
                out.append({**job, "run_id": run["id"], "run_url": run.get("html_url")})
    return out


def parse_failures(text: str) -> dict:
    """What a trimmed pytest job log says failed.

    Returns the failing tests (file, name, error type, first error lines and
    the step that ran them), any step that hit its time limit, the other
    `##[error]` lines, and how many tests pytest re-ran inside the job.
    """
    tests, timeouts, errors = [], [], []
    pending: list[dict] = []
    step = ""
    reruns = 0
    in_failures = in_table = False
    current = None
    for raw in text.splitlines():
        body = log_body(raw)
        run = RUN_RE.match(body)
        if run:
            step = run.group(1)
            continue
        if body.startswith("##[error]"):
            timeout = TIMEOUT_RE.match(body)
            if timeout:
                timeouts.append({"step": timeout.group(1), "minutes": int(timeout.group(2))})
            elif (
                not body.startswith("##[error] ") and "Process completed with exit code" not in body
            ):
                errors.append(body[len("##[error]") :].strip())
            continue
        rerun = RERUN_RE.match(body)
        if rerun:
            reruns += int(rerun.group(1))
        if FAIL_SECTION_RE.match(body):
            in_failures, current = True, None
            continue
        if "Summary of Failures" in body:
            in_table, in_failures = True, False
            continue
        if in_table and TABLE_LINE_RE.match(body):
            if TABLE_ROW_RE.match(body):
                cells = [c.strip() for c in re.split("[\u2502\u2503|]", body.strip())[1:-1]]
                _match_row(pending, cells)
            continue
        in_table = False
        if body.startswith("Results ("):
            in_failures = False
            tests += pending
            pending = []
            continue
        if in_failures:
            header = TEST_HEADER_RE.match(body)
            if header:
                current = {
                    "name": SETUP_PREFIX_RE.sub("", header.group(1)),
                    "file": None,
                    "error_type": None,
                    "error_lines": [],
                    "step": step,
                }
                pending.append(current)
            elif body.startswith("E ") and current is not None:
                current["error_lines"].append(body[1:].strip())
            elif SECTION_RE.match(body):
                in_failures = False
    tests += pending
    for test in tests:
        test["id"] = f"{test['file']}::{test['name']}" if test["file"] else test["name"]
        test["error"] = next((line for line in test["error_lines"] if line), "")
    return {"tests": tests, "timeouts": timeouts, "errors": errors, "reruns_in_job": reruns}


def _match_row(pending: list[dict], cells: list[str]) -> None:
    """Attach a summary-table row (file, function, lines, error type) to its test.

    pytest-pretty shortens long names with an ellipsis, so the row is matched
    to the first unmatched test whose name starts with what the table shows.
    """
    if len(cells) < 5 or cells[0] == "File":
        return
    shown = cells[1].rstrip(ELLIPSIS).strip()
    for test in pending:
        if test["file"] is None and test["name"].startswith(shown):
            test["file"] = cells[0].replace("\\", "/").replace("\ufffd", "\u2026")
            test["error_type"] = cells[4].rstrip(ELLIPSIS).strip()
            return


RESULT_RE = re.compile(r"^\s+(\d+) ([a-z]+)$")
DOTS_RE = re.compile(r"^(?:tests[\\/]\S+\.py )?([.FEsxR]+)")
ITEMS_RE = re.compile(r"^collected (\d+) items|^\d+ workers \[(\d+) items\]")


def parse_probe(text: str) -> list[dict]:
    """What each `Run` step of a probe log shows, in order.

    `results` holds pytest's own counts when the session finished. When it did
    not, `dots` and `fails` count the progress characters printed before it
    stopped. `timeout_dumps` counts the banners pytest-timeout prints when a
    test passes its limit, and `method` is how pytest-timeout enforces it on
    that runner: `signal` fails the one test, `thread` ends the whole process.
    """
    out, current = [], None
    for raw in text.splitlines():
        body = log_body(raw)
        run = RUN_RE.match(body)
        if run:
            current = {
                "command": run.group(1),
                "items": None,
                "method": None,
                "dots": 0,
                "fails": 0,
                "timeout_dumps": 0,
                "results": None,
                "step_limit": False,
            }
            out.append(current)
            continue
        if current is None:
            continue
        items = ITEMS_RE.match(body)
        if items:
            current["items"] = int(items.group(1) or items.group(2))
        elif body.startswith("timeout method:"):
            current["method"] = body.split(":", 1)[1].strip()
        elif body.startswith("Results ("):
            current["results"] = {}
        elif current["results"] is not None and RESULT_RE.match(body):
            count = RESULT_RE.match(body)
            current["results"][count.group(2)] = int(count.group(1))
        elif TIMEOUT_RE.match(body):
            current["step_limit"] = True
        else:
            dots = DOTS_RE.match(body)
            if dots:
                current["dots"] += dots.group(1).count(".")
                current["fails"] += sum(dots.group(1).count(c) for c in "FE")
        if "+ Timeout +" in body:
            current["timeout_dumps"] += 1
    for step in out:
        # pytest-timeout prints the banner twice per timeout, above and below the stacks.
        step["timeouts"] = (step.pop("timeout_dumps") + 1) // 2
    return out


def platform(job_name: str) -> str:
    """`build-lint-test (3.11, windows-latest)` -> `windows`."""
    for key in ("windows", "macos", "ubuntu"):
        if key in job_name:
            return "linux" if key == "ubuntu" else key
    return "linux"


SHARED_MIN_TESTS = 5
JUNIT_RE = re.compile(r"\s*--junit-xml=\S+")


def normalize_command(step: str) -> str:
    """A step name without the per-job report path, so matrix jobs group together."""
    return " ".join(JUNIT_RE.sub("", step).split())


def summarize(parsed: dict) -> dict:
    """Why a job execution failed, as far as its log says.

    `test`: the log names one or more tests that failed on their own.
    `shared`: tests failed, but every one of them shares its error line with
    at least four others in the same job. That is one failure with many
    victims (a server that did not start, a storage emulator that timed out),
    so it is reported once with its error line, and the tests are not ranked.
    `timeout`: a step hit its time limit, so the job stopped with no test named.
    `other`: none of these, for example a setup step that failed.
    """
    errors = Counter(t["error"] for t in parsed["tests"])
    shared = {e: n for e, n in errors.items() if n >= SHARED_MIN_TESTS}
    tests = [t for t in parsed["tests"] if t["error"] not in shared]
    if tests:
        kind = "test"
    elif shared:
        kind = "shared"
    elif parsed["timeouts"]:
        kind = "timeout"
    else:
        kind = "other"
    return {
        "kind": kind,
        "tests": tests,
        "shared": [{"error": e, "tests": n} for e, n in sorted(shared.items())],
        "error": parsed["errors"][-1] if parsed["errors"] else "",
        "timeouts": parsed["timeouts"],
    }


def resolve_files(groups: list[list[dict]], paths: list[str] = ()) -> None:
    """Fill in test files the summary table cut short or left out.

    pytest-pretty shortens a long path with an ellipsis. A short path is
    replaced when exactly one file in the repository starts with what the
    table shows. A missing path is filled in when the same test name appears
    elsewhere in the logs under exactly one file.
    """
    known: dict[str, set[str]] = defaultdict(set)
    for tests in groups:
        for test in tests:
            if test["file"] and "\u2026" not in test["file"]:
                known[test["name"]].add(test["file"])
    for tests in groups:
        for test in tests:
            if test["file"] and "\u2026" in test["file"]:
                shown = test["file"].rstrip("\u2026")
                fits = [p for p in paths if p.startswith(shown)]
                if len(fits) == 1:
                    test["file"] = fits[0]
            elif not test["file"] and len(known.get(test["name"], ())) == 1:
                test["file"] = next(iter(known[test["name"]]))
            test["id"] = f"{test['file']}::{test['name']}" if test["file"] else test["name"]


def rank_tests(instances: list[dict]) -> list[dict]:
    """Tests ordered by how many failed-then-passed job executions name them."""
    groups: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for item in instances:
        seen = set()
        for test in item["tests"]:
            if test["id"] not in seen:
                seen.add(test["id"])
                groups[test["id"]].append((item, test))
    rows = []
    for test_id, pairs in groups.items():
        items = [p[0] for p in pairs]
        errors = Counter((t["error_type"] or "", t["error"]) for _, t in pairs)
        (error_type, error), _ = errors.most_common(1)[0]
        rows.append(
            {
                "test": test_id,
                "name": test_id.rsplit("::", 1)[-1],
                "failures": len(items),
                "sole_failures": sum(1 for i in items if len({t["id"] for t in i["tests"]}) == 1),
                "runs": len({i["run_id"] for i in items}),
                "first": min(i["started_at"] for i in items),
                "last": max(i["started_at"] for i in items),
                "platforms": dict(Counter(platform(i["job"]) for i in items)),
                "on_windows": sum(1 for i in items if platform(i["job"]) == "windows"),
                "error_type": error_type,
                "error": error,
                "distinct_errors": len(errors),
                "examples": [{"run_id": i["run_id"], "url": i["url"]} for i in items[-3:]],
            }
        )
    rows.sort(key=lambda r: (-r["failures"], -r["runs"], r["test"]))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows


def group_counts(instances: list[dict], key) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for item in instances:
        groups[key(item)].append(item)
    rows = [
        {
            "key": list(k),
            "failures": len(v),
            "runs": len({i["run_id"] for i in v}),
            "first": min(i["started_at"] for i in v),
            "last": max(i["started_at"] for i in v),
            "examples": [{"run_id": i["run_id"], "url": i["url"]} for i in v[-3:]],
        }
        for k, v in groups.items()
    ]
    rows.sort(key=lambda r: (-r["failures"], r["key"]))
    return rows


def rerun_cost(
    runs: list[dict], jobs_by_run: dict[int, list[dict]], prior_by_run: dict[int, list[dict]]
) -> dict:
    """What re-running after a failure cost, over runs that ended in a pass.

    Delay: from the end of the first attempt (the first, red, verdict) to the
    end of the last attempt (the green one). Runner minutes: jobs executed in
    attempts after the first, billed the way a private repository would be.
    """
    delays, totals, billed, attempts = [], [], 0, []
    for run in runs:
        prior = prior_by_run.get(run["id"], [])
        if m.rerun_kind(run, prior) != "after_failure" or run["conclusion"] != "success":
            continue
        first = next((a for a in prior if a["conclusion"] in ("failure", "timed_out")), None)
        if not first or not first.get("updated_at"):
            continue
        delays.append(m.seconds(first["updated_at"], run["updated_at"]) or 0.0)
        totals.append(m.seconds(run["created_at"], run["updated_at"]) or 0.0)
        attempts.append(run["run_attempt"])
        for job in executed_jobs(run, jobs_by_run.get(run["id"], []), prior):
            if job.get("run_attempt", 1) > first["attempt"]:
                billed += m.billed_minutes(job)
    return {
        "runs": len(delays),
        "delay_median_s": median(delays) if delays else None,
        "delay_p90_s": m.percentile(delays, 90),
        "delay_total_s": sum(delays),
        "total_median_s": median(totals) if totals else None,
        "billed_min": billed,
        "attempts_max": max(attempts) if attempts else None,
        "attempts": dict(Counter(str(a) for a in attempts)),
    }
