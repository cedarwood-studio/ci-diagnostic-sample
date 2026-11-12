from cidiag import metrics as m

from .fixtures import JOBS, RUNS, job, run, t


def test_seconds_and_percentile():
    assert m.seconds(t(0), t(1, 30)) == 90
    assert m.seconds(None, t(1)) is None
    assert m.percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90) == 9
    assert m.percentile([5], 90) == 5
    assert m.percentile([], 90) is None


def test_billed_minutes_round_each_job_up():
    assert m.billed_minutes(job(1, "a", t(0), t(0), t(0, 1))) == 1
    assert m.billed_minutes(job(1, "a", t(0), t(0), t(2, 0))) == 2
    assert m.billed_minutes(job(1, "a", t(0), t(0), t(2, 1))) == 3
    assert m.billed_minutes(job(1, "a", t(0), None, None, conclusion="skipped")) == 0


def test_run_wall_uses_final_attempt_only():
    jobs = [
        job(1, "a", t(0), t(0), t(30), attempt=1),
        job(2, "a", t(40), t(40), t(45), attempt=2),
    ]
    assert m.run_wall_seconds(jobs) == 300


def test_duration_summary():
    s = m.duration_summary(RUNS, JOBS)
    assert s["runs_total"] == 4
    assert s["runs_with_verdict"] == 3
    assert s["conclusions"] == {"success": 2, "cancelled": 1, "failure": 1}
    # walls: run 1 = 1200 s, run 2 = 600 s, run 4 = 480 s
    assert s["wall_median_s"] == 600
    assert s["wall_p90_s"] == 1200
    assert s["wall_median_success_s"] == 900
    # billed: run 1 = 5 + 20, run 2 = 3 + 8, run 4 = 4 + 8
    assert s["billed_total_min"] == 25 + 11 + 12
    assert s["billed_median_min"] == 12


def test_job_breakdown_and_finished_last():
    rows = {r["job"]: r for r in m.job_breakdown(RUNS, JOBS)}
    assert rows["fast (3.12, a)"]["runs"] == 2
    assert rows["fast (3.12, a)"]["median_s"] == 240
    assert rows["slow (3.12, a)"]["finished_last"] == 1
    assert rows["slow (3.14, a)"]["finished_last"] == 1
    assert rows["slow (3.14, a)"]["queue_median_s"] == 120


def test_step_breakdown_shares_sum_to_one():
    steps = m.step_breakdown(RUNS, JOBS)
    assert steps["runs"] == 2
    by_name = {r["step"]: r for r in steps["rows"]}
    assert by_name["Test"]["seconds"] == 240 + 1110 + 120 + 420
    assert abs(sum(r["share"] for r in steps["rows"]) - 1) < 1e-9


def test_normalize_step_drops_sha_and_python_version():
    sha = "a" * 40
    assert m.normalize_step(f"Run actions/checkout@{sha}") == "Run actions/checkout"
    assert m.normalize_step("Set up Python 3.12") == "Set up Python"


def test_cancelled_cost():
    assert m.cancelled_cost(RUNS, JOBS) == {"runs": 1, "runner_seconds": 150, "billed_min": 3}


def test_failure_rate_leaves_cancelled_and_held_runs_out():
    runs = RUNS + [run(5, "action_required", event="pull_request")]
    rows = {(r["workflow"], r["event"]): r for r in m.failure_rates(runs, {})}
    push = rows[("CI", "push")]
    assert (push["success"], push["failure"], push["cancelled"]) == (2, 1, 1)
    assert push["failure_rate"] == 1 / 3
    pr = rows[("CI", "pull_request")]
    assert pr["held_for_approval"] == 1
    assert pr["failure_rate"] is None


