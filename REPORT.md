# CI Diagnostic: wagtail/wagtail

> **Sample report.** Produced by Cedarwood Studio from public data on wagtail/wagtail as of 2026-11-12. Nobody at the project asked for it. Cedarwood Studio isn't affiliated with the project and the project hasn't endorsed this report. Nothing was sent to the project: no issue, pull request or comment.

This is the report a CI Diagnostic client receives, run here on a public repository so anyone can check it. Every number below was computed from the repository's own CI history, and the command that produces each one is printed next to it. The API responses behind them are stored with the report, with personal fields removed and logs trimmed, so the numbers can be recomputed without network access.

A diagnostic measures how a pipeline behaves. It isn't an audit or a security assessment, and none of this judges the project or the people who maintain it. Wagtail's pipeline is carefully maintained, and most of what follows confirms that.

## The short version

- **Time to a verdict on `main`.** 23:27 at the median and 27:31 at the 90th percentile, using 144 runner minutes a run, over the 73 of the last 100 runs that reached a verdict.
- **Failures and re-runs, 30 days.** 1 of 36 pushes to `main` with a verdict failed (2.8%), and 29.1% of pull-request runs did. No run was re-run after a failure.
- **Tested fix.** A three-line change took the median run from 25:07 to 15:38 (37.7% less) and from 146 to 105.5 runner minutes, over 3 runs before and 4 after on our fork.
- **The fix over 30 days.** At the last 30 days' count of 174 runs, it would save about 27.5 hours of waiting for a verdict and 7,047 runner minutes.
- **Waiting for a runner.** In 17 of 71 successful runs a job waited more than a minute to start. Those runs took 26:05 at the median, against 23:12 for the rest.
- **Actions and caches.** All 40 action references are pinned to commit SHAs, and the dependency cache was hit in 90.4% of job starts.

The summary below gives each finding in full, and the sections after it show the data.

## Summary

**What was measured.** The `Wagtail CI` workflow (`.github/workflows/test.yml`) on GitHub Actions: its last 100 completed runs on `main` (2026-09-07 to 2026-11-10), and all 496 runs of the repository's four workflow files over the 30 days from 2026-10-12 to 2026-11-10. Workflow files were read at commit `030168a`.

**What we found.**

1. **A verdict on `main` takes 23:27 at the median** (27:31 at the 90th percentile) and uses 144 runner minutes, over the 73 of the last 100 runs that reached a verdict. Pull requests wait about the same: 23:54 at the median over 83 passing runs. 91.9% of step time is the test step itself. In all 71 successful runs on `main`, the last test job to finish was a `test-mysql` job.
2. **Tested fix: running three of the four `test-mysql` jobs with `--parallel` cut the median run from 25:07 to 15:38** (37.7% less) and from 146 to 105.5 runner minutes, over 3 runs of the unchanged pipeline and 4 of the changed one on our fork. Every job ran the same number of tests before and after. The change is three lines.
3. **The slowest runs are the ones that waited for a runner.** In 17 of 71 successful runs on `main` at least one job waited more than a minute to start. Those runs took 26:05 at the median, against 23:12 for the rest. The slowest took 61:41, of which 42:02 was a job waiting to start.
4. **27 of the last 100 runs on `main` were cancelled before giving a verdict.** The workflow cancels a run when a newer push arrives on the same branch. The cancelled runs used 2,014 runner minutes.
5. **No run was re-run after a failure in the 30-day window.** On `main`, 1 of 36 pushes with a verdict failed (2.8%). Across pushes to all branches the rate was 8.8%, and on pull requests 29.1%. Of the 16 failed pull-request runs whose jobs can be inspected, 2 failed in a single job and are named in section 3 as candidates. The other 18 failed runs list no jobs, so this window neither shows a flaky check nor rules one out.
6. **All 40 action references are pinned to commit SHAs, none is archived or on a deprecated runtime, and the dependency cache was hit in 90.4% of job starts.** One service image uses a tag that moves (`postgres:latest`).
7. **Coverage measurement accounts for a quarter to a third of job time on Python 3.12 and 3.13 in the jobs we probed, and almost none on 3.14.** The two jobs that moved to Python 3.14 in October got 31.8% and 37.9% faster. One probe run on our fork with coverage switched off made the three older-Python `test-mysql` jobs 25.5% to 36.1% faster and the 3.14 job 1.5% faster.

**What to change, in order of expected saving.** See section 7 for the arithmetic.

