"""Command line: python -m cidiag fetch | analyze | render | verify | query."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analyze, fetch, render
from .gh import Client

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cidiag", description=__doc__)
    parser.add_argument("command", choices=["fetch", "analyze", "render", "verify", "query"])
    parser.add_argument("name", nargs="?", help="for `query`: the measure to print")
    parser.add_argument("--config", default=str(ROOT / "diagnostic.json"))
    parser.add_argument("--data", default=str(ROOT / "data" / "raw"))
    parser.add_argument("--out", default=str(ROOT))
    parser.add_argument(
        "--sample", help="a directory under samples/; sets --config, --data and --out to it"
    )
    args = parser.parse_args(argv)
    template = ROOT / "report" / "REPORT.md.tmpl"
    if args.sample:
        base = ROOT / "samples" / args.sample
        args.config = str(base / "diagnostic.json")
        args.data = str(base / "data" / "raw")
        args.out = str(base)
        template = base / "REPORT.md.tmpl"

    cfg = json.loads(Path(args.config).read_text())
    out = Path(args.out)
    metrics_path = out / "results" / "metrics.json"

    if args.command == "fetch":
        client = Client(Path(args.data))
        fetch.fetch_all(client, cfg)
        print(f"fetched; {client.calls} API calls made, the rest read from {args.data}")
        return 0

    client = Client(Path(args.data), offline=True)
    if args.command == "analyze":
        metrics = analyze.build(client, cfg)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
        print(f"wrote {metrics_path}")
        return 0
    if args.command == "query":
        metrics = analyze.build(client, cfg)
        value = analyze.lookup(metrics, args.name) if args.name else sorted(metrics)
        print(json.dumps(value, indent=2, sort_keys=True))
        return 0
    if args.command == "render":
        metrics = json.loads(metrics_path.read_text())
        render.write_report(template, metrics, out)
        print(f"wrote {out / 'REPORT.md'} and {out / 'report.html'}")
        return 0
    if args.command == "verify":
        fresh = analyze.build(client, cfg)
        stored = json.loads(metrics_path.read_text())
        fresh = json.loads(json.dumps(fresh, sort_keys=True))
        if fresh != stored:
            print("results/metrics.json does not match a fresh computation from data/raw")
            return 1
        expected = render.render_markdown(template.read_text(), fresh)
        if expected != (out / "REPORT.md").read_text():
            print("REPORT.md does not match the template filled from a fresh computation")
            return 1
        print("ok: metrics.json and REPORT.md match a fresh computation from data/raw")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
