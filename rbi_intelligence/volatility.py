"""Past-only event-target GARCH forecasts and frozen training-sample quartiles."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from .event_study import _prepare_inputs, bank_symbols


def _fit_garch(training: pd.Series, distribution: str) -> dict:
    """Fit a model to one origin's history; all returned units are fractions."""
    from arch import arch_model
    from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        model = arch_model(training * 100, mean="Constant", vol="GARCH", p=1, q=1, dist=distribution)
        fitted = model.fit(disp="off", show_warning=False)
        forecast = fitted.forecast(horizon=1, reindex=False)
    variance = float(forecast.variance.iloc[-1, 0] / 10000)
    params = fitted.params
    residual = pd.Series(np.asarray(fitted.std_resid, dtype=float)).replace([np.inf, -np.inf], np.nan).dropna()
    lag = min(10, max(1, len(residual) // 5))
    diagnostic = {"residual_ljung_box_p": np.nan, "squared_residual_ljung_box_p": np.nan, "arch_lm_p": np.nan}
    if len(residual) > 2 * lag + 2:
        diagnostic = {
            "residual_ljung_box_p": float(acorr_ljungbox(residual, lags=[lag], return_df=True)["lb_pvalue"].iloc[0]),
            "squared_residual_ljung_box_p": float(acorr_ljungbox(residual**2, lags=[lag], return_df=True)["lb_pvalue"].iloc[0]),
            "arch_lm_p": float(het_arch(residual, nlags=lag)[1]),
        }
    return {
        "garch_variance": variance,
        "garch_volatility": float(np.sqrt(variance)) if variance > 0 else np.nan,
        "forecast_mean": float(params.get("mu", np.nan) / 100),
        "alpha_1": float(params.get("alpha[1]", np.nan)),
        "beta_1": float(params.get("beta[1]", np.nan)),
        "omega": float(params.get("omega", np.nan) / 10000),
        "persistence": float(params.get("alpha[1]", 0) + params.get("beta[1]", 0)),
        "student_t_degrees_freedom": float(params.get("nu", np.nan)),
        "convergence_flag": int(fitted.convergence_flag),
        "log_likelihood": float(fitted.loglikelihood),
        "aic": float(fitted.aic),
        "bic": float(fitted.bic),
        "diagnostic_lags": lag,
        "fit_warnings": "|".join(sorted({type(w.message).__name__ for w in captured})),
        **diagnostic,
    }


def generate_event_volatility(
    returns: pd.DataFrame,
    events: pd.DataFrame,
    *,
    min_training_obs: int = 500,
    distribution: str = "t",
    rolling_window: int = 20,
) -> pd.DataFrame:
    """Forecast each event day's variance using returns through the prior close.

    No full-sample fitted parameters or event-day returns enter fitting. Only
    event targets are fitted, avoiding thousands of unnecessary daily refits.
    Failed fits remain visible as rows with diagnostic status. Squared event-day
    return is an explicitly noisy ex-post variance proxy, used only for scoring.
    """
    panel, policy = _prepare_inputs(returns, events)
    if min_training_obs < 3 or rolling_window < 2:
        raise ValueError("At least three training returns and two rolling returns are required")
    rows = []
    for symbol in bank_symbols(panel):
        bank = panel[panel["symbol"].eq(symbol)].sort_values("date").set_index("date")
        for event in policy.itertuples(index=False):
            target = pd.Timestamp(event.event_date)
            history = bank.loc[bank.index < target, "return"]
            # The initial price observation has no preceding return. Any later
            # missing return is an unexplained gap, rather than a shorter day.
            valid = history.dropna()
            internal_gap = not valid.empty and history.loc[valid.index[0]:].isna().any()
            origin = valid.index[-1] if len(valid) else pd.NaT
            metadata = bank.iloc[0]
            rolling_variance = float(valid.tail(rolling_window).var(ddof=1)) if len(valid) >= rolling_window else np.nan
            row = {
                "event_id": event.event_id,
                "event_date": target,
                "bank_symbol": symbol,
                "bank_name": metadata["bank_name"],
                "bank_type": metadata["bank_type"],
                "forecast_origin_date": origin,
                "forecast_target_date": target,
                "training_start": valid.index[0] if len(valid) else pd.NaT,
                "n_training": len(valid),
                "model": "GARCH(1,1)",
                "innovation_distribution": distribution,
                "rolling_window": rolling_window,
                "rolling_variance": rolling_variance,
                "rolling_volatility": float(np.sqrt(rolling_variance)) if rolling_variance > 0 else np.nan,
                "garch_variance": np.nan,
                "garch_volatility": np.nan,
                "convergence_flag": -1,
                "converged": False,
                "status": "insufficient_history",
                "error": "",
            }
            if target not in bank.index:
                row["status"] = "missing_target_trading_date"
            elif internal_gap:
                row["status"] = "missing_training_return"
            elif len(valid) >= min_training_obs:
                try:
                    row.update(_fit_garch(valid, distribution))
                    good = row["convergence_flag"] == 0 and np.isfinite(row["garch_variance"]) and row["garch_variance"] > 0
                    row["converged"] = bool(good)
                    row["status"] = "ok" if good else "nonconverged_or_invalid_variance"
                except (ValueError, RuntimeError, ArithmeticError, np.linalg.LinAlgError) as exc:
                    row["status"] = "fit_failed"
                    row["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
            actual = float(bank.loc[target, "return"]) if target in bank.index else np.nan
            proxy = actual**2 if np.isfinite(actual) else np.nan
            row["realized_return"] = actual
            row["realized_squared_return_proxy"] = proxy
            row["variance_proxy_caveat"] = "one_daily_squared_return_is_noisy_not_observed_latent_variance"
            for model_name, variance in (("garch", row["garch_variance"]), ("rolling", rolling_variance)):
                scoreable = np.isfinite(variance) and variance > 0 and np.isfinite(proxy)
                if model_name == "garch":
                    scoreable = scoreable and row["converged"]
                row[f"{model_name}_qlike"] = float(np.log(variance) + proxy / variance) if scoreable else np.nan
                row[f"{model_name}_variance_squared_error"] = float((proxy - variance)**2) if scoreable else np.nan
            rows.append(row)
    if not rows:
        raise ValueError("No bank/event combinations to forecast")
    return pd.DataFrame(rows).sort_values(["event_date", "bank_symbol"]).reset_index(drop=True)


def summarize_volatility_forecasts(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Like-for-like scores on converged forecasts with both losses available."""
    rows = []
    groups = [("All banks", forecasts), *list(forecasts.groupby("bank_symbol", sort=True))]
    for name, group in groups:
        paired = group[group["converged"].eq(True)].dropna(subset=["garch_qlike", "rolling_qlike"])
        rows.append({
            "bank_symbol": name,
            "n_attempted": len(group),
            "n_scored": len(paired),
            "n_events_scored": paired["event_id"].nunique(),
            "mean_garch_qlike": float(paired["garch_qlike"].mean()),
            "mean_rolling_qlike": float(paired["rolling_qlike"].mean()),
            "garch_minus_rolling_qlike": float((paired["garch_qlike"] - paired["rolling_qlike"]).mean()),
            "garch_variance_rmse": float(np.sqrt(paired["garch_variance_squared_error"].mean())),
            "rolling_variance_rmse": float(np.sqrt(paired["rolling_variance_squared_error"].mean())),
            "interpretation": "descriptive_paired_scores_lower_is_better_noisy_daily_proxy",
        })
    return pd.DataFrame(rows)


def classify_volatility_risk(volatility: pd.DataFrame, train_end="2024-12-31"):
    """Return classified forecasts and quartiles fitted ONLY on training events.

    These are sample-relative volatility labels, not credit ratings, loss
    predictions, or calibrated regulatory risk categories. Unknown/failed
    forecasts receive 'Unavailable', never an arbitrary 'Very High' label.
    """
    required = {"event_id", "bank_symbol", "event_date", "garch_volatility", "converged"}
    if required.difference(volatility.columns):
        raise ValueError(f"Missing forecast columns: {sorted(required.difference(volatility.columns))}")
    frame = volatility.copy()
    if frame.duplicated(["event_id", "bank_symbol"]).any():
        raise ValueError("Duplicate bank-event forecasts")
    frame["event_date"] = pd.to_datetime(frame["event_date"])
    cutoff = pd.Timestamp(train_end).normalize()
    usable = frame["converged"].eq(True) & np.isfinite(frame["garch_volatility"]) & frame["garch_volatility"].gt(0)
    training = frame[usable & frame["event_date"].le(cutoff)]
    if len(training) < 4 or training["event_id"].nunique() < 2:
        raise ValueError("Training-only quartiles require four valid forecasts across at least two events")
    quantiles = training["garch_volatility"].quantile([.25, .5, .75]).to_numpy()
    labels = np.array(["Low", "Medium", "High", "Very High"], dtype=object)
    frame["risk_level"] = "Unavailable"
    frame.loc[usable, "risk_level"] = labels[np.searchsorted(quantiles, frame.loc[usable, "garch_volatility"], side="left")]
    frame["threshold_training_cutoff"] = cutoff
    frame["risk_basis"] = "training_sample_garch_volatility_quartiles"
    thresholds = pd.DataFrame({
        "quantile": [.25, .5, .75],
        "threshold": quantiles,
        "training_cutoff": [cutoff] * 3,
        "n_training_rows": [len(training)] * 3,
        "n_training_events": [training["event_id"].nunique()] * 3,
        "classification_basis": ["training_sample_garch_volatility_quartiles"] * 3,
    })
    return frame, thresholds