| # | Change | Expected saving | Size |
| --- | --- | --- | --- |
| 1 | Add `--parallel` to three `test-mysql` matrix entries | 9.5 minutes of waiting and 40.5 runner minutes per run, measured | Three lines |
| 2 | Measure coverage on fewer of the jobs that run Python 3.13 or older | About 21.4 minutes of running time per run, estimated from one probe run | A few lines, plus a decision on which jobs must report coverage |
| 3 | Find the cause of runner queue waits | Unknown until the cause is known; the waits are measured above | Needs the organization's Actions settings |
| 4 | Pin `postgres:latest` to a version | No time saved; removes one source of unexplained change | One line |

Decisions that cost minutes instead of saving them, and what we couldn't measure, are in sections 7 and 8.

## 1. What was measured

| Source | Window | Count |
| --- | --- | --- |
| Completed push runs of `Wagtail CI` on `main` | 2026-09-07 to 2026-11-10 | 100 runs: 71 passed, 2 failed, 27 cancelled |
| Of those, successful runs on the current job matrix | 2026-10-08 to 2026-11-10 | 38 runs of 14 jobs |
| All runs, all workflows, all branches | 2026-10-12 to 2026-11-10 (30 days) | 607 runs: 496 from the repository's workflow files, 111 from workflows GitHub generates (Dependabot, Copilot, code scanning) |
| Job logs, for cache hits | 2026-10-21 to 2026-11-10 | 260 job logs from the 20 most recent runs on `main` that reached a verdict |
| Workflow files | Commit `030168a` | 4 files, 40 `uses:` references |
| Cache entries | Snapshot on 2026-11-12 | 31 entries |
| Fork runs | 2026-11-12 | 3 before the tested fix, 4 after, and 1 probe run with coverage off |

The last 100 runs on `main` reach back nine weeks, and the job matrix changed on 2026-10-08, part way through. Run-level numbers use all 100. Job-level numbers use the 38 successful runs since the change, so they describe the pipeline as it's now.

**Definitions.** A run's *wall-clock time* is the latest job finish minus the earliest job creation, over the run's final attempt: the time a person waits for a verdict. *Runner minutes* round each job's running time up to a whole minute and add them, which is how GitHub bills a private repository. Wagtail is public and pays nothing for these minutes; they are shown because a private repository would. *Queue time* is the gap between a job being created and starting.

**To reproduce.** Clone the report's repository, then:

```
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m cidiag analyze     # recompute results/metrics.json from data/raw
.venv/bin/python -m cidiag verify      # check this report against a fresh computation
.venv/bin/python -m cidiag query main.summary   # print any one measure
```

`python -m cidiag fetch` pulls the same endpoints again through `gh api`. Each section below names the `query` that prints its numbers and the API endpoint the data came from.

## 2. Run time on `main`, and where it goes

Over the 73 of the last 100 runs that reached a verdict:

| Measure | Value |
| --- | --- |
| Median wall-clock time | 23:27 (23.4 min) |
| 90th percentile | 27:31 |
| Slowest | 61:41 |
| Median runner minutes per run | 144 |
| Runner minutes, all 73 runs | 10,362 |

Query: `python -m cidiag query main.summary`. Source: `GET /repos/wagtail/wagtail/actions/workflows/test.yml/runs?branch=main&event=push&status=completed` and `GET /repos/wagtail/wagtail/actions/runs/{id}/jobs?filter=all`.

**By step.** Share of all step time across the 71 successful runs:

| Step | Minutes per run, all jobs | Share of step time |
| --- | --- | --- |
| Test | 125.1 | 91.9% |
| Initialize containers | 4.3 | 3.2% |
| Install dependencies | 2.3 | 1.7% |
| Install uv | 1.2 | 0.9% |
| Run ankane/setup-opensearch | 0.6 | 0.4% |
| Run actions/checkout | 0.5 | 0.4% |
| Install libpq-dev | 0.4 | 0.3% |
| Set up job | 0.3 | 0.2% |

Query: `python -m cidiag query main.steps`. Checkout, Python setup, dependency install and cache restore together are under 4% of the time, so the setup steps aren't where the wait comes from.

**By job.** The 38 successful runs on the current matrix. "Finished last" counts the runs in which that job was the last test job to complete, which makes it the job everyone waited for.

