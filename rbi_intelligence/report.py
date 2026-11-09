"""Generate the research report from this run's tables, never copied metrics."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def _cell(value):
    if pd.isna(value):
        return "—"
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    if isinstance(value, (bool, np.bool_)):
        return "Yes" if value else "No"
    if isinstance(value, (int, np.integer)):
        return str(value)
    if isinstance(value, (float, np.floating)):
        if value != 0 and abs(value) < .0001:
            return f"{value:.3g}"
        return f"{value:.4f}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(frame, columns=None, *, percent=(), rename=None):
    if frame is None or frame.empty:
        return "No eligible records were available for this table; no result is inferred."
    columns = list(frame.columns) if columns is None else [c for c in columns if c in frame.columns]
    displayed = frame[columns].copy()
    for column in percent:
        if column in displayed:
            displayed[column] = pd.to_numeric(displayed[column], errors="coerce") * 100
    if rename:
        displayed = displayed.rename(columns=rename)
    header = "| " + " | ".join(map(str, displayed.columns)) + " |"
    separator = "| " + " | ".join(["---"] * len(displayed.columns)) + " |"
    rows = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in displayed.itertuples(index=False, name=None)]
    return "\n".join([header, separator, *rows])


def _primary(frame):
    return frame[frame["window"].eq("[-1,+1]")].copy() if "window" in frame else frame.copy()


def write_report(output_path, tables, manifest) -> Path:
    """Write a reproducible, observational research report in Markdown.

    Every numerical finding below is calculated from the supplied run tables or
    acquisition manifest. Empty/undefined results are retained as unavailable.
    """
    destination = Path(output_path)
    required = ["event_study", "event_means", "decision_comparisons", "overall_tests",
                "paired_bank_comparisons", "event_volatility", "volatility_thresholds",
                "volatility_forecast_evaluation", "predictive_features", "model_metrics",
                "model_uncertainty", "sensitivity_summary", "corporate_action_overlaps", "composition_changes"]
    missing = [name for name in required if name not in tables]
    if missing:
        raise ValueError(f"Report cannot be generated without tables: {missing}")
    results = tables["event_study"]
    events = results[["event_id", "event_date", "decision"]].drop_duplicates("event_id").copy()
    events["event_date"] = pd.to_datetime(events["event_date"])
    decisions_by_year = pd.crosstab(events.event_date.dt.year.rename("Year"), events.decision).reset_index()
    banks = results[["bank_symbol", "bank_name", "bank_type"]].drop_duplicates("bank_symbol")
    sample = _primary(results[results["benchmark"].eq("^NSEI")])
    comparisons = tables["decision_comparisons"]
    cuts = comparisons[comparisons.group_a.eq("Cut") & comparisons.group_b.eq("Hold")]
    cut_primary = _primary(cuts)
    overall_primary = _primary(tables["overall_tests"])
    paired_primary = _primary(tables["paired_bank_comparisons"])
    forecasts = tables["event_volatility"]
    metrics = tables["model_metrics"]
    uncertainty = tables["model_uncertainty"]
    sensitivity = _primary(tables["sensitivity_summary"])
    overlaps = tables["corporate_action_overlaps"]
    primary_actions = _primary(overlaps).drop_duplicates(["event_id", "bank_symbol", "action_date"])
    data_snapshot = manifest.get("data_snapshot", {})
    if not isinstance(data_snapshot, dict):
        data_snapshot = {}
    acquisition = data_snapshot.get("acquisition", {})
    independent_checks = data_snapshot.get("independent_bank_price_checks", {})
    symbols_manifest = data_snapshot.get("rows_by_symbol", {})
    bank_return_count = sum(symbols_manifest.get(s, {}).get("return_observations", 0) for s in banks.bank_symbol)
    row_count = data_snapshot.get("rows", "unavailable")
    date_count = data_snapshot.get("unique_market_dates", "unavailable")
    valid_tests = comparisons[comparisons.p_value.notna()]
    significant_adjusted = int(valid_tests.p_value_holm.lt(.05).sum())
    n_train_events = int(metrics.n_train_events.max()) if not metrics.empty else 0
    n_test_events = int(metrics.n_test_events.max()) if not metrics.empty else 0
    n_train_rows = int(metrics.n_train_rows.max()) if not metrics.empty else 0
    n_test_rows = int(metrics.n_test_rows.max()) if not metrics.empty else 0
    converged = forecasts[forecasts.converged.eq(True)]
    forecast_status = forecasts.groupby("status").size().rename("Forecasts").reset_index()
    average_by_bank = sample.assign(absolute_car=sample.car.abs()).groupby(
        ["bank_symbol", "bank_name", "bank_type"], as_index=False
    ).agg(n_events=("event_id", "nunique"), mean_car=("car", "mean"), mean_absolute_car=("absolute_car", "mean"))
    average_by_bank = average_by_bank.merge(converged.groupby("bank_symbol")["garch_volatility"].mean(),
                                          on="bank_symbol", how="left")
    window_table = results[["window", "window_start_day", "window_end_day", "n_event"]].drop_duplicates().sort_values("window")
    risk_counts = forecasts.groupby(["bank_type", "risk_level"]).size().rename("Observations").reset_index() if "risk_level" in forecasts else pd.DataFrame()
    diagnostics = pd.DataFrame()
    diagnostic_rows = []
    for column in ("residual_ljung_box_p", "squared_residual_ljung_box_p", "arch_lm_p"):
        if column in converged:
            available = converged[column].dropna()
            diagnostic_rows.append({"Diagnostic": column, "Available fitted models": len(available),
                                    "Unadjusted p < 0.05": int(available.lt(.05).sum())})
    if diagnostic_rows:
        diagnostics = pd.DataFrame(diagnostic_rows)
    auc_uncertainty = uncertainty[uncertainty.metric.eq("roc_auc")] if "metric" in uncertainty else uncertainty
    delta_uncertainty = uncertainty[uncertainty.metric.isin(["accuracy_minus_dummy", "roc_auc_minus_dummy"])] if "metric" in uncertainty else pd.DataFrame()
    parameters = manifest.get("parameters", {})
    parts = [f"""# RBI banking market intelligence: corrected research report

