import numpy as np
import pandas as pd
import pytest

from rbi_intelligence.event_study import run_event_study


def market_fixture():
    dates = pd.bdate_range("2021-01-01", periods=400)
    market = .003 * np.sin(np.arange(400) / 7) + .001 * np.cos(np.arange(400) / 3)
    bank = .0002 + 1.4 * market
    bank[299:302] += [.01, -.02, .03]
    frames = []
    for symbol, series, kind in (("BANK", bank, "Private"), ("^NSEI", market, ""), ("^NSEBANK", market, "")):
        frames.append(pd.DataFrame({"date": dates, "symbol": symbol, "return": series,
                                    "bank_name": symbol, "bank_type": kind}))
    events = pd.DataFrame({"event_id": ["E1"], "event_date": [dates[300]], "decision": ["Hold"]})
    return pd.concat(frames, ignore_index=True), events, dates


def test_common_inclusive_estimation_window_and_known_abnormal_returns():
    panel, events, dates = market_fixture()
    result = run_event_study(panel, events)
    assert len(result) == 8
    assert result.n_estimation.eq(250).all()
    assert result.estimation_start.eq(dates[45]).all()  # event -255
    assert result.estimation_end.eq(dates[294]).all()   # event -6, inclusive
    assert np.allclose(result.alpha, .0002)
    assert np.allclose(result.beta, 1.4)
    assert np.allclose(result.loc[result.window.eq("[-1,+1]"), "car"], .02)
    assert np.allclose(result.loc[result.window.eq("[0,+1]"), "car"], .01)
    assert result.groupby("window").n_event.first().to_dict() == {
        "[-1,+1]": 3, "[-2,+2]": 5, "[-5,+5]": 11, "[0,+1]": 2,
    }


def test_missing_bank_day_is_not_silently_removed_from_calendar():
    panel, events, dates = market_fixture()
    panel = panel[~(panel.symbol.eq("BANK") & panel.date.eq(dates[299]))]
    with pytest.raises(ValueError, match="Missing/non-finite event returns"):
        run_event_study(panel, events)


def test_missing_estimation_return_and_duplicate_rows_fail_explicitly():
    panel, events, dates = market_fixture()
    duplicate = pd.concat([panel, panel.iloc[[100]]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate date/symbol"):
        run_event_study(duplicate, events)
    panel.loc[panel.symbol.eq("BANK") & panel.date.eq(dates[294]), "return"] = np.nan
    with pytest.raises(ValueError, match="Missing/non-finite estimation returns"):
        run_event_study(panel, events)


def test_nontrading_event_and_overlapping_estimation_are_rejected():
    panel, events, _ = market_fixture()
    events["event_date"] = pd.Timestamp("2022-02-26")
    with pytest.raises(ValueError, match="not a .* trading date"):
        run_event_study(panel, events)
    panel, events, _ = market_fixture()
    with pytest.raises(ValueError, match="Estimation interval must end"):
        run_event_study(panel, events, estimation_end_day=-5)


def test_prices_after_event_windows_cannot_change_estimates():
    panel, events, dates = market_fixture()
    original = run_event_study(panel, events)
    panel.loc[panel.date.gt(dates[305]), "return"] += .4
    pd.testing.assert_frame_equal(original, run_event_study(panel, events))
