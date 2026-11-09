import numpy as np
import pandas as pd
import pytest

from rbi_intelligence import volatility


def forecast_fixture():
    dates = pd.bdate_range("2024-01-01", periods=30)
    panel = pd.DataFrame({"date": dates, "symbol": "A", "return": np.arange(30) / 10000,
                          "bank_name": "A", "bank_type": "Public"})
    events = pd.DataFrame({"event_id": ["E"], "event_date": [dates[25]], "decision": ["Hold"]})
    return panel, events, dates


def test_forecast_target_is_event_day_and_origin_is_previous_close(monkeypatch):
    panel, events, dates = forecast_fixture()
    seen = []
    def fake_fit(history, distribution):
        seen.append(history.copy())
        return {"garch_variance": .0004, "garch_volatility": .02, "convergence_flag": 0}
    monkeypatch.setattr(volatility, "_fit_garch", fake_fit)
    original = volatility.generate_event_volatility(panel, events, min_training_obs=20)
    assert seen[0].index[-1] == dates[24]
    assert len(seen[0]) == 25
    assert original.forecast_target_date.iloc[0] == dates[25]
    assert original.forecast_origin_date.iloc[0] == dates[24]
    assert bool(original.converged.iloc[0])
    panel.loc[panel.date.ge(dates[25]), "return"] = .8
    changed = volatility.generate_event_volatility(panel, events, min_training_obs=20)
    pd.testing.assert_series_equal(seen[0], seen[1])
    assert original.garch_volatility.iloc[0] == changed.garch_volatility.iloc[0]
    assert original.realized_squared_return_proxy.iloc[0] != changed.realized_squared_return_proxy.iloc[0]


def test_nonconverged_fit_is_retained_and_not_scored(monkeypatch):
    panel, events, _ = forecast_fixture()
    monkeypatch.setattr(volatility, "_fit_garch", lambda *_: {
        "garch_variance": .0004, "garch_volatility": .02, "convergence_flag": 9})
    result = volatility.generate_event_volatility(panel, events, min_training_obs=20)
    assert len(result) == 1
    assert not bool(result.converged.iloc[0])
    assert np.isnan(result.garch_qlike.iloc[0])
    assert result.status.iloc[0] == "nonconverged_or_invalid_variance"


def test_quartiles_are_frozen_from_training_not_future_events():
    data = pd.DataFrame({
        "event_id": ["E1", "E1", "E2", "E2", "E3", "E3"],
        "bank_symbol": ["A", "B"] * 3,
        "event_date": pd.to_datetime(["2023-01-01"] * 2 + ["2024-01-01"] * 2 + ["2025-01-01"] * 2),
        "garch_volatility": [.01, .02, .03, .04, .05, np.nan],
        "converged": [True] * 5 + [False],
    })
    classified, thresholds = volatility.classify_volatility_risk(data)
    assert thresholds.threshold.tolist() == pytest.approx([.0175, .025, .0325])
    assert classified.risk_level.iloc[-1] == "Unavailable"
    assert classified.risk_level.iloc[-2] == "Very High"
    data.loc[4, "garch_volatility"] = 100
    _, changed_thresholds = volatility.classify_volatility_risk(data)
    pd.testing.assert_frame_equal(thresholds, changed_thresholds)


def test_internal_missing_training_day_is_visible_not_silently_dropped(monkeypatch):
    panel, events, _ = forecast_fixture()
    panel.loc[10, "return"] = np.nan
    def should_not_fit(*_):
        raise AssertionError("Invalid training history should not be fitted")
    monkeypatch.setattr(volatility, "_fit_garch", should_not_fit)
    result = volatility.generate_event_volatility(panel, events, min_training_obs=20)
    assert result.status.iloc[0] == "missing_training_return"