**Project version:** {manifest.get('project_version', 'unavailable')}  
**Generated from this run:** {manifest.get('generated_at_utc', 'unavailable')}  
**Research scope:** historical association between scheduled RBI policy announcements and the returns of six selected banking stocks.

## 1. Findings and their limits

This report studies {events.event_id.nunique()} policy announcements across {banks.bank_symbol.nunique()} banks. The primary outcome is a bank's market-model cumulative abnormal return (CAR) over trading days −1 through +1. The analysis separates an exploratory historical event study from a previous-close prediction experiment and a conditional-volatility monitoring exercise.

The corrected event-level decision comparisons contain **{len(valid_tests)} calculable tests**, of which **{significant_adjusted} have a Holm-adjusted p-value below 0.05** in the declared decision-comparison family. The estimates and their uncertainty are shown below; a favorable unadjusted p-value or bootstrap interval is not substituted for the family-adjusted result. The effect sizes are associations within this particular sample. They do not establish the causal effect of an unexpected policy change.

The prediction experiment trains on {n_train_events} events ({n_train_rows} bank-event rows) and evaluates on {n_test_events} events ({n_test_rows} rows). Those {n_test_rows} rows do not constitute {n_test_rows} independent policy experiments. A model's test score must be read alongside the majority-class baseline and the event-cluster uncertainty intervals, even if a score happens to exceed the baseline in this run.

The market inputs are a **current-vintage historical snapshot**. They were acquired after the study years, and the original project had already inspected its 2025 period. This rebuild is therefore a retrospective chronological holdout evaluation, not an untouched prospective study or a point-in-time data-vintage backtest. Fixed model specifications are used without selecting hyperparameters on this holdout.

## 2. Data provenance, coverage, and quality

