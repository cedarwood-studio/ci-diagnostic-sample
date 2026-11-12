# CI Diagnostic samples

**Sample reports.** Produced by Cedarwood Studio from public data on wagtail/wagtail and temporalio/sdk-python as of 2026-11-12. Nobody at either project asked for them. Cedarwood Studio isn't affiliated with either project and neither has endorsed these reports. Nothing was sent to either project: no issue, pull request or comment.

This repository holds two complete CI Diagnostics, the fixed-price report Cedarwood Studio sells, each run against a public repository so the result can be checked by anyone. It holds the reports, the tool that produced them, and the data behind every number.

The reports describe how two CI pipelines behaved over a few weeks, from what GitHub publishes about them. They don't judge either project or the people who maintain it, and they name no one. If you maintain one of these projects and want something here corrected or taken down, write to hello@cedarwood.studio.

| Sample | What it shows | Report |
| --- | --- | --- |
| wagtail/wagtail | A slow pipeline with no re-runs in its history. Where the time goes, and a three-line fix tested on a fork with runs before and after. | [`REPORT.md`](REPORT.md), [`report.html`](report.html) |
| temporalio/sdk-python | A pipeline where people press re-run. The tests and steps that failed and then passed on the same commit, named and ranked, with the job log behind each one. | [`samples/temporal-sdk-python/REPORT.md`](samples/temporal-sdk-python/REPORT.md), [`report.html`](samples/temporal-sdk-python/report.html) |

Each report opens with a section called "The short version," which holds the handful of numbers to read first.

## Layout

- `cidiag/`: the measurement tool. Python, with unit tests in `tests/`. Both reports come from the same tool.
- The first sample sits at the top level:
    - [`REPORT.md`](REPORT.md) and [`report.html`](report.html), the same text as one self-contained page.
    - `data/raw/`: every API response the report was computed from.
    - `results/metrics.json`: the computed numbers.
    - `report/REPORT.md.tmpl`: the report text, with a placeholder wherever a number goes.
    - `diagnostic.json`: the subject, the windows and the fork runs.
- The second sample has the same files under `samples/temporal-sdk-python/`.

Names, logins and email addresses of the people behind each run are removed before a response is stored (`PERSONAL_KEYS` in `cidiag/gh.py`). Release notes are dropped too, since they credit contributors by handle. Branch names other than `main` are stored as a hash, since people put their handles in them. Job logs are trimmed to the lines the analysis reads, and each third-party action's manifest is cut to the line that names its runtime. No measure uses what was removed. Commit SHAs, run ids and pull request numbers stay, because the links in the reports need them.

## Why these two repositories

**Wagtail.** We wanted a well-known, actively developed project under a permissive license (BSD 3-Clause), on GitHub Actions, in a stack our clients use, with a pipeline that does real work. Wagtail is a Django application tested against PostgreSQL, MySQL, MariaDB, SQLite, Elasticsearch and OpenSearch, which is the shape of pipeline a small SaaS team ends up with. Its tests need no secrets, so the pipeline runs unchanged on a fork. Its pipeline is also well kept, so the report shows what the diagnostic finds when the easy problems are already solved.

**Temporal's Python SDK.** Wagtail's history has no run that was re-run after a failure, so the first report never shows the diagnostic naming a flaky test. For the second we looked for a permissively licensed project whose history does have them. We screened 26 public repositories through the GitHub API, counting runs whose first attempt failed and whose final attempt passed. Most had none in their last 1,000 runs, or had only attempts that were held for a maintainer's approval, which look like re-runs and aren't. `temporalio/sdk-python` (MIT) had the most among the Python projects: 62 runs re-run after a failure in 30 days, 45 of which ended green. It's the official Python SDK for Temporal, tested with pytest against a live server on Linux, macOS and Windows.

## Reproduce every number

Offline, from the stored data:

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m cidiag analyze    # rewrites results/metrics.json from data/raw
.venv/bin/python -m cidiag render     # rewrites REPORT.md and report.html
.venv/bin/python -m cidiag verify     # fails if the report differs from a fresh computation
```

Those commands work on the first sample. Add `--sample temporal-sdk-python` to any of them for the second:

```
.venv/bin/python -m cidiag verify --sample temporal-sdk-python
```

One measure at a time, as cited in each section of the reports:

```
.venv/bin/python -m cidiag query main.summary
.venv/bin/python -m cidiag query fix
.venv/bin/python -m cidiag query flaky.tests --sample temporal-sdk-python
```

From GitHub, with the [`gh` CLI](https://cli.github.com/) signed in to any account:

```
rm -rf data/raw
.venv/bin/python -m cidiag fetch      # roughly 1,000 API calls, a few minutes
.venv/bin/python -m cidiag fetch --sample temporal-sdk-python   # roughly 2,000 calls, with data/raw under samples/ removed first
```

Run counts for the date-bounded windows will match. Cache entries are a snapshot and will differ, and job logs expire (GitHub keeps them 90 days by default), so anything read from logs can only be re-fetched while the logs exist. That covers the cache hit rates and the names of failing tests. The stored copies are what the reports were computed from.

Tests and lint:

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check . && .venv/bin/pytest
```

