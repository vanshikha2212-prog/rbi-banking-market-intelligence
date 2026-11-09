"""Exploratory inference with policy announcements as the sampling units."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .event_study import INFERENCE_WINDOWS


def holm_adjust(p_values) -> np.ndarray:
    """Holm family-wise adjustment, preserving undefined tests as NaN."""
    p = np.asarray(p_values, dtype=float)
    result = np.full(p.shape, np.nan)
    valid = np.flatnonzero(np.isfinite(p))
    if not len(valid):
        return result
    if ((p[valid] < 0) | (p[valid] > 1)).any():
        raise ValueError("p-values must lie in [0,1]")
    order = valid[np.argsort(p[valid], kind="stable")]
    adjusted = np.maximum.accumulate(p[order] * np.arange(len(order), 0, -1))
    result[order] = np.minimum(adjusted, 1.0)
    return result


def bootstrap_mean_difference(a, b, *, n_bootstrap=10000, seed=42):
    """Percentile interval resampling complete event means within each group."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if n_bootstrap < 1:
        raise ValueError("n_bootstrap must be positive")
    if len(a) < 2 or len(b) < 2:
        return {"bootstrap_ci_lower": np.nan, "bootstrap_ci_upper": np.nan, "bootstrap_mean": np.nan}
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Bootstrap input must contain finite event means")
    rng = np.random.default_rng(seed)
    draws = rng.choice(a, (n_bootstrap, len(a))).mean(axis=1) - rng.choice(b, (n_bootstrap, len(b))).mean(axis=1)
    lower, upper = np.quantile(draws, [0.025, 0.975])
    return {"bootstrap_ci_lower": float(lower), "bootstrap_ci_upper": float(upper), "bootstrap_mean": float(draws.mean())}


def _mean_test(values):
    values = np.asarray(values, dtype=float)
    n = len(values)
    result = {"n_events": n, "mean": float(values.mean()) if n else np.nan,
              "standard_error": np.nan, "t_statistic": np.nan, "degrees_freedom": np.nan,
              "p_value": np.nan, "ci_lower": np.nan, "ci_upper": np.nan,
              "status": "insufficient_events"}
    if n < 2:
        return result
    se = float(values.std(ddof=1) / np.sqrt(n))
    result.update(standard_error=se, degrees_freedom=n - 1)
    if se == 0:
        result["status"] = "zero_empirical_variance"
        return result
    statistic = float(values.mean() / se)
    half = float(stats.t.ppf(0.975, n - 1) * se)
    result.update(t_statistic=statistic, p_value=float(2 * stats.t.sf(abs(statistic), n - 1)),
                  ci_lower=float(values.mean() - half), ci_upper=float(values.mean() + half),
                  status="exploratory_small_sample" if n < 20 else "exploratory")
    return result