Actual acquisition provider: **{data_snapshot.get('data_provider', 'See acquisition manifest')}**. Official RBI materials support the policy-event registry. Official NSE archives support the documented index repair and targeted independent bank-price checks. The project does not describe all downloaded prices as NSE-sourced.

The snapshot contains **{row_count} asset-date rows** on **{date_count} observed dates**, including **{bank_return_count} nonmissing bank daily-return observations**. Price rows and return observations have different counts because the first price of each series has no preceding return. Requested acquisition bounds are {acquisition.get('requested_start_inclusive', 'unavailable')} inclusive through {acquisition.get('requested_end_exclusive', 'unavailable')} exclusive. Exchange dates use the recorded exchange timezone.

The event distribution is:

{_table(decisions_by_year)}

All rate-cut events occur in the later sample period. Decision type and market regime are therefore entangled. The sample contains only one hike, so hike comparisons are retained as descriptive entries with undefined inferential p-values rather than treated as six independent hikes because six banks were observed.

The source responses, retrieval times, hashes, corporate-action records, repairs, and price checks are preserved in the [data sources documentation](../docs/data_sources.md) and [market manifest](../data/raw/market_manifest.json). The corrected policy registry places the August 2025 announcement on 6 August; downstream windows are recalculated from the registry rather than changing a label on previously computed results.

There are **{data_snapshot.get('repair_count', 'unavailable')} documented market-data repairs** and **{data_snapshot.get('forward_filled_values', 'unavailable')} forward-filled values** in the acquisition manifest. The special Saturday trading session on 1 February 2025 had a missing Nifty Bank vendor row; a preserved official NSE archive supplies the explicit repair. The original source response remains available. This correction is not a forward-fill from the previous trading day.

Independent bank-price checks cover **{independent_checks.get('bank_price_checks', 'unavailable')} selected bank/date observations**. Their recorded maximum absolute difference is **{_cell(independent_checks.get('maximum_absolute_difference_inr', np.nan))} rupees**, after the documented adjustment convention. These checks validate those selected observations; they do not prove the accuracy of every historical price. A common observed calendar across all assets cannot detect a date omitted jointly by every vendor series.

### Return convention

The primary series uses simple close-to-close **price returns from vendor split-adjusted Close**, retaining ex-dividend price movements. The Nifty benchmarks are price indices. Adjusted Close returns are retained for a separate sensitivity analysis; they are not silently substituted into the primary result. The event study fails on missing required trading-day observations instead of treating missing data as zero or compressing a three-day window into three nonconsecutive rows.

## 3. Common event-study specification

For each bank and announcement, ordinary least squares estimates `bank return = alpha + beta × benchmark return + residual`. The same **250 trading observations, days [−255, −6] inclusive**, are used for both Nifty 50 and Nifty Bank. Expected event-window return is `alpha + beta × observed benchmark return`; abnormal return is actual minus expected return; CAR is the sum of abnormal returns over the declared window.

{_table(window_table, ['window', 'window_start_day', 'window_end_day', 'n_event'], rename={'window':'Window','window_start_day':'First relative day','window_end_day':'Last relative day','n_event':'Trading observations'})}

The primary research window is `[-1,+1]`. The wider windows are sensitivity specifications. `[0,+1]` is reserved for the forward target in the prediction experiment. Calendar dates, sample sizes, regression coefficients, and the actual selected trading dates are stored with each result. The full output has **{len(results)} bank-event-benchmark-window rows**, not {len(results)} independent events.

Nifty 50 is the primary benchmark; Nifty Bank controls for sector-wide movement. Both indices can themselves respond to RBI news and contain banking exposure. CAR consequently measures performance relative to the chosen benchmark, not the entire economic effect of the announcement. Close-to-close daily data also include information arriving before and after the announcement within the same trading day. [Implementation](../rbi_intelligence/event_study.py) · [Full event results](tables/event_study.csv).

## 4. Event-level inference

Banks within one RBI announcement share the same policy news and market conditions. The inferential sampling unit is therefore the **policy event**. Bank CARs are averaged first; ordinary t-tests on all correlated bank rows are not used to manufacture a larger event sample.

