"""Validated, atomic SQLite storage and portable analytical exports.

All validation happens before an existing database is touched. The new database
is built in one transaction in the destination directory and atomically replaces
the old file only after foreign-key and integrity checks pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Mapping

import numpy as np
import pandas as pd


SCHEMA_SQL = """
CREATE TABLE run_metadata (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
CREATE TABLE rbi_events (
    event_id TEXT PRIMARY KEY,
    event_date TEXT NOT NULL UNIQUE,
    decision TEXT NOT NULL CHECK (decision IN ('Cut', 'Hold', 'Hike')),
    repo_before REAL,
    repo_after REAL,
    rate_change_bps REAL,
    stance TEXT,
    source_url TEXT,
    details_json TEXT NOT NULL
);
CREATE TABLE bank_metadata (
    bank_symbol TEXT PRIMARY KEY,
    bank_name TEXT NOT NULL,
    bank_type TEXT NOT NULL
);
CREATE TABLE event_study_results (
    event_id TEXT NOT NULL REFERENCES rbi_events(event_id),
    bank_symbol TEXT NOT NULL REFERENCES bank_metadata(bank_symbol),
    benchmark TEXT NOT NULL,
    window TEXT NOT NULL,
    car REAL NOT NULL,
    absolute_car REAL NOT NULL CHECK (absolute_car >= 0),
    alpha REAL,
    beta REAL,
    estimation_start TEXT,
    estimation_end TEXT,
    n_estimation INTEGER CHECK (n_estimation > 0),
    n_event INTEGER CHECK (n_event > 0),
    details_json TEXT NOT NULL,
    PRIMARY KEY (event_id, bank_symbol, benchmark, window)
);
CREATE TABLE volatility_forecasts (
    event_id TEXT NOT NULL REFERENCES rbi_events(event_id),
    bank_symbol TEXT NOT NULL REFERENCES bank_metadata(bank_symbol),
    forecast_origin_date TEXT NOT NULL,
    forecast_target_date TEXT NOT NULL,
    garch_variance REAL CHECK (garch_variance >= 0),
    garch_volatility REAL CHECK (garch_volatility >= 0),
    rolling_variance REAL CHECK (rolling_variance >= 0),
    rolling_volatility REAL CHECK (rolling_volatility >= 0),
    n_training INTEGER CHECK (n_training > 0),
    convergence_flag INTEGER,
    converged INTEGER NOT NULL CHECK (converged IN (0, 1)),
    risk_level TEXT,
    status TEXT,
    details_json TEXT NOT NULL,
    PRIMARY KEY (event_id, bank_symbol),
    CHECK (forecast_origin_date < forecast_target_date)
);
CREATE TABLE market_data (
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT,
    close REAL,
    adj_close REAL,
    return REAL,
    adj_return REAL,
    details_json TEXT NOT NULL,
    PRIMARY KEY (date, symbol)
);
CREATE INDEX event_results_slice ON event_study_results(benchmark, window);
CREATE VIEW event_explorer AS
SELECT r.event_id, e.event_date, e.decision, e.rate_change_bps,
       b.bank_symbol, b.bank_name, b.bank_type, r.benchmark, r.window,
       r.car, r.absolute_car, r.alpha, r.beta,
       r.estimation_start, r.estimation_end, r.n_estimation, r.n_event,
       v.forecast_origin_date, v.forecast_target_date,
       v.garch_volatility, v.rolling_volatility, v.converged, v.risk_level
FROM event_study_results r
JOIN rbi_events e ON e.event_id = r.event_id
JOIN bank_metadata b ON b.bank_symbol = r.bank_symbol
LEFT JOIN volatility_forecasts v
  ON v.event_id = r.event_id AND v.bank_symbol = r.bank_symbol;
"""


@dataclass(frozen=True)
class ValidatedData:
    events: pd.DataFrame
    results: pd.DataFrame
    forecasts: pd.DataFrame
    banks: pd.DataFrame
    market_data: pd.DataFrame


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy values to strict JSON without NaN or Infinity."""
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _json(value: Any) -> str:
    return json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True, allow_nan=False)


