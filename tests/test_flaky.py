from cidiag import actions, flaky
from cidiag.fetch import days_between

STAMP = "2026-11-06T19:45:09.1431230Z "

LOG = "\n".join(
    STAMP + line
    for line in [
        "##[group]Run poe test -s --junit-xml=junit-xml/3.11--macos-arm.xml",
        "collected 1822 items",
        "some unrelated output",
        "=================== FAILURES ===================",
        "_____________ test_cancel_multi _____________",
        "[gw2] darwin -- Python 3.11.9",
        "    async def test_cancel_multi(client):",
        ">       assert sorted(results) == ['a', 'b']",
        "E       AssertionError: assert ['a', 'c'] == ['a', 'b']",
        "E         At index 1 diff: 'c' != 'b'",
        "_____________ ERROR at setup of test_with_a_very_long_name_here _____________",
        "E   RuntimeError: server did not start",
        "------ generated xml file: junit-xml/3.11--macos-arm.xml ------",
        "          Summary of Failures          ",
        "┏━━┳━━┓",
        "┃  File  ┃  Function  ┃  Function Line  ┃  Error Line  ┃  Error  ┃",
        "│  tests/worker/test_workflow.py  │  test_cancel_multi  │  2306  │  2315"
        "  │  AssertionError  │",
        "│  tests\\test_env.py  │  test_with_a_very_lon…  │  61  │  63" "  │  RuntimeError  │",
        "└──┴──┘",
        "Results (358.48s):",
        "         2 failed",
        "      1778 passed",
        "         3 rerun",
        "##[error]Process completed with exit code 1.",
        "##[error]    raise RuntimeError('Event loop is closed')",
        "Post job cleanup.",
    ]
)


def test_trim_keeps_failure_lines_and_drops_the_rest():
    trimmed = actions.trim_failure_log(LOG)
    assert "test_cancel_multi" in trimmed
    assert "At index 1 diff" in trimmed
    assert "Summary of Failures" in trimmed and "1778 passed" in trimmed
    assert "some unrelated output" not in trimmed
    assert "async def test_cancel_multi" not in trimmed
    assert "Post job cleanup" not in trimmed


def test_parse_failures_names_tests_with_file_and_error():
    parsed = flaky.parse_failures(actions.trim_failure_log(LOG))
    assert [t["id"] for t in parsed["tests"]] == [
        "tests/worker/test_workflow.py::test_cancel_multi",
        "tests/test_env.py::test_with_a_very_long_name_here",
    ]
    first, second = parsed["tests"]
    assert first["error"] == "AssertionError: assert ['a', 'c'] == ['a', 'b']"
    assert first["error_type"] == "AssertionError"
    assert first["step"].startswith("poe test -s")
    assert second["error"] == "RuntimeError: server did not start"
    assert parsed["reruns_in_job"] == 3
    assert parsed["errors"] == [] and parsed["timeouts"] == []


def test_parse_failures_reads_a_step_timeout():
    text = STAMP + "##[error]The action 'Run poe test -s' has timed out after 15 minutes."
    parsed = flaky.parse_failures(text)
    assert parsed["timeouts"] == [{"step": "Run poe test -s", "minutes": 15}]
    assert flaky.summarize(parsed)["kind"] == "timeout"


def _job(job_id, name, attempt, conclusion, started):
    return {
        "id": job_id,
        "name": name,
        "run_attempt": attempt,
        "conclusion": conclusion,
        "started_at": started,
        "completed_at": started,
        "steps": [{"name": "Run tests", "conclusion": conclusion}],
    }