Overall tests use the event means. Decision contrasts use Welch comparisons of event means. The percentile bootstrap resamples whole event means within each decision category, preserving the six-bank event cluster. Public/private comparisons use one paired public-minus-private contrast per event. With only four cuts, bootstrap intervals still reflect a very small observed support and cannot establish stability across monetary-policy cycles.

Holm adjustment is applied separately to the declared families: overall means across benchmarks/windows; decision contrasts across benchmarks/windows; paired signed public/private contrasts; and paired absolute-movement contrasts. Undefined singleton comparisons are not turned into valid tests. Bootstrap intervals are **pointwise exploratory intervals**, not simultaneous multiplicity-adjusted confidence bands. The resampling still assumes that observed events usefully represent the target population; year/regime confounding limits that assumption. [Inference implementation](../rbi_intelligence/statistics.py) · [Decision comparisons](tables/decision_comparisons.csv).

### Overall primary-window reaction

{_table(overall_primary, ['benchmark','n_events','mean','ci_lower','ci_upper','p_value','p_value_holm'], percent=['mean','ci_lower','ci_upper'], rename={'benchmark':'Benchmark','n_events':'Events','mean':'Mean CAR (%)','ci_lower':'95% lower (%)','ci_upper':'95% upper (%)','p_value':'Raw p','p_value_holm':'Holm p'})}

A nonsignificant mean is not evidence that every individual announcement had no effect. Opposite-signed reactions can cancel, and a small event sample provides limited precision.

### Cut minus hold

{_table(cuts, ['benchmark','window','n_a_events','n_b_events','difference','p_value','p_value_holm','bootstrap_ci_lower','bootstrap_ci_upper'], percent=['difference','bootstrap_ci_lower','bootstrap_ci_upper'], rename={'benchmark':'Benchmark','window':'Window','n_a_events':'Cuts','n_b_events':'Holds','difference':'Difference (pp)','p_value':'Raw p','p_value_holm':'Holm p','bootstrap_ci_lower':'Bootstrap lower (pp)','bootstrap_ci_upper':'Bootstrap upper (pp)'})}

`pp` means percentage points: a raw-return difference of −0.01 is −1 percentage point. Confidence intervals and p-values may disagree near a threshold because Welch and the small-sample percentile bootstrap make different approximations. The report shows both, retains all declared windows, and does not select the favorable result. The [leave-one-event-out table](tables/bootstrap_sensitivity.csv) records how each event changes the contrast; it is a sensitivity diagnostic rather than additional independent evidence.

### Public and private banks

{_table(paired_primary, ['benchmark','outcome','n_events','mean','p_value','p_value_holm'], percent=['mean'], rename={'benchmark':'Benchmark','outcome':'Outcome','n_events':'Paired events','mean':'Public minus private (pp)','p_value':'Raw p','p_value_holm':'Holm p'})}

Signed CAR and absolute CAR answer different questions. A bank can have a near-zero average signed reaction and large absolute movements. Public/private results describe these six selected banks, not every bank in either sector.

{_table(average_by_bank, ['bank_name','bank_type','n_events','mean_car','mean_absolute_car','garch_volatility'], percent=['mean_car','mean_absolute_car','garch_volatility'], rename={'bank_name':'Bank','bank_type':'Type','n_events':'Events','mean_car':'Mean CAR (%)','mean_absolute_car':'Mean absolute CAR (%)','garch_volatility':'Mean daily GARCH volatility (%)'})}

## 5. Dividends and corporate-action sensitivity

An ex-dividend price decline is not itself a negative investor total return of the same size. Corporate actions can therefore alter a short price-return event window. The following actions overlap the primary window in this run:

{_table(primary_actions, ['event_id','bank_name','action_date','dividend_cash_per_share','stock_split_factor','action_type'], rename={'event_id':'Event','bank_name':'Bank','action_date':'Action date','dividend_cash_per_share':'Dividend per share (INR)','stock_split_factor':'Split factor','action_type':'Action'})}