## What the diagnostic covers

- Median run time and runner minutes over the last 30 days of runs on the main branch and pull requests, or the last 100 runs if those reach back further, and where the time goes by job and by step.
- Failure rate and re-run rate, and which jobs and steps fail.
- Where the history has re-runs after a failure: each job that failed and then passed on the same commit, the tests its log names, and a ranking of those tests.
- Third-party actions and orbs that aren't pinned, archived, or on a deprecated runtime.
- Dependency caches that are missing or not being hit.
- Changes ranked by what they save, each with its size.
- Where the top change can be tested on a fork, the change made there, with runs of the pipeline before and after.

On CircleCI the numbers are CircleCI's own summaries for each workflow and job, which give run counts, failed runs and how long runs took. We don't recompute them from individual runs, and a CircleCI report has no runner minutes and no re-run rate. Section 9 of the Wagtail report shows what that looks like.

## What it doesn't cover

It isn't a security audit, a code review or an assessment of test quality. It reads CI history and workflow files. It doesn't read application code, and it says nothing about whether the software is correct or safe. A test that failed and then passed on the same commit is evidence that the test is flaky, and the reports say where that evidence is thin. Each report has a section on what couldn't be measured from the data and why.

## How this works on a private repository

Both samples were run on public repositories. On a private one the measurements are the same, and these are the terms.

- **Access.** Read access to the repository and its workflow runs, which includes the job logs, or to your CircleCI project. We don't need write access to your repository, and we ask for nothing in production. You can revoke access at any time.
- **A fix tested on a branch.** Optional. For a private repository it runs on a fork you give us access to.
- **Where the data goes.** The tools we work with send the code and materials you give us access to, in whole or in part, to the AI providers named in the signed scope. Our main AI tool is Anthropic's Claude, with model training turned off on our account, and no other AI provider touches your code unless the scope names it. The evidence that comes with the report holds test names and error lines from your job logs.
- **How long it's kept.** We delete your materials from our systems within 30 days after the engagement and any fix window end, and we confirm it in writing. The exceptions are the records we keep for tax and legal purposes, copies in routine backups, and what an AI provider keeps under its own terms. The scope says what the provider keeps.
- **Turnaround.** Five business days from the day we have access.

The studio's site is [cedarwood.studio](https://cedarwood.studio). To ask about a diagnostic on your own repository, write to hello@cedarwood.studio.

## The forks

- [cedarwood-studio/wagtail](https://github.com/cedarwood-studio/wagtail) holds the before and after runs of the first report, on branches `ci-diagnostic/baseline` and `ci-diagnostic/mysql-parallel`. A third branch, `ci-diagnostic/coverage-off-probe`, holds the one-run probe described in section 2 of that report.
- [cedarwood-studio/sdk-python](https://github.com/cedarwood-studio/sdk-python) holds one branch, `ci-diagnostic/flake-probe`, which adds one workflow file and changes nothing else. It runs the top-ranked test of the second report many times on one commit. No fix was tested there, and section 8 of the second report says why.

Nothing was pushed to wagtail/wagtail or temporalio/sdk-python, and no issue, pull request or comment was opened on either.

## License and attribution

This section records what was checked before the repository was made public. It's no substitute for legal advice.

- **This repository.** The tool and the reports are by Cedarwood Studio. No license is granted; the repository is published as a work sample.
- **The two projects.** Wagtail is the work of its contributors and is licensed under the BSD 3-Clause License. The Temporal Python SDK is the work of Temporal Technologies and its contributors and is licensed under the MIT License.
- **What of theirs is stored here.** No application code and no test code. `data/raw/` and `samples/temporal-sdk-python/data/raw/` hold each project's CI configuration at the commit the report read, as the GitHub API returned it: Wagtail's four workflow files and its CircleCI config, and the Temporal SDK's six workflow files. Those files stay under their projects' licenses, and both license texts are in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
- **Quoted output.** Test names, step names and error lines in the reports and the trimmed logs come from public job logs.
- **Third-party actions.** For each action a workflow uses, the data holds the repository's public metadata and one line of its manifest, the runtime it declares.
- **Everything else** in the data directories is public metadata returned by the GitHub and CircleCI APIs.
- **The forks** carry their upstream licenses unchanged. On the `ci-diagnostic/` branches each adds one workflow file, and in the Wagtail fork that file is a modified copy of Wagtail's own `test.yml`.

Cedarwood Studio, Jack Senechal, principal. hello@cedarwood.studio
