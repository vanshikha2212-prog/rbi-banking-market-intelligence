"""Strict previous-close prediction of wholly future CAR[0,+1].

The realized policy decision is descriptive metadata only and is never an input
feature.  All fitted preprocessing uses the training period.  A small event
holdout is an exploratory evaluation, not evidence of a deployable strategy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, brier_score_loss, confusion_matrix,
    f1_score, log_loss, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .event_study import _prepare_inputs, bank_symbols


NUMERICAL_FEATURES = ["return_1d", "return_5d", "return_20d", "volatility_20d", "volatility_60d", "garch_volatility"]
CATEGORICAL_FEATURES = ["bank_type"]
FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES
TARGET_WINDOW = "[0,+1]"


def build_predictive_dataset(returns, events, event_results, volatility, *, benchmark="^NSEI"):
    """Build features available at the last trading close before each event.

    Compounded five- and twenty-day returns are exact products of simple daily
    returns. Failed GARCH fits remain missing and are imputed within training
    pipelines; dropping the affected test events would change the evaluation.
    """
    panel, policy = _prepare_inputs(returns, events)
    target = event_results.loc[event_results["benchmark"].eq(benchmark) & event_results["window"].eq(TARGET_WINDOW)].copy()
    if target.duplicated(["event_id", "bank_symbol"]).any():
        raise ValueError("Duplicate predictive bank-event targets")
    symbols = bank_symbols(panel)
    expected = pd.MultiIndex.from_product([policy["event_id"], symbols], names=["event_id", "bank_symbol"])
    observed = pd.MultiIndex.from_frame(target[["event_id", "bank_symbol"]])
    if len(expected.difference(observed)) or len(observed.difference(expected)):
        raise ValueError("Predictive targets must cover every requested bank/event exactly once")
    if volatility.duplicated(["event_id", "bank_symbol"]).any():
        raise ValueError("Duplicate bank-event GARCH forecasts")
    forecast_lookup = volatility.set_index(["event_id", "bank_symbol"])
    target_lookup = target.set_index(["event_id", "bank_symbol"])
    rows = []
    for event in policy.itertuples(index=False):
        date = pd.Timestamp(event.event_date)
        for symbol in symbols:
            bank = panel[panel["symbol"].eq(symbol)].sort_values("date")
            previous = bank[bank["date"].lt(date)]
            if len(previous) < 60 or not np.isfinite(previous["return"].tail(60).to_numpy(dtype=float)).all():
                raise ValueError(f"Insufficient complete pre-event history for {event.event_id} / {symbol}")
            cutoff = previous["date"].iloc[-1]
            target_row = target_lookup.loc[(event.event_id, symbol)]
            if pd.Timestamp(target_row["event_date"]) != date:
                raise ValueError("Target event date does not agree with policy metadata")
            if "event_window_start" in target_row and pd.Timestamp(target_row["event_window_start"]) <= cutoff:
                raise ValueError("Prediction target overlaps feature history")
            value = float(target_row["car"])
            if not np.isfinite(value):
                raise ValueError("Prediction target contains non-finite CAR")
            key = (event.event_id, symbol)
            garch = np.nan
            forecast_origin, forecast_target = pd.NaT, pd.NaT
            forecast_status = "missing_forecast"
            if key in forecast_lookup.index:
                forecast = forecast_lookup.loc[key]
                forecast_origin = pd.Timestamp(forecast["forecast_origin_date"])
                forecast_target = pd.Timestamp(forecast["forecast_target_date"])
                forecast_status = forecast.get("status", "unknown")
                if forecast.get("converged", False):
                    if forecast_origin != cutoff or forecast_target != date:
                        raise ValueError(f"Misaligned forecast origin/target for {event.event_id} / {symbol}")
                    garch = float(forecast["garch_volatility"])
                    if not np.isfinite(garch) or garch <= 0:
                        raise ValueError("Converged forecast must have finite positive volatility")
            recent = previous["return"]
            metadata = bank.iloc[0]
            rows.append({
                "event_id": event.event_id, "event_date": date, "bank_symbol": symbol,
                "bank_name": metadata["bank_name"], "bank_type": metadata["bank_type"],
                "benchmark": benchmark, "target_window": TARGET_WINDOW,
                "feature_cutoff_date": cutoff,
                "forecast_origin_date": forecast_origin, "forecast_target_date": forecast_target,
                "garch_status": forecast_status,
                "return_1d": float(recent.iloc[-1]),
                "return_5d": float((1 + recent.tail(5)).prod() - 1),
                "return_20d": float((1 + recent.tail(20)).prod() - 1),
                "volatility_20d": float(recent.tail(20).std(ddof=1)),
                "volatility_60d": float(recent.tail(60).std(ddof=1)),
                "garch_volatility": garch,
                "car_0_plus_1": value, "positive_car": int(value > 0),
                "realized_decision_metadata_only": event.decision,
            })
    return pd.DataFrame(rows).sort_values(["event_date", "bank_symbol"]).reset_index(drop=True)


def _preprocessor(scale: bool):
    numerical = [("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True))]
    if scale:
        numerical.append(("scaler", StandardScaler()))
    return ColumnTransformer([
        ("numeric", Pipeline(numerical), NUMERICAL_FEATURES),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
    ])


def _metrics(y, pred, probability):
    two_classes = len(np.unique(y)) == 2
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)) if two_classes else np.nan,
        "roc_auc": float(roc_auc_score(y, probability)) if two_classes else np.nan,
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "brier_score": float(brier_score_loss(y, probability)),
        "log_loss": float(log_loss(y, np.column_stack([1 - probability, probability]), labels=[0, 1])),
    }


def _bootstrap_metrics(y, pred, probability):
    both = len(np.unique(y)) == 2
    return {
        "accuracy": float(np.mean(y == pred)),
        "balanced_accuracy": float(((pred[y == 0] == 0).mean() + (pred[y == 1] == 1).mean()) / 2) if both else np.nan,
        "roc_auc": float(roc_auc_score(y, probability)) if both else np.nan,
        "brier_score": float(np.mean((y - probability)**2)),
    }


def _cluster_uncertainty(test, predictions, *, seed, n_bootstrap):
    events = test["event_id"].drop_duplicates().to_numpy()
    output = []
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap must be positive")
    if len(events) < 2:
        return pd.DataFrame([{"status": "insufficient_test_events", "n_test_events": len(events)}])
    ids = test["event_id"].to_numpy()
    event_rows = {event: np.flatnonzero(ids == event) for event in events}
    rng = np.random.default_rng(seed)
    draws = [np.concatenate([event_rows[event] for event in sample])
             for sample in rng.choice(events, size=(n_bootstrap, len(events)), replace=True)]
    y = test["positive_car"].to_numpy(dtype=int)
    draw_metrics = {}
    for name, (pred, probability) in predictions.items():
        samples = [_bootstrap_metrics(y[index], pred[index], probability[index]) for index in draws]
        draw_metrics[name] = pd.DataFrame(samples)
        point = _bootstrap_metrics(y, pred, probability)
        for metric, estimate in point.items():
            valid = draw_metrics[name][metric].dropna()
            output.append({
                "model": name, "metric": metric, "estimate": estimate,
                "ci_lower": float(valid.quantile(.025)) if len(valid) else np.nan,
                "ci_upper": float(valid.quantile(.975)) if len(valid) else np.nan,
                "n_valid_bootstrap": len(valid), "n_requested_bootstrap": n_bootstrap,
                "n_test_events": len(events), "bootstrap_seed": seed,
                "sampling_unit": "entire_policy_event_all_banks_together",
                "interval_type": "exploratory_pointwise_percentile_conditional_on_observed_events",
                "status": "few_test_events_intervals_unstable" if len(events) < 20 else "exploratory",
            })
    baseline = draw_metrics.get("dummy_majority")
    if baseline is not None:
        for name in predictions:
            if name == "dummy_majority":
                continue
            for metric in ("accuracy", "balanced_accuracy", "roc_auc", "brier_score"):
                delta = (draw_metrics[name][metric] - baseline[metric]).dropna()
                point_model = _bootstrap_metrics(y, *predictions[name])[metric]
                point_baseline = _bootstrap_metrics(y, *predictions["dummy_majority"])[metric]
                output.append({
                    "model": name, "metric": f"{metric}_minus_dummy", "estimate": point_model - point_baseline,
                    "ci_lower": float(delta.quantile(.025)) if len(delta) else np.nan,
                    "ci_upper": float(delta.quantile(.975)) if len(delta) else np.nan,
                    "n_valid_bootstrap": len(delta), "n_requested_bootstrap": n_bootstrap,
                    "n_test_events": len(events), "bootstrap_seed": seed,
                    "sampling_unit": "paired_entire_event_resamples",
                    "interval_type": "exploratory_pointwise_percentile_conditional_on_observed_events",
                    "status": "few_test_events_intervals_unstable" if len(events) < 20 else "exploratory",
                })
    return pd.DataFrame(output)


def evaluate_prediction(
    dataset, *, train_end="2024-12-31", test_start="2025-01-01", test_end="2025-12-31",
    seed=42, n_bootstrap=2000,
) -> dict[str, pd.DataFrame]:
    """Fit fixed model specifications and report one untouched chronological test.

    Event-cluster bootstrap resamples complete held-out events and keeps model
    predictions paired with the baseline. It describes uncertainty conditional
    on these few observed events; it does not establish cross-regime validity.
    No tuning, threshold selection, or prediction flipping uses the test set.
    """
    frame = dataset.copy()
    required = set(FEATURES + ["event_id", "event_date", "bank_symbol", "positive_car", "feature_cutoff_date"])
    if required.difference(frame.columns):
        raise ValueError(f"Missing predictive columns: {sorted(required.difference(frame.columns))}")
    frame["event_date"] = pd.to_datetime(frame["event_date"])
    frame["feature_cutoff_date"] = pd.to_datetime(frame["feature_cutoff_date"])
    if frame.duplicated(["event_id", "bank_symbol"]).any():
        raise ValueError("Duplicate bank-event rows in prediction dataset")
    if frame["feature_cutoff_date"].isna().any() or frame["feature_cutoff_date"].ge(frame["event_date"]).any():
        raise ValueError("All prediction features must precede their announcement")
    if "target_window" in frame and not frame["target_window"].eq(TARGET_WINDOW).all():
        raise ValueError("Prediction is defined only for the wholly future [0,+1] window")
    if not frame["positive_car"].isin([0, 1]).all():
        raise ValueError("Prediction labels must be binary")
    if pd.Timestamp(train_end) >= pd.Timestamp(test_start) or pd.Timestamp(test_start) > pd.Timestamp(test_end):
        raise ValueError("Training and test date ranges overlap or are reversed")
    frame = frame.sort_values(["event_date", "bank_symbol"]).reset_index(drop=True)
    train = frame[frame["event_date"].le(pd.Timestamp(train_end))].copy()
    test = frame[frame["event_date"].between(pd.Timestamp(test_start), pd.Timestamp(test_end))].copy().reset_index(drop=True)
    if train.empty or test.empty:
        raise ValueError("Both training and test periods must contain observations")
    if set(train.event_id).intersection(test.event_id):
        raise ValueError("A policy event cannot appear in both training and test")
    x_train, x_test = train[FEATURES], test[FEATURES]
    y_train, y_test = train.positive_car.to_numpy(dtype=int), test.positive_car.to_numpy(dtype=int)
    specifications = {
        # Classification remains the training-majority label. Probabilities use
        # the training class prior, a fair baseline for Brier score and log loss.
        "dummy_majority": Pipeline([("preprocessor", _preprocessor(False)), ("classifier", DummyClassifier(strategy="prior"))]),
        "logistic_regression": Pipeline([("preprocessor", _preprocessor(True)), ("classifier", LogisticRegression(C=1, max_iter=1000, random_state=seed))]),
        "random_forest": Pipeline([("preprocessor", _preprocessor(False)), ("classifier", RandomForestClassifier(
            n_estimators=300, max_depth=3, min_samples_leaf=6, class_weight="balanced", random_state=seed, n_jobs=1))]),
    }
    metric_rows, prediction_rows, confusion_rows, fitted_predictions = [], [], [], {}
    for name, model in specifications.items():
        counts = {"model": name, "n_train_rows": len(train), "n_test_rows": len(test),
                  "n_train_events": train.event_id.nunique(), "n_test_events": test.event_id.nunique(),
                  "train_positive_rate": float(y_train.mean()), "test_positive_rate": float(y_test.mean()),
                  "train_end": str(train_end), "test_start": str(test_start), "test_end": str(test_end),
                  "target_window": TARGET_WINDOW, "prediction_origin": "previous_trading_close",
                  "feature_names": "|".join(FEATURES), "seed": seed}
        if len(np.unique(y_train)) < 2 and name != "dummy_majority":
            metric_rows.append({**counts, "status": "not_fit_single_training_class"})
            continue
        model.fit(x_train, y_train)
        pred = model.predict(x_test).astype(int)
        classes = np.asarray(model.named_steps["classifier"].classes_)
        prob_matrix = model.predict_proba(x_test)
        probability = prob_matrix[:, int(np.flatnonzero(classes == 1)[0])] if (classes == 1).any() else np.zeros(len(test))
        fitted_predictions[name] = (pred, probability)
        metric_rows.append({**counts, **_metrics(y_test, pred, probability),
                            "status": "exploratory_few_test_events" if test.event_id.nunique() < 20 else "exploratory"})
        for index, row in test.iterrows():
            prediction_rows.append({"model": name, "event_id": row.event_id, "event_date": row.event_date,
                                    "bank_symbol": row.bank_symbol, "y_true": int(y_test[index]),
                                    "y_pred": int(pred[index]), "probability_positive": float(probability[index])})
        matrix = confusion_matrix(y_test, pred, labels=[0, 1])
        for true in (0, 1):
            for predicted in (0, 1):
                confusion_rows.append({"model": name, "true_class": true, "predicted_class": predicted,
                                       "count": int(matrix[true, predicted])})
    return {
        "metrics": pd.DataFrame(metric_rows),
        "predictions": pd.DataFrame(prediction_rows),
        "confusion_matrices": pd.DataFrame(confusion_rows),
        "uncertainty": _cluster_uncertainty(test, fitted_predictions, seed=seed, n_bootstrap=n_bootstrap),
    }