The complete [corporate-action overlap ledger](tables/corporate_action_overlaps.csv) also covers the wider windows. A nonzero dividend or split on any actual trading date in a bank's window triggers the exclusion sensitivity for that bank/window only. Splits are included as a conservative sensitivity screen even though the primary vendor Close is already split-adjusted.

Two separate checks are reported. **Adjusted-bank-return sensitivity** refits the model using bank Adjusted Close returns while retaining price-index benchmark returns. This is explicitly a **mixed-convention check**, not a consistent total-return study; proper bank and benchmark total-return series would be required for that claim. **Corporate-action exclusion sensitivity** removes affected bank-event-window rows and averages the remaining banks within each event. It changes portfolio composition, so the resulting estimates are not identical-sample comparisons.

{_table(sensitivity, ['scenario','benchmark','difference','p_value','p_value_holm_across_sensitivity_family','min_banks_per_original_event','n_bank_event_observations_excluded'], percent=['difference'], rename={'scenario':'Scenario','benchmark':'Benchmark','difference':'Cut minus hold (pp)','p_value':'Raw p','p_value_holm_across_sensitivity_family':'Joint sensitivity Holm p','min_banks_per_original_event':'Minimum banks/event','n_bank_event_observations_excluded':'Bank-event exclusions'})}

The [sensitivity summary](tables/sensitivity_summary.csv) provides full event counts, pointwise bootstrap intervals, within-scenario adjustment, and a joint sensitivity-family Holm adjustment. The [composition ledger](tables/composition_changes.csv) lists removed banks and events with no retained banks. Changed composition, altered return conventions, and the small event count prevent interpreting a favorable sensitivity as proof of a policy effect. Both checks are retained regardless of whether they strengthen or weaken the original result.

## 6. Conditional volatility and model checks

The volatility model is **GARCH(1,1) with Student-t innovations and a constant mean**. Returns are scaled to percentage units only during fitting for numerical stability; saved forecast volatility is converted back to a fractional daily standard deviation. At each event target, the model is refitted using all available earlier returns, with a minimum of 500 observations. Only event targets are fitted. No event-day return or full-sample fitted parameter enters a historical forecast.

Every forecast stores separate **origin** and **target** dates. The origin is the previous trading close and the target is the announcement trading day. This avoids the earlier ambiguity where a forecast labelled by its target date was joined as if its date were the information cutoff. The daily GARCH forecast and the two- or three-day CAR describe different horizons and are not interchangeable measures. [Volatility implementation](../rbi_intelligence/volatility.py) · [Forecasts and diagnostics](tables/event_volatility.csv).

This run has **{len(converged)} converged, positive-variance forecasts out of {len(forecasts)} attempts**. Failed or insufficient-history fits are kept in the output, not silently removed:

{_table(forecast_status, ['status','Forecasts'], rename={'status':'Status'})}

Standardized residual diagnostics are recorded for each fitted model:

{_table(diagnostics)}

Convergence means the optimizer completed; it does not prove that the conditional variance model is adequate. Residual tests are diagnostic screens, involve repeated testing, and should not be interpreted as independent confirmations of model truth. Persistence, innovation degrees of freedom, AIC/BIC, and warnings remain in the full output.

### Comparison with a simple rolling-variance baseline

A past-only 20-day sample variance is the baseline. The ex-post target proxy is the event day's squared daily return. This is a noisy single-observation proxy for latent variance, not an observed true volatility value. QLIKE and variance squared error are scored on the same converged observations for both methods; lower values are better. QLIKE can be negative because it contains a log-variance term.

{_table(tables['volatility_forecast_evaluation'], ['bank_symbol','n_scored','n_events_scored','mean_garch_qlike','mean_rolling_qlike','garch_minus_rolling_qlike'], rename={'bank_symbol':'Bank/group','n_scored':'Scored bank-events','n_events_scored':'Events','mean_garch_qlike':'GARCH QLIKE','mean_rolling_qlike':'Rolling QLIKE','garch_minus_rolling_qlike':'Difference'})}

