"""Command-line entry point: offline by default, explicit data refresh."""

import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reproduce the RBI banking event study from verified historical snapshots.")
    parser.add_argument("command", choices=["run", "validate-data", "verify", "refresh-data"], nargs="?", default="run")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, help="Dedicated generated-output directory (default: PROJECT/outputs)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap", type=int, default=10000, help="Event-inference bootstrap replicates")
    parser.add_argument("--prediction-bootstrap", type=int, default=2000, help="Held-out event bootstrap replicates")
    args = parser.parse_args(argv)
    try:
        if args.command == "run":
            from .pipeline import run_project
            manifest = run_project(args.project_root, args.output_dir, seed=args.seed,
                                   bootstrap=args.bootstrap, prediction_bootstrap=args.prediction_bootstrap,
                                   progress=lambda message: print(message, flush=True))
            print(json.dumps(manifest["counts"], indent=2))
        elif args.command == "verify":
            from .pipeline import verify_outputs
            print(json.dumps(verify_outputs(args.project_root, args.output_dir), indent=2))
        else:
            from .data import load_events, load_market_panel
            events = load_events(args.project_root)
            panel = load_market_panel(args.project_root, refresh=args.command == "refresh-data")
            print(json.dumps({"events": len(events), "price_rows": len(panel), "symbols": panel.symbol.nunique(),
                              "network_refresh_requested": args.command == "refresh-data"}, indent=2))
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
