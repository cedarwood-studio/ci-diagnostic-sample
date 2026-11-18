# CI Diagnostic samples

**Sample reports.** Produced by Cedarwood Studio from public data on wagtail/wagtail and temporalio/sdk-python as of 2026-11-12. Nobody at either project asked for them. Cedarwood Studio isn't affiliated with either project and neither has endorsed these reports. Nothing was sent to either project: no issue, pull request or comment.

This repository holds two complete CI Diagnostics, the fixed-price report Cedarwood Studio sells, each run against a public repository so the result can be checked by anyone. It holds the reports, the computed results and the data behind every number.

The reports describe how two CI pipelines behaved over a few weeks, from what GitHub publishes about them. They don't judge either project or the people who maintain it, and they name no one. If you maintain one of these projects and want something here corrected or taken down, write to hello@cedarwood.studio.

| Sample | What it shows | Report |
| --- | --- | --- |
| wagtail/wagtail | A slow pipeline with no re-runs in its history. Where the time goes, and a three-line fix tested on a fork with runs before and after. | [`REPORT.md`](REPORT.md), [`report.html`](report.html) |
| temporalio/sdk-python | A pipeline where people press re-run. The tests and steps that failed and then passed on the same commit, named and ranked, with the job log behind each one. | [`samples/temporal-sdk-python/REPORT.md`](samples/temporal-sdk-python/REPORT.md), [`report.html`](samples/temporal-sdk-python/report.html) |

Each report opens with a section called "The short version," which holds the handful of numbers to read first.

## What the two reports found

- **Wagtail.** The pipeline was already well kept. A verdict on `main` took 23:27 at the median. A three-line change cut the median run from 25:07 to 15:38 on our fork, over 3 runs before the change and 4 after.
- **Temporal's Python SDK.** In 30 days, 62 runs were re-run after a failure, and 45 of those ended green. The report names and ranks the tests the job logs name, each with its error line and a link to the log.

## Layout

- The first sample sits at the top level:
    - [`REPORT.md`](REPORT.md) and [`report.html`](report.html), the same text as one self-contained page.
    - `results/metrics.json`: the computed numbers. Each section of the report names the entry that holds its numbers.
    - `data/raw/`: the stored data the numbers were computed from.
- The second sample has the same files under `samples/temporal-sdk-python/`.

Each number in a report names its entry in `results/metrics.json`, and each entry can be traced to the files under `data/raw/`.

Names, logins and email addresses of the people behind each run are removed before anything is stored. Commit SHAs, run ids and pull request numbers stay, because the links in the reports need them.

## Why these two repositories

**Wagtail** is a well-known, actively developed project under a permissive license (BSD 3-Clause), on GitHub Actions, in a common web stack. Its tests need no secrets, so the pipeline runs unchanged on a fork, and its pipeline is well kept, so the report shows what a diagnostic finds when the easy problems are already solved.

**Temporal's Python SDK** (MIT) was chosen because its history has many runs that were re-run after a failure, which Wagtail's doesn't. It's tested with pytest on Linux, macOS and Windows.

## What a diagnostic tells you

- **Where the time goes.** How long a run takes and what it costs in runner minutes, and which jobs and steps the time sits in.
- **How often it fails.** The failure rate and the re-run rate, and which jobs and steps fail.
- **What's flaky.** The jobs that failed and then passed on the same commit, and for pytest and unittest the failing tests the logs name, ranked.
- **What to change first.** The changes ranked by what they save, each with its size. Where the top one is a speed fix that can be tested on a fork, the runs before and after. For a private repository that takes a fork you give us access to.

Finding the cause of a flaky test or fixing it is separate work.

A report you pay for gets a person's review before delivery.

## On your own repository

Both samples were run on public repositories. The paid diagnostic is for GitHub Actions, at a fixed $500, and [the offer page](https://cedarwood.studio/github-actions-ci-diagnostic/) has the terms.

- **Access.** Read access to your repository and its workflow runs, and nothing in production. We never need write access to your repository.
- **How your code and logs are handled.** AI tooling processes your workflow files and job logs, in whole or in part, through a provider that's named in your written scope before you pay or give access, with model training on our data turned off. The evidence that comes with the report holds test names and error lines from your job logs.
- **How long it's kept.** We delete our copies when you ask. What passes through the provider is held under its retention policy, which we don't control.
- **Delivery.** We agree on the delivery date with you in writing before you pay.

To ask about a diagnostic on your own repository, write to hello@cedarwood.studio.

## The forks

- [cedarwood-studio/wagtail](https://github.com/cedarwood-studio/wagtail) holds the before and after runs of the first report, on branches `ci-diagnostic/baseline` and `ci-diagnostic/mysql-parallel`. A third branch, `ci-diagnostic/coverage-off-probe`, holds the one-run probe described in section 2 of that report.
- [cedarwood-studio/sdk-python](https://github.com/cedarwood-studio/sdk-python) holds one branch, `ci-diagnostic/flake-probe`, which adds one workflow file and changes nothing else. Section 8 of the second report describes it.

Nothing was pushed to wagtail/wagtail or temporalio/sdk-python, and no issue, pull request or comment was opened on either.

## License and attribution

This section records what was checked before the repository was made public. It's no substitute for legal advice.

- **This repository.** The reports are by Cedarwood Studio. No license is granted; the repository is published as a work sample.
- **The two projects.** Wagtail is the work of its contributors and is licensed under the BSD 3-Clause License. The Temporal Python SDK is the work of Temporal Technologies and its contributors and is licensed under the MIT License.
- **What of theirs is stored here.** No application code and no test code. `data/raw/` and `samples/temporal-sdk-python/data/raw/` hold each project's CI configuration at the commit the report read, as the GitHub API returned it: Wagtail's four workflow files and its CircleCI config, and the Temporal SDK's six workflow files. Those files stay under their projects' licenses, and both license texts are in [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md).
- **Quoted output.** Test names, step names and error lines in the reports and the trimmed logs come from public job logs.
- **Third-party actions.** For each action a workflow uses, the data holds the repository's public metadata and one line of its manifest, the runtime it declares.
- **Everything else** in the data directories is public metadata returned by the GitHub and CircleCI APIs.
- **The forks** carry their upstream licenses unchanged. On the `ci-diagnostic/` branches each adds one workflow file, and in the Wagtail fork that file is a modified copy of Wagtail's own `test.yml`.

Cedarwood Studio, Jack Senechal, principal. hello@cedarwood.studio