def test_rerun_after_approval_is_not_a_retry():
    approved = run(6, "success", attempt=2)
    retried = run(7, "success", attempt=2)
    prior = {
        6: [{"attempt": 1, "conclusion": "action_required", "jobs": []}],
        7: [{"attempt": 1, "conclusion": "failure", "jobs": []}],
    }
    assert m.rerun_kind(approved, prior[6]) == "after_approval"
    assert m.rerun_kind(retried, prior[7]) == "after_failure"
    assert m.rerun_kind(run(8, "success"), []) is None
    row = m.failure_rates([approved, retried], prior)[0]
    assert row["rerun_after_failure"] == 1
    assert row["rerun_after_approval"] == 1
    assert row["rerun_rate"] == 0.5
    assert m.totals([row])["rerun_rate"] == 0.5


def test_flaky_candidate_is_fail_then_pass_on_same_run():
    r = run(9, "success", attempt=2)
    final = [job(92, "tests", t(10), t(10), t(15), attempt=2)]
    prior = {
        9: [
            {
                "attempt": 1,
                "conclusion": "failure",
                "jobs": [
                    job(
                        91,
                        "tests",
                        t(0),
                        t(0),
                        t(5),
                        conclusion="failure",
                        attempt=1,
                        steps=[{"name": "Test", "conclusion": "failure"}],
                    ),
                ],
            }
        ]
    }
    found = m.flaky_candidates([r], {9: final}, prior)
    assert len(found) == 1
    assert found[0]["job"] == "tests"
    assert found[0]["failed_step"] == "Test"
    assert m.flaky_candidates(RUNS, JOBS, {}) == []


def test_failing_jobs_counts_allowed_failures_apart():
    allowed_run = run(10, "success")
    jobs = dict(JOBS)
    jobs[10] = [
        job(
            101,
            "exp (3.15)",
            t(0),
            t(0),
            t(1),
            conclusion="failure",
            steps=[{"name": "Test", "conclusion": "failure"}],
        )
    ]
    rows = {(r["job"], r["step"]): r for r in m.failing_jobs(RUNS + [allowed_run], jobs)}
    assert rows[("fast", "Test")] == {
        "workflow": "CI",
        "job": "fast",
        "step": "Test",
        "failures": 1,
        "allowed": 0,
    }
    assert rows[("exp", "Test")]["allowed"] == 1


def test_failed_run_shapes():
    shapes = m.failed_run_shapes(RUNS + [run(11, "failure")], {**JOBS, 11: []})
    assert shapes["shapes"] == {"one_job": 1, "no_failed_job": 1}
    assert shapes["single_job_failures"][0]["job"] == "fast (3.12, a)"


def test_queue_summary():
    q = m.queue_summary(RUNS, JOBS, threshold=60)
    assert q["runs"] == 2
    assert q["runs_over_threshold"] == 1
    assert q["max_s"] == 120
    assert q["slowest_run"]["run_id"] == 1


def test_python_pairs_compare_jobs_that_differ_only_in_python():
    rows = m.job_breakdown(RUNS, JOBS)
    pairs = m.python_pairs(rows)
    assert len(pairs) == 1
    pair = pairs[0]
    assert (pair["old_python"], pair["new_python"]) == ("3.12", "3.14")
    assert pair["old_median_s"] == 1170 and pair["new_median_s"] == 480
    assert round(pair["change"], 3) == round((480 - 1170) / 1170, 3)


def test_superseded_runs_counts_minutes_after_the_newer_push():
    older = {**run(1, "success", event="pull_request", created=t(0)), "head_sha": "a"}
    newer = {**run(2, "success", event="pull_request", created=t(10)), "head_sha": "b"}
    for item in (older, newer):
        item["head_branch"] = "feature"
    jobs = {
        1: [job(1, "test", t(0), t(1), t(20)), job(2, "lint", t(0), t(1), t(5))],
        2: [job(3, "test", t(10), t(11), t(30))],
    }
    out = m.superseded_runs([newer, older], jobs)
    # Only the test job of run 1 was still running at 10:10; it ran ten more minutes.
    assert out == {"runs": 1, "billed_min_after": 10}
