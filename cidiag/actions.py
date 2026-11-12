"""Static checks on workflow files: action pinning, runtimes and caches."""

from __future__ import annotations

import re

import yaml

USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?([^\s'\"#]+)['\"]?\s*(?:#\s*(.*))?$")
IMAGE_RE = re.compile(r"^\s*image:\s*['\"]?([^\s'\"#]+)")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
USING_RE = re.compile(r"^\s*using:\s*['\"]?([A-Za-z0-9]+)", re.M)

# Node runtimes GitHub has announced as deprecated for JavaScript actions.
DEPRECATED_RUNTIMES = {"node12", "node16", "node20"}

INSTALL_PATTERNS = {
    "uv": re.compile(r"\buv (sync|pip install)\b"),
    "pip": re.compile(r"(?<!uv )\bpip3? install\b"),
    "npm": re.compile(r"\bnpm (ci|install)\b"),
    "apt": re.compile(r"\bapt(-get)? install\b"),
    "bundler": re.compile(r"\bbundle install\b"),
}


def classify_ref(ref: str | None) -> str:
    if ref is None:
        return "local"
    if SHA_RE.match(ref):
        return "sha"
    return "tag_or_branch"


def find_uses(path: str, text: str) -> list[dict]:
    """Every `uses:` reference in a workflow file, with how it is pinned."""
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = USES_RE.match(line)
        if not match:
            continue
        target, comment = match.group(1), (match.group(2) or "").strip()
        if target.startswith("./"):
            out.append(
                {
                    "file": path,
                    "line": number,
                    "action": target,
                    "ref": None,
                    "pin": "local",
                    "comment": comment,
                }
            )
            continue
        if target.startswith("docker://"):
            pin = "sha" if "@sha256:" in target else "tag_or_branch"
            out.append(
                {
                    "file": path,
                    "line": number,
                    "action": target,
                    "ref": None,
                    "pin": pin,
                    "comment": comment,
                }
            )
            continue
        action, _, ref = target.partition("@")
        out.append(
            {
                "file": path,
                "line": number,
                "action": action,
                "ref": ref or None,
                "pin": classify_ref(ref) if ref else "tag_or_branch",
                "comment": comment,
            }
        )
    return out


def find_images(path: str, text: str) -> list[dict]:
    """Container images named in a workflow, and whether each is fixed by digest."""
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = IMAGE_RE.match(line)
        if not match:
            continue
        image = match.group(1)
        if "${{" in image:
            continue
        if "@sha256:" in image:
            pin = "digest"
        elif ":" not in image.rsplit("/", 1)[-1] or image.endswith(":latest"):
            pin = "floating"
        else:
            pin = "tag"
        out.append({"file": path, "line": number, "image": image, "pin": pin})
    return out


def action_repo(action: str) -> tuple[str, str]:
    """`github/codeql-action/init` -> (`github/codeql-action`, `init`)."""
    parts = action.split("/")
    return "/".join(parts[:2]), "/".join(parts[2:])


def runtime(manifest: str) -> str | None:
    match = USING_RE.search(manifest or "")
    return match.group(1) if match else None


def major(version: str | None) -> int | None:
    match = re.search(r"v?(\d+)", version or "")
    return int(match.group(1)) if match else None


def assess_action(use: dict, meta: dict) -> dict:
    """Combine one `uses:` reference with what the action's repository says."""
    using = runtime(meta.get("manifest", ""))
    pinned_major = major(use.get("comment")) if use["pin"] == "sha" else major(use.get("ref"))
    latest_major = major(meta.get("latest_release"))
    return {
        "action": use["action"],
        "ref": use["ref"],
        "pin": use["pin"],
        "version_comment": use.get("comment", ""),
        "archived": bool(meta.get("archived")),
        "runtime": using,
        "runtime_deprecated": using in DEPRECATED_RUNTIMES,
        "latest_release": meta.get("latest_release"),
        "majors_behind": (latest_major - pinned_major)
        if latest_major is not None and pinned_major is not None
        else None,
    }


def _step_caches(step: dict) -> bool:
    uses = str(step.get("uses", ""))
    params = step.get("with") or {}
    if uses.startswith(("actions/cache", "Swatinem/rust-cache")):
        return True
    if uses.startswith("astral-sh/setup-uv"):
        # setup-uv caches by default on GitHub-hosted runners (enable-cache: auto).
        return str(params.get("enable-cache", "auto")).lower() != "false"
    if uses.startswith(("actions/setup-python", "actions/setup-node", "ruby/setup-ruby")):
        return bool(params.get("cache") or params.get("bundler-cache"))
    return False


def job_caches(path: str, text: str) -> list[dict]:
    """Per job: which package managers it installs with and whether a cache step exists."""
    doc = yaml.safe_load(text) or {}
    rows = []
    for name, job in (doc.get("jobs") or {}).items():
        steps = job.get("steps") or []
        installers = set()
        for step in steps:
            command = str(step.get("run", ""))
            for manager, pattern in INSTALL_PATTERNS.items():
                if pattern.search(command):
                    installers.add(manager)
        rows.append(
            {
                "file": path,
                "job": name,
                "installs": sorted(installers),
                "has_cache": any(_step_caches(s) for s in steps),
                "services": sorted((job.get("services") or {}).keys()),
            }
        )
    return rows


CACHE_HIT_RE = re.compile(r"Cache hit for: (\S+)|cache restored from GitHub Actions cache")
CACHE_MISS_RE = re.compile(r"No GitHub Actions cache found for key: (\S+)")
RAN_RE = re.compile(r"Ran (\d+) tests? in ([0-9.]+)s")
KEEP_RE = re.compile(
    r"Cache hit for|cache restored from|No GitHub Actions cache found|Trying to restore cache"
    r"|Ran \d+ tests? in|Cache saved|Installed \d+ packages? in|^.{0,40}(OK|FAILED) \("
    r"|Using \d+ parallel|Cloning test database|(FAIL|ERROR): \S+ \("
)
FAILED_TEST_RE = re.compile(r"(FAIL|ERROR): (\S+) \(([^)]*)\)")


def filter_log(text: str) -> str:
    """Keep only the log lines the analysis reads, so the cache stays small."""
    return "\n".join(line for line in text.splitlines() if KEEP_RE.search(line))


ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
STAMP_RE = re.compile(r"^\d{4}-\d\d-\d\dT[\d:.]+Z ")
FAIL_SECTION_RE = re.compile(r"^=+ (FAILURES|ERRORS) =+$")
SECTION_RE = re.compile(r"^=+ .* =+$")
TEST_HEADER_RE = re.compile(r"^_{3,} (.+?) _{3,}$")
RESULT_COUNT_RE = re.compile(r"^\s+\d+ [a-z]+$")
FAILURE_KEEP_RE = re.compile(
    r"^##\[error\]|^##\[group\]Run |^(FAILED|ERROR) \S+::|Restored from cache key|No cache found"
)
TABLE_LINE_RE = re.compile(r"^\s*[\u2500-\u257f+|]")
TABLE_ROW_RE = re.compile(r"^\s*[\u2502\u2503|](?!-)")
E_LINES_PER_TEST = 6
LINE_LIMIT = 400


def log_body(line: str) -> str:
    """A log line without colour codes and without GitHub's timestamp prefix."""
    return STAMP_RE.sub("", ANSI_RE.sub("", line))


PROGRESS_RE = re.compile(
    r"^(tests[\\/]\S+\.py )?[.FEsxR]+(\s*\[\s*\d+%\])?(\+{5,} Timeout \+{5,})?$"
    r"|\+{5,} Timeout \+{5,}|^timeout method:|^collected \d+ items|^\d+ workers \["
)


def trim_probe_log(text: str) -> str:
    """`trim_failure_log`, plus pytest's progress lines and timeout markers.

    Used for the probe runs on a fork, where the question is how many
    repetitions of one test got through before something stopped the step.
    """
    return trim_failure_log(text, progress=True)


def trim_failure_log(text: str, progress: bool = False) -> str:
    """`filter_log`, plus the lines that say which tests failed and why.

    Kept from a pytest log: each failing test's header in the FAILURES and
    ERRORS sections with the first `E` lines under it, the "Summary of
    Failures" table (pytest-pretty), the result counts, any `FAILED path::test`
    line, and every `##[error]` annotation. `##[group]Run` lines are kept so a
    failure can be tied to the step that produced it.
    """
    kept = []
    in_failures = in_table = in_results = False
    e_lines = 0
    for raw in text.splitlines():
        line = ANSI_RE.sub("", raw)
        body = STAMP_RE.sub("", line)
        keep = bool(KEEP_RE.search(line) or FAILURE_KEEP_RE.search(body))
        keep = keep or bool(progress and PROGRESS_RE.search(body))
        if in_results:
            in_results = bool(RESULT_COUNT_RE.match(body))
            keep = keep or in_results
        if body.startswith("Results ("):
            in_results, in_failures, in_table, keep = True, False, False, True
        elif "Summary of Failures" in body:
            in_table, in_failures, keep = True, False, True
        elif in_table:
            # Box-drawing characters (heavy or light), or plain ASCII on some consoles.
            keep = in_table = bool(TABLE_LINE_RE.match(body))
        elif FAIL_SECTION_RE.match(body):
            in_failures, keep = True, True
        elif in_failures:
            if TEST_HEADER_RE.match(body):
                e_lines, keep = 0, True
            elif body.startswith("E ") and e_lines < E_LINES_PER_TEST:
                e_lines += 1
                keep = True
            elif SECTION_RE.match(body):
                in_failures = False
        if keep:
            kept.append(line[:LINE_LIMIT])
    return "\n".join(kept)


def failed_tests(text: str) -> list[str]:
    """Names of tests a unittest-style log reports as FAIL or ERROR."""
    names = []
    for _, test, where in FAILED_TEST_RE.findall(text):
        name = where if where.endswith(test) else f"{where}.{test}"
        if name not in names:
            names.append(name)
    return names


RUST_CACHE_RE = re.compile(r"Restored from cache key .* full match: (true|false)")


def rust_cache(text: str) -> str | None:
    """What Swatinem/rust-cache restored: `full`, `partial`, `miss`, or None if it did not run."""
    match = RUST_CACHE_RE.search(text)
    if match:
        return "full" if match.group(1) == "true" else "partial"
    return "miss" if "No cache found" in text else None


def parse_log(text: str) -> dict:
    hit = bool(CACHE_HIT_RE.search(text))
    miss = bool(CACHE_MISS_RE.search(text))
    ran = RAN_RE.findall(text)
    return {
        "cache": "hit" if hit else "miss" if miss else "none",
        "tests_ran": int(ran[-1][0]) if ran else None,
        "tests_seconds": float(ran[-1][1]) if ran else None,
    }
