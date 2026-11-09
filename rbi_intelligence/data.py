"""Acquire, preserve and validate the study's policy and market observations.

The default path is offline: rebuild the panel from the committed source snapshots.
Yahoo Close price returns are the primary convention; adjusted-price returns are
retained only for a clearly labelled dividend-adjustment sensitivity analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tempfile
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import zipfile

import numpy as np
import pandas as pd


START_DATE = "2021-01-01"
END_DATE = "2026-01-01"  # Exclusive; the research period ends on 2025-12-31.
EXCHANGE_TIMEZONE = "Asia/Kolkata"
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
BANKS = tuple(symbol for symbol, meta in ASSETS.items() if meta["asset_type"] == "bank")
BENCHMARKS = ("^NSEI", "^NSEBANK")
PRICE_COLUMNS = ("open", "high", "low", "close", "adj_close")
MARKET_COLUMNS = (*PRICE_COLUMNS, "volume")
EVENT_DATES = (
    "2023-02-08", "2023-04-06", "2023-06-08", "2023-08-10", "2023-10-06", "2023-12-08",
    "2024-02-08", "2024-04-05", "2024-06-07", "2024-08-08", "2024-10-09", "2024-12-06",
    "2025-02-07", "2025-04-09", "2025-06-06", "2025-08-06", "2025-10-01", "2025-12-05",
)
NSE_REPAIR_URL = "https://archives.nseindia.com/content/indices/ind_close_all_01022025.csv"
NSE_SPOT_CHECKS = (
    ("2023-08-09", "https://archives.nseindia.com/content/historical/EQUITIES/2023/AUG/cm09AUG2023bhav.csv.zip"),
    ("2025-06-06", "https://archives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20250606_F_0000.csv.zip"),
)


def sha256_file(path: str | Path) -> str:
    """Return a reproducibility checksum, not an authenticity guarantee."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _json_path(root: Path, symbol: str) -> Path:
    return root / "data/raw/yahoo_chart_2021_2025" / (symbol.replace("^", "INDEX_") + ".json")


def _exchange_dates(timestamps: list[int]) -> pd.DatetimeIndex:
    return (
        pd.to_datetime(timestamps, unit="s", utc=True)
        .tz_convert(EXCHANGE_TIMEZONE)
        .normalize()
        .tz_localize(None)
    )


def validate_events(events: pd.DataFrame) -> pd.DataFrame:
    """Validate the frozen 18-event research design and return parsed dates.

    Assertions check the already source-reconciled historical table. They do not
    claim to re-read or authenticate RBI pages on every pipeline execution.
    """
    required = {
        "event_id", "meeting_start", "meeting_end", "event_date", "repo_before",
        "repo_after", "rate_change_bps", "decision", "stance", "source_url",
    }
    if required - set(events.columns):
        raise ValueError(f"Missing policy columns: {sorted(required - set(events.columns))}")
    frame = events.copy()
    for column in ("meeting_start", "meeting_end", "event_date"):
        frame[column] = pd.to_datetime(frame[column], errors="raise")
        if frame[column].isna().any():
            raise ValueError(f"Missing policy date in {column}")
    if len(frame) != 18 or frame["event_id"].duplicated().any() or frame["event_date"].duplicated().any():
        raise ValueError("The frozen study requires exactly 18 unique policy events")
    frame = frame.sort_values("event_date").reset_index(drop=True)
    if frame["event_date"].dt.strftime("%Y-%m-%d").tolist() != list(EVENT_DATES):
        raise ValueError("Policy dates differ from the source-verified research design (including 2025-08-06)")
    expected_ids = ["MPC_" + date[:7].replace("-", "_") for date in EVENT_DATES]
    if frame.event_id.tolist() != expected_ids:
        raise ValueError("Policy event IDs disagree with their verified dates")
    if not ((frame.meeting_start <= frame.event_date) & (frame.meeting_end == frame.event_date)).all():
        raise ValueError("Announcement dates must equal the actual meeting end, after its start")
    august = frame.loc[frame.event_id.eq("MPC_2025_08")]
    if len(august) != 1 or august.iloc[0].meeting_start != pd.Timestamp("2025-08-04"):
        raise ValueError("The August 2025 meeting was held on August 4–6")
    rates = frame[["repo_before", "repo_after", "rate_change_bps"]].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(rates.to_numpy()).all() or (rates[["repo_before", "repo_after"]] <= 0).any().any():
        raise ValueError("Invalid policy rates")
    if not np.allclose((rates.repo_after - rates.repo_before) * 100, rates.rate_change_bps, atol=1e-8):
        raise ValueError("Policy basis-point changes do not reconcile to rate levels")
    if not np.allclose(rates.repo_after.iloc[:-1], rates.repo_before.iloc[1:], atol=1e-8):
        raise ValueError("Policy-rate chain is discontinuous")
    expected_decision = np.select(
        [rates.rate_change_bps.gt(0), rates.rate_change_bps.lt(0)], ["Hike", "Cut"], default="Hold"
    )
    if not np.array_equal(frame.decision.to_numpy(), expected_decision):
        raise ValueError("Policy decision labels disagree with signed rate changes")
    if frame.decision.value_counts().to_dict() != {"Hold": 13, "Cut": 4, "Hike": 1}:
        raise ValueError("Unexpected policy-decision counts")
    if frame.source_url.isna().any() or not frame.source_url.str.match(r"https://(?:www\.)?rbi\.org\.in/(?:Scripts|scripts)/").all():
        raise ValueError("Every policy event needs a specific official RBI source URL")
    if frame.source_url.str.contains("Record/Home", regex=False).any():
        raise ValueError("A generic RBI home/index URL is not an event-specific citation")
    return frame


