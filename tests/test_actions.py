from cidiag import actions

WORKFLOW = """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      db:
        image: postgres:latest
      search:
        image: docker.elastic.co/elasticsearch/elasticsearch:8.11.2
      pinned:
        image: redis@sha256:0123456789abcdef
      templated:
        image: ${{ matrix.image }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: astral-sh/setup-uv@main
      - uses: ./.github/actions/local
      - run: uv sync --locked
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v4
      - run: npm ci
  cached:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          cache: pip
      - run: pip install -r requirements.txt
"""


def test_find_uses_classifies_pins():
    uses = actions.find_uses("ci.yml", WORKFLOW)
    pins = {u["action"]: u["pin"] for u in uses}
    assert pins["actions/checkout"] == "sha"
    assert pins["actions/setup-python"] == "tag_or_branch"
    assert pins["astral-sh/setup-uv"] == "tag_or_branch"
    assert pins["./.github/actions/local"] == "local"
    checkout = next(u for u in uses if u["action"] == "actions/checkout")
    assert checkout["comment"] == "v7.0.1"
    assert checkout["line"] == 17


def test_find_images():
    images = {i["image"]: i["pin"] for i in actions.find_images("ci.yml", WORKFLOW)}
    assert images == {
        "postgres:latest": "floating",
        "docker.elastic.co/elasticsearch/elasticsearch:8.11.2": "tag",
        "redis@sha256:0123456789abcdef": "digest",
    }


def test_job_caches():
    rows = {r["job"]: r for r in actions.job_caches("ci.yml", WORKFLOW)}
    assert rows["test"]["installs"] == ["uv"] and rows["test"]["has_cache"]
    assert rows["lint"]["installs"] == ["npm"] and not rows["lint"]["has_cache"]
    assert rows["cached"]["installs"] == ["pip"] and rows["cached"]["has_cache"]
    assert rows["test"]["services"] == ["db", "pinned", "search", "templated"]


def test_action_repo_and_runtime():
    assert actions.action_repo("github/codeql-action/init") == ("github/codeql-action", "init")
    assert actions.action_repo("actions/checkout") == ("actions/checkout", "")
    assert actions.runtime("runs:\n  using: 'node20'\n  main: x.js\n") == "node20"
    assert actions.runtime("runs:\n  using: composite\n") == "composite"
    assert actions.runtime("") is None


def test_assess_action():
    use = {"action": "actions/checkout", "ref": "a" * 40, "pin": "sha", "comment": "v3.6.0"}
    meta = {"archived": False, "latest_release": "v7.0.1", "manifest": "runs:\n  using: node16\n"}
    row = actions.assess_action(use, meta)
    assert row["runtime_deprecated"] is True
    assert row["majors_behind"] == 4
    assert row["archived"] is False


LOG = """2026-11-10T10:33:16Z Trying to restore cache from GitHub Actions cache with key: k1
2026-11-10T10:33:16Z Cache hit for: k1
2026-11-10T10:33:22Z Installed 138 packages in 454ms
2026-11-10T10:33:23Z some unrelated line
2026-11-10T10:38:10Z Ran 7981 tests in 212.948s
2026-11-10T10:38:10Z OK (skipped=38)
"""


def test_filter_and_parse_log():
    kept = actions.filter_log(LOG)
    assert "unrelated" not in kept
    parsed = actions.parse_log(kept)
    assert parsed == {"cache": "hit", "tests_ran": 7981, "tests_seconds": 212.948}
    miss = actions.parse_log("x No GitHub Actions cache found for key: k2\n")
    assert miss["cache"] == "miss" and miss["tests_ran"] is None
    assert actions.parse_log("")["cache"] == "none"


def test_failed_tests_reads_unittest_names():
    log = (
        "x FAIL: test_a (pkg.tests.Case.test_a)\n"
        "x ERROR: test_b (pkg.tests.Case)\n"
        "x FAIL: test_a (pkg.tests.Case.test_a)\n"
    )
    kept = actions.filter_log(log)
    assert actions.failed_tests(kept) == ["pkg.tests.Case.test_a", "pkg.tests.Case.test_b"]
