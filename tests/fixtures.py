"""Small hand-built run and job records in the shape the GitHub API returns."""


def t(minute: int, second: int = 0) -> str:
    return f"2026-01-01T10:{minute:02d}:{second:02d}Z"


def step(name, start, end, conclusion="success"):
    return {"name": name, "started_at": start, "completed_at": end, "conclusion": conclusion}


def job(job_id, name, created, started, completed, conclusion="success", attempt=1, steps=None):
    return {
        "id": job_id,
        "name": name,
        "created_at": created,
        "started_at": started,
        "completed_at": completed,
        "conclusion": conclusion,
        "run_attempt": attempt,
        "steps": steps or [],
        "html_url": f"https://example.test/job/{job_id}",
    }


def run(run_id, conclusion, name="CI", event="push", attempt=1, created=None):
    return {
        "id": run_id,
        "name": name,
        "event": event,
        "conclusion": conclusion,
        "run_attempt": attempt,
        "created_at": created or t(0),
        "head_branch": "main",
        "html_url": f"https://example.test/run/{run_id}",
        "path": ".github/workflows/ci.yml",
    }


# Run 1: success. Two jobs created at 10:00:00; the slow one ends at 10:20:00.
# Run 2: success. Slow job ends at 10:10:00.
# Run 3: cancelled after 2m30s of one job.
# Run 4: failure, one job failed in step "Test".
RUNS = [run(1, "success"), run(2, "success"), run(3, "cancelled"), run(4, "failure")]

JOBS = {
    1: [
        job(
            11,
            "fast (3.12, a)",
            t(0),
            t(0, 10),
            t(5, 10),
            steps=[step("Install", t(0, 10), t(1, 10)), step("Test", t(1, 10), t(5, 10))],
        ),
        job(
            12,
            "slow (3.12, a)",
            t(0),
            t(0, 30),
            t(20),
            steps=[step("Install", t(0, 30), t(1, 30)), step("Test", t(1, 30), t(20))],
        ),
    ],
    2: [
        job(
            21,
            "fast (3.12, a)",
            t(0),
            t(0, 10),
            t(3, 10),
            steps=[step("Install", t(0, 10), t(1, 10)), step("Test", t(1, 10), t(3, 10))],
        ),
        job(
            22,
            "slow (3.14, a)",
            t(0),
            t(2, 0),
            t(10),
            steps=[step("Install", t(2), t(3)), step("Test", t(3), t(10))],
        ),
    ],
    3: [job(31, "fast (3.12, a)", t(0), t(0), t(2, 30), conclusion="cancelled")],
    4: [
        job(
            41,
            "fast (3.12, a)",
            t(0),
            t(0),
            t(4),
            conclusion="failure",
            steps=[step("Install", t(0), t(1)), step("Test", t(1), t(4), "failure")],
        ),
        job(42, "slow (3.12, a)", t(0), t(0), t(8)),
    ],
}
