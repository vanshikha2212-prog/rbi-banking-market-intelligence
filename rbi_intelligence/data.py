"""Load and validate the frozen RBI/NSE research snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

import numpy as np
import pandas as pd


START_DATE = "2015-01-01"
END_DATE = "2026-01-01"
ASSETS = {
    "HDFCBANK.NS": {"bank_name": "HDFC Bank", "bank_type": "Private", "asset_type": "bank"},
    "ICICIBANK.NS": {"bank_name": "ICICI Bank", "bank_type": "Private", "asset_type": "bank"},
    "AXISBANK.NS": {"bank_name": "Axis Bank", "bank_type": "Private", "asset_type": "bank"},
    "SBIN.NS": {"bank_name": "State Bank of India", "bank_type": "Public", "asset_type": "bank"},
    "BANKBARODA.NS": {"bank_name": "Bank of Baroda", "bank_type": "Public", "asset_type": "bank"},
    "CANBK.NS": {"bank_name": "Canara Bank", "bank_type": "Public", "asset_type": "bank"},
    "^NSEI": {"bank_name": "Nifty 50", "bank_type": "", "asset_type": "benchmark"},
    "^NSEBANK": {"bank_name": "Nifty Bank", "bank_type": "", "asset_type": "benchmark"},
}
BANKS = tuple(symbol for symbol, metadata in ASSETS.items() if metadata["asset_type"] == "bank")
BENCHMARKS = ("^NSEI", "^NSEBANK")
PRICE_COLUMNS = ("open", "high", "low", "close")
MARKET_COLUMNS = (*PRICE_COLUMNS, "volume")
EVENT_FILE = "data/raw/rbi_mpc_events_2016_2025.csv"
PRICE_FILE = "data/raw/nse_market_prices_2015_2025.csv"
RETRIEVAL_FILE = "data/raw/nse_market_retrieval_manifest.json"


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def validate_events(events: pd.DataFrame) -> pd.DataFrame:
    required = {
        "event_id", "meeting_start", "meeting_end", "event_date", "repo_before",
        "repo_after", "rate_change_bps", "decision", "stance", "source_url",
    }
    if required - set(events):
        raise ValueError(f"Missing policy columns: {sorted(required - set(events))}")
    frame = events.copy()
    for column in ("meeting_start", "meeting_end", "event_date"):
        frame[column] = pd.to_datetime(frame[column], errors="raise")
    if len(frame) != 57 or frame.event_id.duplicated().any() or frame.event_date.duplicated().any():
        raise ValueError("The frozen extended study requires exactly 57 unique repo-rate announcement events")
    frame = frame.sort_values("event_date").reset_index(drop=True)
    if frame.event_date.min() != pd.Timestamp("2016-10-04") or frame.event_date.max() != pd.Timestamp("2025-12-05"):
        raise ValueError("Extended MPC coverage must run from 2016-10-04 through 2025-12-05")
    expected_ids = "MPC_" + frame.event_date.dt.strftime("%Y_%m")
    if not frame.event_id.eq(expected_ids).all():
        raise ValueError("Policy event IDs disagree with verified announcement months")
    if not ((frame.meeting_start <= frame.event_date) & frame.meeting_end.eq(frame.event_date)).all():
        raise ValueError("Announcement dates must equal the actual meeting end")
    rates = frame[["repo_before", "repo_after", "rate_change_bps"]].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(rates.to_numpy()).all() or (rates[["repo_before", "repo_after"]] <= 0).any().any():
        raise ValueError("Invalid policy rates")
    if not np.allclose((rates.repo_after - rates.repo_before) * 100, rates.rate_change_bps, atol=1e-8):
        raise ValueError("Policy basis-point changes do not reconcile to rate levels")
    if not np.allclose(rates.repo_after.iloc[:-1], rates.repo_before.iloc[1:], atol=1e-8):
        raise ValueError("Policy-rate chain is discontinuous")
    expected = np.select([rates.rate_change_bps.gt(0), rates.rate_change_bps.lt(0)], ["Hike", "Cut"], default="Hold")
    if not np.array_equal(frame.decision.to_numpy(), expected):
        raise ValueError("Policy decision labels disagree with signed rate changes")
    counts = frame.decision.value_counts().to_dict()
    if counts != {"Hold": 36, "Cut": 13, "Hike": 8}:
        raise ValueError(f"Unexpected extended policy-decision counts: {counts}")
    official = frame.source_url.astype(str).str.match(r"https://(?:www\.)?rbi\.org\.in/(?:Scripts|scripts)/")
    if not official.all() or frame.source_url.astype(str).str.contains("Record/Home", regex=False).any():
        raise ValueError("Every policy event needs a specific official RBI source URL")
    return frame


def load_events(project_root: str | Path) -> pd.DataFrame:
    return validate_events(pd.read_csv(Path(project_root) / EVENT_FILE))


def validate_price_panel(panel: pd.DataFrame, expected_symbols: tuple[str, ...] | None = None) -> None:
    symbols = expected_symbols if expected_symbols is not None else tuple(ASSETS)
    required = {"date", "symbol", *MARKET_COLUMNS, "previous_close"}
    if required - set(panel):
        raise ValueError(f"Missing market columns: {sorted(required - set(panel))}")
    if set(panel.symbol.unique()) != set(symbols):
        raise ValueError("Market panel does not contain the expected asset universe")
    if panel.date.isna().any() or panel.duplicated(["date", "symbol"]).any():
        raise ValueError("Missing dates or duplicate date/symbol observations")
    if not pd.api.types.is_datetime64_any_dtype(panel.date):
        raise ValueError("Market dates must be parsed exchange-local calendar dates")
    if not ((panel.date >= pd.Timestamp(START_DATE)) & (panel.date < pd.Timestamp(END_DATE))).all():
        raise ValueError("Market dates fall outside the frozen research period")
    values = panel[list(MARKET_COLUMNS)].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Missing or non-finite market values")
    if (panel[list(PRICE_COLUMNS)] <= 0).any().any() or (panel.volume < 0).any():
        raise ValueError("Prices must be positive and volume non-negative")
    tolerance = 1e-7
    if ((panel.high + tolerance < panel[["open", "close", "low"]].max(axis=1)) |
        (panel.low - tolerance > panel[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC ordering is invalid")
    banks = panel.symbol.isin(BANKS)
    if panel.loc[banks, "previous_close"].isna().any() or (panel.loc[banks, "previous_close"] <= 0).any():
        raise ValueError("Every official NSE bank row needs a positive previous close")
    calendar = set(panel.date.unique())
    gaps = {symbol: sorted(calendar - set(part.date.unique())) for symbol, part in panel.groupby("symbol") if set(part.date) != calendar}
    if gaps:
        raise ValueError(f"Unequal observed trading calendars; do not compress missing sessions: {gaps}")


def calculate_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Use NSE previous close for banks and consecutive closes for indices."""
    frame = panel.sort_values(["symbol", "date"]).copy()
    consecutive = frame.groupby("symbol", sort=False).close.pct_change(fill_method=None)
    bank_mask = frame.symbol.isin(BANKS)
    frame["return"] = consecutive
    frame.loc[bank_mask, "return"] = frame.loc[bank_mask, "close"] / frame.loc[bank_mask, "previous_close"] - 1
    first = frame.groupby("symbol", sort=False).head(1).index
    frame.loc[first, "return"] = np.nan
    frame["adj_close"] = frame["close"]
    frame["adj_return"] = frame["return"]
    frame["dividends"] = 0.0
    frame["stock_splits"] = 0.0
    return frame.reset_index(drop=True)


