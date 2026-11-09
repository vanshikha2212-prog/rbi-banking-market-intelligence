"""Leakage-free event-grouped walk-forward prediction and calibration."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, brier_score_loss, confusion_matrix,
    f1_score, log_loss, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .event_study import _prepare_inputs, bank_symbols


NUMERICAL_FEATURES = [
    "return_1d", "return_5d", "return_20d", "return_60d",
    "volatility_20d", "volatility_60d", "downside_volatility_60d",
    "volume_zscore_20d", "market_return_1d", "market_return_5d",
    "market_return_20d", "market_return_60d", "market_volatility_20d",
    "market_volatility_60d", "bank_market_beta_60d", "bank_market_corr_60d",
    "group_return_20d", "repo_before", "prior_rate_change_bps",
    "days_since_previous_mpc", "days_since_rate_change", "garch_volatility",
]
CATEGORICAL_FEATURES = ["bank_type"]
FEATURES = CATEGORICAL_FEATURES + NUMERICAL_FEATURES
TARGET_WINDOW = "[0,+1]"


def _compound(values: pd.Series, window: int) -> float:
    return float((1 + values.tail(window)).prod() - 1)


def build_predictive_dataset(returns, events, event_results, volatility, *, benchmark="^NSEI"):
    """Construct only information observed by the previous market close."""
    panel, policy = _prepare_inputs(returns, events)
    target = event_results.loc[event_results.benchmark.eq(benchmark) & event_results.window.eq(TARGET_WINDOW)].copy()
    if target.duplicated(["event_id", "bank_symbol"]).any():
        raise ValueError("Duplicate predictive bank-event targets")
    symbols = bank_symbols(panel)
    expected = pd.MultiIndex.from_product([policy.event_id, symbols], names=["event_id", "bank_symbol"])
    observed = pd.MultiIndex.from_frame(target[["event_id", "bank_symbol"]])
    if len(expected.difference(observed)) or len(observed.difference(expected)):
        raise ValueError("Predictive targets must cover every bank/event exactly once")
    forecast_lookup = volatility.set_index(["event_id", "bank_symbol"]) if not volatility.empty else pd.DataFrame()
    target_lookup = target.set_index(["event_id", "bank_symbol"])
    market = panel.loc[panel.symbol.eq(benchmark)].sort_values("date").set_index("date")
    bank_panel = panel.loc[panel.symbol.isin(symbols)].copy()
    rows = []
    previous_event_date = None
    last_change_date = None
    prior_change = 0.0
    for event in policy.sort_values("event_date").itertuples(index=False):
        date = pd.Timestamp(event.event_date)
        for symbol in symbols:
            bank = bank_panel.loc[bank_panel.symbol.eq(symbol)].sort_values("date")
            previous = bank.loc[bank.date.lt(date)].set_index("date")
            market_previous = market.loc[market.index < date]
            if len(previous) < 120 or len(market_previous) < 120:
                raise ValueError(f"Insufficient pre-event history for {event.event_id} / {symbol}")
            cutoff = previous.index[-1]
            if cutoff != market_previous.index[-1]:
                raise ValueError("Bank and benchmark feature cutoffs must match")
            target_row = target_lookup.loc[(event.event_id, symbol)]
            if pd.Timestamp(target_row.event_window_start) <= cutoff:
                raise ValueError("Prediction target overlaps feature history")
            recent = previous["return"]
            market_recent = market_previous["return"]
            paired = pd.concat([recent.rename("bank"), market_recent.rename("market")], axis=1).dropna().tail(60)
            variance = float(paired.market.var(ddof=1))
            beta = float(paired.cov().loc["bank", "market"] / variance) if variance > 0 else np.nan
            correlation = float(paired.bank.corr(paired.market))
            metadata = previous.iloc[-1]
            group_symbols = bank_panel.loc[bank_panel.bank_type.eq(metadata.bank_type), "symbol"].drop_duplicates()
            group_values = []
            for group_symbol in group_symbols:
                series = bank_panel.loc[(bank_panel.symbol.eq(group_symbol)) & (bank_panel.date.lt(date))].sort_values("date")["return"]
                group_values.append(_compound(series, 20))
            garch = np.nan
            if not volatility.empty and (event.event_id, symbol) in forecast_lookup.index:
                forecast = forecast_lookup.loc[(event.event_id, symbol)]
                if bool(forecast.get("converged", False)):
                    if pd.Timestamp(forecast.forecast_origin_date) != cutoff or pd.Timestamp(forecast.forecast_target_date) != date:
                        raise ValueError("Misaligned GARCH forecast origin/target")
                    garch = float(forecast.garch_volatility)
            volume = previous.volume.astype(float)
            volume_scale = float(volume.tail(20).std(ddof=1))
            rows.append({
                "event_id": event.event_id, "event_date": date, "bank_symbol": symbol,
                "bank_name": metadata.bank_name, "bank_type": metadata.bank_type,
                "feature_cutoff_date": cutoff, "benchmark": benchmark, "target_window": TARGET_WINDOW,
                "return_1d": float(recent.iloc[-1]), "return_5d": _compound(recent, 5),
                "return_20d": _compound(recent, 20), "return_60d": _compound(recent, 60),
                "volatility_20d": float(recent.tail(20).std(ddof=1)),
                "volatility_60d": float(recent.tail(60).std(ddof=1)),
                "downside_volatility_60d": float(recent.tail(60).clip(upper=0).std(ddof=1)),
                "volume_zscore_20d": float((volume.iloc[-1] - volume.tail(20).mean()) / volume_scale) if volume_scale > 0 else 0.0,
                "market_return_1d": float(market_recent.iloc[-1]), "market_return_5d": _compound(market_recent, 5),
                "market_return_20d": _compound(market_recent, 20), "market_return_60d": _compound(market_recent, 60),
                "market_volatility_20d": float(market_recent.tail(20).std(ddof=1)),
                "market_volatility_60d": float(market_recent.tail(60).std(ddof=1)),
                "bank_market_beta_60d": beta, "bank_market_corr_60d": correlation,
                "group_return_20d": float(np.mean(group_values)), "repo_before": float(event.repo_before),
                "prior_rate_change_bps": float(prior_change),
                "days_since_previous_mpc": float((date - previous_event_date).days) if previous_event_date is not None else np.nan,
                "days_since_rate_change": float((date - last_change_date).days) if last_change_date is not None else np.nan,
                "garch_volatility": garch,
                "car_0_plus_1": float(target_row.car), "positive_car": int(float(target_row.car) > 0),
                "realized_decision_metadata_only": event.decision,
            })
        previous_event_date = date
        if float(event.rate_change_bps) != 0:
            last_change_date = date
        prior_change = float(event.rate_change_bps)
    return pd.DataFrame(rows).sort_values(["event_date", "bank_symbol"]).reset_index(drop=True)


def _preprocessor(scale: bool) -> ColumnTransformer:
    numerical = [("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True))]
    if scale:
        numerical.append(("scaler", StandardScaler()))
    return ColumnTransformer([
        ("numeric", Pipeline(numerical), NUMERICAL_FEATURES),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
    ])


def _specifications(seed: int) -> dict[str, Pipeline]:
    return {
        "logistic_l2": Pipeline([("preprocessor", _preprocessor(True)), ("classifier", LogisticRegression(C=1, max_iter=3000, random_state=seed))]),
        "elastic_net": Pipeline([("preprocessor", _preprocessor(True)), ("classifier", LogisticRegression(
            C=.5, penalty="elasticnet", l1_ratio=.5, solver="saga", max_iter=5000, random_state=seed))]),
        "random_forest": Pipeline([("preprocessor", _preprocessor(False)), ("classifier", RandomForestClassifier(
            n_estimators=400, max_depth=4, min_samples_leaf=6, max_features="sqrt", class_weight="balanced_subsample", random_state=seed, n_jobs=1))]),
        "hist_gradient_boosting": Pipeline([("preprocessor", _preprocessor(False)), ("classifier", HistGradientBoostingClassifier(
            max_iter=150, max_leaf_nodes=7, learning_rate=.05, l2_regularization=1.0, random_state=seed))]),
    }


def _metrics(y, pred, probability) -> dict[str, float]:
    both = len(np.unique(y)) == 2
    bins = np.minimum((np.asarray(probability) * 5).astype(int), 4)
    ece = sum((bins == value).mean() * abs(np.asarray(y)[bins == value].mean() - np.asarray(probability)[bins == value].mean())
              for value in np.unique(bins))
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)) if both else np.nan,
        "roc_auc": float(roc_auc_score(y, probability)) if both else np.nan,
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "brier_score": float(brier_score_loss(y, probability)),
        "log_loss": float(log_loss(y, np.column_stack([1 - probability, probability]), labels=[0, 1])),
        "expected_calibration_error_5bin": float(ece),
    }


def _calibration_splits(train: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    events = train[["event_id", "event_date"]].drop_duplicates().sort_values("event_date").event_id.to_numpy()
    blocks = np.array_split(events, 4)
    ids = train.event_id.to_numpy()
    splits = []
    for index in range(1, len(blocks)):
        earlier = np.concatenate(blocks[:index])
        validation = blocks[index]
        train_indices = np.flatnonzero(np.isin(ids, earlier))
        validation_indices = np.flatnonzero(np.isin(ids, validation))
        if len(train_indices) and len(validation_indices) and train.iloc[train_indices].positive_car.nunique() == 2:
            splits.append((train_indices, validation_indices))
    return splits


def _event_bootstrap(predictions: pd.DataFrame, *, seed: int, n_bootstrap: int) -> pd.DataFrame:
    events = predictions[["event_id", "event_date"]].drop_duplicates().sort_values("event_date").event_id.to_numpy()
    rng = np.random.default_rng(seed)
    rows = []
    models = predictions.model.drop_duplicates().tolist()
    point = {name: _metrics(group.y_true.to_numpy(), group.y_pred.to_numpy(), group.probability_positive.to_numpy())
             for name, group in predictions.groupby("model", sort=False)}
    samples = {name: {metric: [] for metric in ("accuracy", "balanced_accuracy", "roc_auc", "brier_score")} for name in models}
    for _ in range(n_bootstrap):
        draw = rng.choice(events, size=len(events), replace=True)
        for name in models:
            group = predictions[predictions.model.eq(name)]
            sampled = pd.concat([group[group.event_id.eq(event)] for event in draw], ignore_index=True)
            values = _metrics(sampled.y_true.to_numpy(), sampled.y_pred.to_numpy(), sampled.probability_positive.to_numpy())
            for metric in samples[name]:
                samples[name][metric].append(values[metric])
    baseline = "dummy_majority"
    for name in models:
        for metric, values in samples[name].items():
            valid = np.asarray(values, dtype=float)
            valid = valid[np.isfinite(valid)]
            rows.append({"model": name, "metric": metric, "estimate": point[name][metric],
                         "ci_lower": float(np.quantile(valid, .025)) if len(valid) else np.nan,
                         "ci_upper": float(np.quantile(valid, .975)) if len(valid) else np.nan,
                         "n_valid_bootstrap": len(valid), "n_requested_bootstrap": n_bootstrap,
                         "n_test_events": len(events), "sampling_unit": "entire_policy_event_all_banks_together"})
            if name != baseline:
                delta = np.asarray(values) - np.asarray(samples[baseline][metric])
                delta = delta[np.isfinite(delta)]
                rows.append({"model": name, "metric": f"{metric}_minus_dummy_majority",
                             "estimate": point[name][metric] - point[baseline][metric],
                             "ci_lower": float(np.quantile(delta, .025)) if len(delta) else np.nan,
                             "ci_upper": float(np.quantile(delta, .975)) if len(delta) else np.nan,
                             "n_valid_bootstrap": len(delta), "n_requested_bootstrap": n_bootstrap,
                             "n_test_events": len(events), "sampling_unit": "paired_entire_policy_event"})
    return pd.DataFrame(rows)


def evaluate_prediction(dataset, *, min_train_events=24, seed=42, n_bootstrap=2000, **_ignored) -> dict[str, pd.DataFrame]:
    """Pre-specified expanding-window evaluation with complete event groups."""
    frame = dataset.copy()
    required = set(FEATURES + ["event_id", "event_date", "bank_symbol", "positive_car", "feature_cutoff_date"])
    if required - set(frame):
        raise ValueError(f"Missing predictive columns: {sorted(required - set(frame))}")
    frame.event_date = pd.to_datetime(frame.event_date)
    frame.feature_cutoff_date = pd.to_datetime(frame.feature_cutoff_date)
    if frame.duplicated(["event_id", "bank_symbol"]).any() or frame.feature_cutoff_date.ge(frame.event_date).any():
        raise ValueError("Duplicate rows or non-past feature cutoff")
    events = frame[["event_id", "event_date"]].drop_duplicates().sort_values("event_date").reset_index(drop=True)
    if len(events) <= min_train_events:
        raise ValueError("Not enough complete events for walk-forward evaluation")
    prediction_rows, fold_rows = [], []
    specifications = _specifications(seed)
    for outer in range(min_train_events, len(events)):
        train_ids = set(events.iloc[:outer].event_id)
        test_id = events.iloc[outer].event_id
        train = frame[frame.event_id.isin(train_ids)].sort_values(["event_date", "bank_symbol"]).reset_index(drop=True)
        test = frame[frame.event_id.eq(test_id)].sort_values("bank_symbol").reset_index(drop=True)
        x_train, x_test = train[FEATURES], test[FEATURES]
        y_train, y_test = train.positive_car.to_numpy(int), test.positive_car.to_numpy(int)
        prior = float(y_train.mean())
        baseline_predictions = {
            "dummy_majority": (np.full(len(test), int(prior >= .5)), np.full(len(test), prior), "training_prevalence"),
            "bank_historical_rate": (np.zeros(len(test), dtype=int), np.zeros(len(test)), "laplace_smoothed_bank_rate"),
            "last_event_persistence": (np.zeros(len(test), dtype=int), np.zeros(len(test)), "last_observed_bank_label"),
        }
        for index, row in test.iterrows():
            history = train[train.bank_symbol.eq(row.bank_symbol)].sort_values("event_date")
            probability = float((history.positive_car.sum() + 1) / (len(history) + 2))
            baseline_predictions["bank_historical_rate"][0][index] = int(probability >= .5)
            baseline_predictions["bank_historical_rate"][1][index] = probability
            last = int(history.positive_car.iloc[-1])
            baseline_predictions["last_event_persistence"][0][index] = last
            baseline_predictions["last_event_persistence"][1][index] = float(last)
        fitted = dict(baseline_predictions)
        splits = _calibration_splits(train)
        for name, base in specifications.items():
            if len(np.unique(y_train)) < 2:
                continue
            model = base
            calibration_status = "uncalibrated_insufficient_inner_folds"
            if len(splits) >= 2:
                model = CalibratedClassifierCV(base, method="sigmoid", cv=splits, ensemble=True)
                calibration_status = "sigmoid_event_grouped_expanding_cv"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model.fit(x_train, y_train)
            probability = model.predict_proba(x_test)[:, list(model.classes_).index(1)]
            fitted[name] = ((probability >= .5).astype(int), probability, calibration_status)
        for name, (pred, probability, calibration_status) in fitted.items():
            fold_rows.append({"model": name, "event_id": test_id, "event_date": test.event_date.iloc[0],
                              "n_train_events": outer, "n_train_rows": len(train), "n_test_rows": len(test),
                              "calibration": calibration_status, **_metrics(y_test, pred, probability)})
            for index, row in test.iterrows():
                prediction_rows.append({"model": name, "event_id": test_id, "event_date": row.event_date,
                                        "bank_symbol": row.bank_symbol, "y_true": int(y_test[index]),
                                        "y_pred": int(pred[index]), "probability_positive": float(probability[index]),
                                        "n_prior_events": outer, "calibration": calibration_status})
    predictions = pd.DataFrame(prediction_rows)
    metric_rows, confusion_rows = [], []
    for name, group in predictions.groupby("model", sort=False):
        metric_rows.append({"model": name, "evaluation": "event_grouped_expanding_walk_forward",
                            "n_test_events": group.event_id.nunique(), "n_test_rows": len(group),
                            "first_test_event": group.event_date.min(), "last_test_event": group.event_date.max(),
                            "feature_names": "|".join(FEATURES), "status": "exploratory_out_of_sample",
                            **_metrics(group.y_true.to_numpy(), group.y_pred.to_numpy(), group.probability_positive.to_numpy())})
        matrix = confusion_matrix(group.y_true, group.y_pred, labels=[0, 1])
        for truth in (0, 1):
            for predicted in (0, 1):
                confusion_rows.append({"model": name, "actual": truth, "predicted": predicted, "count": int(matrix[truth, predicted])})
    uncertainty = _event_bootstrap(predictions, seed=seed, n_bootstrap=n_bootstrap)
    calibration_rows = []
    for name, group in predictions.groupby("model", sort=False):
        assigned = pd.cut(group.probability_positive, bins=np.linspace(0, 1, 6), include_lowest=True, labels=False)
        for bin_number, part in group.groupby(assigned, observed=True):
            calibration_rows.append({"model": name, "probability_bin": int(bin_number),
                                     "n_rows": len(part), "n_events": part.event_id.nunique(),
                                     "mean_predicted_probability": float(part.probability_positive.mean()),
                                     "observed_positive_rate": float(part.y_true.mean())})
    return {"metrics": pd.DataFrame(metric_rows), "fold_metrics": pd.DataFrame(fold_rows),
            "predictions": predictions, "confusion_matrices": pd.DataFrame(confusion_rows),
            "calibration": pd.DataFrame(calibration_rows), "uncertainty": uncertainty}