def _require(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{name}: missing required columns {missing}")


def _unique(frame: pd.DataFrame, keys: list[str], name: str) -> None:
    if frame[keys].isna().any().any() or frame[keys].astype(str).apply(lambda col: col.str.strip().eq("")).any().any():
        raise ValueError(f"{name}: missing or empty key in {keys}")
    if frame.duplicated(keys).any():
        raise ValueError(f"{name}: duplicate keys {keys}")


def _dates(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    for column in columns:
        if column not in frame:
            continue
        try:
            parsed = pd.to_datetime(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}: invalid date in {column}") from exc
        if parsed.isna().any():
            raise ValueError(f"{name}: missing date in {column}")
        frame[column] = parsed.dt.strftime("%Y-%m-%d")


def _numeric(frame: pd.DataFrame, columns: list[str], name: str, *, nullable: bool = False) -> None:
    for column in columns:
        if column not in frame:
            continue
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}: nonnumeric {column}") from exc
        values = frame[column].to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(values).any() or (not nullable and np.isnan(values).any()):
            raise ValueError(f"{name}: nonfinite {column}")


def _check_event_metadata(frame: pd.DataFrame, events: pd.DataFrame, name: str) -> None:
    event_ids = set(events["event_id"])
    if not set(frame["event_id"]).issubset(event_ids):
        raise ValueError(f"{name}: unknown event_id")
    event_lookup = events.set_index("event_id")
    for field in ("event_date", "decision"):
        if field in frame:
            expected = frame["event_id"].map(event_lookup[field])
            if not frame[field].eq(expected).all():
                raise ValueError(f"{name}: {field} disagrees with events")


def validate_inputs(
    events: pd.DataFrame,
    results: pd.DataFrame,
    forecasts: pd.DataFrame | None = None,
    market_data: pd.DataFrame | None = None,
) -> ValidatedData:
    """Validate identity, units, numerical values and point-in-time alignment.

    This checks internal integrity; it does not independently verify RBI releases
    or market prices. Failed GARCH fits remain visible as unavailable forecasts.
    """
    events, results = events.copy(), results.copy()
    forecasts = pd.DataFrame() if forecasts is None else forecasts.copy()
    market_data = pd.DataFrame() if market_data is None else market_data.copy()
    _require(events, ["event_id", "event_date", "decision"], "events")
    core = ["event_id", "event_date", "decision", "bank_symbol", "bank_name", "bank_type", "benchmark", "window", "car"]
    _require(results, core, "results")
    if events.empty or results.empty:
        raise ValueError("events and results must not be empty")
    _unique(events, ["event_id"], "events")
    _dates(events, ["event_date", "meeting_start", "meeting_end"], "events")
    _unique(events, ["event_date"], "events")
    if not events["decision"].isin(["Cut", "Hold", "Hike"]).all():
        raise ValueError("events: decision must be Cut, Hold, or Hike")
    _numeric(events, ["repo_before", "repo_after", "rate_change_bps"], "events")
    if {"repo_before", "repo_after", "rate_change_bps"}.issubset(events.columns):
        changes = (events["repo_after"] - events["repo_before"]) * 100
        if not np.allclose(changes, events["rate_change_bps"], rtol=0, atol=1e-8):
            raise ValueError("events: repo rates disagree with basis-point changes")
        expected_decisions = np.where(changes > 1e-8, "Hike", np.where(changes < -1e-8, "Cut", "Hold"))
        if not np.array_equal(events["decision"].to_numpy(), expected_decisions):
            raise ValueError("events: decision disagrees with repo-rate change")
    _unique(results, ["event_id", "bank_symbol", "benchmark", "window"], "results")
    _dates(results, ["event_date", "estimation_start", "estimation_end"], "results")
    _numeric(results, ["car", "alpha", "beta", "n_estimation", "n_event"], "results")
    for column in ["n_estimation", "n_event"]:
        if column in results and ((results[column] <= 0) | (results[column] % 1 != 0)).any():
            raise ValueError(f"results: {column} must contain positive integers")
    if results[["bank_name", "bank_type"]].isna().any().any():
        raise ValueError("results: missing bank metadata")
    _check_event_metadata(results, events, "results")
    bank_rows = results[["bank_symbol", "bank_name", "bank_type"]].drop_duplicates()
    _unique(bank_rows, ["bank_symbol"], "bank metadata")
    banks = bank_rows.sort_values("bank_symbol").reset_index(drop=True)
    if "absolute_car" in results and not np.allclose(results["absolute_car"], results["car"].abs(), rtol=0, atol=1e-12):
        raise ValueError("results: absolute_car disagrees with car")
    results["absolute_car"] = results["car"].abs()

    if not forecasts.empty:
        _require(forecasts, ["event_id", "bank_symbol", "forecast_origin_date", "forecast_target_date", "garch_volatility"], "forecasts")
        _unique(forecasts, ["event_id", "bank_symbol"], "forecasts")
        _dates(forecasts, ["event_date", "forecast_origin_date", "forecast_target_date"], "forecasts")
        _check_event_metadata(forecasts, events, "forecasts")
        if not set(forecasts["bank_symbol"]).issubset(set(banks["bank_symbol"])):
            raise ValueError("forecasts: unknown bank_symbol")
        expected_date = forecasts["event_id"].map(events.set_index("event_id")["event_date"])
        if not forecasts["forecast_target_date"].eq(expected_date).all():
            raise ValueError("forecasts: forecast target must be the event date")
        if not forecasts["forecast_origin_date"].lt(forecasts["forecast_target_date"]).all():
            raise ValueError("forecasts: forecast origin must precede target")
        _numeric(forecasts, ["garch_variance", "garch_volatility", "rolling_variance", "rolling_volatility", "n_training", "convergence_flag"], "forecasts", nullable=True)
        if "converged" not in forecasts:
            if "convergence_flag" not in forecasts:
                raise ValueError("forecasts: converged or convergence_flag is required")
            forecasts["converged"] = forecasts["convergence_flag"].eq(0)
        if not forecasts["converged"].isin([True, False, 0, 1]).all():
            raise ValueError("forecasts: converged must be boolean")
        forecasts["converged"] = forecasts["converged"].astype(bool)
        if "convergence_flag" in forecasts:
            flags = forecasts["convergence_flag"]
            if (flags.notna() & forecasts["converged"].ne(flags.eq(0))).any():
                raise ValueError("forecasts: conflicting convergence indicators")
        valid = forecasts["converged"]
        if forecasts.loc[valid, "garch_volatility"].isna().any():
            raise ValueError("forecasts: converged forecast has no volatility")
        for column in ["garch_variance", "garch_volatility", "rolling_variance", "rolling_volatility"]:
            if column in forecasts and forecasts[column].dropna().lt(0).any():
                raise ValueError(f"forecasts: negative {column}")
        if "garch_variance" in forecasts:
            comparable = valid & forecasts["garch_variance"].notna()
            if not np.allclose(forecasts.loc[comparable, "garch_volatility"] ** 2, forecasts.loc[comparable, "garch_variance"], rtol=1e-7, atol=1e-12):
                raise ValueError("forecasts: variance and volatility disagree")
        if "risk_level" not in forecasts:
            forecasts["risk_level"] = "Unclassified"
        forecasts.loc[~valid, "risk_level"] = "Unavailable"

    if not market_data.empty:
        _require(market_data, ["date", "symbol"], "market_data")
        _dates(market_data, ["date"], "market_data")
        _unique(market_data, ["date", "symbol"], "market_data")
        _numeric(market_data, ["close", "adj_close", "return", "adj_return"], "market_data", nullable=True)
        for column in ["close", "adj_close"]:
            if column in market_data and market_data[column].dropna().le(0).any():
                raise ValueError(f"market_data: {column} must be positive")
    return ValidatedData(events, results, forecasts, banks, market_data)


def _insert(connection: sqlite3.Connection, table: str, frame: pd.DataFrame, columns: list[str]) -> None:
    if frame.empty:
        return
    quoted = ", ".join('"' + column + '"' for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    rows = []
    for record in frame.to_dict(orient="records"):
        rows.append(tuple(_json(record) if column == "details_json" else json_safe(record.get(column)) for column in columns))
    connection.executemany(f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})', rows)


def build_database(
    output_path: str | Path,
    events: pd.DataFrame,
    results: pd.DataFrame,
    forecasts: pd.DataFrame | None = None,
    *,
    market_data: pd.DataFrame | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> Path:
    """Build a complete database, preserving any existing database on failure."""
    data = validate_inputs(events, results, forecasts, market_data)
    manifest_json = _json(manifest or {})
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent)
    os.close(descriptor)
    temp_path = Path(temp_name)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(temp_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("BEGIN IMMEDIATE;\n" + SCHEMA_SQL)
        _insert(connection, "rbi_events", data.events, ["event_id", "event_date", "decision", "repo_before", "repo_after", "rate_change_bps", "stance", "source_url", "details_json"])
        _insert(connection, "bank_metadata", data.banks, ["bank_symbol", "bank_name", "bank_type"])
        _insert(connection, "event_study_results", data.results, ["event_id", "bank_symbol", "benchmark", "window", "car", "absolute_car", "alpha", "beta", "estimation_start", "estimation_end", "n_estimation", "n_event", "details_json"])
        _insert(connection, "volatility_forecasts", data.forecasts, ["event_id", "bank_symbol", "forecast_origin_date", "forecast_target_date", "garch_variance", "garch_volatility", "rolling_variance", "rolling_volatility", "n_training", "convergence_flag", "converged", "risk_level", "status", "details_json"])
        _insert(connection, "market_data", data.market_data, ["date", "symbol", "asset_type", "close", "adj_close", "return", "adj_return", "details_json"])
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in ["rbi_events", "bank_metadata", "event_study_results", "volatility_forecasts", "market_data"]}
        connection.executemany("INSERT INTO run_metadata VALUES (?, ?)", [("manifest", manifest_json), ("table_counts", _json(counts)), ("schema_version", "1")])
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Database failed foreign-key validation")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Database failed integrity validation")
        connection.commit()
        connection.close()
        connection = None
        with temp_path.open("rb") as file:
            os.fsync(file.fileno())
        os.replace(temp_path, output_path)
    except BaseException:
        if connection is not None:
            connection.rollback()
            connection.close()
        temp_path.unlink(missing_ok=True)
        raise
    return output_path


