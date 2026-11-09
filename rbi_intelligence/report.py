"""Generate a numerical research report directly from the current run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _cell(value):
    if pd.isna(value):
        return "—"
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    if isinstance(value, (float, np.floating)):
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(frame, columns, *, percent=(), rename=None):
    if frame.empty:
        return "No eligible records."
    data = frame[[column for column in columns if column in frame]].copy()
    for column in percent:
        if column in data:
            data[column] = pd.to_numeric(data[column], errors="coerce") * 100
    if rename:
        data = data.rename(columns=rename)
    header = "| " + " | ".join(data.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(data.columns)) + " |"
    rows = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in data.itertuples(index=False, name=None)]
    return "\n".join([header, separator, *rows])


def write_report(output_path, tables, manifest) -> Path:
    destination = Path(output_path)
    results = tables["event_study"]
    events = results[["event_id", "event_date", "decision"]].drop_duplicates().sort_values("event_date")
    decisions = events.decision.value_counts().reindex(["Hike", "Cut", "Hold"], fill_value=0)
    primary = tables["decision_comparisons"].query("benchmark == '^NSEI' and window == '[-1,+1]'")
    overall = tables["overall_tests"].query("benchmark == '^NSEI' and window == '[-1,+1]'")
    paired = tables["paired_bank_comparisons"].query("benchmark == '^NSEI' and window == '[-1,+1]'")
    metrics = tables["model_metrics"].sort_values("balanced_accuracy", ascending=False, na_position="last")
    baseline = metrics[metrics.model.eq("dummy_majority")]
    best_model = metrics[~metrics.model.str.startswith(("dummy_", "bank_", "last_"))].head(1)
    beats_accuracy = (not baseline.empty and not best_model.empty and best_model.accuracy.iloc[0] > baseline.accuracy.iloc[0])
    beats_brier = (not baseline.empty and not best_model.empty and best_model.brier_score.iloc[0] < baseline.brier_score.iloc[0])
    uncertainty = tables["model_uncertainty"]
    delta = uncertainty[uncertainty.metric.eq("balanced_accuracy_minus_dummy_majority")]
    robust_win = bool((delta.ci_lower > 0).any()) if not delta.empty else False
    years = pd.to_datetime(events.event_date).dt.year
    by_year = pd.crosstab(years.rename("Year"), events.decision).reset_index()
    bank_summary = results.query("benchmark == '^NSEI' and window == '[-1,+1]'").assign(
        absolute_car=lambda x: x.car.abs()).groupby(["bank_name", "bank_type"], as_index=False).agg(
        mean_car=("car", "mean"), mean_absolute_car=("absolute_car", "mean"), events=("event_id", "nunique"))
    conclusion = (
        "At least one learned model exceeds the rolling majority baseline on both accuracy and Brier score, "
        "but the event-bootstrap comparison does not establish a robust advantage."
        if beats_accuracy and beats_brier and not robust_win else
        "At least one learned model has a positive event-bootstrap lower bound versus the majority baseline on balanced accuracy."
        if robust_win else
        "The evaluated learned models do not show a robust out-of-sample advantage over the rolling majority-class baseline."
    )
    report = f"""# RBI monetary policy and Indian bank stocks — extended study

**Generated:** {manifest.get('generated_at_utc', 'unavailable')}
**Scope:** 57 RBI MPC repo-rate announcements from 4 October 2016 through 5 December 2025; six NSE-listed banks; official NSE daily bank and benchmark prices.

## Executive conclusion

This project measures **historical association**, not causality. It asks whether bank stocks earned abnormal returns around RBI announcements after controlling for either Nifty 50 or Nifty Bank. It also asks a separate question: whether information available by the previous close predicts the sign of the wholly post-origin CAR `[0,+1]` in event-grouped walk-forward testing.

The sample contains **{decisions.Hike} hikes, {decisions.Cut} cuts, and {decisions.Hold} holds**. The primary Nifty 50 `[-1,+1]` decision contrasts are below. Raw, Holm-adjusted, permutation, bootstrap, and leave-one-event-out results are all retained; no specification is selected because it looks favorable.