def _rerun():
    run = {
        "id": 7,
        "name": "CI",
        "event": "pull_request",
        "run_attempt": 3,
        "conclusion": "success",
        "html_url": "https://example.test/runs/7",
        "run_started_at": "2026-11-01T12:00:00Z",
    }
    first = [
        _job(1, "test (linux)", 1, "failure", "2026-11-01T10:00:05Z"),
        _job(2, "test (windows)", 1, "success", "2026-11-01T10:00:05Z"),
        _job(3, "gate", 1, "failure", "2026-11-01T10:20:00Z"),
    ]
    second = [
        _job(4, "test (linux)", 2, "failure", "2026-11-01T11:00:05Z"),
        # Not re-run: a copy of attempt 1's job under a new id, with its old start time.
        _job(5, "test (windows)", 2, "success", "2026-11-01T10:00:05Z"),
        _job(6, "gate", 2, "failure", "2026-11-01T11:20:00Z"),
    ]
    third = [
        _job(8, "test (linux)", 3, "success", "2026-11-01T12:00:05Z"),
        _job(9, "test (windows)", 3, "success", "2026-11-01T10:00:05Z"),
        _job(10, "gate", 3, "success", "2026-11-01T12:20:00Z"),
    ]
    prior = [
        {
            "attempt": 1,
            "conclusion": "failure",
            "run_started_at": "2026-11-01T10:00:00Z",
            "updated_at": "2026-11-01T10:21:00Z",
            "jobs": first,
        },
        {
            "attempt": 2,
            "conclusion": "failure",
            "run_started_at": "2026-11-01T11:00:00Z",
            "updated_at": "2026-11-01T11:21:00Z",
            "jobs": second,
        },
    ]
    return run, first + second + third, prior


def test_failed_then_passed_counts_each_failed_execution_once():
    run, jobs, prior = _rerun()
    found = flaky.failed_then_passed([run], {7: jobs}, {7: prior}, {"gate"})
    assert [(i["job_id"], i["attempt"], i["passed_in_attempt"]) for i in found] == [
        (1, 1, 3),
        (4, 2, 3),
    ]
    assert found[0]["url"] == "https://example.test/runs/7/job/1"


def test_copies_of_jobs_that_were_not_rerun_are_not_executions():
    run, jobs, prior = _rerun()
    ids = {j["id"] for j in flaky.executed_jobs(run, jobs, prior)}
    assert ids == {1, 2, 3, 4, 6, 8, 10}


def test_a_job_that_never_passes_is_not_a_flaky_candidate():
    run, jobs, prior = _rerun()
    jobs = [j for j in jobs if j["id"] != 8] + [
        _job(8, "test (linux)", 3, "failure", "2026-11-01T12:00:05Z")
    ]
    assert flaky.failed_then_passed([run], {7: jobs}, {7: prior}, {"gate"}) == []


def test_rank_orders_by_failures_then_runs():
    def item(run_id, job_id, names, started="2026-11-01T10:00:00Z"):
        return {
            "run_id": run_id,
            "job_id": job_id,
            "job": "test (windows-latest)",
            "started_at": started,
            "url": f"u/{job_id}",
            "tests": [
                {"id": n, "error_type": "AssertionError", "error": "AssertionError: x"}
                for n in names
            ],
        }

    rows = flaky.rank_tests(
        [item(1, 1, ["a", "b"]), item(1, 2, ["a"]), item(2, 3, ["b"]), item(3, 4, ["c", "c"])]
    )
    assert [(r["rank"], r["test"], r["failures"], r["runs"]) for r in rows] == [
        (1, "b", 2, 2),
        (2, "a", 2, 1),
        (3, "c", 1, 1),
    ]
    assert rows[0]["platforms"] == {"windows": 2}


def test_days_between_includes_both_ends():
    assert days_between("2026-10-30", "2026-11-01") == ["2026-10-30", "2026-10-31", "2026-11-01"]


def test_rust_cache_states():
    assert actions.rust_cache('Restored from cache key "v0-rust-x" full match: true.') == "full"
    assert actions.rust_cache('Restored from cache key "v0-rust-x" full match: false.') == "partial"
    assert actions.rust_cache("No cache found.") == "miss"
    assert actions.rust_cache("nothing here") is None


def _test(name, error, file="tests/test_a.py"):
    return {"name": name, "file": file, "error": error, "error_type": "E", "error_lines": [error]}


