# CI Diagnostic: temporalio/sdk-python

> **Sample report.** Produced by Cedarwood Studio from public data on temporalio/sdk-python as of 2026-11-12. Nobody at the project asked for it. Cedarwood Studio isn't affiliated with the project and the project hasn't endorsed this report. Nothing was sent to the project: no issue, pull request or comment.

This is the report a CI Diagnostic client receives, run here on a public repository so anyone can check it. It's the second sample. The first, on wagtail/wagtail, found a slow pipeline with no re-runs in its history. This one was chosen because its history has many re-runs after a failure, so it shows what the diagnostic does with a pipeline where people press re-run. It names the tests and steps that failed and then passed on the same commit, and ranks them.

Every number below was computed from the repository's own CI history, and the command that produces each one is printed next to it. The API responses behind them are stored with the report, with personal fields removed and logs trimmed, so the numbers can be recomputed without network access.

A diagnostic measures how a pipeline behaves. It isn't an audit or a security assessment, and none of this judges the project or the people who maintain it. This SDK tests concurrent workers against a live server on three operating systems, and that kind of suite is hard to keep free of timing-dependent failures.

## Summary

**What was measured.** The `Continuous Integration` workflow (`.github/workflows/ci.yml`) on GitHub Actions: all 414 of its runs over the 30 days from 2026-10-12 to 2026-11-10, on pull requests and pushes, with every attempt of every run that was re-run; its last 100 completed runs on `main` (2026-10-06 to 2026-11-11); and the log of every job that failed and later passed. Workflow files were read at commit `57f3dd6`.

**What we found.**

1. **62 runs were re-run after a failure, and 45 of them then passed with no change to the code.** Those re-runs hold 127 job executions that failed and later passed on the same commit ("failed, then passed" below; section 2 defines it). The log names a failing test in 61 of them. In 39 a test step ran past its time limit and the job was stopped. 5 had one error shared by many tests, and 22 failed outside the tests.
2. **One test accounts for 22 of the 61 failures that name a test.** `tests/worker/test_worker.py::test_warns_when_workers_too_low` failed and then passed 22 times across 15 runs, every time on pytest's 60-second limit for one test. Run alone on our fork, it timed out the same way in 11 of 780 repetitions, counting the steps that ran to the end. The second, `tests/worker/test_worker.py::test_worker_with_worker_deployment_config`, did so 9 times. The logs name 26 tests in all, 8 of them more than once. Section 2 ranks them with the job log behind each.
3. **37 of the 39 time-limit failures were on Windows, and 30 of the 39 fall in the last seven days of the window.** A Windows job execution failed and then passed 6.0% of the time, against 1.6% on Linux.
4. **None of the 11 push runs on `main` since the job matrix changed on 2026-11-06 ended green, as of 2026-11-11.** 7 of them have a Windows test step past its time limit. Over the last 100 pushes, 50 ended red and none was re-run. 21 of those red runs name a test from the ranked list. A red run is the conclusion of a CI run. It doesn't by itself say the code on `main` is broken, and section 2 shows why many of these may be flaky checks.
5. **A re-run that ended green delayed the verdict by 39:12 at the median.** A pull-request run that passes the first time takes 23:49. Added up over the 45 runs, the delay comes to 223.5 hours. That total includes the time before anyone pressed re-run, which in some runs was overnight. The re-run jobs used 1,989 runner minutes.
6. **53 pull-request runs kept going after a newer commit had started a new run.** The workflow has no `concurrency` group, so the older run isn't cancelled. The jobs of those runs used 5,512 runner minutes after the newer run began.
7. **66 of 74 action references are pinned to commit SHAs, 7 are local to the repository and one follows a branch.** 6 actions run on a Node version GitHub has deprecated. The cache store holds 10,754 MB against GitHub's default limit of 10 GB.

**What to change, in order of expected effect.** Section 7 has the arithmetic and the caveats.

| # | Change | Evidence | Size |
| --- | --- | --- | --- |
| 1 | Find what stalls the Windows test steps | 39 failed-then-passed executions, 37 on Windows and 30 in the last seven days, and 7 of the 11 red runs on `main` since 2026-11-06 | A logging change to make the log name the stalled test; the fix depends on what it names |
| 2 | Fix `test_warns_when_workers_too_low` | 22 failed-then-passed executions and 9 more failed jobs on `main`; the only test named in 21 of the 22 | One test |
| 3 | Fix `test_worker_with_worker_deployment_config` | 9 failed-then-passed executions and 3 more failed jobs on `main` | One test |
| 4 | Cancel superseded pull-request runs | 5,512 runner minutes in 30 days | Three lines |
| 5 | Take two downloads off the path of every job | 18 executions failed fetching `protoc`, 9 on a corrupt test-server download | A cache step or a pinned download for each |
| 6 | Decide how red runs on `main` are handled | 50 of 100 pushes red, none re-run | A decision |
| 7 | Pin the one reusable workflow that follows a branch, and move 6 actions off Node 20 | No time saved | A few lines |

What this evidence shows and what it doesn't is at the end of section 2. What couldn't be measured, and why no fix was tested on a fork, is in section 8.

## 1. What was measured

| Source | Window | Count |
| --- | --- | --- |
| All runs, all workflows, all branches | 2026-10-12 to 2026-11-10 (30 days) | 1,714 runs: 1,660 from workflow files, 54 from workflows GitHub generates (Dependabot) |
| Of those, runs of `Continuous Integration` | Same | 414 runs, 114 with more than one attempt |
| Completed push runs of `Continuous Integration` on `main` | 2026-10-06 to 2026-11-11 | 100 runs: 43 passed, 50 failed, 7 cancelled |
| Logs of job executions that failed and then passed | 2026-10-13 to 2026-11-10 | 127 logs |
| Logs of failed jobs in red runs on `main` | 2026-10-06 to 2026-11-11 | 85 logs |
| Job logs, for cache hits | 2026-11-07 to 2026-11-11 | 150 logs from the 10 most recent runs on `main` that reached a verdict |
| Workflow files | Commit `57f3dd6` | 6 files, 74 `uses:` references |
| Cache entries | Snapshot on 2026-11-12 | 50 entries |
| Probe runs on our fork | 2026-11-12 | 2 runs, 18 test steps |

**Definitions.** A run's *wall-clock time* is the latest job finish minus the earliest job creation, over the run's final attempt, which is the time a person waits for a verdict. *Runner minutes* round each job's running time up to a whole minute and add them. That's the unit GitHub bills a private repository in, before the higher rates it charges for Windows and macOS runners. This repository is public and pays nothing for standard runners; the minutes are shown because a private repository would pay. *Queue time* is the gap between a job being created and starting. *Failure rate* is failed runs over passed plus failed. Timings and runner minutes leave out `Required PR Checks`, a job that only reports on the other jobs.

