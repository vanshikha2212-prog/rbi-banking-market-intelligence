"""One reproducible offline build with validated, staged output publication."""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import tempfile
from uuid import uuid4

from . import __version__
from .data import load_events, load_market_panel, sha256_file


def _write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _publish_directory(staging: Path, destination: Path):
    """Rollback the previous complete output if installation of the stage fails."""
    backup = destination.parent / f".outputs-backup-{uuid4().hex}"
    existed = destination.exists()
    if existed:
        destination.rename(backup)
    try:
        staging.rename(destination)
    except BaseException:
        if existed:
            backup.rename(destination)
        raise
    else:
        if existed:
            shutil.rmtree(backup)


def run_project(project_root, output_dir=None, *, seed=42, bootstrap=10000,
                prediction_bootstrap=2000, progress=print):
    root = Path(project_root).resolve()
    destination = Path(output_dir).resolve() if output_dir else root / "outputs"
    protected = [root / name for name in (
        "data", "rbi_intelligence", "tests", "docs", "sql", "pyspark", "sas",
        "tableau", "src", ".git", ".github", ".venv",
    )]
    if destination == root or destination in root.parents or any(destination.is_relative_to(path) for path in protected):
        raise ValueError("Output must be a dedicated generated-output directory")
    if destination.exists() and not destination.is_dir():
        raise ValueError("Output destination must be a directory")
    if bootstrap < 1 or prediction_bootstrap < 1:
        raise ValueError("Bootstrap counts must be positive")
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "rbi-mpl-cache"))

    # Imports are deferred until the plotting cache directory is configured.
    from .event_study import run_event_study, DEFAULT_WINDOWS
    from .statistics import run_inference
    from .sensitivity import run_sensitivity
    from .volatility import generate_event_volatility, summarize_volatility_forecasts, classify_volatility_risk
    from .prediction import build_predictive_dataset, evaluate_prediction, FEATURES
    from .database import build_database, export_dashboard_data
    from .dashboard import build_dashboard
    from .figures import create_figures
    from .report import write_report

    progress("[1/8] Verifying source hashes, rebuilding prices and checking events")
    events = load_events(root)
    panel = load_market_panel(root)
    snapshot = json.loads((root / "data/raw/market_manifest.json").read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".build-", dir=destination.parent))
    try:
        progress("[2/8] Estimating matched-calendar market models and event-level inference")
        results = run_event_study(panel, events)
        tables = {"event_study": results, **run_inference(results, seed=seed, n_bootstrap=bootstrap)}
        progress("[3/8] Checking dividend adjustments and corporate-action exclusions")
        tables.update(run_sensitivity(panel, events, results, seed=seed, n_bootstrap=bootstrap))
        progress("[4/8] Fitting past-only event-target volatility forecasts")
        forecasts = generate_event_volatility(panel, events)
        classified, thresholds = classify_volatility_risk(forecasts)
        tables.update(event_volatility=classified, volatility_thresholds=thresholds,
                      volatility_forecast_evaluation=summarize_volatility_forecasts(forecasts))
        progress("[5/8] Evaluating the fixed 2025 prediction holdout and whole-event uncertainty")
        features = build_predictive_dataset(panel, events, results, forecasts)
        prediction = evaluate_prediction(features, seed=seed, n_bootstrap=prediction_bootstrap)
        tables["predictive_features"] = features
        for name, frame in prediction.items():
            tables[f"model_{name}"] = frame
        table_dir = staging / "tables"
        table_dir.mkdir()
        for name, frame in tables.items():
            frame.to_csv(table_dir / f"{name}.csv", index=False, float_format="%.12g")
        packages = ["numpy", "pandas", "scipy", "statsmodels", "scikit-learn", "arch", "matplotlib"]
        code_paths = sorted((root / "rbi_intelligence").glob("*.py")) + [root / name for name in ("requirements.txt", "requirements-lock.txt", "pyproject.toml")]
        input_paths = sorted(path for path in (root / "data/raw").rglob("*") if path.is_file())
        manifest = {
            "manifest_version": 2, "project_version": __version__,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "command": "python -m rbi_intelligence run",
            "network_used_by_build": False,
            "runtime": {"python": platform.python_version(), "platform": platform.system(),
                        "packages": {name: version(name) for name in packages}},
            "parameters": {"seed": seed, "inference_bootstrap_repetitions": bootstrap,
                           "prediction_bootstrap_repetitions": prediction_bootstrap,
                           "estimation_days": 250, "estimation_inclusive_relative_days": [-255, -6],
                           "windows": {key: list(value) for key, value in DEFAULT_WINDOWS.items()},
                           "benchmarks": ["^NSEI", "^NSEBANK"],
                           "garch_distribution": "Student-t", "garch_min_training_returns": 500,
                           "train_end": "2024-12-31", "test_start": "2025-01-01", "test_end": "2025-12-31",
                           "prediction_features": FEATURES, "target_window": "[0,+1]"},
            "counts": {"events": len(events), "banks": int(panel.loc[panel.asset_type.eq("bank"), "symbol"].nunique()),
                       "bank_event_pairs": len(features), "event_result_rows": len(results),
                       "garch_attempts": len(forecasts), "garch_converged": int(forecasts.converged.sum()),
                       "tables": {name: len(frame) for name, frame in tables.items()}},
            "data_snapshot": snapshot,
            "inputs_sha256": {str(path.relative_to(root)): sha256_file(path) for path in input_paths},
            "analysis_code_sha256": {str(path.relative_to(root)): sha256_file(path) for path in code_paths},
            "table_files_sha256": {str(path.relative_to(staging)): sha256_file(path) for path in sorted(table_dir.glob("*.csv"))},
            "validation_scope": "Internal integrity and timing checks; not full independent price authentication or causal identification",
            "optional_tools": {"spark": "separate optional parity command", "sas": "script supplied; SAS execution not part of this build", "tableau": "CSV exports supplied; no executed Tableau workbook claimed"},
        }
        progress("[6/8] Rendering figures, offline dashboard, exports and research report")
        create_figures(staging / "figures", tables)
        export_dashboard_data(staging / "tableau", events, results, classified)
        build_dashboard(staging / "dashboard.html", events, results, classified, manifest=manifest)
        write_report(staging / "RESEARCH_REPORT.md", tables, manifest)
        progress("[7/8] Building the validated SQLite database and output manifest")
        build_database(staging / "study.sqlite", events, results, classified, market_data=panel, manifest=manifest)
        # The database is regenerated rather than committed. All other artifacts
        # are portable and checked even in a fresh clone.
        manifest["artifacts_sha256"] = {str(path.relative_to(staging)): sha256_file(path)
                                         for path in sorted(staging.rglob("*")) if path.is_file() and path.name != "study.sqlite"}
        manifest["local_regenerable_artifacts_sha256"] = {"study.sqlite": sha256_file(staging / "study.sqlite")}
        _write_json(staging / "run_manifest.json", manifest)
        verify_outputs(root, staging)
        _publish_directory(staging, destination)
        progress(f"[8/8] Complete: {destination}")
        return manifest
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_outputs(project_root, output_dir=None) -> dict:
    root = Path(project_root).resolve()
    directory = Path(output_dir).resolve() if output_dir else root / "outputs"
    manifest = json.loads((directory / "run_manifest.json").read_text())
    checked = 0
    for key, base in (("artifacts_sha256", directory), ("inputs_sha256", root), ("analysis_code_sha256", root)):
        if not manifest.get(key):
            raise ValueError(f"Manifest has no {key}; rebuild required")
        for relative, expected in manifest[key].items():
            path = (base / relative).resolve()
            if not path.is_relative_to(base):
                raise ValueError(f"Manifest path leaves its root: {relative}")
            if not path.is_file() or sha256_file(path) != expected:
                raise ValueError(f"Missing or changed file: {relative}; rebuild or restore the recorded version")
            checked += 1
    local_count = 0
    for relative, expected in manifest.get("local_regenerable_artifacts_sha256", {}).items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Local manifest path leaves output root")
        if path.exists():
            if sha256_file(path) != expected:
                raise ValueError(f"Changed local artifact: {relative}")
            local_count += 1
    return {"status": "ok", "files_checked": checked, "local_regenerable_files_checked": local_count,
            "database_present": (directory / "study.sqlite").is_file()}
