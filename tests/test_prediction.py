import numpy as np
import pandas as pd
import pytest

from rbi_intelligence.prediction import FEATURES, build_predictive_dataset, evaluate_prediction


def feature_fixture():
    dates = pd.bdate_range("2024-01-01", periods=100)
    panel = pd.DataFrame({"date": dates, "symbol": "A", "return": .01,
                          "bank_name": "Bank A", "bank_type": "Private"})
    events = pd.DataFrame({"event_id": ["E1"], "event_date": [dates[80]], "decision": ["Cut"]})
    targets = pd.DataFrame({"event_id": ["E1"], "event_date": [dates[80]], "bank_symbol": ["A"],
                            "benchmark": ["^NSEI"], "window": ["[0,+1]"], "car": [.03],
                            "event_window_start": [dates[80]]})
    forecasts = pd.DataFrame({"event_id": ["E1"], "bank_symbol": ["A"], "forecast_origin_date": [dates[79]],
                              "forecast_target_date": [dates[80]], "converged": [True],
                              "garch_volatility": [.02], "status": ["ok"]})
    return panel, events, targets, forecasts, dates


def test_features_are_compounded_past_only_and_target_is_wholly_future():
    panel, events, targets, forecasts, dates = feature_fixture()
    result = build_predictive_dataset(panel, events, targets, forecasts)
    assert result.return_5d.iloc[0] == pytest.approx(1.01**5 - 1)
    assert result.return_20d.iloc[0] == pytest.approx(1.01**20 - 1)
    assert result.feature_cutoff_date.iloc[0] == dates[79]
    assert result.target_window.iloc[0] == "[0,+1]"
    assert "decision" not in FEATURES
    assert not any("realized" in feature or "car" in feature for feature in FEATURES)
    panel.loc[panel.date.ge(dates[80]), "return"] = .7
    changed = build_predictive_dataset(panel, events, targets, forecasts)
    pd.testing.assert_frame_equal(result, changed)


def test_stale_garch_target_and_label_history_overlap_are_rejected():
    panel, events, targets, forecasts, dates = feature_fixture()
    forecasts.loc[0, "forecast_target_date"] = dates[79]
    with pytest.raises(ValueError, match="Misaligned forecast"):
        build_predictive_dataset(panel, events, targets, forecasts)
    forecasts.loc[0, "forecast_target_date"] = dates[80]
    targets.loc[0, "event_window_start"] = dates[79]
    with pytest.raises(ValueError, match="target overlaps"):
        build_predictive_dataset(panel, events, targets, forecasts)


def small_dataset():
    rng = np.random.default_rng(4)
    rows = []
    for i, date in enumerate(pd.to_datetime(["2023-02-01", "2023-06-01", "2024-02-01", "2024-06-03", "2025-02-03", "2025-06-02"])):
        for bank in range(2):
            rows.append({"event_id": f"E{i}", "event_date": date, "bank_symbol": f"B{bank}",
                         "bank_type": "Private" if bank else "Public", "positive_car": (i + bank) % 2,
                         "feature_cutoff_date": date - pd.offsets.BDay(1), "target_window": "[0,+1]",
                         "realized_decision_metadata_only": "Cut" if i > 3 else "Hold",
                         **{column: float(rng.uniform(.005, .03)) for column in FEATURES if column != "bank_type"}})
    return pd.DataFrame(rows)


def test_models_use_chronological_events_and_never_realized_decision_metadata():
    frame = small_dataset()
    output = evaluate_prediction(frame, n_bootstrap=20)
    assert output["metrics"].n_train_events.eq(4).all()
    assert output["metrics"].n_test_events.eq(2).all()
    assert len(output["predictions"]) == 12
    assert output["confusion_matrices"].groupby("model")["count"].sum().eq(4).all()
    assert output["uncertainty"].n_test_events.eq(2).all()
    frame["realized_decision_metadata_only"] = "arbitrarily changed future label"
    changed = evaluate_prediction(frame, n_bootstrap=20)
    pd.testing.assert_frame_equal(output["predictions"], changed["predictions"])


def test_preprocessing_is_fitted_on_training_only(monkeypatch):
    from sklearn.preprocessing import StandardScaler
    observed_sizes = []
    original = StandardScaler.fit
    def capture(self, x, y=None, sample_weight=None):
        observed_sizes.append(len(x))
        return original(self, x, y=y, sample_weight=sample_weight)
    monkeypatch.setattr(StandardScaler, "fit", capture)
    frame = small_dataset()
    frame.loc[frame.event_date.dt.year.eq(2025), "return_20d"] = 100000
    evaluate_prediction(frame, n_bootstrap=10)
    assert observed_sizes == [8]


def test_invalid_asof_and_single_test_class_are_handled():
    frame = small_dataset()
    frame.loc[0, "feature_cutoff_date"] = frame.loc[0, "event_date"]
    with pytest.raises(ValueError, match="must precede"):
        evaluate_prediction(frame, n_bootstrap=10)
    frame = small_dataset()
    frame.loc[frame.event_date.dt.year.eq(2025), "positive_car"] = 1
    output = evaluate_prediction(frame, n_bootstrap=10)
    assert output["metrics"].roc_auc.isna().all()
    assert output["metrics"].balanced_accuracy.isna().all()
    assert output["metrics"].accuracy.notna().all()