def _welch(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    result = {"n_a_events": len(a), "n_b_events": len(b),
              "mean_a": float(a.mean()) if len(a) else np.nan,
              "mean_b": float(b.mean()) if len(b) else np.nan,
              "difference": float(a.mean() - b.mean()) if len(a) and len(b) else np.nan,
              "standard_error": np.nan, "t_statistic": np.nan, "degrees_freedom": np.nan,
              "p_value": np.nan, "ci_lower": np.nan, "ci_upper": np.nan,
              "status": "insufficient_events"}
    if min(len(a), len(b)) < 2:
        return result
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    variance = va + vb
    if variance <= 0:
        result["status"] = "zero_empirical_variance"
        return result
    df = float(variance**2 / (va**2 / (len(a) - 1) + vb**2 / (len(b) - 1)))
    se = float(np.sqrt(variance))
    statistic = result["difference"] / se
    half = float(stats.t.ppf(0.975, df) * se)
    result.update(standard_error=se, t_statistic=float(statistic), degrees_freedom=df,
                  p_value=float(2 * stats.t.sf(abs(statistic), df)),
                  ci_lower=result["difference"] - half, ci_upper=result["difference"] + half,
                  status="exploratory_small_sample" if min(len(a), len(b)) < 20 else "exploratory")
    return result


def _adjust_frame(frame, family):
    frame = frame.copy()
    frame["multiple_testing_family"] = family
    frame["p_value_holm"] = holm_adjust(frame["p_value"])
    if "permutation_p_value" in frame:
        frame["permutation_p_value_holm"] = holm_adjust(frame["permutation_p_value"])
    if "wilcoxon_p_value" in frame:
        frame["wilcoxon_p_value_holm"] = holm_adjust(frame["wilcoxon_p_value"])
    frame["n_tests_in_family"] = int(frame["p_value"].notna().sum())
    frame["sampling_unit"] = "policy_event"
    frame["interpretation"] = "exploratory_association_not_causation"
    return frame


def run_inference(event_results, *, seed=42, n_bootstrap=10000) -> dict[str, pd.DataFrame]:
    """Compare event means and paired sector means with declared Holm families.

    All two-benchmark/three-window decision contrasts form one family. Overall
    mean tests form another. Signed and absolute public/private contrasts each
    form their own family. Undefined single-event comparisons are retained and
    labelled, never presented as inferential evidence. Bootstrap CIs are pointwise
    exploratory intervals, not multiplicity-adjusted simultaneous intervals.
    """
    required = {"event_id", "event_date", "decision", "bank_symbol", "bank_type", "benchmark", "window", "car"}
    if required.difference(event_results.columns):
        raise ValueError(f"Missing event-result columns: {sorted(required.difference(event_results.columns))}")
    data = event_results[event_results["window"].isin(INFERENCE_WINDOWS)].copy()
    if data.empty:
        raise ValueError("No declared inference windows found")
    if data.duplicated(["event_id", "bank_symbol", "benchmark", "window"]).any():
        raise ValueError("Duplicate bank-event-benchmark-window observations")
    if not np.isfinite(data["car"].to_numpy(dtype=float)).all():
        raise ValueError("Non-finite CAR values cannot enter inference")
    if (data.groupby("event_id")["decision"].nunique() > 1).any():
        raise ValueError("An event has conflicting decision labels")
    data["absolute_car"] = data["car"].abs()
    keys = ["event_id", "event_date", "decision", "benchmark", "window"]
    event_means = data.groupby(keys, as_index=False, dropna=False).agg(
        mean_car=("car", "mean"), mean_absolute_car=("absolute_car", "mean"), n_banks=("bank_symbol", "nunique")
    )
    overall, comparisons, sensitivity, paired = [], [], [], []
    comparison_names = (("Cut", "Hold"), ("Hike", "Hold"), ("Cut", "Hike"))
    for (benchmark, window), group in event_means.groupby(["benchmark", "window"], sort=True):
        identity = {"benchmark": benchmark, "window": window}
        overall.append({**identity, **_mean_test(group["mean_car"]), "outcome": "mean_car"})
        for group_a, group_b in comparison_names:
            a_frame = group[group["decision"].eq(group_a)]
            b_frame = group[group["decision"].eq(group_b)]
            a, b = a_frame["mean_car"].to_numpy(), b_frame["mean_car"].to_numpy()
            row = {**identity, "group_a": group_a, "group_b": group_b,
                   "comparison": f"{group_a} minus {group_b}", **_welch(a, b),
                   **bootstrap_mean_difference(a, b, n_bootstrap=n_bootstrap, seed=seed),
                   "bootstrap_unit": "policy_event_mean", "bootstrap_repetitions": n_bootstrap,
                   "bootstrap_seed": seed, "bootstrap_interval_type": "pointwise_percentile_95pct"}
            row["permutation_p_value"] = (
                float(stats.permutation_test(
                    (a, b), lambda x, y: np.mean(x) - np.mean(y),
                    permutation_type="independent", alternative="two-sided",
                    n_resamples=9999, random_state=np.random.default_rng(seed),
                ).pvalue)
                if min(len(a), len(b)) >= 2 else np.nan
            )
            comparisons.append(row)
            if min(len(a), len(b)) >= 2:
                for which, frame in (("a", a_frame), ("b", b_frame)):
                    for removed in frame.itertuples(index=False):
                        reduced_a = a_frame.loc[a_frame.event_id.ne(removed.event_id), "mean_car"] if which == "a" else a
                        reduced_b = b_frame.loc[b_frame.event_id.ne(removed.event_id), "mean_car"] if which == "b" else b
                        sensitivity.append({**identity, "comparison": row["comparison"],
                                            "removed_event_id": removed.event_id, "removed_decision": removed.decision,
                                            "difference_without_event": float(np.mean(reduced_a) - np.mean(reduced_b)),
                                            "full_sample_difference": row["difference"]})
    for outcome in ("car", "absolute_car"):
        grouped = data.groupby(["benchmark", "window", "event_id", "bank_type"])[outcome].mean().unstack("bank_type")
        if not {"Public", "Private"}.issubset(grouped.columns):
            continue
        for (benchmark, window), group in grouped.groupby(level=["benchmark", "window"]):
            complete = group[["Public", "Private"]].dropna()
            differences = (complete["Public"] - complete["Private"]).to_numpy()
            row = {"benchmark": benchmark, "window": window, "outcome": outcome,
                   "comparison": "Public minus Private (paired by event)", **_mean_test(differences)}
            try:
                row["wilcoxon_p_value"] = float(stats.wilcoxon(differences, alternative="two-sided").pvalue) if len(differences) >= 2 else np.nan
            except ValueError:
                row["wilcoxon_p_value"] = np.nan
            row["n_incomplete_pairs"] = len(group) - len(complete)
            if len(differences) >= 2:
                rng = np.random.default_rng(seed)
                draws = rng.choice(differences, (n_bootstrap, len(differences))).mean(axis=1)
                row.update(bootstrap_ci_lower=float(np.quantile(draws, .025)),
                           bootstrap_ci_upper=float(np.quantile(draws, .975)))
            else:
                row.update(bootstrap_ci_lower=np.nan, bootstrap_ci_upper=np.nan)
            paired.append(row)
    paired_frame = pd.DataFrame(paired)
    adjusted_pairs = []
    if not paired_frame.empty:
        for outcome, group in paired_frame.groupby("outcome", sort=True):
            adjusted_pairs.append(_adjust_frame(group, f"paired_public_private_{outcome}_all_benchmarks_windows"))
    return {
        "event_means": event_means.sort_values(["event_date", "benchmark", "window"]).reset_index(drop=True),
        "decision_comparisons": _adjust_frame(pd.DataFrame(comparisons), "decision_contrasts_all_benchmarks_windows"),
        "overall_tests": _adjust_frame(pd.DataFrame(overall), "overall_means_all_benchmarks_windows"),
        "paired_bank_comparisons": pd.concat(adjusted_pairs, ignore_index=True) if adjusted_pairs else pd.DataFrame(),
        "bootstrap_sensitivity": pd.DataFrame(sensitivity),
    }