These are descriptive paired scores across correlated bank-event observations, not a formal proof that one forecasting method dominates across future periods. A stronger volatility validation would add more policy cycles, realistic forecast origins, and a better realized-volatility measure where available.

## 7. Training-defined volatility categories

Low, Medium, High, and Very High refer to quartiles of valid **2023–2024 training-event GARCH volatility**. Those thresholds are frozen before applying them to 2025. They are relative positions in this training sample, not universal financial-risk ratings or predictions of loss. Absolute CAR is not used to assign the categories.

{_table(tables['volatility_thresholds'], ['quantile','threshold','training_cutoff','n_training_rows','n_training_events'], percent=['threshold'], rename={'quantile':'Training quantile','threshold':'Daily volatility threshold (%)','training_cutoff':'Cutoff','n_training_rows':'Training bank-events','n_training_events':'Training events'})}

{_table(risk_counts, ['bank_type','risk_level','Observations'], rename={'bank_type':'Bank type','risk_level':'Volatility category'})}

Training-period displayed categories are retrospective descriptions relative to the full training-period thresholds. Only their application to the later test period respects that frozen threshold timing. A historical live-monitoring simulation within 2023–2024 would instead need thresholds fitted using data available at each earlier origin. Failed or missing forecasts receive **Unavailable**, not an arbitrary high-risk label.

## 8. Previous-close prediction experiment

The prediction is made at the last trading close before the announcement. Its target is the sign of **Nifty 50 CAR[0,+1]**, so none of the target return interval has yet occurred. Realized cut/hold/hike is retained only as clearly named descriptive metadata. It is never included in the model's feature list; the actual decision is not known at a before-announcement forecast origin.

Features are bank type, the previous daily return, exact compounded five- and twenty-day returns, twenty- and sixty-day sample volatility, and the correctly aligned event-day GARCH volatility forecast. Compounded returns use the product of one plus daily simple returns, not their sum. Missing GARCH forecasts are retained and imputed inside the training-fitted pipeline, avoiding selective removal of test events. Numeric imputation, scaling, and category encoding are all fit only on training data.

The fixed models are logistic regression (`C=1`, up to 1,000 iterations) and a random forest (300 trees, depth 3, minimum leaf size 6, balanced class weights). The dummy predicts the **training-majority class**, while its probability is the **training positive-class prior**. Using the prior gives a meaningful probability baseline for Brier score and log loss, rather than an artificially overconfident 0/1 baseline. The split is 2023–2024 training and 2025 testing; all banks in one event stay together. [Prediction implementation](../rbi_intelligence/prediction.py) · [Features](tables/predictive_features.csv).

{_table(metrics, ['model','accuracy','balanced_accuracy','roc_auc','precision','recall','f1','brier_score','log_loss'], rename={'model':'Model','accuracy':'Accuracy','balanced_accuracy':'Balanced accuracy','roc_auc':'ROC-AUC','precision':'Precision','recall':'Recall','f1':'F1','brier_score':'Brier score','log_loss':'Log loss'})}

Accuracy, balanced accuracy, ROC-AUC, and F1 are better when higher; Brier score and log loss are better when lower. ROC-AUC is unavailable for a one-class test/resample. The [confusion matrices](tables/model_confusion_matrices.csv) and [per-observation predictions](tables/model_predictions.csv) retain information hidden by any single score.

### Event-cluster uncertainty

The bootstrap resamples whole test events with all their banks together. Models and baseline use the same sampled events for paired differences. The intervals describe variation conditional on these few observed test events; they do not estimate the full uncertainty of learning a model from new training data, selecting the project specification, or entering a new policy regime. Event-level resampling addresses dependence among banks within an announcement; it does not remove possible temporal dependence across announcements.

{_table(auc_uncertainty, ['model','estimate','ci_lower','ci_upper','n_valid_bootstrap','n_requested_bootstrap'], rename={'model':'Model','estimate':'ROC-AUC','ci_lower':'95% lower','ci_upper':'95% upper','n_valid_bootstrap':'Valid resamples','n_requested_bootstrap':'Requested resamples'})}

