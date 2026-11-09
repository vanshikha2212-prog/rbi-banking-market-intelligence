import numpy as np
import pandas as pd
import pytest

from rbi_intelligence.prediction import FEATURES, build_predictive_dataset, evaluate_prediction


def feature_fixture():
    dates = pd.bdate_range("2023-01-02", periods=180)
    rows = []
    for symbol, name, bank_type, asset_type in [
        ("A", "Bank A", "Private", "bank"), ("^NSEI", "Nifty 50", "", "benchmark")
    ]:
        for index, day in enumerate(dates):
            rows.append({"date": day, "symbol": symbol, "return": .001 + index / 1_000_000,
                         "volume": 100 + index, "bank_name": name, "bank_type": bank_type,
                         "asset_type": asset_type})
    panel = pd.DataFrame(rows)
    event_date = dates[150]
    events = pd.DataFrame({"event_id": ["E1"], "event_date": [event_date], "decision": ["Cut"],
                           "repo_before": [6.5], "rate_change_bps": [-25]})
    targets = pd.DataFrame({"event_id": ["E1"], "event_date": [event_date], "bank_symbol": ["A"],
                            "benchmark": ["^NSEI"], "window": ["[0,+1]"], "car": [.03],
                            "event_window_start": [event_date]})
    forecasts = pd.DataFrame({"event_id": ["E1"], "bank_symbol": ["A"], "forecast_origin_date": [dates[149]],
                              "forecast_target_date": [event_date], "converged": [True],
                              "garch_volatility": [.02]})
    return panel, events, targets, forecasts, dates


def test_features_are_past_only_and_realized_decision_is_not_a_feature():
    panel, events, targets, forecasts, dates = feature_fixture()
    result = build_predictive_dataset(panel, events, targets, forecasts)
    assert result.feature_cutoff_date.iloc[0] == dates[149]
    assert result.target_window.iloc[0] == "[0,+1]"
    assert "realized_decision_metadata_only" not in FEATURES
    assert "decision" not in FEATURES
    panel.loc[panel.date.ge(dates[150]), "return"] = .7
    changed = build_predictive_dataset(panel, events, targets, forecasts)
    pd.testing.assert_frame_equal(result, changed)


def walk_forward_fixture(n_events=28):
    rng = np.random.default_rng(8)
    rows = []
    dates = pd.date_range("2017-01-01", periods=n_events, freq="70D")
    for event_index, day in enumerate(dates):
        for bank in range(2):
            row = {"event_id": f"E{event_index:02}", "event_date": day, "bank_symbol": f"B{bank}",
                   "bank_type": "Public" if bank == 0 else "Private", "positive_car": (event_index + bank) % 2,
                   "feature_cutoff_date": day - pd.Timedelta(days=1), "target_window": "[0,+1]"}
            row.update({feature: float(rng.normal()) for feature in FEATURES if feature != "bank_type"})
            rows.append(row)
    return pd.DataFrame(rows)


def test_walk_forward_keeps_complete_events_and_reports_all_baselines():
    output = evaluate_prediction(walk_forward_fixture(), min_train_events=24, n_bootstrap=20)
    predictions = output["predictions"]
    assert predictions.event_id.nunique() == 4
    assert predictions.groupby(["model", "event_id"]).bank_symbol.nunique().eq(2).all()
    assert {"dummy_majority", "bank_historical_rate", "last_event_persistence"}.issubset(predictions.model.unique())
    assert output["metrics"].n_test_events.eq(4).all()
    assert output["uncertainty"].n_test_events.eq(4).all()


def test_walk_forward_rejects_nonpast_cutoff_and_is_invariant_to_realized_metadata():
    frame = walk_forward_fixture()
    frame["realized_decision_metadata_only"] = "Hold"
    first = evaluate_prediction(frame, min_train_events=24, n_bootstrap=10)["predictions"]
    frame["realized_decision_metadata_only"] = "future label changed"
    second = evaluate_prediction(frame, min_train_events=24, n_bootstrap=10)["predictions"]
    pd.testing.assert_frame_equal(first, second)
    frame.loc[0, "feature_cutoff_date"] = frame.loc[0, "event_date"]
    with pytest.raises(ValueError, match="non-past"):
        evaluate_prediction(frame, min_train_events=24, n_bootstrap=10)