def test_an_error_shared_by_many_tests_is_one_failure_not_many_flaky_tests():
    tests = [_test(f"test_{n}", "RuntimeError: server did not start") for n in range(40)]
    summary = flaky.summarize({"tests": tests, "timeouts": [], "errors": []})
    assert summary["kind"] == "shared" and summary["tests"] == []
    assert summary["shared"] == [{"error": "RuntimeError: server did not start", "tests": 40}]


def test_a_test_with_its_own_error_is_still_named_beside_a_shared_one():
    tests = [_test(f"test_{n}", "TimeoutError: timed out") for n in range(6)]
    tests.append(_test("test_alone", "AssertionError: 1"))
    summary = flaky.summarize({"tests": tests, "timeouts": [], "errors": []})
    assert summary["kind"] == "test"
    assert [t["name"] for t in summary["tests"]] == ["test_alone"]
    assert summary["shared"][0]["tests"] == 6


def test_resolve_files_expands_a_cut_path_and_fills_a_missing_one():
    whole = _test("test_x", "e", "tests/worker/test_workflow.py")
    short = _test("test_z", "e", "tests/worker/test_workf\u2026")
    missing = _test("test_x", "e", None)
    unknown = _test("test_y", "e", None)
    paths = ["tests/worker/test_workflow.py", "tests/worker/test_worker.py"]
    flaky.resolve_files([[whole], [short, missing, unknown]], paths)
    assert short["id"] == "tests/worker/test_workflow.py::test_z"
    assert missing["id"] == "tests/worker/test_workflow.py::test_x"
    assert unknown["id"] == "test_y"


def test_ascii_summary_table_from_a_windows_console():
    log = "\n".join(
        [
            "=================== FAILURES ===================",
            "_____________ test_cancel_activity_while_cancelled _____________",
            "E       assert not [1]",
            "          Summary of Failures          ",
            "+----------------------------------------------+",
            "|  File  |  Function  |  Function Line  |  Error Line  |  Error  |",
            "|--------+------------+-----------------+--------------+---------|",
            "|  tests\\worker\\test_workflow.py  |  test_cancel_activi\ufffd  |  1097  |  1137"
            "  |  AssertionError  |",
            "+----------------------------------------------+",
            "Results (298.92s):",
            "         1 failed",
            "this line is not part of the table or the results",
        ]
    )
    trimmed = actions.trim_failure_log(log)
    assert "not part of the table" not in trimmed
    parsed = flaky.parse_failures(trimmed)
    assert parsed["tests"][0]["id"] == (
        "tests/worker/test_workflow.py::test_cancel_activity_while_cancelled"
    )


def test_normalize_command_drops_the_report_path():
    step = "Run poe test  -s --junit-xml=junit-xml/3.11--windows-latest.xml"
    assert flaky.normalize_command(step) == "Run poe test -s"


def test_parse_probe_counts_progress_when_the_session_never_finished():
    log = "\n".join(
        [
            '##[group]Run uv run pytest "$TEST_ID" --flake-finder --flake-runs=200',
            "timeout method: thread",
            "collected 200 items",
            "tests\\worker\\test_worker.py ........+++++++++ Timeout +++++++++",
            "~~~~ Stack of MainThread (9392) ~~~~",
            "+++++++++ Timeout +++++++++",
            "##[error]Process completed with exit code 1.",
            "##[group]Run uv run pytest tests/worker/test_worker.py -n auto",
            "timeout method: thread",
            "2 workers [49 items]",
            ".............................................",
            "Results (64.50s):",
            "        45 passed",
            "         4 skipped",
        ]
    )
    trimmed = actions.trim_probe_log(log)
    assert "Stack of MainThread" not in trimmed
    first, second = flaky.parse_probe(trimmed)
    assert (first["items"], first["dots"], first["timeouts"], first["results"]) == (200, 8, 1, None)
    assert first["method"] == "thread" and not first["step_limit"]
    assert second["results"] == {"passed": 45, "skipped": 4} and second["items"] == 49