{_table(delta_uncertainty, ['model','metric','estimate','ci_lower','ci_upper'], rename={'model':'Model','metric':'Paired difference','estimate':'Estimate','ci_lower':'95% lower','ci_upper':'95% upper'})}

All cuts occur in the later period, so deleting the unavailable decision feature does not eliminate the broader regime shift. Six test events are insufficient to establish a stable trading edge. Models are not selected, retuned, or inverted after seeing these test scores. The fixed specifications should be evaluated on genuinely new events before any claim of prospective predictive usefulness.

## 9. Interpretation and remaining limitations

The defensible contribution is a transparent historical association study with reproducible calculations, sensitivity analyses, and an explicitly exploratory prediction experiment. The project is not a causal identification design or a production investment system.

1. **Small and imbalanced policy sample:** four cuts, one hike, and thirteen holds do not cover multiple comparable policy cycles. More bank rows cannot replace more policy events.
2. **Regime confounding and expectations:** actual decisions are responses to economic conditions. No credible policy-surprise series is constructed, so expected and unexpected policy components are not separated.
3. **Contemporaneous news:** earnings, domestic and global news, liquidity measures, and other announcements can coincide with the event windows. Dividend/split checks address only one known class of overlap.
4. **Daily timing and benchmark exposure:** daily returns blend intraday information, and both benchmarks can respond to the same news. Relative CAR cannot be read as the total causal market response.
5. **Vendor and data-vintage limitations:** preserved responses and targeted NSE checks improve traceability, but do not create a complete independent audit of every price or a historical point-in-time data feed.
6. **Return-convention and composition sensitivities:** adjusted-bank/price-index results mix conventions; exclusion results change the bank portfolio. Neither is an interchangeable replacement for a consistent primary specification.
7. **Model uncertainty:** volatility diagnostics, noisy daily variance proxies, and event-cluster prediction intervals are useful checks, but the short holdout cannot support strong generalization.
8. **Operational scope:** there is no execution engine, transaction-cost model, live data service, or demonstrated investment performance. CSV exports and a local dashboard are evidence of analytical presentation, not evidence that an external Tableau workbook or SAS job was run.

## 10. Reproduction, evidence, and résumé wording

From the repository root, run `python -m rbi_intelligence run` in the documented environment to regenerate this report and its tables. Run `python -m rbi_intelligence verify` for the artifact checks and `python -m pytest` for the automated suite. The [README](../README.md) records the exact environment setup and invocation. Raw snapshots and acquisition hashes allow this run to be distinguished from a later refreshed-data run.

This report links to the generated CSV tables rather than repeating manually maintained result constants. The [research design](../docs/research_design.md), [data dictionary](../docs/data_dictionary.md), [source documentation](../docs/data_sources.md), and source modules explain the assumptions and implementation. The offline dashboard presents historical results with their benchmark/window context; it is not a live market forecast service.

Suggested accurate project description, subject to the author being able to explain and reproduce the work:

> Built a reproducible RBI banking event-study pipeline covering 18 policy announcements and six banks; implemented event-level inference, benchmark and corporate-action sensitivities, past-only GARCH forecasts, chronological prediction baselines, SQL outputs, and an interactive historical-analysis dashboard.

Quantify verified coverage and implemented validation. Do not claim profitable trading, accurate stock prediction, causal policy effects, full NSE sourcing, or executed external-tool validation without the corresponding evidence. A documented null or weak predictive result is a research finding, not a reason to report a more favorable metric from another split.

### Run parameters

```json
{json.dumps(parameters, indent=2, sort_keys=True, default=str)}
```

**Numerical provenance:** all tables in this report are rendered from the supplied current-run result DataFrames. Missing results are shown as unavailable; raw-return fractions are multiplied by 100 only for columns explicitly labelled percent or percentage points.
"""]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(parts), encoding="utf-8")
    return destination
