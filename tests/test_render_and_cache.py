import json

from cidiag import render
from cidiag.analyze import lookup
from cidiag.gh import Client, cache_name


def test_lookup_walks_dicts_and_lists():
    data = {"a": {"b": [{"c": 7}]}}
    assert lookup(data, "a.b.0.c") == 7


def test_formats():
    assert render.fmt_min(1407) == "23.4"
    assert render.fmt_mmss(1407) == "23:27"
    assert render.fmt_pct(0.0877) == "8.8%"
    assert render.fmt_pct(None) == "n/a"
    assert render.fmt_int(2014.4) == "2,014"
    assert render.fmt_date("2026-11-10T10:33:03Z") == "2026-11-10"


def test_render_markdown_fills_placeholders():
    out = render.render_markdown(
        "Median {{ a.b | min }} min over {{ n }} runs.", {"a": {"b": 600}, "n": 3}
    )
    assert out == "Median 10.0 min over 3 runs."


def test_render_html_is_self_contained():
    page = render.render_html("# Title\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n", "Title")
    assert "<table>" in page and "<title>Title</title>" in page
    assert "http://" not in page and "https://" not in page
    assert "<script" not in page and "<link" not in page


def test_cache_name_is_stable_and_safe():
    name = cache_name("repos/o/r/actions/runs?created=2026-10-12..2026-11-10&page=1")
    assert "/" not in name and "?" not in name and name.endswith(".json")
    assert name == cache_name("repos/o/r/actions/runs?created=2026-10-12..2026-11-10&page=1")


def test_client_reads_cache_and_refuses_network_when_offline(tmp_path):
    client = Client(tmp_path, offline=True)
    endpoint = "repos/o/r/actions/runs?per_page=100&page=1"
    client.path_for(endpoint).write_text(json.dumps({"workflow_runs": [{"id": 1}]}))
    assert client.get_pages("repos/o/r/actions/runs", "workflow_runs") == [{"id": 1}]
    assert client.calls == 0
    try:
        client.get("repos/o/r/not-cached")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("offline client must not call the API")


def test_scrub_drops_personal_fields_at_any_depth():
    from cidiag.gh import scrub

    data = {
        "workflow_runs": [
            {
                "id": 1,
                "actor": {"login": "x"},
                "head_commit": {"author": {"email": "a@b.c"}},
                "event": "push",
            }
        ]
    }
    assert scrub(data) == {"workflow_runs": [{"id": 1, "event": "push"}]}


def test_fmt_num_keeps_halves():
    assert render.fmt_num(146) == "146"
    assert render.fmt_num(105.5) == "105.5"
    assert render.fmt_num(7047.0) == "7,047"


def test_scrub_masks_branch_names_and_drops_release_authors():
    from cidiag.gh import scrub

    data = {
        "workflow_runs": [
            {"id": 1, "head_branch": "main"},
            {"id": 2, "head_branch": "someone/fix-the-thing"},
            {"id": 3, "head_branch": "someone/fix-the-thing"},
        ],
        "author": {"login": "someone"},
        "tag_name": "v1.2.3",
    }
    out = scrub(data)
    assert "author" not in out and out["tag_name"] == "v1.2.3"
    first, second, third = out["workflow_runs"]
    assert first["head_branch"] == "main"
    assert second["head_branch"].startswith("branch-") and "someone" not in second["head_branch"]
    assert second["head_branch"] == third["head_branch"]
    assert scrub(out) == out


def test_scrub_drops_release_notes_and_trims_action_manifests():
    import base64

    from cidiag.actions import runtime
    from cidiag.gh import scrub

    manifest = "name: Thing\nauthor: someone\nruns:\n  using: node24\n  main: dist/index.js\n"
    data = {
        "tag_name": "v2",
        "body": "Thanks @someone for the fix",
        "blob": {"name": "action.yml", "content": base64.b64encode(manifest.encode()).decode()},
        "other": {"name": "ci.yml", "content": base64.b64encode(b"on: push\n").decode()},
    }
    out = scrub(data)
    assert "body" not in out and out["tag_name"] == "v2"
    kept = base64.b64decode(out["blob"]["content"]).decode()
    assert kept == "runs:\n  using: node24\n"
    assert runtime(kept) == "node24"
    assert out["other"] == data["other"]
    assert scrub(out) == out