def export_dashboard_data(
    output_dir: str | Path,
    events: pd.DataFrame,
    results: pd.DataFrame,
    forecasts: pd.DataFrame | None = None,
) -> dict[str, Path]:
    """Export tidy, explicitly labelled data for Tableau and optional SAS work."""
    data = validate_inputs(events, results, forecasts)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    keys = ["benchmark", "window", "bank_symbol", "bank_name", "bank_type"]
    performance = data.results.groupby(keys, as_index=False).agg(event_count=("event_id", "nunique"), mean_car=("car", "mean"), mean_absolute_car=("absolute_car", "mean"))
    event_keys = ["event_id", "event_date", "decision", "benchmark", "window"]
    event_means = data.results.groupby(event_keys, as_index=False).agg(bank_count=("bank_symbol", "nunique"), mean_car=("car", "mean"), mean_absolute_car=("absolute_car", "mean"))
    explorer = data.results.copy()
    if not data.forecasts.empty:
        forecast_columns = [column for column in data.forecasts if column not in explorer or column in ["event_id", "bank_symbol"]]
        explorer = explorer.merge(data.forecasts[forecast_columns], on=["event_id", "bank_symbol"], how="left", validate="many_to_one")
    primary = data.results.loc[(data.results["benchmark"] == "^NSEI") & (data.results["window"] == "[-1,+1]")]
    primary_means = event_means.loc[(event_means["benchmark"] == "^NSEI") & (event_means["window"] == "[-1,+1]")]
    frames = {"rbi_events.csv": data.events, "event_results.csv": data.results, "event_explorer.csv": explorer, "bank_performance.csv": performance, "event_means.csv": event_means, "volatility_forecasts.csv": data.forecasts, "sas_event_results.csv": primary, "sas_event_means.csv": primary_means}
    paths = {}
    for name, frame in frames.items():
        path = directory / name
        frame.to_csv(path, index=False)
        paths[name] = path
    return paths