**To reproduce.** Clone the report's repository, then:

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m cidiag analyze --sample temporal-sdk-python   # recompute results/metrics.json from data/raw
.venv/bin/python -m cidiag verify --sample temporal-sdk-python    # check this report against a fresh computation
.venv/bin/python -m cidiag query flaky.tests --sample temporal-sdk-python   # print any one measure
```

`python -m cidiag fetch --sample temporal-sdk-python` pulls the same endpoints again through `gh api`. Each section names the `query` that prints its numbers. Add `--sample temporal-sdk-python` to each.

## 2. Flaky checks

### How a flaky failure is counted

A re-run executes the same commit again. If a job fails in one attempt and passes in a later attempt of the same run, the code was the same both times, so something other than the code decided the result. Each such failed execution is counted once below as "failed, then passed".

Three things in the API make a naive count wrong, and the tool corrects for each.

- **Attempts held for approval.** 114 runs of `Continuous Integration` have an attempt number above 1. In 43 of them the first attempt was held for a maintainer's approval and never ran, so the second attempt was the first real execution. 62 runs have an earlier attempt that failed. Only those count as re-runs after a failure.
- **Copies of jobs that weren't re-run.** When someone re-runs only the failed jobs, GitHub lists every other job again under the new attempt, with a new id and its original start time. A job that failed in attempt 2 and was left alone in attempt 3 shows up as a failure in both. Here a job counts only in the attempt it started in.
- **Jobs that report on other jobs.** `Required PR Checks` fails whenever a job it waits for fails. It's left out.

Query: `python -m cidiag query flaky.instances`. Sources: `GET /repos/temporalio/sdk-python/actions/runs/{id}/attempts/{n}`, `.../attempts/{n}/jobs` and `GET /repos/temporalio/sdk-python/actions/jobs/{id}/logs`.

### Re-runs in the 30 days

| Measure | Value |
| --- | --- |
| Runs of `Continuous Integration` | 414 |
| Runs that reached a verdict | 388 |
| Had at least one failed attempt | 247 (63.7%) |
| Re-run after a failed attempt | 62 |
| Re-run, and ended green | 45 |
| Re-run, and still red | 15 |
| Re-run, then cancelled | 2 |
| Most attempts on one run | 7 |
| Ended red after any re-runs | 52.1% of runs with a verdict |

Query: `python -m cidiag query flaky.rerun_final`. 62 of the 62 re-run runs were on pull requests. Percentages are of the runs that reached a verdict. Counting the 2 that had a failed attempt and ended cancelled, 249 runs had a failed attempt, and 62 of those (24.9%) were re-run.

Most runs had a failed attempt, and much of that isn't flakiness. The most frequent failing step in the window is the lint step (section 3), and a pull request that fails lint is failing on its own change. The 45 runs that went green on a re-run are the ones where the history shows the code alone didn't decide the result.

### What failed, by kind

The 127 failed-then-passed job executions, by what their log says:

| Kind | Executions | What it means |
| --- | --- | --- |
| Names a failing test | 61 | pytest reported one or more tests failing on their own. Ranked below. |
| Step ran past its time limit | 39 | The runner stopped a test step at the limit in the workflow file. No test is named. |
| One error shared by many tests | 5 | Five or more tests in the job failed with the same error line. That's one failure, so it's listed once and those tests aren't ranked. |
| Failed outside the tests | 22 | A setup step failed, or the log has no error line the parser reads. |

Query: `python -m cidiag query flaky.by_kind`.

### Tests that failed and then passed, ranked

61 executions name 26 tests between them. The count is job executions, so one run with the test failing on two runners counts twice under "Failed, then passed" and once under "Runs". "Also failed on main" counts failed jobs in the last 100 pushes to `main` whose log names the same test. Those were never re-run, so they aren't in the first count. The error line is the first line pytest printed for the failure. Where a test failed with more than one error, it's the most frequent.

| # | Test | Failed, then passed | Runs | Seen | Also failed on main | Runner | Error line | Most recent job logs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `tests/worker/test_worker.py::test_warns_when_workers_too_low` | 22 | 15 | 2026-10-29 to 2026-11-10 | 9 | linux 16, macos 6 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [42908130654](https://github.com/temporalio/sdk-python/actions/runs/42908130654/job/130151392745), [42908130654](https://github.com/temporalio/sdk-python/actions/runs/42908130654/job/130151393148), [42918643927](https://github.com/temporalio/sdk-python/actions/runs/42918643927/job/130187509299) |
| 2 | `tests/worker/test_worker.py::test_worker_with_worker_deployment_config` | 9 | 7 | 2026-11-05 to 2026-11-06 | 3 | linux 9 | `AssertionError: assert 'version-v3' == 'version-v2'` | [42136990712](https://github.com/temporalio/sdk-python/actions/runs/42136990712/job/127639534567), [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127646931148), [42279866572](https://github.com/temporalio/sdk-python/actions/runs/42279866572/job/128105738305) |
| 3 | `tests/testing/test_workflow.py::test_workflow_env_time_skipping_basic` | 4 | 4 | 2026-10-20 to 2026-11-05 | 1 | linux 3, windows 1 | `RuntimeError: Failed starting test server: invalid ephemeral server download: could not extract tar archive entry` | [39827582866](https://github.com/temporalio/sdk-python/actions/runs/39827582866/job/119994867201), [41653264899](https://github.com/temporalio/sdk-python/actions/runs/41653264899/job/125976738846), [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127434934764) |
| 4 | `tests/worker/test_worker.py::test_custom_slot_supplier` | 3 | 2 | 2026-10-29 to 2026-11-05 | 2 | linux 1, macos 1, windows 1 | `temporal_sdk_bridge.RPCError: (1, 'operation was canceled', b'')` | [40949338621](https://github.com/temporalio/sdk-python/actions/runs/40949338621/job/123712981685), [40949338621](https://github.com/temporalio/sdk-python/actions/runs/40949338621/job/123712981679), [42128350012](https://github.com/temporalio/sdk-python/actions/runs/42128350012/job/127598255936) |
| 5 | `tests/testing/test_workflow.py::test_ui_port` | 2 | 2 | 2026-10-19 to 2026-10-22 | 3 | linux 1, windows 1 | `RuntimeError: Failed starting Temporal dev server: invalid ephemeral server download: could not extract tar archive e...` | [39281238651](https://github.com/temporalio/sdk-python/actions/runs/39281238651/job/118155744977), [39840312543](https://github.com/temporalio/sdk-python/actions/runs/39840312543/job/120039286072) |
| 6 | `tests/worker/test_worker.py::test_worker_deployment_ramp` | 2 | 2 | 2026-11-05 to 2026-11-09 | 1 | linux 2 | `RecursionError: maximum recursion depth exceeded` | [42128350012](https://github.com/temporalio/sdk-python/actions/runs/42128350012/job/127598255376), [42679739634](https://github.com/temporalio/sdk-python/actions/runs/42679739634/job/129370729355) |
| 7 | `tests/worker/test_worker.py::test_worker_fatal_error_with` | 2 | 2 | 2026-11-05 to 2026-11-09 | 2 | linux 2 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [42101160398](https://github.com/temporalio/sdk-python/actions/runs/42101160398/job/127533670069), [42688982209](https://github.com/temporalio/sdk-python/actions/runs/42688982209/job/129403352161) |
| 8 | `tests/worker/test_workflow.py::test_workflow_cancel_multi` | 2 | 2 | 2026-10-22 to 2026-11-06 | 0 | macos 2 | `temporalio.client._exceptions.WorkflowFailureError: Workflow execution failed` | [39727841101](https://github.com/temporalio/sdk-python/actions/runs/39727841101/job/119655775549), [42279866572](https://github.com/temporalio/sdk-python/actions/runs/42279866572/job/128105738597) |
| 9 | `tests/testing/test_workflow.py::test_workflow_env_time_skipping_manual` | 1 | 1 | 2026-11-05 | 0 | linux 1 | `RuntimeError: Failed starting test server: invalid ephemeral server download: could not extract tar archive entry` | [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127434934764) |
| 10 | `tests/worker/test_activ…::test_sync_activity_process_cancel` | 1 | 1 | 2026-11-06 | 0 | macos 1 | `temporalio.client._exceptions.WorkflowFailureError: Workflow execution failed` | [42136242308](https://github.com/temporalio/sdk-python/actions/runs/42136242308/job/127624997645) |
| 11 | `tests/worker/test_event_groups.py::test_timer_commands_carry_markers` | 1 | 1 | 2026-11-02 | 1 | linux 1 | `assert 0 == 1` | [41176936720](https://github.com/temporalio/sdk-python/actions/runs/41176936720/job/125403278718) |
| 12 | `tests/worker/test_extstore.py::test_worker_storage_drivers_empty_without_external_storage` | 1 | 1 | 2026-10-29 | 0 | linux 1 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123712983943) |
| 13 | `tests/worker/test_extstore.py::test_worker_storage_drivers_populated_from_client` | 1 | 1 | 2026-11-10 | 0 | linux 1 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130189102903) |
| 14 | `tests/worker/test_interceptor.py::test_worker_interceptor` | 1 | 1 | 2026-11-07 | 0 | windows 1 | `temporal_sdk_bridge.RPCError: (1, 'operation was canceled', b'')` | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128238642418) |
| 15 | `tests/worker/test_worker.py::test_worker_fatal_error_run` | 1 | 1 | 2026-11-06 | 0 | linux 1 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [42305815253](https://github.com/temporalio/sdk-python/actions/runs/42305815253/job/128204568821) |
| 16 | `tests/worker/test_workflow.py::test_activity_pause_unpause` | 1 | 1 | 2026-10-14 | 1 | linux 1 | `temporal_sdk_bridge.RPCError: (1, 'operation was canceled', b'')` | [38590740106](https://github.com/temporalio/sdk-python/actions/runs/38590740106/job/115944621624) |
| 17 | `tests/worker/test_workflow.py::test_alternate_async_loop_ordering` | 1 | 1 | 2026-10-13 | 1 | macos 1 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [38442762780](https://github.com/temporalio/sdk-python/actions/runs/38442762780/job/115453277843) |
| 18 | `tests/worker/test_workflow.py::test_wait_condition_timer_options_not_used_by_later_timers` | 1 | 1 | 2026-11-03 | 0 | linux 1 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [41731429920](https://github.com/temporalio/sdk-python/actions/runs/41731429920/job/126249487288) |
| 19 | `tests/worker/test_workflow.py::test_workflow_cancel_activity_then_evict[local-try-cancel-task-failure]` | 1 | 1 | 2026-10-13 | 1 | linux 1 | `Failed: Timeout (>60.0s) from pytest-timeout.` | [38486702807](https://github.com/temporalio/sdk-python/actions/runs/38486702807/job/115601968171) |
| 20 | `tests/worker/test_workflow.py::test_workflow_cancel_activity_while_workflow_cancelled` | 1 | 1 | 2026-10-14 | 2 | windows 1 | `assert not [event_id: 12\nevent_time {\n seconds: 3684182490\n nanos: 455000000\n}\nevent_type: EVENT_TYPE_WORKFLOW_T...` | [38655157187](https://github.com/temporalio/sdk-python/actions/runs/38655157187/job/116163050702) |
| 21 | `tests/worker/test_workflow.py::test_workflow_cancel_child_started[False]` | 1 | 1 | 2026-10-28 | 0 | linux 1 | `AssertionError: assert False` | [40738924878](https://github.com/temporalio/sdk-python/actions/runs/40738924878/job/122995000801) |
| 22 | `tests/worker/test_workflow.py::test_workflow_cancel_child_started[True]` | 1 | 1 | 2026-11-05 | 0 | linux 1 | `AssertionError: assert False` | [42101161020](https://github.com/temporalio/sdk-python/actions/runs/42101161020/job/127504008913) |
| 23 | `tests/worker/test_workflow.py::test_workflow_cancel_external` | 1 | 1 | 2026-10-22 | 1 | macos 1 | `Failed: DID NOT RAISE WorkflowFailureError` | [39727834777](https://github.com/temporalio/sdk-python/actions/runs/39727834777/job/119655755601) |
| 24 | `tests/worker/test_workflow.py::test_workflow_local_activity_cancel_during_backoff[False]` | 1 | 1 | 2026-10-28 | 0 | macos 1 | `assert 19 in [1, 5, 6, 7, 25, 17, ...]` | [40611793357](https://github.com/temporalio/sdk-python/actions/runs/40611793357/job/122938106845) |
| 25 | `tests/worker/test_workflow.py::test_workflow_sleep_task_cancellation` | 1 | 1 | 2026-10-29 | 0 | macos 1 | `AssertionError: Expected TimerCanceled event in history` | [40803372300](https://github.com/temporalio/sdk-python/actions/runs/40803372300/job/123216456828) |
| 26 | `tests/worker/test_workflow.py::test_workflow_stack_trace` | 1 | 1 | 2026-11-06 | 0 | macos 1 | `temporal_sdk_bridge.RPCError: (3, "[TMPRL1101] Potential deadlock detected: workflow didn't yield within 2 second(s)....` | [42136242308](https://github.com/temporalio/sdk-python/actions/runs/42136242308/job/127624997645) |

Query: `python -m cidiag query flaky.tests`. One path in the table ends in an ellipsis because the log cut it short and more than one file in the repository fits.

The top two tests are 31 of the 61 named failures. `test_warns_when_workers_too_low` hit pytest's 60-second per-test limit every time, on Linux and macOS, over 2026-10-29 to 2026-11-10. It was the only test named in 21 of its 22 executions. `test_worker_with_worker_deployment_config` failed on Linux only, with an assertion that a worker reported one deployment version when the test expected another.

### One test, run alone on a fork

The ranking says `test_warns_when_workers_too_low` fails with no change to the code. To check that away from the project's own pull requests, we forked the repository to [cedarwood-studio/sdk-python](https://github.com/cedarwood-studio/sdk-python) and pushed one branch, `ci-diagnostic/flake-probe`, from commit `57f3dd6`. The branch adds one workflow file and changes nothing else. On a Linux, a Windows and a macOS runner it builds the SDK with the same steps as `ci.yml`. Then it runs the test alone repeatedly in one process, runs it alone 200 times spread over the runner's cores, and runs all of `tests/worker/test_worker.py` once the way CI does. No test is skipped, retried or changed.

We ran it twice. The first run gave the one-process step 200 repetitions and a 20-minute limit, which was too tight to finish. The second used 60 repetitions and longer limits. Both are in the table.

| Run and job | Runner | Step | Passed | Failed | How the step ended | Time |
| --- | --- | --- | --- | --- | --- | --- |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785743) | linux | The test alone, 200 times, one process | 123 | 1 | stopped at our step limit | 20:13 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785743) | linux | The test alone, 200 times, spread over all cores | 199 | 1 | finished | 14:03 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785743) | linux | The whole test file, as CI runs it | 47 | 0 | finished | 0:37 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785937) | macos | The test alone, 200 times, one process | 113 | 3 | stopped at our step limit | 20:12 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785937) | macos | The test alone, 200 times, spread over all cores | 197 | 3 | finished | 6:36 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785937) | macos | The whole test file, as CI runs it | 47 | 0 | finished | 0:27 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785546) | windows | The test alone, 200 times, one process | 8 | 0 | pytest-timeout ended the process | 3:09 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785546) | windows | The test alone, 200 times, spread over all cores | 3 | 0 | stopped at our step limit | 20:08 |
| [43156891102](https://github.com/cedarwood-studio/sdk-python/actions/runs/43156891102/job/130978785546) | windows | The whole test file, as CI runs it | 45 | 0 | finished | 1:06 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997525) | linux | The test alone, 60 times, one process | 56 | 4 | finished | 29:29 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997525) | linux | The test alone, 200 times, spread over all cores | 100 | 3 | stopped at our step limit | 30:13 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997525) | linux | The whole test file, as CI runs it | 47 | 0 | finished | 0:30 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997591) | macos | The test alone, 60 times, one process | 58 | 2 | finished | 4:32 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997591) | macos | The test alone, 200 times, spread over all cores | 199 | 1 | finished | 5:34 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997591) | macos | The whole test file, as CI runs it | 47 | 0 | finished | 0:23 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997308) | windows | The test alone, 60 times, one process | 60 | 0 | finished | 5:09 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997308) | windows | The test alone, 200 times, spread over all cores | 135 | 0 | stopped at our step limit | 30:07 |
| [43160729589](https://github.com/cedarwood-studio/sdk-python/actions/runs/43160729589/job/130990997308) | windows | The whole test file, as CI runs it | 45 | 0 | finished | 1:13 |

Query: `python -m cidiag query probe`. "Passed" and "Failed" are pytest's own counts where the step finished, and counts of its progress marks where it didn't.

- **The test fails when run alone.** In the 6 single-test steps that ran to the end, 11 of 780 repetitions failed. Of the 11 failures pytest printed an error for, 11 read `Failed: Timeout (>60.0s) from pytest-timeout.`, the same line as in the project's history.
- **One run of the test file doesn't show it.** The whole file passed in all 6 of its steps: 278 test results and 0 failures. Someone who runs the file once will probably see nothing wrong.
- **On Windows the same stall takes a different shape.** On Linux and macOS, pytest-timeout enforces the 60-second limit with a signal and fails the one test. Windows has no such signal, so pytest-timeout uses a watchdog thread there (the logs say `timeout method: thread`), and when a test runs past the limit it ends the whole pytest process. 1 of the 4 single-test steps on Windows ran to the end. In 1, pytest-timeout ended the process with no summary and no test named. 2 went quiet until our step limit, and the log doesn't say why.

A Windows step that goes quiet with no test named resembles the 37 Windows time-limit failures in the project's history (next subsection). In the ranking above, `test_warns_when_workers_too_low` is named 22 times on Linux and macOS and 0 times on Windows. Taken together, that suggests some of the Windows time-limit failures are this test, or others like it, reported in a different way.

The probe doesn't prove that. It ran one test, on a later day, on runners assigned to our fork. Repeating a test inside one pytest session is also not how CI runs it, and the repetition may add stalls of its own. What it does show is that this test can run past 60 seconds with no pull request involved. It did so on Linux and macOS in the steps that finished, and on Windows in the step pytest-timeout ended.

### Steps that ran past their time limit

In 39 failed-then-passed executions the log names no test. A test step reached the `timeout-minutes` set for it in the workflow file and the runner stopped it.

| Job | Step limit | Failed, then passed | Runs | Seen | Most recent job logs |
| --- | --- | --- | --- | --- | --- |
| `build-lint-test (3.15, windows-latest)` | 10 min | 8 | 4 | 2026-11-06 to 2026-11-09 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/128185984515), [42305815253](https://github.com/temporalio/sdk-python/actions/runs/42305815253/job/128194717990), [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/129321802365) |
| `build-lint-test (3.15, windows-latest)` | 15 min | 8 | 6 | 2026-11-06 to 2026-11-10 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/129336725091), [42755878845](https://github.com/temporalio/sdk-python/actions/runs/42755878845/job/129630018815), [42777052659](https://github.com/temporalio/sdk-python/actions/runs/42777052659/job/129964787011) |
| `build-lint-test (3.11, windows-latest)` | 15 min | 7 | 6 | 2026-11-06 to 2026-11-10 | [42918643927](https://github.com/temporalio/sdk-python/actions/runs/42918643927/job/130187509373), [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130189102990), [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130201893250) |
| `build-lint-test (3.10, windows-latest)` | 15 min | 5 | 5 | 2026-10-29 to 2026-11-05 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123726199512), [42081130391](https://github.com/temporalio/sdk-python/actions/runs/42081130391/job/127434134622), [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127434935116) |
| `build-lint-test (3.10, windows-latest)` | 10 min | 4 | 4 | 2026-10-13 to 2026-11-05 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123712983847), [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127459953253), [42130768800](https://github.com/temporalio/sdk-python/actions/runs/42130768800/job/127606492280) |
| `build-lint-test (3.14, windows-latest)` | 15 min | 4 | 3 | 2026-10-29 to 2026-11-05 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123738353870), [41512911720](https://github.com/temporalio/sdk-python/actions/runs/41512911720/job/125509012690), [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127434934973) |
| `build-lint-test (3.10, macos-arm)` | 15 min | 1 | 1 | 2026-10-13 | [38451473069](https://github.com/temporalio/sdk-python/actions/runs/38451473069/job/115483184206) |
| `build-lint-test (3.14, windows-latest)` | 10 min | 1 | 1 | 2026-11-05 | [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127459953130) |
| `build-lint-test (3.15, ubuntu-latest)` | 10 min | 1 | 1 | 2026-11-05 | [42128350012](https://github.com/temporalio/sdk-python/actions/runs/42128350012/job/127598255553) |

Query: `python -m cidiag query flaky.timeouts`. By runner: windows 37, linux 1, macos 1. 30 of the 39 started on or after 2026-11-04.

The project sets `timeout = 60` and `timeout_func_only = true` for pytest in `pyproject.toml`. With that setting the 60-second limit covers the body of each test and leaves out its fixtures, so a stall while a fixture sets up or tears down would run until the step limit with no test named. That fits what the logs show. We didn't establish that it's the cause. Our stored copy of each log keeps the failure lines and drops pytest's progress output, so it can't say whether one test stalled or the whole step ran slow.

### One error shared by many tests

| Error line | Failed, then passed | Tests it took down per job | Seen | Job logs |
| --- | --- | --- | --- | --- |
| `RuntimeError: Failed starting Temporal dev server: invalid ephemeral server download: could not extract tar archive entry` | 4 | 18 to 624 | 2026-10-13 to 2026-11-05 | [40008061417](https://github.com/temporalio/sdk-python/actions/runs/40008061417/job/122234383085), [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123726199679), [42119706012](https://github.com/temporalio/sdk-python/actions/runs/42119706012/job/127568543267) |
| `TimeoutError: timed out` | 1 | 10 | 2026-11-03 | [41718242569](https://github.com/temporalio/sdk-python/actions/runs/41718242569/job/126203818088) |

Query: `python -m cidiag query flaky.shared`. In the largest case every test in the job that needs the local test server failed with the same line, because the server binary didn't download intact. Counting those as hundreds of flaky tests would bury the ranking above. Three tests in the ranking (`test_workflow_env_time_skipping_basic`, `test_workflow_env_time_skipping_manual` and `test_ui_port`) failed on their own with a download error of the same kind. In all, 9 executions on 7 different days trace to that download.

### Failures outside the tests

| Failing step | Error line | Failed, then passed | Runs | Seen | Most recent job logs |
| --- | --- | --- | --- | --- | --- |
| `Run arduino/setup-protoc@c65c819552d16ad3c9b72d9dfd5ba5237b9c906b` | `Error: unable to get latest version` | 15 | 3 | 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964370058), [39816766359](https://github.com/temporalio/sdk-python/actions/runs/39816766359/job/119968935520), [39816766359](https://github.com/temporalio/sdk-python/actions/runs/39816766359/job/119968935791) |
| `Install Protoc` | `Error: unable to get latest version` | 2 | 2 | 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948162441), [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964369816) |
| `Run SDK-features tests directly` | none in the log | 2 | 2 | 2026-10-28 to 2026-11-10 | [40571679224](https://github.com/temporalio/sdk-python/actions/runs/40571679224/job/122932219336), [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130189103582) |
| `Run arduino/setup-protoc@c65c819552d16ad3c9b72d9dfd5ba5237b9c906b` | `Error: Failed to download version v23.4: Error, Unexpected HTTP response: 500 - 500` | 1 | 1 | 2026-10-20 | [39451551904](https://github.com/temporalio/sdk-python/actions/runs/39451551904/job/118727390864) |
| `Run poe test -s --workflow-environment time-skipping` | none in the log | 1 | 1 | 2026-10-13 | [38447120318](https://github.com/temporalio/sdk-python/actions/runs/38447120318/job/115468297216) |
| `Test Alpine wheel` | none in the log | 1 | 1 | 2026-10-23 | [39920469335](https://github.com/temporalio/sdk-python/actions/runs/39920469335/job/120532851838) |

Query: `python -m cidiag query flaky.other`. 18 executions in 4 runs failed while installing `protoc`, all on 2026-10-20 and 2026-10-22. `arduino/setup-protoc` asks the GitHub API for the full list of protobuf releases on every job to resolve the version, at the commit pinned here (`src/installer.ts`, `fetchVersions`). When that list comes back empty the step stops with "unable to get latest version". The history shows the lookup failing in a burst. It gives no reason.

### By runner

Every job execution of `Continuous Integration` in the window that ended in a pass or a failure, and how many of them failed and then passed:

| Runner | Job executions | Failed, then passed | Share |
| --- | --- | --- | --- |
| linux | 4,006 | 63 | 1.6% |
| windows | 765 | 46 | 6.0% |
| macos | 747 | 18 | 2.4% |

Query: `python -m cidiag query flaky.platforms`.

### The main branch

No run on `main` was re-run in the last 100 pushes, so there's no second attempt to compare, and nothing on `main` counts as "failed, then passed". 50 of those pushes ended red. We read the logs of their failed jobs:

| Measure | Value |
| --- | --- |
| Red runs on `main` | 50 of 100 |
| Failed jobs in them, `Required PR Checks` left out | 85 |
| Of those, naming a test | 48 |
| Step past its time limit | 17 |
| One error shared by many tests | 4 |
| Outside the tests | 16 |
| Red runs that name a test from the ranked list | 21 |
| Red runs where every failed job names only tests from the ranked list | 11 |
| Red runs with a step past its time limit | 15 |
| Tests named on `main` that aren't in the ranked list | 17 |

Query: `python -m cidiag query flaky.main`.

The job matrix changed on 2026-11-06, when the Python versions moved from 3.10 and 3.14 to 3.11 and 3.15. All 11 pushes to `main` since then ended red, up to the last one read (2026-11-11). Of their 24 failed jobs, 14 name a test, 9 are a step past its time limit and 1 is one error shared by many tests. All 9 time-limit failures were Windows jobs, in 7 of the 11 runs. Query: `python -m cidiag query flaky.main.latest_matrix`.

A red run on `main` that names only tests known to fail and pass on the same commit elsewhere is probably flaky too. The history can't confirm it, because nobody ran it again.

### What the re-runs cost

Over the 45 runs that were re-run after a failure and ended green:

| Measure | Value |
| --- | --- |
| Delay from the first red verdict to the green one, median | 39:12 |
| Delay, 90th percentile | 16:33:49 |
| Delay, all 45 runs added up | 223.5 hours |
| Time from the run starting to the green verdict, median | 1:18:19 |
| A pull-request run that passes the first time, median | 23:49 |
| Runner minutes used by the re-run jobs | 1,989 |
| Attempts it took | 2 attempts in 26 runs, 3 in 15, 4 in 1, 5 in 1, 6 in 1, 7 in 1 |

Query: `python -m cidiag query flaky.cost`. The delay runs from the end of the first attempt to the end of the last. It includes the time before someone noticed the failure and pressed re-run, and at the 90th percentile that's overnight. The runner minutes are the smaller cost next to a pull request sitting red for 39:12 on a commit that later passed.

### What this evidence shows and what it doesn't

- **It shows** that each failure counted above didn't come from the commit alone. The same job, on the same commit, later passed.
- **A pass after a failure suggests a flaky test without proving one.** It says the failure isn't deterministic. One occurrence could be a slow runner or a network fault. `test_warns_when_workers_too_low` failed this way 22 times in 15 runs on two operating systems, which is hard to explain as chance. The 18 tests that appear once are candidates, and we wouldn't act on one of them without seeing it again.
- **It undercounts.** A failure is counted only if someone re-ran the job and it then passed. 24.9% of the runs with a failed attempt were re-run. Failures on `main` were never re-run. A flaky failure that the author cleared by pushing another commit is invisible here.
- **It doesn't say why a test is flaky.** The error line says what the test saw. Finding the cause means reading the test and the code under it, which a diagnostic doesn't do.
- **A step past its time limit names no test.** The 39 time-limit failures could be one stalled test or many.
- **The ranking covers 30 days.** A test that fails one time in several hundred runs may not appear at all, and GitHub keeps job logs for 90 days by default, so the window can't be pushed back far.
- **The project has its own reporting.** The workflow uploads JUnit XML for every test job. A team with those files can count failures per test directly, without waiting for someone to press re-run. We didn't use them because the artifacts expire after 14 days.

## 3. Failure rates by workflow

All runs created from 2026-10-12 to 2026-11-10, on every branch:

| Workflow | Trigger | Runs | Passed | Failed | Cancelled | Held for approval | Failure rate | Re-run after failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Changelog | pull_request | 374 | 249 | 114 | 0 | 11 | 31.4% | 2 |
| Check for CODEOWNERS | pull_request_target | 334 | 233 | 0 | 0 | 0 | 0.0% | 0 |
| Opengrep SAST | pull_request | 333 | 283 | 39 | 0 | 11 | 12.1% | 0 |
| Continuous Integration | pull_request | 329 | 149 | 161 | 8 | 11 | 51.9% | 62 |
| SDK Sentinel PR responder relay | issue_comment | 154 | 0 | 0 | 0 | 0 | n/a | 0 |
| Continuous Integration | push | 85 | 37 | 41 | 7 | 0 | 52.6% | 0 |
| Nightly | schedule | 30 | 30 | 0 | 0 | 0 | 0.0% | 0 |
| Check for CODEOWNERS | pull_request | 20 | 15 | 0 | 0 | 5 | 0.0% | 0 |
| Release from main | workflow_dispatch | 1 | 1 | 0 | 0 | 0 | 0.0% | 0 |

Query: `python -m cidiag query window.rows`. Source: `GET /repos/temporalio/sdk-python/actions/runs?created={day}`, one request per day, because GitHub returns at most 1,000 runs for one query and this window holds 1,714.

Cancelled runs and runs held for approval never reached a verdict and are left out of the failure rate, as are runs GitHub skipped. The failure rate is for the final attempt, so a run that failed, was re-run and passed counts as passed. "Re-run after failure" counts runs with an earlier attempt that failed. `Opengrep SAST` and `Check for CODEOWNERS` run on this repository but their files aren't in its `.github/workflows` directory at the commit we read, so they're counted here and not examined in section 5. A failed `Changelog` run means the pull request has no changelog entry yet, which is the check doing its job.

**What failed.** Failed jobs of `Continuous Integration` in the window, by job and step, over each run's final attempt. The ten most frequent:

| Job | Failing step | Failures |
| --- | --- | --- |
| `build-lint-test` | `Run poe lint` | 188 |
| `Required PR Checks` | `Fail if any check failed or was cancelled` | 95 |
| `build-lint-test` | `Run poe test -s` | 78 |
| `build-lint-test` | `Run poe test --reruns 3 --only-rerun "RuntimeError: Failed validating workflow" -s` | 45 |
| `cloud-test` | `Run poe test -s --workflow-environment envconfig` | 35 |
| `build-lint-test` | `Run poe test -s --workflow-environment time-skipping-v2` | 33 |
| `test-latest-deps` | `Run poe lint` | 31 |
| `build-lint-test` | `Run arduino/setup-protoc` | 18 |
| `fips-build` | `Run tests against the FIPS build` | 17 |
| `test-latest-deps` | `Run poe test -s` | 15 |

Query: `python -m cidiag query window.failing_jobs`. `build-lint-test` runs as eight matrix jobs, so one pull request that fails lint adds eight to the first row.

## 4. Run time, and where it goes

Over the 93 of the last 100 runs on `main` that reached a verdict:

| Measure | Value |
| --- | --- |
| Median wall-clock time | 23:00 (23.0 min) |
| Median, successful runs only | 22:57 |
| 90th percentile | 28:21 |
| Slowest | 60:31 |
| Median runner minutes per run | 238 |
| Runner minutes, all 93 runs | 21,560 |

Query: `python -m cidiag query main.summary`. Source: `GET /repos/temporalio/sdk-python/actions/workflows/ci.yml/runs?branch=main&event=push&status=completed` and `GET /repos/temporalio/sdk-python/actions/runs/{id}/jobs?filter=all`.

On pull requests, the 63 runs that passed on the first attempt took 23:49 at the median and 27:36 at the 90th percentile. Query: `python -m cidiag query flaky.pr_first_pass`.

**By step.** Share of all step time across the 43 successful runs on `main`, with the per-job report path removed from step names so that matrix jobs add up:

| Step | Minutes per run, all jobs | Share of step time |
| --- | --- | --- |
| Run poe test --reruns 3 --only-rerun "RuntimeError: Failed validating workflow" -s | 28.0 | 12.4% |
| Build Alpine wheel | 27.4 | 12.2% |
| Run poe test  -s | 27.4 | 12.1% |
| Run poe build-develop | 21.0 | 9.3% |
| Run poe test --reruns 3 --only-rerun "RuntimeError: Failed validating workflow" -s --workflow-environment time-skipping-v2 | 20.3 | 9.0% |
| Run poe test  -s --workflow-environment time-skipping-v2 | 19.6 | 8.7% |
| Run poe lint | 16.3 | 7.2% |
| Run poe test -s --workflow-environment envconfig | 7.6 | 3.4% |

Query: `python -m cidiag query main.steps`. The test steps are the largest share. Building the Rust extension (`poe build-develop`, plus `Build Alpine wheel` in the two packaging jobs) is the next largest.

**By job.** The job matrix changed on 2026-11-06 and no run on `main` has passed since, so there are no successful runs of the current matrix to time. The table covers the 43 successful runs on the matrix before the change (2026-10-06 onward). "Finished last" counts the runs in which that job was the last to complete.

| Job | Runs | Median | 90th pct | Finished last |
| --- | --- | --- | --- | --- |
| `build-lint-test (3.10, windows-latest)` | 43 | 22:35 | 25:08 | 24 |
| `build-lint-test (3.14, windows-latest)` | 43 | 22:00 | 23:55 | 14 |
| `build-lint-test (3.14, ubuntu-latest)` | 43 | 20:34 | 23:10 | 2 |
| `build-lint-test (3.10, ubuntu-arm)` | 43 | 18:13 | 19:18 | 0 |
| `build-lint-test (3.14, ubuntu-arm)` | 43 | 17:28 | 19:20 | 1 |
| `build-lint-test (3.10, ubuntu-latest)` | 43 | 17:18 | 19:04 | 0 |
| `build-lint-test (3.10, macos-arm)` | 43 | 16:55 | 19:30 | 1 |
| `build-lint-test (3.14, macos-arm)` | 43 | 16:31 | 19:18 | 0 |
| `alpine-package-test (cp310-musllinux_aarch64, ubuntu-24.04-arm64-2-core)` | 43 | 15:12 | 16:13 | 0 |
| `alpine-package-test (cp310-musllinux_x86_64, ubuntu-latest)` | 43 | 13:46 | 14:54 | 0 |
| `fips-build` | 43 | 13:31 | 15:59 | 1 |
| `cloud-test` | 43 | 11:05 | 12:44 | 0 |
| `test-latest-deps` | 43 | 10:22 | 11:35 | 0 |
| `check-protos` | 43 | 10:14 | 11:00 | 0 |
| `features-tests / test` | 43 | 8:11 | 9:11 | 0 |

Query: `python -m cidiag query main.current_matrix.jobs` (the name is the tool's; here it holds the matrix of the most recent run that passed). A Windows job finished last in 38 of the 43 runs.

**Waiting for a runner.** The longest wait any job had in a run was 5 seconds at the median and 10 seconds at most, over 43 successful runs. No run had a job wait more than a minute. Query: `python -m cidiag query main.queue`.

**Cancelled runs.** 7 of the last 100 runs on `main` were cancelled before a verdict, after using 1,812 runner minutes. Across pushes and pull requests in the 30-day window, 15 runs were cancelled after using 4,697 runner minutes. Query: `python -m cidiag query main.cancelled`.

**Superseded runs.** The workflow file has no `concurrency` group, so a new push to a pull request starts a new run and leaves the old one going. 53 pull-request runs were still running when a newer commit on the same branch started a run of its own. Their jobs used 5,512 runner minutes after that moment. Query: `python -m cidiag query flaky.superseded`. Runs are matched by head branch name, so two forks that both open a pull request from a branch called `main` could be confused. We saw no sign of that but didn't rule it out.

## 5. Third-party actions

74 `uses:` references across 6 workflow files. 7 point at actions inside the repository. The rest go to 14 pairs of action and pinned version, two of them reusable workflows:

| Action | Ref | Version comment | Uses | Pinned to | Runtime | Latest release | Archived |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Swatinem/rust-cache | `e18b497796c1` | v2 | 7 | commit SHA | node24 | v2.9.3 | no |
| actions/checkout | `9c091bb21b7c` | v7.0.0 | 11 | commit SHA | node24 | v7.0.1 | no |
| actions/checkout | `de0fac2e4500` | v6 | 3 | commit SHA | node24 | v7.0.1 | no |
| actions/create-github-app-token | `fee1f7d63c2f` | v2 | 1 | commit SHA | node20 | v3.3.0 | no |
| actions/setup-go | `d35c59abb061` | v5 | 1 | commit SHA | node20 | v7.0.0 | no |
| actions/setup-node | `49933ea5288c` | v4 | 1 | commit SHA | node20 | v7.1.0 | no |
| actions/setup-python | `a26af69be951` | v5 | 9 | commit SHA | node20 | v7.1.0 | no |
| actions/upload-artifact | `ea165f8d65b6` | v4 | 6 | commit SHA | node20 | v7.0.2 | no |
| arduino/setup-protoc | `c65c819552d1` | v3 | 7 | commit SHA | node20 | v3.0.0 | no |
| astral-sh/setup-uv | `cec208311dfd` | v8 | 8 | commit SHA | node24 | v10.3.3 | no |
| dtolnay/rust-toolchain | `29eef336d9b2` | stable | 9 | commit SHA | composite | v1 | no |
| pypa/gh-action-pypi-publish | `cef221092ed1` | release/v1 | 2 | commit SHA | composite | v1.14.3 | no |
| temporalio/.github/.github/workflows/changelog-fragments.yml | `f2a689950aa8` |  | 1 | commit SHA |  |  | no |
| temporalio/features/.github/workflows/python.yaml | `main` |  | 1 | tag or branch |  |  | no |

Query: `python -m cidiag query static.actions`. Source: the workflow files at `57f3dd6`, plus `GET /repos/{owner}/{action}` and each action's `action.yml` at the pinned ref. The last two rows are reusable workflows, which have no runtime or release of their own.

- **Pinned:** 66 references are full commit SHAs. 1 follows a branch:

| Reference | Ref | File | Line |
| --- | --- | --- | --- |
| `temporalio/features/.github/workflows/python.yaml` | `main` | ci.yml | 356 |

- **Deprecated runtime:** 6 actions declare Node 20, which GitHub has deprecated: `actions/setup-python`, `arduino/setup-protoc`, `actions/upload-artifact`, `actions/setup-node`, `actions/setup-go`, `actions/create-github-app-token`. The job logs carry GitHub's own warning that these are being forced onto Node 24 (the warning line isn't among the lines our stored copies keep).
- **Behind:** 7 pinned actions are at least one major version behind their latest release.
- **Archived:** 0 of the action repositories are archived.

The reusable workflow on line 356 of `ci.yml` runs whatever is on `main` of `temporalio/features` at the time. It's the same organization's repository, so this is a matter of repeatability more than of trust. A red `features-tests` job can come from a change in the other repository.

## 6. Dependency caches

8 jobs install dependencies and all of them have a cache step. Query: `python -m cidiag query static.jobs`.

Whether a cache is hit can only be read from job logs. In 150 job logs from the 10 most recent runs on `main` that reached a verdict:

| Measure | Value |
| --- | --- |
| Python package cache (`setup-uv`) restored | 110 of 150 lookups (73.3%) |
| Rust build cache (`rust-cache`) restored in full | 92 of 130 lookups (70.8%) |
| Rust build cache restored from an older key | 14 |
| Rust build cache not found | 24 |
| `Run poe build-develop` step with a full restore, median | 1:29 over 85 jobs |
| `Run poe build-develop` step without one, median | 2:10 over 35 jobs |

Query: `python -m cidiag query caches`. Source: `GET /repos/temporalio/sdk-python/actions/jobs/{id}/logs`, trimmed to the cache, failure and result lines.

The cache list on 2026-11-12 held 50 entries totaling 10,754 MB. GitHub's default limit for a repository is 10 GB, and it evicts the entries read least recently once a repository is over. A store sitting at the limit is a likely reason for some of the misses above, though the list is a snapshot and holds no history of evictions. 45 of the 50 entries hadn't been read since they were written, 13 of them on pull-request refs, where a cache written by one pull request can't be read by another.

A full restore of the Rust cache is worth 41 seconds on the build step at the median. That's small next to the test steps, so the caches aren't where this pipeline's time goes.

## 7. Changes ranked by expected effect

Most of this pipeline's cost is red verdicts on commits that later passed unchanged. The minutes are the smaller part. The order below follows how many failed-then-passed executions and red runs each item accounts for.

**1. Find what stalls the Windows test steps.**

- Evidence: 39 failed-then-passed executions ended at a step time limit, 37 of them on Windows and 30 since 2026-11-04 (the last seven days of the window). On `main`, 7 of the 11 runs since the matrix change have a Windows test step past its limit, and none of the 11 passed.
- Most of these are recent. The matrix moved to Python 3.11 and 3.15 on 2026-11-06. Time-limit failures before that date exist too (2026-10-13 is the first), so the change may have made an existing problem more frequent. We haven't shown that it did.
- One candidate comes from the probe in section 2. On Windows, the probe's steps stopped with the whole pytest process ended or with the step silent, where Linux and macOS reported a failure by name. If that's what's happening here, the Windows time-limit failures and the ranked tests are partly the same problem, and items 2 and 3 would shrink this one.
- The first step is to get a name. Two cheap ways are to run the Windows jobs with verbose output, so the log lists each test as it finishes and the ones that never finish stand out, or to set pytest's `faulthandler_timeout`, which prints every thread's stack when a test runs long. We haven't tried either on this suite, and under `pytest-xdist` what a worker process prints doesn't always reach the log.
- Raising the step limit might turn some of these green and wouldn't tell anyone why they're slow. We wouldn't start there.
- Size: a logging change to get the name. The fix is unknown until then.

**2. Fix `test_warns_when_workers_too_low`.**

- Evidence: 22 failed-then-passed executions in 15 runs, 9 more failed jobs on `main`. It was the only test named in 21 of the 22. Every failure is the 60-second per-test limit.
- If it stopped failing, 21 of the 127 failed-then-passed executions wouldn't have happened. Most of the runs it appears in had other failures as well. In 1 of its 15 runs it was the only reason for the re-run.
- Size: one test. The cause needs someone who knows the worker code.
- Marking the test to retry on failure would take it off this list and leave whatever makes a worker wait 60 seconds. We wouldn't recommend that as the fix.

**3. Fix `test_worker_with_worker_deployment_config`.**

- Evidence: 9 failed-then-passed executions in 7 runs, all on Linux, and 3 more failed jobs on `main`.
- The assertion compares deployment version strings and fails with `AssertionError: assert 'version-v3' == 'version-v2'`. A test that sees the next version too early or the previous one too late may be racing a server-side change. That's a guess from the error line.
- Size: one test.

**4. Cancel superseded pull-request runs.**

- Evidence: 53 runs in 30 days, 5,512 runner minutes used after a newer commit had its own run.
- Change: a `concurrency` group keyed on the pull request, with `cancel-in-progress` set for pull requests only. Three lines. On `main` every push should keep its own verdict.
- Runner minutes here are free to a public repository. For a private one this is the largest saving in minutes in the report.

**5. Take two downloads off the path of every job.**

- `protoc`: 18 failed-then-passed executions in 4 runs, on two days. The setup action lists every protobuf release from the GitHub API on each job. Setting an exact version wouldn't remove that lookup, because the action lists releases either way. Caching the `protoc` binary, or fetching one fixed release directly, would.
- Test server: 9 executions on 7 days failed because the test server archive didn't extract. The tests download it at run time. Caching it between runs, keyed on its version, would remove the download from most jobs. We haven't checked how the SDK chooses the version to download.
- Size: one cache step each, untested.

**6. Decide how red runs on `main` are handled.** This is a choice for the project.

- 50 of the last 100 pushes ended red and none was re-run. With half the runs red, many of them for the reasons in section 2, a red run caused by a real regression is hard to tell from the rest.
- Options that cost little: re-run failed jobs on `main` once automatically and record that it happened, or post red runs on `main` to a channel with the failing test names from the JUnit files the workflow already uploads.
- An automatic retry hides flakiness unless something counts the retries. If the project adds one, the count belongs in the same place as the result.

**7. Pin the reusable workflow and move off Node 20.** No time saved.

- `temporalio/features/.github/workflows/python.yaml@main` is the one reference that follows a branch.
- 6 actions run on Node 20. GitHub forces them onto Node 24 today, and a later runner update can break them.

**Smaller observations.**

- At the commit we read, one test step in `ci.yml` (line 162, the FIPS build) retries tests that fail with one named error, up to three times. Earlier in the window the Python 3.10 jobs carried the same retry, which is why it shows in step names in sections 3 and 4. That's a targeted retry. Tests retried inside a job don't show in run history. In the 150 logs we read from `main`, pytest's result counts report 0 retried tests.
- The cache store is at GitHub's 10 GB default. Dropping caches written on pull-request refs, which no other pull request can read, would leave more room for the ones `main` reads.

## 8. What couldn't be measured

- **No fix was tested on a fork.** The first sample changed three lines and showed runs before and after. A flaky test doesn't allow that in a handful of runs. A test that fails one time in twenty needs a few hundred runs on each side to show a difference, and the fix itself needs someone who knows the code under test. What we ran on our fork was a measurement of one test, described in section 2 under "One test, run alone on a fork". We didn't add retries or skip any test on the fork to get a green run.
- **Which test was running when a step hit its time limit.** Covered in section 2.
- **Failures nobody re-ran.** 249 runs had a failed attempt and 62 were re-run. We read the logs of the red runs on `main` and didn't read the logs of red pull-request runs that were never re-run, since a pull request can fail on its own change and the history can't tell the two apart.
- **Why a test is flaky.** The report names tests and quotes what they printed. It doesn't read the SDK's code.
- **Why the `protoc` lookup failed on two days.** The log gives the action's error and no HTTP status.
- **The `cloud-test` job.** It runs against a hosted service with secrets, so it can't run on a fork, and its failures in the window weren't examined beyond the counts in section 3.
- **Flakiness older than the window.** Logs are kept 90 days by default. We read 30 days of re-runs and about five weeks of `main`.
- **Cost in dollars.** The repository is public. Runner minutes are reported raw. GitHub bills a private repository more per minute for Windows and macOS runners than for Linux, and one job here runs on a runner with a custom label whose rate we can't see. For a client, the report prices the minutes at the rate on the client's bill and the waiting at a loaded hourly rate the client gives us.
- **Cache hits before the log sample.** The hit rates come from 10 runs. The cache list is a snapshot.

## 9. How this report was made

- **Tool.** The `cidiag` package in this repository, written in Python with unit tests. It calls the GitHub REST API through `gh api`, stores every response under `samples/temporal-sdk-python/data/raw/` (with the names, logins and email addresses of the people behind each run removed, release notes dropped, action manifests cut to the line that names the runtime, and logs trimmed to the lines the analysis reads), and computes everything from those files.
- **Every number is generated.** This file is produced from `REPORT.md.tmpl` and `results/metrics.json` in the same directory. `python -m cidiag verify --sample temporal-sdk-python` recomputes the metrics from the raw data and fails if this file differs by a character. The repository's CI runs that check on every push.
- **Test names** come from pytest's failure sections and its summary table in each job log. The parser is in `cidiag/flaky.py` and reads pytest output. A suite on another test runner needs its own parser.
- **Percentiles** are nearest-rank, so each one is a value that occurred. A median over an even number of runs is the average of the two middle values.
- **Scope.** This report covers how the pipeline performs: time, failures, re-runs, pins, caches. It isn't a review of the project's code, tests or security.

## Appendix: every job execution that failed and then passed

| Date | Job log | Failed in attempt | Job | What failed |
| --- | --- | --- | --- | --- |
| 2026-10-13 | [38442762780](https://github.com/temporalio/sdk-python/actions/runs/38442762780/job/115453277843) | 1, passed in 2 | `build-lint-test (3.10, macos-arm)` | `test_alternate_async_loop_ordering` |
| 2026-10-13 | [38447120318](https://github.com/temporalio/sdk-python/actions/runs/38447120318/job/115468297216) | 1, passed in 2 | `build-lint-test (3.14, windows-latest)` | outside the tests |
| 2026-10-13 | [38451473069](https://github.com/temporalio/sdk-python/actions/runs/38451473069/job/115483184496) | 1, passed in 2 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-10-13 | [38451473069](https://github.com/temporalio/sdk-python/actions/runs/38451473069/job/115483184206) | 1, passed in 2 | `build-lint-test (3.10, macos-arm)` | step past its time limit |
| 2026-10-13 | [38460304882](https://github.com/temporalio/sdk-python/actions/runs/38460304882/job/115513433647) | 1, passed in 2 | `check-protos` | one error shared by many tests |
| 2026-10-13 | [38486702807](https://github.com/temporalio/sdk-python/actions/runs/38486702807/job/115601968171) | 1, passed in 2 | `build-lint-test (3.10, ubuntu-arm)` | `test_workflow_cancel_activity_then_evict[local-try-cancel-task-failure]` |
| 2026-10-14 | [38590740106](https://github.com/temporalio/sdk-python/actions/runs/38590740106/job/115944621624) | 1, passed in 2 | `build-lint-test (3.10, ubuntu-latest)` | `test_activity_pause_unpause` |
| 2026-10-14 | [38655157187](https://github.com/temporalio/sdk-python/actions/runs/38655157187/job/116163050702) | 1, passed in 3 | `build-lint-test (3.14, windows-latest)` | `test_workflow_cancel_activity_while_workflow_cancelled` |
| 2026-10-19 | [39281238651](https://github.com/temporalio/sdk-python/actions/runs/39281238651/job/118155744977) | 1, passed in 3 | `build-lint-test (3.14, windows-latest)` | `test_ui_port` |
| 2026-10-20 | [39451551904](https://github.com/temporalio/sdk-python/actions/runs/39451551904/job/118727390864) | 1, passed in 2 | `build-lint-test (3.14, windows-latest)` | outside the tests |
| 2026-10-20 | [39509291394](https://github.com/temporalio/sdk-python/actions/runs/39509291394/job/118925982740) | 1, passed in 2 | `build-lint-test (3.14, ubuntu-latest)` | `test_workflow_env_time_skipping_basic` |
| 2026-10-22 | [39727834777](https://github.com/temporalio/sdk-python/actions/runs/39727834777/job/119655755601) | 1, passed in 2 | `build-lint-test (3.10, macos-arm)` | `test_workflow_cancel_external` |
| 2026-10-22 | [39727841101](https://github.com/temporalio/sdk-python/actions/runs/39727841101/job/119655775549) | 1, passed in 2 | `build-lint-test (3.10, macos-arm)` | `test_workflow_cancel_multi` |
| 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948161597) | 2, passed in 3 | `fips-build` | outside the tests |
| 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948162142) | 2, passed in 3 | `check-protos` | outside the tests |
| 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948162175) | 2, passed in 3 | `build-lint-test (3.10, ubuntu-latest)` | outside the tests |
| 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948162441) | 2, passed in 3 | `features-tests / test` | outside the tests |
| 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948162478) | 2, passed in 3 | `build-lint-test (3.14, ubuntu-latest)` | outside the tests |
| 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948162637) | 2, passed in 3 | `build-lint-test (3.14, macos-arm)` | outside the tests |
| 2026-10-22 | [39814145763](https://github.com/temporalio/sdk-python/actions/runs/39814145763/job/119948162359) | 2, passed in 3 | `build-lint-test (3.10, ubuntu-arm)` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964369652) | 1, passed in 2 | `check-protos` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964369816) | 1, passed in 2 | `features-tests / test` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964369856) | 1, passed in 2 | `build-lint-test (3.10, ubuntu-latest)` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964369863) | 1, passed in 2 | `build-lint-test (3.14, macos-arm)` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964369977) | 1, passed in 2 | `build-lint-test (3.14, ubuntu-latest)` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964370004) | 1, passed in 2 | `build-lint-test (3.10, windows-latest)` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964370077) | 1, passed in 2 | `build-lint-test (3.10, macos-arm)` | outside the tests |
| 2026-10-22 | [39818846071](https://github.com/temporalio/sdk-python/actions/runs/39818846071/job/119964370058) | 1, passed in 2 | `build-lint-test (3.10, ubuntu-arm)` | outside the tests |
| 2026-10-22 | [39816766359](https://github.com/temporalio/sdk-python/actions/runs/39816766359/job/119968935520) | 2, passed in 3 | `check-protos` | outside the tests |
| 2026-10-22 | [39816766359](https://github.com/temporalio/sdk-python/actions/runs/39816766359/job/119968935791) | 2, passed in 3 | `build-lint-test (3.14, ubuntu-arm)` | outside the tests |
| 2026-10-22 | [39827582866](https://github.com/temporalio/sdk-python/actions/runs/39827582866/job/119994867201) | 1, passed in 2 | `build-lint-test (3.14, windows-latest)` | `test_workflow_env_time_skipping_basic` |
| 2026-10-22 | [39840312543](https://github.com/temporalio/sdk-python/actions/runs/39840312543/job/120039286072) | 1, passed in 2 | `test-latest-deps` | `test_ui_port` |
| 2026-10-23 | [39920469335](https://github.com/temporalio/sdk-python/actions/runs/39920469335/job/120532851838) | 2, passed in 3 | `alpine-package-test (cp310-musllinux_x86_64, ubuntu-latest)` | outside the tests |
| 2026-10-27 | [40008061417](https://github.com/temporalio/sdk-python/actions/runs/40008061417/job/122234383085) | 2, passed in 3 | `build-lint-test (3.10, ubuntu-arm)` | one error shared by many tests |
| 2026-10-28 | [40571679224](https://github.com/temporalio/sdk-python/actions/runs/40571679224/job/122932219336) | 2, passed in 3 | `features-tests / test` | outside the tests |
| 2026-10-28 | [40611793357](https://github.com/temporalio/sdk-python/actions/runs/40611793357/job/122938106845) | 2, passed in 3 | `build-lint-test (3.10, macos-arm)` | `test_workflow_local_activity_cancel_during_backoff[False]` |
| 2026-10-28 | [40738924878](https://github.com/temporalio/sdk-python/actions/runs/40738924878/job/122995000801) | 2, passed in 3 | `build-lint-test (3.10, ubuntu-arm)` | `test_workflow_cancel_child_started[False]` |
| 2026-10-29 | [40803372300](https://github.com/temporalio/sdk-python/actions/runs/40803372300/job/123216456828) | 1, passed in 2 | `build-lint-test (3.14, macos-arm)` | `test_workflow_sleep_task_cancellation` |
| 2026-10-29 | [40940430278](https://github.com/temporalio/sdk-python/actions/runs/40940430278/job/123682073571) | 1, passed in 2 | `build-lint-test (3.14, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-10-29 | [40940430278](https://github.com/temporalio/sdk-python/actions/runs/40940430278/job/123682073477) | 1, passed in 2 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-10-29 | [40940759080](https://github.com/temporalio/sdk-python/actions/runs/40940759080/job/123683206280) | 1, passed in 2 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-10-29 | [40949338621](https://github.com/temporalio/sdk-python/actions/runs/40949338621/job/123712981685) | 1, passed in 2 | `check-protos` | `test_custom_slot_supplier` |
| 2026-10-29 | [40949338621](https://github.com/temporalio/sdk-python/actions/runs/40949338621/job/123712981679) | 1, passed in 2 | `build-lint-test (3.10, windows-latest)` | `test_custom_slot_supplier` |
| 2026-10-29 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123712983569) | 1, passed in 2 | `fips-build` | `test_warns_when_workers_too_low` |
| 2026-10-29 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123712983801) | 1, passed in 4 | `build-lint-test (3.14, windows-latest)` | step past its time limit |
| 2026-10-29 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123712983847) | 1, passed in 3 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-10-29 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123712983943) | 1, passed in 2 | `build-lint-test (3.10, ubuntu-latest)` | `test_worker_storage_drivers_empty_without_external_storage` |
| 2026-10-29 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123726199512) | 2, passed in 3 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-10-29 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123726199679) | 2, passed in 4 | `build-lint-test (3.14, windows-latest)` | one error shared by many tests |
| 2026-10-29 | [40949339295](https://github.com/temporalio/sdk-python/actions/runs/40949339295/job/123738353870) | 3, passed in 4 | `build-lint-test (3.14, windows-latest)` | step past its time limit |
| 2026-11-02 | [41176936720](https://github.com/temporalio/sdk-python/actions/runs/41176936720/job/125403278718) | 2, passed in 3 | `build-lint-test (3.10, ubuntu-arm)` | `test_timer_commands_carry_markers` |
| 2026-11-02 | [41512911720](https://github.com/temporalio/sdk-python/actions/runs/41512911720/job/125509012690) | 1, passed in 2 | `build-lint-test (3.14, windows-latest)` | step past its time limit |
| 2026-11-03 | [41653264899](https://github.com/temporalio/sdk-python/actions/runs/41653264899/job/125976738846) | 1, passed in 2 | `test-latest-deps` | `test_workflow_env_time_skipping_basic` |
| 2026-11-03 | [41718242569](https://github.com/temporalio/sdk-python/actions/runs/41718242569/job/126203818088) | 1, passed in 2 | `build-lint-test (3.10, ubuntu-latest)` | one error shared by many tests |
| 2026-11-03 | [41731429920](https://github.com/temporalio/sdk-python/actions/runs/41731429920/job/126249487288) | 1, passed in 2 | `cloud-test` | `test_wait_condition_timer_options_not_used_by_later_timers` |
| 2026-11-05 | [42081130391](https://github.com/temporalio/sdk-python/actions/runs/42081130391/job/127434134622) | 1, passed in 2 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-11-05 | [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127434934764) | 1, passed in 2 | `check-protos` | `test_workflow_env_time_skipping_basic`, `test_workflow_env_time_skipping_manual` |
| 2026-11-05 | [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127434934973) | 1, passed in 3 | `build-lint-test (3.14, windows-latest)` | step past its time limit |
| 2026-11-05 | [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127434935116) | 1, passed in 3 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-11-05 | [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127459953130) | 2, passed in 3 | `build-lint-test (3.14, windows-latest)` | step past its time limit |
| 2026-11-05 | [42081358180](https://github.com/temporalio/sdk-python/actions/runs/42081358180/job/127459953253) | 2, passed in 3 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-11-05 | [42101160398](https://github.com/temporalio/sdk-python/actions/runs/42101160398/job/127504005782) | 1, passed in 2 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-05 | [42101160398](https://github.com/temporalio/sdk-python/actions/runs/42101160398/job/127504006173) | 1, passed in 3 | `build-lint-test (3.14, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-11-05 | [42101161020](https://github.com/temporalio/sdk-python/actions/runs/42101161020/job/127504008432) | 1, passed in 2 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-05 | [42101161020](https://github.com/temporalio/sdk-python/actions/runs/42101161020/job/127504008506) | 1, passed in 2 | `fips-build` | `test_warns_when_workers_too_low` |
| 2026-11-05 | [42101161020](https://github.com/temporalio/sdk-python/actions/runs/42101161020/job/127504008875) | 1, passed in 2 | `build-lint-test (3.10, macos-arm)` | `test_warns_when_workers_too_low` |
| 2026-11-05 | [42101161020](https://github.com/temporalio/sdk-python/actions/runs/42101161020/job/127504008913) | 1, passed in 2 | `build-lint-test (3.10, ubuntu-arm)` | `test_workflow_cancel_child_started[True]` |
| 2026-11-05 | [42101160398](https://github.com/temporalio/sdk-python/actions/runs/42101160398/job/127533670069) | 2, passed in 3 | `build-lint-test (3.14, ubuntu-latest)` | `test_warns_when_workers_too_low`, `test_worker_fatal_error_with` |
| 2026-11-05 | [42119706012](https://github.com/temporalio/sdk-python/actions/runs/42119706012/job/127568543267) | 1, passed in 2 | `cloud-test` | one error shared by many tests |
| 2026-11-05 | [42128350012](https://github.com/temporalio/sdk-python/actions/runs/42128350012/job/127598255376) | 1, passed in 2 | `fips-build` | `test_worker_deployment_ramp` |
| 2026-11-05 | [42128350012](https://github.com/temporalio/sdk-python/actions/runs/42128350012/job/127598255936) | 1, passed in 2 | `build-lint-test (3.11, macos-arm)` | `test_custom_slot_supplier` |
| 2026-11-05 | [42128350012](https://github.com/temporalio/sdk-python/actions/runs/42128350012/job/127598255553) | 1, passed in 2 | `build-lint-test (3.15, ubuntu-latest)` | step past its time limit |
| 2026-11-05 | [42130768800](https://github.com/temporalio/sdk-python/actions/runs/42130768800/job/127606492110) | 1, passed in 2 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-05 | [42130768800](https://github.com/temporalio/sdk-python/actions/runs/42130768800/job/127606492280) | 1, passed in 2 | `build-lint-test (3.10, windows-latest)` | step past its time limit |
| 2026-11-06 | [42136242308](https://github.com/temporalio/sdk-python/actions/runs/42136242308/job/127624997407) | 1, passed in 2 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-06 | [42136242308](https://github.com/temporalio/sdk-python/actions/runs/42136242308/job/127624997645) | 1, passed in 2 | `build-lint-test (3.10, macos-arm)` | `test_sync_activity_process_cancel`, `test_workflow_stack_trace` |
| 2026-11-06 | [42136990712](https://github.com/temporalio/sdk-python/actions/runs/42136990712/job/127627552851) | 1, passed in 2 | `build-lint-test (3.14, macos-arm)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42136990712](https://github.com/temporalio/sdk-python/actions/runs/42136990712/job/127627552971) | 1, passed in 3 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-06 | [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127631355455) | 1, passed in 2 | `build-lint-test (3.11, macos-arm)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127631355588) | 1, passed in 3 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-06 | [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127631355611) | 1, passed in 2 | `build-lint-test (3.11, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127631355636) | 1, passed in 2 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127631355835) | 1, passed in 2 | `build-lint-test (3.15, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127631355904) | 1, passed in 2 | `build-lint-test (3.11, ubuntu-arm)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42136990712](https://github.com/temporalio/sdk-python/actions/runs/42136990712/job/127639534567) | 2, passed in 3 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-06 | [42138126482](https://github.com/temporalio/sdk-python/actions/runs/42138126482/job/127646931148) | 2, passed in 3 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-06 | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128077119523) | 1, passed in 6 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128077119192) | 1, passed in 2 | `build-lint-test (3.11, windows-latest)` | step past its time limit |
| 2026-11-06 | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128077119207) | 1, passed in 2 | `build-lint-test (3.15, macos-arm)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128103031758) | 2, passed in 6 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/128105737774) | 1, passed in 7 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42279866572](https://github.com/temporalio/sdk-python/actions/runs/42279866572/job/128105738305) | 1, passed in 2 | `cloud-test` | `test_worker_with_worker_deployment_config` |
| 2026-11-06 | [42279866572](https://github.com/temporalio/sdk-python/actions/runs/42279866572/job/128105738461) | 1, passed in 2 | `test-latest-deps` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42279866572](https://github.com/temporalio/sdk-python/actions/runs/42279866572/job/128105738597) | 1, passed in 2 | `build-lint-test (3.11, macos-arm)` | `test_workflow_cancel_multi` |
| 2026-11-06 | [42279866572](https://github.com/temporalio/sdk-python/actions/runs/42279866572/job/128105738639) | 1, passed in 2 | `build-lint-test (3.15, macos-arm)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128131439098) | 3, passed in 6 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128177376096) | 4, passed in 6 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42302504174](https://github.com/temporalio/sdk-python/actions/runs/42302504174/job/128183561550) | 1, passed in 2 | `build-lint-test (3.11, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42302504174](https://github.com/temporalio/sdk-python/actions/runs/42302504174/job/128183561713) | 1, passed in 2 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/128185984515) | 2, passed in 7 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42305815253](https://github.com/temporalio/sdk-python/actions/runs/42305815253/job/128194717839) | 1, passed in 3 | `build-lint-test (3.15, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42305815253](https://github.com/temporalio/sdk-python/actions/runs/42305815253/job/128194717990) | 1, passed in 3 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/128203143594) | 3, passed in 7 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42305815253](https://github.com/temporalio/sdk-python/actions/runs/42305815253/job/128204568343) | 2, passed in 3 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-06 | [42305815253](https://github.com/temporalio/sdk-python/actions/runs/42305815253/job/128204568821) | 2, passed in 3 | `build-lint-test (3.15, ubuntu-latest)` | `test_worker_fatal_error_run` |
| 2026-11-06 | [42311937516](https://github.com/temporalio/sdk-python/actions/runs/42311937516/job/128215236309) | 1, passed in 2 | `check-protos` | `test_warns_when_workers_too_low` |
| 2026-11-06 | [42311937516](https://github.com/temporalio/sdk-python/actions/runs/42311937516/job/128215236337) | 1, passed in 2 | `build-lint-test (3.11, windows-latest)` | step past its time limit |
| 2026-11-07 | [42271554950](https://github.com/temporalio/sdk-python/actions/runs/42271554950/job/128238642418) | 5, passed in 6 | `build-lint-test (3.15, windows-latest)` | `test_worker_interceptor` |
| 2026-11-07 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/128238688256) | 4, passed in 7 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-09 | [42324268431](https://github.com/temporalio/sdk-python/actions/runs/42324268431/job/129286507213) | 2, passed in 3 | `build-lint-test (3.11, windows-latest)` | step past its time limit |
| 2026-11-09 | [42324268431](https://github.com/temporalio/sdk-python/actions/runs/42324268431/job/129286507588) | 2, passed in 3 | `build-lint-test (3.11, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-11-09 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/129321802365) | 5, passed in 7 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-09 | [42667785610](https://github.com/temporalio/sdk-python/actions/runs/42667785610/job/129335957445) | 1, passed in 2 | `build-lint-test (3.11, windows-latest)` | step past its time limit |
| 2026-11-09 | [42279866249](https://github.com/temporalio/sdk-python/actions/runs/42279866249/job/129336725091) | 6, passed in 7 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-09 | [42679739634](https://github.com/temporalio/sdk-python/actions/runs/42679739634/job/129370729355) | 1, passed in 2 | `fips-build` | `test_worker_deployment_ramp` |
| 2026-11-09 | [42688982209](https://github.com/temporalio/sdk-python/actions/runs/42688982209/job/129403352161) | 1, passed in 2 | `fips-build` | `test_worker_fatal_error_with` |
| 2026-11-10 | [42755878845](https://github.com/temporalio/sdk-python/actions/runs/42755878845/job/129630018815) | 1, passed in 2 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-10 | [42777052659](https://github.com/temporalio/sdk-python/actions/runs/42777052659/job/129964786307) | 2, passed in 3 | `test-latest-deps` | `test_warns_when_workers_too_low` |
| 2026-11-10 | [42777052659](https://github.com/temporalio/sdk-python/actions/runs/42777052659/job/129964787011) | 2, passed in 3 | `build-lint-test (3.15, windows-latest)` | step past its time limit |
| 2026-11-10 | [42908130654](https://github.com/temporalio/sdk-python/actions/runs/42908130654/job/130151392745) | 1, passed in 2 | `check-protos` | `test_warns_when_workers_too_low` |
| 2026-11-10 | [42908130654](https://github.com/temporalio/sdk-python/actions/runs/42908130654/job/130151393148) | 1, passed in 2 | `build-lint-test (3.15, macos-arm)` | `test_warns_when_workers_too_low` |
| 2026-11-10 | [42918643927](https://github.com/temporalio/sdk-python/actions/runs/42918643927/job/130187509299) | 1, passed in 2 | `build-lint-test (3.11, ubuntu-latest)` | `test_warns_when_workers_too_low` |
| 2026-11-10 | [42918643927](https://github.com/temporalio/sdk-python/actions/runs/42918643927/job/130187509373) | 1, passed in 2 | `build-lint-test (3.11, windows-latest)` | step past its time limit |
| 2026-11-10 | [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130189102903) | 1, passed in 2 | `check-protos` | `test_worker_storage_drivers_populated_from_client` |
| 2026-11-10 | [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130189102990) | 1, passed in 4 | `build-lint-test (3.11, windows-latest)` | step past its time limit |
| 2026-11-10 | [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130189103582) | 1, passed in 2 | `features-tests / test` | outside the tests |
| 2026-11-10 | [42919105015](https://github.com/temporalio/sdk-python/actions/runs/42919105015/job/130201893250) | 2, passed in 4 | `build-lint-test (3.11, windows-latest)` | step past its time limit |

Query: `python -m cidiag query flaky.instances`.

Cedarwood Studio, Jack Senechal, principal. hello@cedarwood.studio
