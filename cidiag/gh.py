"""Thin wrapper around `gh api` that caches every response on disk.

Every number in the report is computed from the cached files, so the
analysis can be re-run offline and checked against the API later.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


def cache_name(endpoint: str) -> str:
    """Map an API endpoint to a stable, readable file name."""
    name = re.sub(r"[^A-Za-z0-9._=-]+", "_", endpoint.strip("/"))
    return name[:180] + ".json"


# Fields dropped before a response is stored. They hold names, logins and
# email addresses of the people who pushed or triggered a run, or who are
# credited in release notes (`body`). No measure uses them, and a diagnostic
# has no reason to keep them.
PERSONAL_KEYS = frozenset(
    {
        "actor",
        "triggering_actor",
        "head_commit",
        "repository",
        "head_repository",
        "owner",
        "pull_requests",
        "display_title",
        "organization",
        "runner_name",
        "author",
        "uploader",
        "body",
    }
)

# An action's manifest is someone else's file under that action's license. The
# analysis reads one fact from it, the runtime, so only that line is stored.
MANIFEST_NAMES = frozenset({"action.yml", "action.yaml"})
MANIFEST_KEEP_RE = re.compile(r"^\s*(?:runs:\s*$|using:)")


def trim_manifest(blob: dict) -> dict:
    """Cut a cached `action.yml` down to its `runs:` and `using:` lines."""
    try:
        text = base64.b64decode(blob["content"]).decode()
    except (ValueError, UnicodeDecodeError):
        return blob
    kept = "\n".join(line for line in text.splitlines() if MANIFEST_KEEP_RE.match(line))
    return {**blob, "content": base64.b64encode((kept + "\n").encode()).decode()}


# Branch names are chosen by the people who push them and often carry a
# handle. The analysis only asks whether two runs share a branch and whether
# a branch is the default one, so every other name is stored as a hash.
KEPT_BRANCHES = frozenset({"main", "master"})


def mask_branch(name):
    if not isinstance(name, str) or name in KEPT_BRANCHES or name.startswith("branch-"):
        return name
    return "branch-" + hashlib.sha256(name.encode()).hexdigest()[:12]


def scrub(value):
    """Remove PERSONAL_KEYS from a decoded JSON value, at any depth, and mask branch names."""
    if isinstance(value, dict):
        if value.get("name") in MANIFEST_NAMES and isinstance(value.get("content"), str):
            value = trim_manifest(value)
        return {
            k: mask_branch(v) if k == "head_branch" else scrub(v)
            for k, v in value.items()
            if k not in PERSONAL_KEYS
        }
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


class Client:
    def __init__(self, cache_dir: Path, offline: bool = False, pause: float = 0.1):
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self.pause = pause
        self.calls = 0
        self._memo: dict = {}

    def path_for(self, endpoint: str) -> Path:
        return self.cache_dir / cache_name(endpoint)

    def get(self, endpoint: str, refresh: bool = False):
        """Return parsed JSON for `gh api <endpoint>`, reading the cache first."""
        if endpoint in self._memo and not refresh:
            return self._memo[endpoint]
        path = self.path_for(endpoint)
        if path.exists() and not refresh:
            data = json.loads(path.read_text())
        elif self.offline:
            raise FileNotFoundError(f"not cached and offline: {endpoint}")
        else:
            data = scrub(json.loads(self._run(endpoint)))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, separators=(",", ":")))
        # The analysis reads the same files several times; parse each once.
        self._memo[endpoint] = data
        return data

    def _run(self, endpoint: str) -> str:
        for attempt in range(4):
            proc = subprocess.run(
                ["gh", "api", "-H", "Accept: application/vnd.github+json", endpoint],
                capture_output=True,
                text=True,
            )
            self.calls += 1
            time.sleep(self.pause)
            if proc.returncode == 0:
                return proc.stdout
            if "rate limit" in proc.stderr.lower() and attempt < 3:
                time.sleep(60 * (attempt + 1))
                continue
            if re.search(r"HTTP 50[0234]", proc.stderr) and attempt < 3:
                # Large job lists sometimes time out on GitHub's side; ask again.
                time.sleep(5 * (attempt + 1))
                continue
            if "HTTP 404" in proc.stderr or "HTTP 403" in proc.stderr:
                return json.dumps({"_error": proc.stderr.strip()})
            raise RuntimeError(f"gh api {endpoint} failed: {proc.stderr.strip()}")
        raise RuntimeError(f"gh api {endpoint} failed after retries")

    def get_pages(self, endpoint: str, key: str, limit: int | None = None) -> list:
        """Fetch a paginated list endpoint, one cached file per page.

        A run with many attempts can have a job list too large for GitHub to
        return 100 at a time (it answers 502). Those are fetched 30 at a time.
        """
        try:
            return self._pages(endpoint, key, limit, 100)
        except (RuntimeError, FileNotFoundError):
            return self._pages(endpoint, key, limit, 30)

    def _pages(self, endpoint: str, key: str, limit: int | None, size: int) -> list:
        items: list = []
        page = 1
        sep = "&" if "?" in endpoint else "?"
        while True:
            data = self.get(f"{endpoint}{sep}per_page={size}&page={page}")
            batch = data.get(key, []) if isinstance(data, dict) else data
            items.extend(batch)
            if len(batch) < size or (limit and len(items) >= limit):
                break
            page += 1
        return items[:limit] if limit else items

    def get_text(self, endpoint: str, transform=None) -> str:
        """Fetch a non-JSON endpoint (job logs). `transform` trims it before caching."""
        path = self.path_for(endpoint).with_suffix(".txt")
        if path.exists():
            return path.read_text()
        if self.offline:
            raise FileNotFoundError(f"not cached and offline: {endpoint}")
        proc = subprocess.run(
            ["gh", "api", "--allow-escape-sequences", endpoint], capture_output=True, text=True
        )
        self.calls += 1
        text = proc.stdout if proc.returncode == 0 else ""
        if transform:
            text = transform(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return text

    def get_url(self, url: str) -> dict:
        """Fetch a public JSON URL outside the GitHub API (CircleCI Insights)."""
        path = self.cache_dir / cache_name(url.split("://", 1)[1])
        if path.exists():
            return json.loads(path.read_text())
        if self.offline:
            raise FileNotFoundError(f"not cached and offline: {url}")
        proc = subprocess.run(["curl", "-sS", "-m", "30", url], capture_output=True, text=True)
        self.calls += 1
        if proc.returncode != 0:
            raise RuntimeError(f"curl {url} failed: {proc.stderr.strip()}")
        data = scrub(json.loads(proc.stdout))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, separators=(",", ":")))
        return data