def build_market_panel(project_root: str | Path) -> pd.DataFrame:
    root = Path(project_root)
    price_path = root / PRICE_FILE
    retrieval_path = root / RETRIEVAL_FILE
    if not price_path.is_file() or not retrieval_path.is_file():
        raise FileNotFoundError("Official NSE snapshot is absent; run python scripts/fetch_nse_history.py")
    retrieval = json.loads(retrieval_path.read_text(encoding="utf-8"))
    observed_hash = sha256_file(price_path)
    if observed_hash != retrieval.get("consolidated_csv_sha256"):
        raise ValueError("NSE consolidated snapshot checksum mismatch")
    frame = pd.read_csv(price_path, parse_dates=["date"])
    for symbol, metadata in ASSETS.items():
        mask = frame.symbol.eq(symbol)
        for column, value in metadata.items():
            frame.loc[mask, column] = value
    validate_price_panel(frame)
    panel = calculate_returns(frame)
    first = panel.groupby("symbol", sort=False).head(1).index
    if panel.drop(index=first)["return"].isna().any() or not np.isfinite(panel.drop(index=first)["return"]).all():
        raise ValueError("A non-initial return is missing or non-finite")
    events = load_events(root)
    if not set(events.event_date).issubset(set(panel.date)):
        missing = sorted(set(events.event_date) - set(panel.date))
        raise ValueError(f"Verified policy announcements absent from the NSE calendar: {missing}")
    output = root / "data/processed/market_panel.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False, date_format="%Y-%m-%d", float_format="%.15g")
    diagnostics = {
        "provider": "National Stock Exchange of India official daily archives",
        "return_convention": "NSE close / NSE previous close - 1 for banks; consecutive official closes for indices",
        "corporate_action_handling": "NSE previous-close bases are used; no synthetic price adjustment or forward fill",
        "rows": len(panel), "trading_sessions": int(panel.date.nunique()),
        "absolute_return_over_10_percent": int(panel["return"].abs().gt(.10).sum()),
        "forward_filled_values": 0,
    }
    _write_json(root / "data/raw/market_diagnostics.json", diagnostics)
    manifest = {
        "manifest_version": 3, "data_provider": diagnostics["provider"],
        "purpose": "Historical academic event study; not a live market-data service",
        "acquisition": retrieval["retrieval_scope"], "source_file_count": len(retrieval.get("source_files", [])),
        "consolidated_source_sha256": observed_hash,
        "software_at_panel_build": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "return_convention": diagnostics["return_convention"],
        "rows": int(len(panel)), "unique_market_dates": int(panel.date.nunique()),
        "rows_by_symbol": {symbol: int(len(part)) for symbol, part in panel.groupby("symbol")},
        "files_sha256": {PRICE_FILE: observed_hash, RETRIEVAL_FILE: sha256_file(retrieval_path), EVENT_FILE: sha256_file(root / EVENT_FILE)},
        "verification_limits": [
            "Hashes identify the official daily bytes used but do not independently certify every exchange observation.",
            "Daily prices are historical end-of-day observations, not intraday announcement prices.",
            "Previous close handles exchange corporate-action bases; dividends remain part of price-return reactions.",
        ],
    }
    _write_json(root / "data/raw/market_manifest.json", manifest)
    return panel


def fetch_source_snapshots(project_root: str | Path) -> None:
    root = Path(project_root).resolve()
    subprocess.run([sys.executable, str(root / "scripts/fetch_nse_history.py")], cwd=root, check=True)


def load_market_panel(project_root: str | Path, refresh: bool = False) -> pd.DataFrame:
    if refresh:
        fetch_source_snapshots(project_root)
    return build_market_panel(project_root)