| Job | Runs | Median | 90th pct | Finished last |
| --- | --- | --- | --- | --- |
| test-mysql (3.12, Django>=5.2,<5.3, false) | 38 | 22:04 | 23:28 | 24 |
| test-mysql (3.13, Django>=6.0,<6.1, false, mysql:8.4, emailuser) | 38 | 21:46 | 22:59 | 13 |
| test-mysql (3.12, Django>=6.0,<6.1, false, mariadb:10.6) | 38 | 18:54 | 19:46 | 1 |
| test-postgres (3.14, django@stable/6.1.x, psycopg>=3... | 38 | 14:34 | 15:23 | 0 |
| test-mysql (3.14, Django>=6.1,<6.2, false, mariadb:11.4, yes) | 38 | 13:57 | 14:30 | 0 |
| test-postgres (3.11, Django>=5.2,<5.3, psycopg2>=2.8.4, false, --parallel, yes) | 38 | 8:10 | 8:49 | 0 |
| test-postgres (3.15, Django>=6.1,<6.2, psycopg>=3.1.8, postgres:15, notz, false, --parallel) | 38 | 6:44 | 7:18 | 0 |
| test-postgres (3.15, django@main, psycopg>=3.1.8, tr... | 37 | 6:37 | 8:06 | 0 |
| test-sqlite (3.13, Django>=5.2,<5.3, 1, --parallel) | 38 | 5:06 | 5:25 | 0 |
| test-postgres-elasticsearch7 (3.11, Django>=5.2,<5.3, false) | 38 | 4:14 | 4:38 | 0 |
| test-sqlite-opensearch2 (3.13, Django>=5.2,<5.3, false) | 38 | 3:42 | 3:58 | 0 |
| test-sqlite (3.14, Django>=6.0,<6.1, yes, --parallel) | 38 | 3:10 | 3:22 | 0 |
| test-sqlite-elasticsearch8 (3.15, Django>=6.1,<6.2, emailuser) | 38 | 3:00 | 4:22 | 0 |
| coverage | 38 | 0:40 | 0:44 | 0 |

Query: `python -m cidiag query main.current_matrix.jobs`.

All jobs run on GitHub-hosted `ubuntu-26.04-arm` runners. The four `test-mysql` jobs run the suite on one process. The `test-postgres` and `test-sqlite` jobs that pass `--parallel` finish in about eight minutes or less. Across all 71 successful runs in the window, the last test job to finish was a `test-mysql` job in 71. A change that doesn't touch those jobs won't shorten the wait. Section 6 tests the change.

**Waiting for a runner.** The median job starts 8 seconds after it's created. The tail is long:

| Measure | Value |
| --- | --- |
| Successful runs where a job waited over 60 seconds | 17 of 71 (23.9%) |
| 90th percentile of the longest wait in a run | 7:12 |
| Longest wait | 42:02, in [run 37917837634](https://github.com/wagtail/wagtail/actions/runs/37917837634) |

Query: `python -m cidiag query main.queue`. The 17 runs with a wait over a minute took 26:05 at the median; the other runs took 23:12. The slowest run in the window took 61:41, and 42:02 of that was a job waiting to start. Each run starts 13 test jobs at once, so two runs close together ask for more runners than one. Public data doesn't show whether the waits come from the organization's limit on concurrent jobs or from GitHub's supply of ARM runners (section 8).

**Python 3.14.** The matrix change on 2026-10-08 moved several jobs to a newer Python and changed nothing else about them. That gives a direct comparison:

| Job (Python version removed) | Earlier Python | Median | Later Python | Median | Change |
| --- | --- | --- | --- | --- | --- |
| test-sqlite (Django>=6.0,<6.1, yes, --parallel) | 3.13 (33 runs) | 5:06 | 3.14 (38 runs) | 3:10 | -38% |
| test-mysql (Django>=6.1,<6.2, false, mariadb:11.4, yes) | 3.12 (33 runs) | 20:28 | 3.14 (38 runs) | 13:57 | -32% |
| test-mysql (Django>=5.2,<5.3, false) | 3.11 (33 runs) | 22:22 | 3.12 (38 runs) | 22:04 | -1% |
| test-postgres (django@main, psycopg>=3.1.8, tr... | 3.14 (33 runs) | 6:41 | 3.15 (37 runs) | 6:37 | -1% |
| test-postgres (Django>=6.1,<6.2, psycopg>=3.1.8, postgres:15, notz, false, --parallel) | 3.14 (33 runs) | 6:42 | 3.15 (38 runs) | 6:44 | +0% |
| test-sqlite-elasticsearch8 (Django>=6.1,<6.2, emailuser) | 3.14 (33 runs) | 2:56 | 3.15 (38 runs) | 3:00 | +2% |
| test-sqlite-opensearch2 (Django>=5.2,<5.3, false) | 3.11 (33 runs) | 3:37 | 3.13 (38 runs) | 3:42 | +2% |
| test-mysql (Django>=6.0,<6.1, false, mysql:8.4, emailuser) | 3.12 (33 runs) | 21:05 | 3.13 (38 runs) | 21:46 | +3% |

Query: `python -m cidiag query main.python_pairs`. The two jobs that moved to 3.14 got 31.8% and 37.9% faster. Jobs that moved between other versions didn't change. The job definitions were otherwise the same, though the two periods are different weeks of commits.

One candidate cause is coverage measurement. The suite runs under `coverage` with branch coverage on, and the coverage.py documentation says its `sysmon` measurement core is the default from Python 3.14 and doesn't support branch coverage on 3.12 and 3.13. We tested it with one run on our fork ([run 43152857357](https://github.com/cedarwood-studio/wagtail/actions/runs/43152857357), branch `ci-diagnostic/coverage-off-probe`), in which the four `test-mysql` jobs ran the tests without `coverage`. Each is compared with the median of the same job in the 3 unchanged runs from section 6:

| Job | With coverage (median of baseline runs) | Without coverage (one run) | Change | Tests run |
| --- | --- | --- | --- | --- |
| test-mysql (3.12, Django>=6.0,<6.1, false, mariadb:10.6) | 19:31 | 12:28 | -36% | 7981 |
| test-mysql (3.12, Django>=5.2,<5.3, false) | 24:27 | 16:29 | -33% | 7981 |
| test-mysql (3.13, Django>=6.0,<6.1, false, mysql:8.4, emailuser) | 21:18 | 15:52 | -26% | 7981 |
| test-mysql (3.14, Django>=6.1,<6.2, false, mariadb:11.4, yes) | 14:41 | 14:28 | -1% | 7981 |

Query: `python -m cidiag query fix.probe`. With coverage off, the three jobs on Python 3.12 and 3.13 ran 25.5% to 36.1% faster, and the job on 3.14 ran 1.5% faster. That fits the explanation: on older Pythons, measuring coverage is a large share of the test time, and on 3.14 it's close to free. This is one run, so the percentages are rough, but the gap between the two groups is far larger than the run-to-run spread in section 6.

## 3. Failures and re-runs

All runs created from 2026-10-12 to 2026-11-10, from the repository's own workflow files, on every branch:

| Workflow | Trigger | Runs | Passed | Failed | Cancelled | Held for approval | Failure rate | Re-run after failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| zizmor | pull_request | 180 | 127 | 20 | 2 | 31 | 13.6% | 0 |
| Wagtail CI | pull_request | 169 | 83 | 34 | 22 | 30 | 29.1% | 0 |
| Wagtail CI | push | 78 | 52 | 5 | 21 | 0 | 8.8% | 0 |
| zizmor | push | 56 | 56 | 0 | 0 | 0 | 0.0% | 0 |
| Test against latest dependencies | schedule | 9 | 7 | 2 | 0 | 0 | 22.2% | 0 |
| CodeQL | schedule | 4 | 4 | 0 | 0 | 0 | 0.0% | 0 |

Query: `python -m cidiag query window.rows`. Source: `GET /repos/wagtail/wagtail/actions/runs?created=2026-10-12..2026-11-10`.

*Failure rate* is failed runs over passed plus failed. Cancelled runs and runs held for approval never reached a verdict and are left out. The push row covers 14 branches. On `main` alone there were 54 push runs in the window: 35 passed, 1 failed and 18 were cancelled, a failure rate of 2.8%. (Section 1 counts 2 failures on `main` because its window is the last 100 runs, which is nine weeks.)

**Time to a verdict on pull requests.** The 83 pull-request runs that passed took 23:54 at the median and 33:54 at the 90th percentile, close to the figures for `main` in section 2. Query: `python -m cidiag query window.ci_pr_duration`.

**Re-runs.** 16 runs in the window have an attempt number above 1. In every one, the first attempt was held for a maintainer's approval (GitHub can require approval before workflows run on a pull request from a fork) and the second attempt was the first real execution. None was a retry of a failed attempt. Counting by attempt number alone would report 8 re-runs in the 169 pull-request runs of `Wagtail CI`. Checking each first attempt's conclusion brings that to 0.

No job failed and then passed on the same commit. Query: `python -m cidiag query window.flaky_candidates` (an empty list). Source for earlier attempts: `GET /repos/wagtail/wagtail/actions/runs/{id}/attempts/{n}`.

**What failed.** Failed jobs of `Wagtail CI` in the window, by job and step:

| Job | Failing step | Failures | Of which allowed to fail |
| --- | --- | --- | --- |
| test-postgres | Test | 33 | 6 |
| test-mysql | Test | 22 | 0 |
| test-sqlite | Test | 21 | 0 |
| test-postgres | Test project template | 20 | 17 |
| test-postgres-elasticsearch7 | Test | 1 | 0 |
| test-sqlite-opensearch2 | Test | 1 | 0 |
| test-sqlite-elasticsearch8 | Test | 1 | 0 |

Query: `python -m cidiag query window.failing_jobs`. "Allowed to fail" counts failures in runs that still passed: the two `test-postgres` entries that test against Django's development branches are marked `continue-on-error`, and they fail often, as a job that tracks an unreleased dependency should.

**Shape of the failed runs.** A commit that breaks a test usually breaks it on every database, so several jobs fail together. A single failing job, while the same tests pass on the other databases, is where a flaky test would show.

- Pushes: 5 failed runs, each with several failed jobs.
- Pull requests: 34 failed runs. 14 had several failed jobs. 2 had exactly one. 18 list no jobs at all in the API (section 8).

The two single-job failures, with the failing tests read from the job logs:

- [Run 39617570818](https://github.com/wagtail/wagtail/actions/runs/39617570818/job/119282447190), a `test-postgres` job: 1 test, `wagtail.api.v3.tests.test_streamfield_schemas.TestBlockSchema.test_annotated_api_representation`.
- [Run 38893935232](https://github.com/wagtail/wagtail/actions/runs/38893935232/job/116949795623), a `test-mysql` job: 6 tests, all in the API v3 workflow tests.

Query: `python -m cidiag query window.failed_shapes`. Neither run was re-run, so the history doesn't tell us whether these are flaky tests, database-specific failures, or the pull request's own changes. That's two candidates among the 16 failed pull-request runs that can be inspected. With no re-runs in the window and 18 failed runs that can't be inspected, this history doesn't confirm a flaky check and can't rule one out. A team that re-runs failed jobs leaves a clearer trail: a job that fails and then passes on the same commit is counted directly, and the `flaky_candidates` query lists each one with its failing step.

## 4. Third-party actions, images and orbs

40 `uses:` references across 4 workflow files, to 11 distinct actions:

| Action | Ref | Version comment | Uses | Pinned to | Runtime | Latest release | Archived |
| --- | --- | --- | --- | --- | --- | --- | --- |
| actions/checkout | `3d3c42e5aac5` | v7.0.1 | 10 | commit SHA | node24 | v7.0.1 | no |
| actions/download-artifact | `9000827ccba6` | v8.0.2 | 1 | commit SHA | node24 | v8.0.2 | no |
| actions/setup-python | `6d4fd22b2046` | v7.1.0 | 8 | commit SHA | node24 | v7.1.0 | no |
| actions/upload-artifact | `cf430e030ddb` | v7.0.2 | 7 | commit SHA | node24 | v7.0.2 | no |
| ankane/setup-opensearch | `b73d8d2d65ea` | v1 | 1 | commit SHA | node24 |  | no |
| astral-sh/setup-uv | `07a047e608db` | v10.3.2 | 8 | commit SHA | node24 | v10.3.3 | no |
| codecov/codecov-action | `303a32d7a59b` | v7.1.1 | 1 | commit SHA | composite | v7.1.1 | no |
| github/codeql-action/analyze | `9b3254085494` | v4.39.1 | 1 | commit SHA | node24 | codeql-bundle-v2.27.4 | no |
| github/codeql-action/init | `9b3254085494` | v4.39.1 | 1 | commit SHA | node24 | codeql-bundle-v2.27.4 | no |
| slackapi/slack-github-action | `dcb1066f776d` | v4.0.0 | 1 | commit SHA | node24 | v4.0.0 | no |
| zizmorcore/zizmor-action | `53290badfa36` | v0.8.0 | 1 | commit SHA | composite | v0.8.1 | no |

Query: `python -m cidiag query static.actions`. Source: the workflow files at `030168a`, plus `GET /repos/{owner}/{action}` and each action's `action.yml` at the pinned commit.

- **Pinned:** 40 of 40 references are full commit SHAs. 0 are tags or branches.
- **Deprecated:** GitHub publishes no list of deprecated actions, so we check two things that can be read from the API. The 11 actions live in 10 repositories, and 0 of those are archived. 0 declare a Node runtime GitHub has deprecated (node12, node16 or node20).
- **Behind:** 0 are a major version behind their latest release.

Nothing to change here.

**Container images.** Service containers are third-party code too, so the same check applies:

| Image | File | Line | Fixed by |
| --- | --- | --- | --- |
| `docker.elastic.co/elasticsearch/elasticsearch:8.11.2` | test.yml | 281 | version tag |
| `postgres:latest` | test.yml | 339 | moves with every release |
| `docker.elastic.co/elasticsearch/elasticsearch:7.17.13` | test.yml | 346 | version tag |

Query: `python -m cidiag query static.images`. `postgres:latest` on line 339 of `test.yml` follows each new PostgreSQL release as it's published. If that's meant as an early warning it's doing its job. If not, a version tag makes a red run easier to explain. Images set through the matrix (`postgres:15`, `mysql:8.4`, `mariadb:11.4` and so on) carry version tags.

## 5. Dependency caches

Every job that installs dependencies has a cache: 8 jobs install with `uv`, and all 8 run `astral-sh/setup-uv`, which caches by default on GitHub-hosted runners. 0 install without a cache. Query: `python -m cidiag query static.jobs`.

Whether the cache is hit can only be read from job logs. In the 260 test-job logs of the 20 most recent runs on `main` that reached a verdict:

| Measure | Value |
| --- | --- |
| Cache hit | 235 of 260 (90.4%) |
| Cache miss | 25 |
| "Install dependencies" step, median | 6 seconds |
| "Install dependencies" step, 90th percentile | 21 seconds |

Query: `python -m cidiag query caches`. Source: `GET /repos/wagtail/wagtail/actions/jobs/{id}/logs`, filtered to the cache and test-count lines.

The cache key includes a hash of the lock file, so a miss is expected on the first run after a dependency update. With a 6-second median install there's no time to recover here.

The cache list on 2026-11-12 held 31 entries totaling 5,927 MB. 13 had never been read since they were written, 11 of them on pull-request refs, where a cache written by one pull request can't be read by another. That's how GitHub scopes caches and isn't a fault. It's worth knowing because a repository's cache storage is capped (10 GB by default), and entries nobody reads count toward the cap.

Nothing to change here.

## 6. The top change, tested on a fork

**The change.** Add `parallel: '--parallel'` to three of the four `test-mysql` matrix entries (MySQL 8.0, MariaDB 10.6 and MySQL 8.4). The MariaDB 11.4 entry stays serial.

The workflow file explains why some jobs are serial: an error raised inside a parallel test process sometimes can't be passed back, and the traceback is lost, so the project keeps one serial run for each database. Today all four `test-mysql` jobs are serial. This change keeps one. We kept the MariaDB 11.4 job because it runs on Python 3.14 and is the fastest of the four. Whether one serial job is enough for MySQL and MariaDB together, or whether each needs its own, is the project's call. With two kept serial the saving in runner minutes would be smaller, and the saving in waiting would depend on which two.

**How it was tested.** We forked the repository to [cedarwood-studio/wagtail](https://github.com/cedarwood-studio/wagtail) and pushed two branches from commit `030168a`:

- `ci-diagnostic/baseline`: the pipeline as it is.
- `ci-diagnostic/mysql-parallel`: the same, plus the three lines.

GitHub didn't run the workflows our fork inherited, and they're enabled from the fork's web interface, which we didn't use. Both branches carry a copy of `test.yml` under a new name, `ci-diagnostic.yml`. The copy differs from the original in its name, its triggers, and a condition that stops our fork from uploading coverage to Codecov. The jobs are identical. Runs were started one at a time, each after the previous one finished, so no run competed with another for runners. The two branches were interleaved over the same few hours; the table below gives each run's start time. Nothing was pushed to wagtail/wagtail and no pull request was opened there.

**Result.** Runs before: 3. Runs after: 4.

| Measure | Before | After | Difference |
| --- | --- | --- | --- |
| Median wall-clock time | 25:07 | 15:38 | 9.5 minutes less (37.7%) |
| Fastest and slowest run | 23:55 to 25:34 | 15:26 to 15:52 | |
| Median runner minutes per run | 146 | 105.5 | 40.5 fewer (27.7%) |

Every run:

| Arm | Run | Started | Result | Wall clock | Running time (min) | Runner minutes | Longest queue (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| before | [43140086233](https://github.com/cedarwood-studio/wagtail/actions/runs/43140086233) | 02:15 UTC | success | 25:34 | 143.4 | 151 | 6 |
| before | [43144886309](https://github.com/cedarwood-studio/wagtail/actions/runs/43144886309) | 02:57 UTC | success | 25:07 | 138.5 | 146 | 4 |
| before | [43149624894](https://github.com/cedarwood-studio/wagtail/actions/runs/43149624894) | 03:39 UTC | success | 23:55 | 135.8 | 144 | 5 |
| after | [43136329875](https://github.com/cedarwood-studio/wagtail/actions/runs/43136329875) | 01:42 UTC | success | 15:41 | 105.5 | 112 | 4 |
| after | [43138170661](https://github.com/cedarwood-studio/wagtail/actions/runs/43138170661) | 01:58 UTC | success | 15:52 | 97.2 | 106 | 5 |
| after | [43143129291](https://github.com/cedarwood-studio/wagtail/actions/runs/43143129291) | 02:41 UTC | success | 15:26 | 95.9 | 104 | 7 |
| after | [43147850222](https://github.com/cedarwood-studio/wagtail/actions/runs/43147850222) | 03:23 UTC | success | 15:36 | 98.3 | 105 | 5 |

By job, with the number of tests each job reported running (from "Ran N tests" in its log). If the "before" and "after" counts match for a job, the change didn't drop any tests:

| Job | Before (median) | After (median) | Tests run before | Tests run after |
| --- | --- | --- | --- | --- |
| test-mysql (3.12, Django>=5.2,<5.3, false) **(made parallel)** | 24:27 | 9:33 | 7981 | 7981 |
| test-mysql (3.13, Django>=6.0,<6.1, false, mysql:8.4, emailuser) **(made parallel)** | 21:18 | 9:08 | 7981 | 7981 |
| test-mysql (3.12, Django>=6.0,<6.1, false, mariadb:10.6) **(made parallel)** | 19:31 | 8:42 | 7981 | 7981 |
| test-postgres (3.14, django@stable/6.1.x, psycopg>=3... | 15:24 | 14:48 | 7981 | 7981 |
| test-mysql (3.14, Django>=6.1,<6.2, false, mariadb:11.4, yes) | 14:41 | 14:34 | 7981 | 7981 |
| test-postgres (3.11, Django>=5.2,<5.3, psycopg2>=2.8.4, false, --parallel, yes) | 8:33 | 8:13 | 7981 | 7981 |
| test-postgres (3.15, Django>=6.1,<6.2, psycopg>=3.1.8, postgres:15, notz, false, --parallel) | 6:57 | 6:46 | 7981 | 7981 |
| test-postgres (3.15, django@main, psycopg>=3.1.8, tr... | 6:43 | 7:18 | 7981 | 7981 |
| test-sqlite (3.13, Django>=5.2,<5.3, 1, --parallel) | 5:16 | 5:11 | 7981 | 7981 |
| test-postgres-elasticsearch7 (3.11, Django>=5.2,<5.3, false) | 4:11 | 4:21 | 1082 | 1082 |
| test-sqlite-opensearch2 (3.13, Django>=5.2,<5.3, false) | 3:34 | 3:40 | 1082 | 1082 |
| test-sqlite (3.14, Django>=6.0,<6.1, yes, --parallel) | 3:08 | 3:08 | 7981 | 7981 |
| test-sqlite-elasticsearch8 (3.15, Django>=6.1,<6.2, emailuser) | 3:02 | 3:01 | 1082 | 1082 |
| coverage | 0:30 | 0:34 |  |  |

Query: `python -m cidiag query fix`. **Every job reported the same number of tests before and after.**

**What this does and doesn't show.** The range of "before" runs and the range of "after" runs don't overlap. This is 3 runs against 4, all on one commit, on GitHub-hosted runners assigned to our fork. For comparison, the 38 upstream runs on the same matrix have a median of 23:49, against 25:07 for the unchanged pipeline on our fork. The saving a team sees on its own runners may differ by a similar margin. After the change, the longest job is `test-postgres (3.14, django@stable/6.1.x, psycopg>=3...` at a median of 14:48. That job is the next limit on the wait.

We haven't shown that parallel MySQL runs stay reliable over hundreds of runs. All 4 passed. A team adopting this should watch the first weeks of runs for failures that appear only in the parallel jobs.

## 7. Changes ranked by expected saving

`Wagtail CI` produced 174 runs with a verdict in the 30-day window (pushes and pull requests). Savings per 30 days multiply a per-run saving by that count.

**1. Run three `test-mysql` jobs with `--parallel`.** Measured in section 6.

- Waiting: 9.5 minutes per run × 174 runs = 27.5 hours of waiting for a verdict per 30 days.
- Runner time: 40.5 minutes per run × 174 runs = 7,047 runner minutes per 30 days.
- Assumptions: every run saves what the fork's median run saved, and the run count stays at the last 30 days' level. Both overstate a little: 39 of the 174 runs failed, and a failed run can end early. The measurement is 3 runs against 4 on one commit.
- Size: three lines in one file. The branch on our fork shows the edit, made in the diagnostic copy of the workflow file.

**2. Measure coverage on fewer of the older-Python jobs.** Estimated from one probe run.

- 7 of the 14 jobs run on Python 3.13 or older. Their median times add up to 83.9 minutes of running time per run.
- The probe measured a drop of 25.5% to 36.1% on 3 of them with coverage off. At the smallest of those: 83.9 × 25.5% = 21.4 minutes per run if none of the 7 measured coverage.
- The real saving is smaller than that figure. The probe covered serial `test-mysql` jobs only, the other four older-Python jobs may differ, and the project will want coverage from some of these jobs, since code paths differ by database. It also overlaps change 1: once three of these jobs run in parallel, there's less time left in them to save.
- The trade is the project's to make: which jobs must report coverage. The probed Python 3.14 job measures it at almost no cost.
- Size: a matrix flag and a condition on two steps. The probe branch shows the edit for one job group.

**3. Find the cause of runner queue waits.** Measured, cause unknown.

- 17 of 71 successful runs had a job wait over a minute, and the 90th-percentile wait was 7:12.
- If the organization's concurrent-job limit is the cause, change 1 helps a little, since each run would hold its runners for fewer minutes. If GitHub's ARM runner supply is the cause, nothing in the workflow file changes it.
- Size: someone with access to the organization's Actions settings can answer this in a few minutes.

**4. Pin `postgres:latest`.** Saves no time. One line. Removes one way a run can turn red with no change in the repository.

**Decisions that cost minutes.** These are choices for the project, listed so the cost is known.

- *Cancelled runs on `main`.* The workflow cancels a run when a newer push arrives on the same branch. On pull requests that saves runner time and loses nothing. On `main` it means 27 of the last 100 pushes (27.0%) have no verdict of their own. Those runs used 2,014 runner minutes before they were cancelled, about 75 each. A successful run on the current matrix uses 141 runner minutes at the median, so letting them finish would have cost about 27 × 141 − 2,014 = 1,793 more runner minutes over the nine weeks. The change is one line: cancel in-progress runs only for pull requests. Across pushes and pull requests together, 43 runs were cancelled in the 30-day window after using 2,936 runner minutes.

## 8. What couldn't be measured

- **Why 18 failed pull-request runs list no jobs.** The API returns an empty job list for 18 of the 34 failed pull-request runs of `Wagtail CI`. We can count them and can't say what failed in them.
- **Why jobs queue.** The API shows when a job was created and when it started. It doesn't show the organization's plan, its concurrent-job limit, or runner availability.
- **Individual flaky tests.** Run history names failing jobs and steps. Test names come from logs, which GitHub keeps for a limited time (90 days by default), and only for jobs that ran. A test that fails one time in a few hundred would need a longer window than 30 days, or the project's own test reports.
- **Cache hits before the log window.** The cache hit rate comes from logs of the 20 most recent runs. The cache list is a snapshot of what exists today and holds no history.
- **Deprecated actions, in general.** There's no registry of deprecated actions. We check for archived repositories and deprecated runtimes, and report what those two checks cover.
- **Cost in dollars.** The repository is public, so GitHub bills nothing. We report runner minutes as a private repository would be billed for them. A client's report gives runner minutes and waiting time the same way. For a client who shares their per-minute runner rate, the report shows the multiplication.
- **How much coverage costs outside `test-mysql`.** The probe switched coverage off in four jobs for one run. The other jobs weren't probed.
- **Whether the tested fix holds over time.** 4 passing runs show the change works and what it saves. They don't show how it behaves over months.

## 9. The CircleCI side

Wagtail also runs a `test` workflow on CircleCI (lint, a second backend test run, the frontend build and browser tests). CircleCI publishes summary figures for public projects, and the diagnostic covers CircleCI, so they're included. These are CircleCI's own workflow and job summaries for `main` from 2026-08-13 to 2026-11-10. We didn't recompute them from individual runs, and they have no runner minutes and no re-run rate.

| Measure | Value |
| --- | --- |
| Runs | 164 |
| Failed | 8 (95.1% passed) |
| Median duration | 8:19 |
| 95th percentile | 9:28 |

| Job | Runs | Failed | Median | 95th pct |
| --- | --- | --- | --- | --- |
| backend | 163 | 7 | 8:18 | 9:27 |
| frontend | 163 | 0 | 3:42 | 4:22 |
| ui_tests | 164 | 2 | 2:49 | 3:24 |

Query: `python -m cidiag query circleci`. Source: `GET https://circleci.com/api/v2/insights/gh/wagtail/wagtail/workflows?branch=main` and `.../workflows/test/jobs`.

The one orb, `codecov/codecov@6.1.0`, is pinned to an exact version. All three jobs restore a dependency cache keyed on a lock file. At a median of 8:19 this workflow finishes well before the GitHub Actions one, so it doesn't set the wait. Nothing to change here.

## 10. How this report was made

- **Tool.** The `cidiag` package in this repository, written in Python with unit tests. It calls the GitHub REST API through `gh api`, stores every response under `data/raw/` (with the names, logins and email addresses of the people behind each run removed, release notes dropped, action manifests cut to the line that names the runtime, and logs trimmed to the lines the analysis reads), and computes everything from those files.
- **Every number is generated.** This file is produced from `report/REPORT.md.tmpl` and `results/metrics.json`. `python -m cidiag verify` recomputes the metrics from the raw data and fails if this file differs by a character. The repository's CI runs that check on every push.
- **Percentiles** are nearest-rank, so each one is a value that occurred. A median over an even number of runs is the average of the two middle values.
- **Scope.** This report covers how the pipeline performs: time, failures, pins, caches. It isn't a review of the project's code, tests or security, and it shouldn't be read as one.

Cedarwood Studio, Jack Senechal, principal. hello@cedarwood.studio
