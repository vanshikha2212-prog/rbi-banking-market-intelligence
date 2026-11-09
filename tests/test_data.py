import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rbi_intelligence.data import calculate_returns, load_events, sha256_file, validate_events, validate_price_panel


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def small_panel():
    rows = []
    for symbol in ("BANK_A", "INDEX"):
        for date, close in zip(pd.to_datetime(["2025-01-29", "2025-01-30", "2025-01-31"]), [100.0, 101.0, 102.0]):
            rows.append({"date": date, "symbol": symbol, "open": close, "high": close + 1,
                         "low": close - 1, "close": close, "previous_close": close - 1,
                         "volume": 10.0})
    return pd.DataFrame(rows)


def test_extended_policy_registry_has_verified_balance_and_dates():
    events = load_events(ROOT)
    assert len(events) == 57
    assert events.decision.value_counts().to_dict() == {"Hold": 36, "Cut": 13, "Hike": 8}
    assert events.event_date.min() == pd.Timestamp("2016-10-04")
    assert events.event_date.max() == pd.Timestamp("2025-12-05")
    assert events.source_url.str.contains("rbi.org.in", case=False).all()


def test_actual_august_2025_announcement_replaces_superseded_schedule():
    events = load_events(ROOT)
    august = events.loc[events.event_id.eq("MPC_2025_08")].iloc[0]
    assert august.event_date == pd.Timestamp("2025-08-06")
    assert august.meeting_start == pd.Timestamp("2025-08-04")
    incorrect = events.copy()
    incorrect.loc[incorrect.event_id.eq("MPC_2025_08"), "event_date"] = pd.Timestamp("2025-08-07")
    with pytest.raises(ValueError):
        validate_events(incorrect)


def test_rate_decision_and_chain_must_reconcile():
    events = load_events(ROOT)
    events.loc[events.event_id.eq("MPC_2022_05"), "decision"] = "Hold"
    with pytest.raises(ValueError, match="decision labels"):
        validate_events(events)
    events = load_events(ROOT)
    events.loc[10, "repo_before"] = 9
    with pytest.raises(ValueError):
        validate_events(events)


def test_nse_previous_close_prevents_split_jump_from_becoming_return():
    panel = pd.DataFrame({
        "date": pd.to_datetime(["2024-05-10", "2024-05-13"]), "symbol": ["CANBK.NS"] * 2,
        "open": [500, 100], "high": [505, 103], "low": [495, 98], "close": [500, 102],
        "previous_close": [498, 100], "volume": [10, 10],
    })
    result = calculate_returns(panel)
    assert pd.isna(result.loc[0, "return"])
    assert result.loc[1, "return"] == pytest.approx(.02)
    assert result.loc[1, "return"] != pytest.approx(102 / 500 - 1)


def test_cross_asset_calendar_gap_is_rejected(small_panel):
    with pytest.raises(ValueError, match="Unequal observed trading calendars"):
        validate_price_panel(small_panel.drop(index=4), expected_symbols=("BANK_A", "INDEX"))


def test_duplicate_nonpositive_and_ohlc_errors_are_rejected(small_panel):
    with pytest.raises(ValueError, match="duplicate"):
        validate_price_panel(pd.concat([small_panel, small_panel.iloc[[0]]]), expected_symbols=("BANK_A", "INDEX"))
    invalid = small_panel.copy()
    invalid.loc[0, "close"] = 0
    with pytest.raises(ValueError, match="positive"):
        validate_price_panel(invalid, expected_symbols=("BANK_A", "INDEX"))
    invalid = small_panel.copy()
    invalid.loc[0, "close"] = 500
    with pytest.raises(ValueError, match="OHLC"):
        validate_price_panel(invalid, expected_symbols=("BANK_A", "INDEX"))


def test_consolidated_nse_snapshot_matches_retrieval_manifest():
    path = ROOT / "data/raw/nse_market_prices_2015_2025.csv"
    manifest_path = ROOT / "data/raw/nse_market_retrieval_manifest.json"
    if not path.exists() or not manifest_path.exists():
        pytest.skip("Official NSE snapshot not fetched")
    manifest = json.loads(manifest_path.read_text())
    assert sha256_file(path) == manifest["consolidated_csv_sha256"]
    assert manifest["trading_sessions"] >= 2700
