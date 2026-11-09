"""Validate every Spark CSV partition against the canonical Pandas bank panel.

Compares complete, unique (date, symbol) keys, null positions and finite returns.
A missing partition, duplicate, missing value or numeric mismatch fails the run.
The six initial null returns are compared explicitly, never silently dropped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def validate_returns(pandas_path: Path, spark_directory: Path, tolerance: float = 1e-10) -> dict:
    if not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    pandas_frame = pd.read_csv(pandas_path)
    if "asset_type" in pandas_frame:
        pandas_frame = pandas_frame.loc[pandas_frame["asset_type"].str.lower() == "bank"].copy()
    parts = sorted(spark_directory.glob("part-*.csv"))
    if not parts:
        raise FileNotFoundError(f"No Spark part-*.csv files in {spark_directory}")
    part_frames = []
    spark_columns = ["date", "symbol", "daily_return"]
    for path in parts:
        frame = pd.read_csv(path)
        if not set(spark_columns).issubset(frame.columns):
            raise ValueError(f"Spark partition {path.name}: missing required columns")
        if not frame.empty:
            part_frames.append(frame[spark_columns])
    if not part_frames:
        raise ValueError("Spark: no bank rows across all partitions")
    spark_frame = pd.concat(part_frames, ignore_index=True)
    for name, frame, return_column in [("Pandas", pandas_frame, "return"), ("Spark", spark_frame, "daily_return")]:
        required = {"date", "symbol", return_column}
        if not required.issubset(frame.columns):
            raise ValueError(f"{name}: missing columns {sorted(required - set(frame.columns))}")
        if frame.empty:
            raise ValueError(f"{name}: no bank rows")
        frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.strftime("%Y-%m-%d")
        if frame[["date", "symbol"]].isna().any().any() or frame["symbol"].astype(str).str.strip().eq("").any():
            raise ValueError(f"{name}: missing date/symbol key")
        if frame.duplicated(["date", "symbol"]).any():
            raise ValueError(f"{name}: duplicate (date, symbol) keys")
        frame[return_column] = pd.to_numeric(frame[return_column], errors="raise")
        if np.isinf(frame[return_column].to_numpy(dtype=float)).any():
            raise ValueError(f"{name}: infinite return")
        first_dates = frame.groupby("symbol")["date"].transform("min")
        if (frame[return_column].isna() & frame["date"].ne(first_dates)).any():
            raise ValueError(f"{name}: missing return after a bank's first observation")
    comparison = pandas_frame[["date", "symbol", "return"]].merge(
        spark_frame[["date", "symbol", "daily_return"]], on=["date", "symbol"], how="outer", validate="one_to_one", indicator=True,
    )
    if not comparison["_merge"].eq("both").all():
        counts = comparison["_merge"].value_counts().to_dict()
        raise ValueError(f"Incomplete key coverage: {counts}")
    if not comparison["return"].isna().eq(comparison["daily_return"].isna()).all():
        raise ValueError("Pandas/Spark missing-return masks differ")
    complete = comparison["return"].notna()
    differences = (comparison.loc[complete, "return"] - comparison.loc[complete, "daily_return"]).abs()
    if differences.empty:
        raise ValueError("No non-null returns were compared")
    maximum = float(differences.max())
    if maximum > tolerance:
        raise ValueError(f"Maximum absolute difference {maximum:.12g} exceeds tolerance {tolerance:.12g}")
    return {
        "status": "passed", "scope": "daily close-to-close bank returns only",
        "pandas_rows": int(len(pandas_frame)), "spark_rows": int(len(spark_frame)),
        "matched_rows": int(len(comparison)), "parts_read": len(parts),
        "non_null_returns": int(complete.sum()), "initial_null_returns": int((~complete).sum()),
        "maximum_absolute_difference": maximum, "mean_absolute_difference": float(differences.mean()),
        "tolerance": tolerance,
        "python_version": platform.python_version(), "pandas_version": pd.__version__,
        "pandas_file_sha256": hashlib.sha256(pandas_path.read_bytes()).hexdigest(),
        "spark_parts_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in parts},
        "validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pandas", type=Path, default=ROOT / "data/processed/market_panel.csv")
    parser.add_argument("--spark-dir", type=Path, default=ROOT / "outputs/spark/bank_returns")
    parser.add_argument("--tolerance", type=float, default=1e-10)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = validate_returns(args.pandas, args.spark_dir, args.tolerance)
    except (ValueError, FileNotFoundError, pd.errors.EmptyDataError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, allow_nan=False)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
