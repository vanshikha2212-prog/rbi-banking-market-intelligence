"""Regression guards for consequential data errors found in the project audit."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rbi_intelligence.data import (
    apply_documented_repairs,
    calculate_returns,
    fetch_source_snapshots,
    load_events,
    parse_yahoo_chart,
    sha256_file,
    validate_events,
    validate_price_panel,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def small_panel():
    rows = []
    for symbol in ("BANK_A", "INDEX"):
        for date, close in zip(pd.to_datetime(["2025-01-29", "2025-01-30", "2025-01-31"]), [100.0, 101.0, 102.0]):
            rows.append({"date": date, "symbol": symbol, "open": close, "high": close + 1,
                         "low": close - 1, "close": close, "adj_close": close,
                         "volume": 10.0, "dividends": 0.0, "stock_splits": 0.0})
    return pd.DataFrame(rows)


def test_actual_august_2025_announcement_replaces_superseded_schedule():
    events = load_events(ROOT)
    august = events.loc[events.event_id.eq("MPC_2025_08")].iloc[0]
    assert august.event_date == pd.Timestamp("2025-08-06")
    assert august.meeting_start == pd.Timestamp("2025-08-04")
    assert august.meeting_end == pd.Timestamp("2025-08-06")
    assert "prid=60957" in august.source_url
    incorrect = events.copy()
    incorrect.loc[incorrect.event_id.eq("MPC_2025_08"), "event_date"] = pd.Timestamp("2025-08-07")
    with pytest.raises(ValueError, match="source-verified"):
        validate_events(incorrect)


def test_rate_decision_must_match_signed_basis_points():
    events = load_events(ROOT)
    events.loc[events.event_id.eq("MPC_2025_06"), "decision"] = "Hold"
    with pytest.raises(ValueError, match="decision labels"):
        validate_events(events)


def test_generic_homepage_does_not_count_as_event_source():
    events = load_events(ROOT)
    events.loc[0, "source_url"] = "https://www.rbi.org.in/scripts/BS_ViewBulletin.aspx/Record/Home.aspx"
    with pytest.raises(ValueError, match="generic RBI"):
        validate_events(events)


def test_missing_policy_source_is_rejected():
    events = load_events(ROOT)
    events.loc[0, "source_url"] = np.nan
    with pytest.raises(ValueError, match="specific official RBI"):
        validate_events(events)


def test_returns_are_not_forward_filled_across_missing_prices():
    prices = pd.DataFrame({"date": pd.date_range("2025-01-27", periods=4),
                           "symbol": ["A"] * 4, "close": [100.0, np.nan, 102.0, 103.0],
                           "adj_close": [100.0, np.nan, 102.0, 103.0]})
    result = calculate_returns(prices)
    assert result["return"].iloc[:3].isna().all()
    assert result["return"].iloc[3] == pytest.approx(103 / 102 - 1)


def test_cross_asset_calendar_gap_is_rejected(small_panel):
    incomplete = small_panel.drop(index=4)
    with pytest.raises(ValueError, match="Unequal observed trading calendars"):
        validate_price_panel(incomplete, expected_symbols=("BANK_A", "INDEX"))


def test_duplicate_keys_cannot_multiply_joined_observations(small_panel):
    duplicate = pd.concat([small_panel, small_panel.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        validate_price_panel(duplicate, expected_symbols=("BANK_A", "INDEX"))


def test_partial_ohlc_missingness_is_not_silently_dropped(small_panel):
    small_panel.loc[0, "high"] = np.nan
    with pytest.raises(ValueError, match="Missing or non-finite"):
        validate_price_panel(small_panel, expected_symbols=("BANK_A", "INDEX"))


def test_nonpositive_prices_and_inconsistent_ohlc_are_rejected(small_panel):
    invalid = small_panel.copy()
    invalid.loc[0, "close"] = 0
    with pytest.raises(ValueError, match="positive"):
        validate_price_panel(invalid, expected_symbols=("BANK_A", "INDEX"))
    invalid = small_panel.copy()
    invalid.loc[0, "close"] = 500
    with pytest.raises(ValueError, match="OHLC"):
        validate_price_panel(invalid, expected_symbols=("BANK_A", "INDEX"))


def test_nse_budget_session_repair_is_observed_price_not_zero_return():
    payload = json.loads((ROOT / "data/raw/yahoo_chart_2021_2025/INDEX_NSEBANK.json").read_text())
    raw, _ = parse_yahoo_chart(payload, "^NSEBANK")
    date = pd.Timestamp("2025-02-01")
    assert raw.loc[raw.date.eq(date), "close"].isna().all()
    fixed, ledger = apply_documented_repairs(raw, ROOT)
    row = fixed.loc[fixed.date.eq(date)].iloc[0]
    assert row.close == pytest.approx(49506.95)
    assert row.open == pytest.approx(49592.55)
    assert row.high == pytest.approx(50009.50)
    assert row.low == pytest.approx(48925.45)
    assert ledger[0]["before"]["close"] is None
    assert "archives.nseindia.com" in ledger[0]["source_url"]
    returns = calculate_returns(fixed)
    previous = returns.loc[returns.date.eq(pd.Timestamp("2025-01-31")), "close"].iloc[0]
    assert returns.loc[returns.date.eq(date), "return"].iloc[0] == pytest.approx(49506.95 / previous - 1)
    assert returns.loc[returns.date.eq(date), "return"].iloc[0] != 0.0


def test_raw_source_hashes_match_preserved_bytes():
    records = json.loads((ROOT / "data/raw/yahoo_retrieval_records.json").read_text())
    for record in records:
        assert sha256_file(ROOT / record["path"]) == record["sha256"]
    record = json.loads((ROOT / "data/raw/nse_retrieval_record.json").read_text())
    assert sha256_file(ROOT / record["path"]) == record["sha256"]


def test_dividend_on_cut_announcement_is_preserved_for_sensitivity():
    payload = json.loads((ROOT / "data/raw/yahoo_chart_2021_2025/BANKBARODA.NS.json").read_text())
    prices, _ = parse_yahoo_chart(payload, "BANKBARODA.NS")
    row = prices.loc[prices.date.eq(pd.Timestamp("2025-06-06"))].iloc[0]
    assert row.dividends == pytest.approx(8.35)
    assert row.adj_close != row.close


def test_source_dates_use_exchange_calendar_not_utc_clock_day():
    payload = json.loads((ROOT / "data/raw/yahoo_chart_2021_2025/HDFCBANK.NS.json").read_text())
    # A synthetic timestamp near local midnight isolates timezone conversion.
    source = payload["chart"]["result"][0]
    source["timestamp"] = [int(pd.Timestamp("2025-01-01T20:00:00Z").timestamp())]
    source["indicators"]["quote"] = [{key: [100.0] for key in ("open", "high", "low", "close", "volume")}]
    source["indicators"]["adjclose"] = [{"adjclose": [100.0]}]
    source["events"] = {}
    parsed, _ = parse_yahoo_chart(payload, "HDFCBANK.NS")
    assert parsed.date.iloc[0] == pd.Timestamp("2025-01-02")


def test_failed_refresh_preserves_previous_snapshot(tmp_path, monkeypatch):
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    snapshot = raw / "previous_source.json"
    snapshot.write_bytes(b'{"verified": true}')

    def failed_download(stage):
        (stage / "data/raw/previous_source.json").write_bytes(b"partial download")
        raise OSError("Simulated network interruption")

    monkeypatch.setattr("rbi_intelligence.data._fetch_source_snapshots_in_place", failed_download)
    with pytest.raises(OSError, match="network interruption"):
        fetch_source_snapshots(tmp_path)
    assert snapshot.read_bytes() == b'{"verified": true}'
    assert list(raw.iterdir()) == [snapshot]