def load_events(project_root: str | Path) -> pd.DataFrame:
    """Load and validate data/raw/rbi_mpc_events_2023_2025.csv."""
    return validate_events(pd.read_csv(Path(project_root) / "data/raw/rbi_mpc_events_2023_2025.csv"))


def parse_yahoo_chart(payload: dict[str, Any], symbol: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Normalize one preserved Yahoo chart response without repairing its values."""
    if symbol not in ASSETS:
        raise ValueError(f"Unexpected study symbol: {symbol}")
    chart = payload.get("chart", {})
    if chart.get("error") or not chart.get("result"):
        raise ValueError(f"Yahoo returned no usable result for {symbol}: {chart.get('error')}")
    result = chart["result"][0]
    meta = result.get("meta", {})
    if meta.get("symbol") != symbol or meta.get("currency") != "INR":
        raise ValueError(f"Unexpected symbol/currency metadata for {symbol}")
    if meta.get("exchangeTimezoneName") not in {"Asia/Kolkata", "Asia/Calcutta"}:
        raise ValueError(f"Unexpected exchange timezone for {symbol}")
    timestamps = result.get("timestamp", [])
    if not timestamps:
        raise ValueError(f"No timestamped prices for {symbol}")
    quotes = result["indicators"]["quote"][0]
    frame = pd.DataFrame({column: quotes[column] for column in ("open", "high", "low", "close", "volume")})
    frame["adj_close"] = result["indicators"]["adjclose"][0]["adjclose"]
    frame["date"] = _exchange_dates(timestamps)
    frame["symbol"] = symbol
    for column, value in ASSETS[symbol].items():
        frame[column] = value
    frame["source_provider"] = "Yahoo Finance"
    frame["dividends"] = 0.0
    frame["stock_splits"] = 0.0
    actions: list[dict[str, Any]] = []
    for action_type, mapping in result.get("events", {}).items():
        if action_type not in {"dividends", "splits"}:
            raise ValueError(f"Unimplemented action type {action_type} for {symbol}")
        for action in mapping.values():
            day = _exchange_dates([int(action["date"])])[0]
            amount = float(action["amount"]) if action_type == "dividends" else float(action["numerator"]) / float(action["denominator"])
            matches = frame["date"].eq(day)
            if matches.sum() != 1:
                raise ValueError(f"Corporate action {symbol} {day.date()} has no unique market observation")
            frame.loc[matches, "dividends" if action_type == "dividends" else "stock_splits"] = amount
            actions.append({"date": day.strftime("%Y-%m-%d"), "symbol": symbol, "action_type": action_type,
                            "value": amount, "unit": "INR per share (vendor basis)" if action_type == "dividends" else "new shares / old shares",
                            "source_provider": "Yahoo Finance"})
    ordered = ["date", "symbol", "bank_name", "bank_type", "asset_type", *MARKET_COLUMNS,
               "dividends", "stock_splits", "source_provider"]
    return frame[ordered].sort_values("date").reset_index(drop=True), actions


def _verify_retrieval_records(root: Path) -> list[dict[str, Any]]:
    records = json.loads((root / "data/raw/yahoo_retrieval_records.json").read_text())
    if {item["symbol"] for item in records} != set(ASSETS) or len(records) != len(ASSETS):
        raise ValueError("Retrieval records must cover all eight study assets exactly once")
    for record in records:
        if sha256_file(_json_path(root, record["symbol"])) != record["sha256"]:
            raise ValueError(f"Source checksum mismatch for {record['symbol']}")
    return records


def apply_documented_repairs(panel: pd.DataFrame, project_root: str | Path) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Fill the one observed Yahoo gap from a preserved, cited NSE observation.

    This is a source-backed replacement, not interpolation. If Yahoo supplies the
    row after a future refresh it is retained, and its close is compared with NSE.
    """
    root = Path(project_root)
    frame = panel.copy()
    record = json.loads((root / "data/raw/nse_retrieval_record.json").read_text())
    archive_path = root / "data/raw/nse_index_close_2025-02-01.csv"
    if sha256_file(archive_path) != record["sha256"]:
        raise ValueError("NSE repair archive checksum mismatch")
    archive = pd.read_csv(archive_path)
    nse_rows = archive.loc[(archive["Index Name"] == "Nifty Bank") & (archive["Index Date"] == "01-02-2025")]
    if len(nse_rows) != 1:
        raise ValueError("NSE archive lacks the unique Nifty Bank observation for 2025-02-01")
    nse = nse_rows.iloc[0]
    fields = {"open": "Open Index Value", "high": "High Index Value", "low": "Low Index Value",
              "close": "Closing Index Value", "volume": "Volume"}
    replacement = {field: float(nse[source]) for field, source in fields.items()}
    replacement["adj_close"] = replacement["close"]  # A price index, not a dividend-paying security.
    mask = frame.symbol.eq("^NSEBANK") & frame.date.eq(pd.Timestamp("2025-02-01"))
    if mask.sum() != 1:
        raise ValueError("Expected exactly one raw Nifty Bank row on the documented repair date")
    current = frame.loc[mask, list(MARKET_COLUMNS)]
    missing = current.isna().iloc[0]
    if missing.any() and not missing.all():
        raise ValueError("Partial Nifty Bank gap differs from the documented all-field source gap")
    if not missing.any():
        if not np.isclose(float(current.iloc[0]["close"]), replacement["close"], rtol=0, atol=0.02):
            raise ValueError("Refreshed Yahoo Nifty Bank close differs from the documented NSE observation")
        return frame, []
    for field, value in replacement.items():
        frame.loc[mask, field] = value
    frame.loc[mask, "source_provider"] = "NSE official index archive (documented Yahoo gap repair)"
    repair = {"date": "2025-02-01", "symbol": "^NSEBANK", "reason": "Yahoo returned all market fields null on the Budget trading session",
              "before": {field: None for field in MARKET_COLUMNS}, "after": replacement,
              "source_url": NSE_REPAIR_URL, "source_file": "data/raw/nse_index_close_2025-02-01.csv",
              "source_sha256": record["sha256"], "method": "Exact official observation; no interpolation or forward fill"}
    return frame, [repair]


def validate_price_panel(panel: pd.DataFrame, expected_symbols: tuple[str, ...] | None = None) -> None:
    """Reject invalid quotes, unequal observed calendars, and duplicate keys."""
    symbols = expected_symbols if expected_symbols is not None else tuple(ASSETS)
    required = {"date", "symbol", *MARKET_COLUMNS, "dividends", "stock_splits"}
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
        raise ValueError("Missing or non-finite market values; repair from an explicit source before analysis")
    if (panel[list(PRICE_COLUMNS)] <= 0).any().any() or (panel.volume < 0).any():
        raise ValueError("Prices must be positive and volume non-negative")
    if not np.isfinite(panel[["dividends", "stock_splits"]].to_numpy(dtype=float)).all():
        raise ValueError("Non-finite corporate-action fields")
    if (panel[["dividends", "stock_splits"]] < 0).any().any():
        raise ValueError("Negative dividend or split-ratio observations")
    tolerance = 1e-7
    if ((panel.high + tolerance < panel[["open", "close", "low"]].max(axis=1)) |
        (panel.low - tolerance > panel[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC ordering is invalid")
    calendar = set(panel.date.unique())
    gaps = {symbol: sorted(pd.Timestamp(d).strftime("%Y-%m-%d") for d in calendar - set(part.date.unique()))
            for symbol, part in panel.groupby("symbol") if set(part.date.unique()) != calendar}
    if gaps:
        raise ValueError(f"Unequal observed trading calendars; do not compress missing sessions: {gaps}")


def calculate_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """Calculate simple price and adjusted-price returns without filling gaps."""
    frame = panel.sort_values(["symbol", "date"]).copy()
    frame["return"] = frame.groupby("symbol", sort=False)["close"].pct_change(fill_method=None)
    frame["adj_return"] = frame.groupby("symbol", sort=False)["adj_close"].pct_change(fill_method=None)
    return frame.reset_index(drop=True)


def verify_nse_spot_checks(panel: pd.DataFrame, project_root: str | Path) -> dict[str, Any]:
    """Reconcile all six bank closes on two selected dividend-confounded dates.

    NSE bhavcopies show the contemporaneous unadjusted share price. Yahoo Close
    uses the later share basis, so only the observed subsequent split ratios are
    applied. This is a 12-observation check, never an entire-history validation.
    """
    root = Path(project_root)
    directory = root / "data/raw/nse_spot_checks"
    records = json.loads((directory / "retrieval_records.json").read_text())
    if {(record["date"], record["url"]) for record in records} != set(NSE_SPOT_CHECKS):
        raise ValueError("NSE equity spot-check sources are incomplete or unexpected")
    comparisons = []
    for record in records:
        archive_path = root / record["path"]
        if sha256_file(archive_path) != record["sha256"]:
            raise ValueError(f"NSE equity archive checksum mismatch: {record['date']}")
        with zipfile.ZipFile(archive_path) as archive:
            for extracted in record["extracted_files"]:
                file_path = root / extracted
                if file_path.read_bytes() != archive.read(file_path.name):
                    raise ValueError(f"NSE extracted CSV differs from its retained archive: {file_path.name}")
        source = pd.read_csv(root / record["extracted_files"][0])
        date = pd.Timestamp(record["date"])
        for symbol in BANKS:
            exchange_symbol = symbol.removesuffix(".NS")
            if "SYMBOL" in source:  # Historical cash-market bhavcopy format.
                match = source.loc[source.SYMBOL.eq(exchange_symbol) & source.SERIES.eq("EQ")]
                price_column = "CLOSE"
            else:  # UDiFF format used by the later source.
                match = source.loc[source.TckrSymb.eq(exchange_symbol) & source.SctySrs.eq("EQ")]
                price_column = "ClsPric"
            if len(match) != 1:
                raise ValueError(f"Missing or duplicate NSE equity observation: {symbol} {record['date']}")
            nse_close = float(match.iloc[0][price_column])
            future_splits = panel.loc[panel.symbol.eq(symbol) & panel.date.gt(date) & panel.stock_splits.gt(0), "stock_splits"]
            factor = float(future_splits.prod())
            comparable = nse_close / factor
            yahoo_row = panel.loc[panel.symbol.eq(symbol) & panel.date.eq(date)]
            if len(yahoo_row) != 1:
                raise ValueError(f"Missing or duplicate Yahoo spot-check observation: {symbol} {record['date']}")
            yahoo_close = float(yahoo_row.close.iloc[0])
            difference = yahoo_close - comparable
            comparisons.append({"date": record["date"], "symbol": symbol, "nse_unadjusted_close": nse_close,
                                "subsequent_vendor_split_ratio": factor, "nse_close_on_vendor_share_basis": comparable,
                                "yahoo_close": yahoo_close, "difference_inr": difference,
                                "within_0_02_inr": abs(difference) <= 0.02, "source_url": record["url"]})
    frame = pd.DataFrame(comparisons).sort_values(["date", "symbol"])
    if len(frame) != 12 or not frame.within_0_02_inr.all():
        raise ValueError("NSE bank-price spot checks failed; investigate rather than silently changing prices")
    frame.to_csv(directory / "price_comparisons.csv", index=False, float_format="%.15g")
    return {"bank_price_checks": int(len(frame)), "all_within_0_02_inr": True,
            "maximum_absolute_difference_inr": float(frame.difference_inr.abs().max()),
            "comparison_file": "data/raw/nse_spot_checks/price_comparisons.csv",
            "scope": "Six banks on two selected dates. Does not establish accuracy for every daily observation.",
            "adjustment": "Contemporaneous NSE price divided by subsequent vendor-reported split ratios; no dividend adjustment applied."}


def _download(url: str, path: Path) -> dict[str, Any]:
    observed = datetime.now(timezone.utc).isoformat()
    request = Request(url, headers={"User-Agent": "RBI-Event-Study/1.0 (academic research)"})
    with urlopen(request, timeout=40) as response:
        body = response.read()
        status = response.status
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {"url": url, "retrieved_at_utc": observed, "http_status": status,
            "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
            "retrieval_client": "Python urllib.request"}


def _fetch_source_snapshots_in_place(project_root: str | Path) -> None:
    """Acquire into an isolated staging directory, never the active snapshot."""
    root = Path(project_root)
    parameters = {"period1": 1609459200, "period2": 1767225600, "interval": "1d",
                  "events": "div,splits", "includeAdjustedClose": "true"}
    records = []
    for symbol in ASSETS:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(symbol, safe="") + "?" + urlencode(parameters)
        path = _json_path(root, symbol)
        record = _download(url, path)
        payload = json.loads(path.read_text())
        parse_yahoo_chart(payload, symbol)  # Fail on vendor errors before recording a usable snapshot.
        result = payload["chart"]["result"][0]
        record.update({"symbol": symbol, "path": str(path.relative_to(root)),
                       "metadata": {key: result["meta"].get(key) for key in
                                    ("currency", "symbol", "exchangeName", "fullExchangeName", "instrumentType", "exchangeTimezoneName")},
                       "timestamp_count": len(result["timestamp"]),
                       "action_counts": {key: len(value) for key, value in result.get("events", {}).items()}})
        records.append(record)
    _write_json(root / "data/raw/yahoo_retrieval_records.json", records)
    nse_path = root / "data/raw/nse_index_close_2025-02-01.csv"
    nse_record = _download(NSE_REPAIR_URL, nse_path)
    nse_record["path"] = str(nse_path.relative_to(root))
    _write_json(root / "data/raw/nse_retrieval_record.json", nse_record)
    equity_records = []
    spot_dir = root / "data/raw/nse_spot_checks"
    for date, url in NSE_SPOT_CHECKS:
        path = spot_dir / (date + ".zip")
        record = _download(url, path)
        extracted_files = []
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith(".csv"):
                    extracted = spot_dir / Path(name).name
                    extracted.write_bytes(archive.read(name))
                    extracted_files.append(str(extracted.relative_to(root)))
        record.update({"date": date, "path": str(path.relative_to(root)), "extracted_files": extracted_files})
        equity_records.append(record)
    _write_json(spot_dir / "retrieval_records.json", equity_records)


def fetch_source_snapshots(project_root: str | Path) -> None:
    """Refresh public sources transactionally after validating the new snapshot.

    The default run never calls this function. A failed request or validation
    leaves the previous source snapshot intact. Successful refreshes change the
    data vintage and require a complete downstream rerun.
    """
    root = Path(project_root).resolve()
    raw = root / "data/raw"
    (root / "data").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="market-refresh-", dir=root / "data") as temporary:
        stage = Path(temporary)
        shutil.copytree(raw, stage / "data/raw")
        _fetch_source_snapshots_in_place(stage)
        build_market_panel(stage)  # Source checks, documented repair and NSE comparisons must all pass.
        backup = stage / "previous_raw"
        raw.rename(backup)
        try:
            (stage / "data/raw").rename(raw)
        except BaseException:
            backup.rename(raw)
            raise


def build_market_panel(project_root: str | Path) -> pd.DataFrame:
    """Rebuild and save a validated panel and provenance manifest from snapshots."""
    root = Path(project_root)
    records = _verify_retrieval_records(root)
    events = load_events(root)
    parts, actions = [], []
    for symbol in ASSETS:
        frame, symbol_actions = parse_yahoo_chart(json.loads(_json_path(root, symbol).read_text()), symbol)
        parts.append(frame)
        actions.extend(symbol_actions)
    raw = pd.concat(parts, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    raw_path = root / "data/raw/market_prices_2021_2025.csv"
    raw.to_csv(raw_path, index=False, date_format="%Y-%m-%d", float_format="%.15g")
    fixed, repairs = apply_documented_repairs(raw, root)
    validate_price_panel(fixed)
    panel = calculate_returns(fixed)
    equity_check = verify_nse_spot_checks(panel, root)
    first_rows = panel.groupby("symbol", sort=False).head(1).index
    non_initial = panel.index.difference(first_rows)
    if panel.loc[non_initial, ["return", "adj_return"]].isna().any().any():
        raise ValueError("A non-initial return is missing; a session gap must not be silently bridged")
    if not np.isfinite(panel.loc[non_initial, ["return", "adj_return"]].to_numpy()).all():
        raise ValueError("Non-finite calculated returns")
    if not set(events.event_date).issubset(set(panel.date)):
        raise ValueError("At least one verified policy announcement is absent from the market calendar")
    output = root / "data/processed/market_panel.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False, date_format="%Y-%m-%d", float_format="%.15g")
    action_frame = pd.DataFrame(actions).sort_values(["date", "symbol", "action_type"])
    action_path = root / "data/raw/corporate_actions_2021_2025.csv"
    action_frame.to_csv(action_path, index=False, float_format="%.15g")
    _write_json(root / "data/raw/market_repairs.json", repairs)
    split_rows = panel.loc[panel.stock_splits.ne(0), ["date", "symbol", "stock_splits", "return", "adj_return"]].copy()
    split_rows["date"] = split_rows.date.dt.strftime("%Y-%m-%d")
    outliers = panel.loc[panel["return"].abs().gt(0.10), ["date", "symbol", "return", "adj_return"]].copy()
    outliers["date"] = outliers.date.dt.strftime("%Y-%m-%d")
    dividend_overlap = []
    calendar = sorted(panel.date.unique())
    for event in events.itertuples():
        position = calendar.index(event.event_date)
        dates = set(calendar[max(0, position - 5):position + 6])
        matching = panel.loc[panel.date.isin(dates) & panel.dividends.gt(0), ["date", "symbol", "dividends"]]
        for action in matching.itertuples():
            dividend_overlap.append({"event_id": event.event_id, "event_date": event.event_date.strftime("%Y-%m-%d"),
                                     "ex_date": action.date.strftime("%Y-%m-%d"), "symbol": action.symbol,
                                     "dividend": float(action.dividends), "relative_trading_day": calendar.index(action.date) - position})
    nse = pd.read_csv(root / "data/raw/nse_index_close_2025-02-01.csv")
    nse_nifty = float(nse.loc[nse["Index Name"].eq("Nifty 50"), "Closing Index Value"].iloc[0])
    yahoo_nifty = float(raw.loc[raw.symbol.eq("^NSEI") & raw.date.eq(pd.Timestamp("2025-02-01")), "close"].iloc[0])
    diagnostics = {
        "split_date_returns": split_rows.to_dict("records"),
        "absolute_price_return_over_10_percent": outliers.to_dict("records"),
        "outlier_handling": "Flagged and retained; not winsorized or automatically declared erroneous. No exhaustive independent verification claimed.",
        "dividends_in_widest_event_windows": dividend_overlap,
        "independent_nse_spot_check": {"date": "2025-02-01", "symbol": "^NSEI", "yahoo_close": yahoo_nifty,
                                        "nse_close": nse_nifty, "difference_points": yahoo_nifty - nse_nifty,
                                        "within_0_02_points": bool(abs(yahoo_nifty - nse_nifty) <= 0.02)},
        "independent_nse_equity_spot_checks": equity_check,
        "calendar_validation": "All eight assets share the same observed calendar after the one documented repair. A date omitted jointly by all vendor series cannot be detected by this check; no full independent NSE calendar audit claimed.",
        "adjustment_policy": "Vendor split-adjusted Close simple price returns primary. Adj Close simple returns retained for dividend sensitivity only; Nifty benchmarks are price indices, not matched total-return indices.",
    }
    _write_json(root / "data/raw/market_diagnostics.json", diagnostics)
    paths = [raw_path, action_path, output, root / "data/raw/market_repairs.json", root / "data/raw/market_diagnostics.json",
             root / "data/raw/rbi_mpc_events_2023_2025.csv", root / "data/raw/yahoo_retrieval_records.json",
             root / "data/raw/nse_index_close_2025-02-01.csv", root / "data/raw/nse_retrieval_record.json"]
    paths.extend(sorted((root / "data/raw/nse_spot_checks").iterdir()))
    manifest = {
        "manifest_version": 1, "data_provider": "Yahoo Finance chart endpoint; one explicitly recorded NSE official index-archive repair",
        "purpose": "Historical academic event-study snapshot, not a licensed live market-data service",
        "acquisition": {"requested_start_inclusive": START_DATE, "requested_end_exclusive": END_DATE,
                        "interval": "1d", "events": "div,splits", "includeAdjustedClose": True,
                        "exchange_timezone": EXCHANGE_TIMEZONE, "retrieved_at_utc_by_asset":
                        {record["symbol"]: record["retrieved_at_utc"] for record in records}},
        "software_at_panel_build": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "return_convention": diagnostics["adjustment_policy"],
        "calendar_check": diagnostics["calendar_validation"],
        "rows": int(len(panel)), "unique_market_dates": int(panel.date.nunique()),
        "rows_by_symbol": {symbol: {"rows": int(len(part)), "return_observations": int(part["return"].notna().sum()),
                                    "first_date": part.date.min().strftime("%Y-%m-%d"), "last_date": part.date.max().strftime("%Y-%m-%d"),
                                    "raw_missing_market_rows": int(raw.loc[raw.symbol.eq(symbol), list(MARKET_COLUMNS)].isna().any(axis=1).sum())}
                           for symbol, part in panel.groupby("symbol")},
        "source_responses": [{key: value for key, value in record.items() if key != "metadata"} for record in records],
        "corporate_actions": {"dividend_records": sum(a["action_type"] == "dividends" for a in actions),
                              "split_records": sum(a["action_type"] == "splits" for a in actions)},
        "repair_count": len(repairs), "excluded_price_rows": 0, "forward_filled_values": 0,
        "large_return_flags": int(len(outliers)),
        "independent_bank_price_checks": equity_check,
        "files_sha256": {str(path.relative_to(root)): sha256_file(path) for path in paths},
        "verification_limits": ["Checksums prove which bytes were used, not correctness of every vendor price.",
                                "NSE verification consists of one gap repair, one Nifty 50 close spot-check, and 12 bank-close spot-checks; it is not an entire-history reconciliation.",
                                "The source snapshot may reflect vendor corrections and corporate actions known at acquisition time; point-in-time vendor vintage data are unavailable."]
    }
    _write_json(root / "data/raw/market_manifest.json", manifest)
    return panel


def load_market_panel(project_root: str | Path, refresh: bool = False) -> pd.DataFrame:
    """Load verified snapshots, optionally refresh them explicitly, and rebuild."""
    if refresh:
        fetch_source_snapshots(project_root)
    return build_market_panel(project_root)