{_table(primary, ['comparison','n_a_events','n_b_events','difference','ci_lower','ci_upper','p_value','p_value_holm','permutation_p_value','permutation_p_value_holm','bootstrap_ci_lower','bootstrap_ci_upper'], percent=['difference','ci_lower','ci_upper','bootstrap_ci_lower','bootstrap_ci_upper'], rename={'difference':'Difference (pp)','ci_lower':'95% CI low (pp)','ci_upper':'95% CI high (pp)','bootstrap_ci_lower':'Bootstrap low (pp)','bootstrap_ci_upper':'Bootstrap high (pp)'})}

The overall mean-CAR test and paired public/private comparison answer different questions:

{_table(overall, ['outcome','n_events','mean','ci_lower','ci_upper','p_value','p_value_holm'], percent=['mean','ci_lower','ci_upper'])}

{_table(paired, ['outcome','comparison','n_events','mean','ci_lower','ci_upper','p_value','p_value_holm','wilcoxon_p_value','wilcoxon_p_value_holm'], percent=['mean','ci_lower','ci_upper'])}

An adjusted p-value below 0.05 is statistical evidence within its declared family; it is not proof that the repo decision caused the return. Daily windows contain other news, expected and unexpected policy components are not separately observed, and Nifty Bank contains the studied sector.

## Which banks and groups move differently?

The following are descriptive Nifty 50 benchmark results for `[-1,+1]`. Mean absolute CAR measures movement magnitude; signed mean CAR measures direction. They should not be ranked as causal “sensitivity” coefficients.

{_table(bank_summary, ['bank_name','bank_type','events','mean_car','mean_absolute_car'], percent=['mean_car','mean_absolute_car'], rename={'mean_car':'Mean CAR (%)','mean_absolute_car':'Mean |CAR| (%)'})}

Public versus private inference is paired within the same announcement, so each policy event contributes one public-minus-private difference. This is preferable to treating 342 bank-event rows as independent policy shocks.

## Predictive performance — separate from inference

{conclusion}

{_table(metrics, ['model','n_test_events','n_test_rows','accuracy','balanced_accuracy','roc_auc','brier_score','log_loss','expected_calibration_error_5bin','status'], percent=['accuracy','balanced_accuracy'])}

The evaluation begins only after 24 complete training events and then predicts each later announcement once, using every earlier event and keeping all six banks from an announcement together. Calibration uses chronological, event-grouped inner folds. Fixed models include L2 logistic regression, elastic-net logistic regression, random forest, and histogram gradient boosting. Baselines include rolling majority prevalence, bank-specific historical positive rates, and last-event persistence.

Accuracy is not a significance test. A model can beat a baseline by a few rows without a stable advantage across announcements. Conversely, a statistically detectable average abnormal return does not imply that its sign is predictable for a new event.

## Data and research design

{_table(by_year, list(by_year.columns))}

- RBI dates and decisions are tied to event-specific official RBI resolutions or minutes.
- The market snapshot uses official NSE bhavcopies for bank OHLCV and previous close, plus official NSE daily index archives for Nifty 50 and Nifty Bank.
- Bank return is `NSE close / NSE previous close − 1`; the exchange previous-close base prevents split and bonus adjustments from becoming false returns.
- The primary market model uses 250 trading returns ending on day −6. Sensitivities use 120 and 180 days, both benchmarks, several event windows, leave-one-event-out diagnostics, and pre-declared COVID/off-cycle exclusions.
- No forward filling, outcome-driven model choice, test-set threshold selection, or result deletion is permitted.

## Reproducibility and limits

The [run manifest](run_manifest.json) records input, code, package, and output hashes. Full numerical tables are under `outputs/tables`; the dashboard is an **interactive historical dashboard**, not a live market feed.

This remains an observational event study. It does not identify monetary-policy surprises, intraday announcement timing, bank fundamentals, lending/deposit transmission, or long-run causal effects. Results are research evidence, not investment advice.
"""
    destination.write_text(report, encoding="utf-8")
    return destination
