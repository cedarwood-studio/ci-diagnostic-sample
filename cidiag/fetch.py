"""Pull run, job, workflow-file and cache data for one repository."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from .gh import Client


def main_runs(client: Client, repo: str, workflow: str, branch: str, count: int) -> list[dict]:
    """The last `count` completed push runs of one workflow on one branch."""
    endpoint = (
        f"repos/{repo}/actions/workflows/{workflow}/runs"
        f"?branch={branch}&event=push&status=completed"
    )
    return client.get_pages(endpoint, "workflow_runs", limit=count)


def window_runs(
    client: Client, repo: str, since: str, until: str, by_day: bool = False
) -> list[dict]:
    """Every run of every workflow created between two dates (inclusive, UTC).

    GitHub returns at most 1,000 runs for one query. A busy repository passes
    that in a 30-day window, so `by_day` asks for one day at a time.
    """
    if not by_day:
        endpoint = f"repos/{repo}/actions/runs?created={since}..{until}"
        return client.get_pages(endpoint, "workflow_runs")
    runs = []
    for day in days_between(since, until):
        runs += client.get_pages(f"repos/{repo}/actions/runs?created={day}", "workflow_runs")
    return runs


def days_between(since: str, until: str) -> list[str]:
    """Every date from `since` to `until`, both included, as ISO strings."""
    first, last = date.fromisoformat(since), date.fromisoformat(until)
    return [str(first + timedelta(days=n)) for n in range((last - first).days + 1)]


def run_jobs(client: Client, repo: str, run_id: int) -> list[dict]:
    """All jobs of a run, across every attempt."""
    return client.get_pages(f"repos/{repo}/actions/runs/{run_id}/jobs?filter=all", "jobs")


def prior_attempts(client: Client, repo: str, run: dict) -> list[dict]:
    """Earlier attempts of a run: each attempt's conclusion and its jobs.

    The jobs endpoint returns only what GitHub still holds for the latest
    attempt in some cases, so earlier attempts are fetched one by one.
    """
    out = []
    for number in range(1, run.get("run_attempt", 1)):
        attempt = client.get(f"repos/{repo}/actions/runs/{run['id']}/attempts/{number}")
        jobs = client.get_pages(
            f"repos/{repo}/actions/runs/{run['id']}/attempts/{number}/jobs", "jobs"
        )
        out.append(
            {
                "attempt": number,
                "conclusion": attempt.get("conclusion"),
                "run_started_at": attempt.get("run_started_at"),
                "updated_at": attempt.get("updated_at"),
                "jobs": jobs,
            }
        )
    return out


def job_log(
    client: Client, repo: str, job_id: int, failures: bool = False, probe: bool = False
) -> str:
    """The lines of one job's log that the analysis reads.

    `failures` also keeps the lines that name failing tests and their errors.
    `probe` keeps pytest's progress lines as well (see the three functions in
    actions: filter_log, trim_failure_log, trim_probe_log).
    """
    from .actions import filter_log, trim_failure_log, trim_probe_log

    transform = trim_probe_log if probe else trim_failure_log if failures else filter_log
    return client.get_text(f"repos/{repo}/actions/jobs/{job_id}/logs", transform=transform)


def log_sample(runs: list[dict], count: int) -> list[dict]:
    """The most recent `count` runs that reached a verdict."""
    verdict = [r for r in runs if r["conclusion"] in ("success", "failure")]
    return sorted(verdict, key=lambda r: r["created_at"], reverse=True)[:count]


def circleci(client: Client, slug: str, workflow: str, branch: str) -> dict:
    """CircleCI Insights for a public project; no token needed."""
    base = f"https://circleci.com/api/v2/insights/{slug}/workflows"
    return {
        "workflows": client.get_url(f"{base}?branch={branch}"),
        "jobs": client.get_url(f"{base}/{workflow}/jobs?branch={branch}"),
    }


def repo_file(client: Client, repo: str, path: str, ref: str) -> str | None:
    blob = client.get(f"repos/{repo}/contents/{path}?ref={ref}")
    if "content" not in blob:
        return None
    return base64.b64decode(blob["content"]).decode()


def repo_paths(client: Client, repo: str, ref: str, prefix: str = "") -> list[str]:
    """Every file path in the repository at a commit, optionally under one directory."""
    tree = client.get(f"repos/{repo}/git/trees/{ref}?recursive=1")
    return sorted(
        e["path"]
        for e in tree.get("tree", [])
        if e["type"] == "blob" and e["path"].startswith(prefix)
    )


def workflow_files(client: Client, repo: str, ref: str) -> dict[str, str]:
    """Workflow file contents at a fixed commit, keyed by path."""
    listing = client.get(f"repos/{repo}/contents/.github/workflows?ref={ref}")
    files = {}
    for entry in listing:
        if not entry["name"].endswith((".yml", ".yaml")):
            continue
        blob = client.get(f"repos/{repo}/contents/{entry['path']}?ref={ref}")
        files[entry["path"]] = base64.b64decode(blob["content"]).decode()
    return files


def caches(client: Client, repo: str) -> list[dict]:
    return client.get_pages(f"repos/{repo}/actions/caches", "actions_caches")


def action_metadata(client: Client, owner_repo: str, ref: str, subpath: str = "") -> dict:
    """Repository flags and the action manifest at the pinned ref."""
    info = client.get(f"repos/{owner_repo}")
    latest = client.get(f"repos/{owner_repo}/releases/latest")
    prefix = f"{subpath}/" if subpath else ""
    manifest = ""
    for name in ("action.yml", "action.yaml"):
        blob = client.get(f"repos/{owner_repo}/contents/{prefix}{name}?ref={ref}")
        if "content" in blob:
            manifest = base64.b64decode(blob["content"]).decode()
            break
    return {
        "archived": info.get("archived"),
        "latest_release": latest.get("tag_name"),
        "manifest": manifest,
    }


def scoped_jobs(client: Client, cfg: dict, runs: list[dict], fetch: bool = False) -> dict:
    """Jobs per run. With `jobs_scope: workflow`, only for the measured workflow
    and for runs that have more than one attempt; other runs get an empty list."""
    repo = cfg["repo"]

    def wanted(run: dict) -> bool:
        if cfg.get("jobs_scope") != "workflow":
            return True
        return run["name"] == cfg["workflow_name"] or run.get("run_attempt", 1) > 1

    chosen = [r for r in runs if wanted(r)]
    if fetch:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda r: run_jobs(client, repo, r["id"]), chosen))
    jobs = {r["id"]: [] for r in runs}
    jobs.update({r["id"]: run_jobs(client, repo, r["id"]) for r in chosen})
    return jobs


def fetch_flaky_sample(client: Client, cfg: dict) -> None:
    """Everything the `flaky` profile reads (see analyze.build_flaky)."""
    from . import actions, flaky

    repo = cfg["repo"]
    runs = main_runs(client, repo, cfg["workflow"], cfg["branch"], cfg["main_run_count"])
    window = window_runs(
        client, repo, cfg["window_since"], cfg["window_until"], cfg.get("window_by_day", False)
    )
    by_id = {run["id"]: run for run in runs + window}
    everything = list(by_id.values())
    jobs = scoped_jobs(client, cfg, everything, fetch=True)
    reruns = [run for run in everything if run.get("run_attempt", 1) > 1]
    with ThreadPoolExecutor(max_workers=4) as pool:
        prior = dict(
            zip(
                [r["id"] for r in reruns],
                pool.map(lambda run: prior_attempts(client, repo, run), reruns),
                strict=True,
            )
        )
        gate = set(cfg.get("flaky", {}).get("gate_jobs", []))
        instances = flaky.failed_then_passed(window, jobs, prior, gate)
        log_jobs = [item["job_id"] for item in instances]
        log_jobs += [job["id"] for job in flaky.failed_final_jobs(runs, jobs, gate)]
        for run in log_sample(runs, cfg["log_run_count"]):
            log_jobs += [job["id"] for job in run_jobs(client, repo, run["id"])]
        list(pool.map(lambda job_id: job_log(client, repo, job_id, failures=True), log_jobs))
    files = workflow_files(client, repo, cfg["workflow_ref"])
    for path, text in files.items():
        for use in actions.find_uses(path, text):
            if use["ref"]:
                owner_repo, subpath = actions.action_repo(use["action"])
                action_metadata(client, owner_repo, use["ref"], subpath)
    caches(client, repo)
    repo_paths(client, repo, cfg["workflow_ref"])
    probe = cfg.get("probe")
    for run_id in probe["run_ids"] if probe else []:
        client.get(f"repos/{probe['repo']}/actions/runs/{run_id}")
        for job in run_jobs(client, probe["repo"], run_id):
            job_log(client, probe["repo"], job["id"], probe=True)


def fetch_all(client: Client, cfg: dict) -> None:
    from . import actions

    if cfg.get("profile") == "flaky":
        fetch_flaky_sample(client, cfg)
        return
    repo = cfg["repo"]
    runs = main_runs(client, repo, cfg["workflow"], cfg["branch"], cfg["main_run_count"])
    window = window_runs(client, repo, cfg["window_since"], cfg["window_until"])
    by_id = {run["id"]: run for run in runs + window}
    # Four requests at a time stays far inside GitHub's rate limits.
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda run_id: run_jobs(client, repo, run_id), sorted(by_id)))
        reruns = [run for run in by_id.values() if run.get("run_attempt", 1) > 1]
        list(pool.map(lambda run: prior_attempts(client, repo, run), reruns))
        log_jobs = [
            job["id"]
            for run in log_sample(runs, cfg["log_run_count"])
            for job in run_jobs(client, repo, run["id"])
        ]
        list(pool.map(lambda job_id: job_log(client, repo, job_id), log_jobs))

    # Logs of failed runs in which exactly one job failed, to name the tests.
    from . import metrics

    ci = [r for r in window if r["name"] == cfg["workflow_name"]]
    jobs = {r["id"]: run_jobs(client, repo, r["id"]) for r in ci}
    for item in metrics.failed_run_shapes(ci, jobs)["single_job_failures"]:
        job_log(client, repo, int(item["url"].rsplit("/", 1)[1]))

    files = workflow_files(client, repo, cfg["workflow_ref"])
    for path, text in files.items():
        for use in actions.find_uses(path, text):
            if use["ref"]:
                owner_repo, subpath = actions.action_repo(use["action"])
                action_metadata(client, owner_repo, use["ref"], subpath)
    caches(client, repo)
    if cfg.get("circleci"):
        circleci(client, cfg["circleci"]["slug"], cfg["circleci"]["workflow"], cfg["branch"])
        repo_file(client, repo, ".circleci/config.yml", cfg["workflow_ref"])

    spec = cfg.get("fix", {})
    for arm in spec.get("arms", []) + ([spec["probe"]] if spec.get("probe") else []):
        fork = cfg["fix"]["repo"]
        for run_id in arm["run_ids"]:
            client.get(f"repos/{fork}/actions/runs/{run_id}")
            for job in run_jobs(client, fork, run_id):
                job_log(client, fork, job["id"])
