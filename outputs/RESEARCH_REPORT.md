# RBI banking market intelligence: corrected research report

**Project version:** 2.0.0  
**Generated from this run:** 2026-11-02T05:06:55.927004+00:00  
**Research scope:** historical association between scheduled RBI policy announcements and the returns of six selected banking stocks.

## 1. Findings and their limits

This report studies 18 policy announcements across 6 banks. The primary outcome is a bank's market-model cumulative abnormal return (CAR) over trading days −1 through +1. The analysis separates an exploratory historical event study from a previous-close prediction experiment and a conditional-volatility monitoring exercise.

The corrected event-level decision comparisons contain **6 calculable tests**, of which **0 have a Holm-adjusted p-value below 0.05** in the declared decision-comparison family. The estimates and their uncertainty are shown below; a favorable unadjusted p-value or bootstrap interval is not substituted for the family-adjusted result. The effect sizes are associations within this particular sample. They do not establish the causal effect of an unexpected policy change.

The prediction experiment trains on 12 events (72 bank-event rows) and evaluates on 6 events (36 rows). Those 36 rows do not constitute 36 independent policy experiments. A model's test score must be read alongside the majority-class baseline and the event-cluster uncertainty intervals, even if a score happens to exceed the baseline in this run.

The market inputs are a **current-vintage historical snapshot**. They were acquired after the study years, and the original project had already inspected its 2025 period. This rebuild is therefore a retrospective chronological holdout evaluation, not an untouched prospective study or a point-in-time data-vintage backtest. Fixed model specifications are used without selecting hyperparameters on this holdout.

## 2. Data provenance, coverage, and quality

Actual acquisition provider: **Yahoo Finance chart endpoint; one explicitly recorded NSE official index-archive repair**. Official RBI materials support the policy-event registry. Official NSE archives support the documented index repair and targeted independent bank-price checks. The project does not describe all downloaded prices as NSE-sourced.

The snapshot contains **9888 asset-date rows** on **1236 observed dates**, including **7410 nonmissing bank daily-return observations**. Price rows and return observations have different counts because the first price of each series has no preceding return. Requested acquisition bounds are 2021-01-01 inclusive through 2026-01-01 exclusive. Exchange dates use the recorded exchange timezone.

The event distribution is:

| Year | Cut | Hike | Hold |
| --- | --- | --- | --- |
| 2023 | 0 | 1 | 5 |
| 2024 | 0 | 0 | 6 |
| 2025 | 4 | 0 | 2 |

All rate-cut events occur in the later sample period. Decision type and market regime are therefore entangled. The sample contains only one hike, so hike comparisons are retained as descriptive entries with undefined inferential p-values rather than treated as six independent hikes because six banks were observed.

The source responses, retrieval times, hashes, corporate-action records, repairs, and price checks are preserved in the [data sources documentation](../docs/data_sources.md) and [market manifest](../data/raw/market_manifest.json). The corrected policy registry places the August 2025 announcement on 6 August; downstream windows are recalculated from the registry rather than changing a label on previously computed results.

There are **1 documented market-data repairs** and **0 forward-filled values** in the acquisition manifest. The special Saturday trading session on 1 February 2025 had a missing Nifty Bank vendor row; a preserved official NSE archive supplies the explicit repair. The original source response remains available. This correction is not a forward-fill from the previous trading day.

Independent bank-price checks cover **12 selected bank/date observations**. Their recorded maximum absolute difference is **4.88e-05 rupees**, after the documented adjustment convention. These checks validate those selected observations; they do not prove the accuracy of every historical price. A common observed calendar across all assets cannot detect a date omitted jointly by every vendor series.

### Return convention

The primary series uses simple close-to-close **price returns from vendor split-adjusted Close**, retaining ex-dividend price movements. The Nifty benchmarks are price indices. Adjusted Close returns are retained for a separate sensitivity analysis; they are not silently substituted into the primary result. The event study fails on missing required trading-day observations instead of treating missing data as zero or compressing a three-day window into three nonconsecutive rows.

## 3. Common event-study specification

For each bank and announcement, ordinary least squares estimates `bank return = alpha + beta × benchmark return + residual`. The same **250 trading observations, days [−255, −6] inclusive**, are used for both Nifty 50 and Nifty Bank. Expected event-window return is `alpha + beta × observed benchmark return`; abnormal return is actual minus expected return; CAR is the sum of abnormal returns over the declared window.

| Window | First relative day | Last relative day | Trading observations |
| --- | --- | --- | --- |
| [-1,+1] | -1 | 1 | 3 |
| [-2,+2] | -2 | 2 | 5 |
| [-5,+5] | -5 | 5 | 11 |
| [0,+1] | 0 | 1 | 2 |

The primary research window is `[-1,+1]`. The wider windows are sensitivity specifications. `[0,+1]` is reserved for the forward target in the prediction experiment. Calendar dates, sample sizes, regression coefficients, and the actual selected trading dates are stored with each result. The full output has **864 bank-event-benchmark-window rows**, not 864 independent events.

Nifty 50 is the primary benchmark; Nifty Bank controls for sector-wide movement. Both indices can themselves respond to RBI news and contain banking exposure. CAR consequently measures performance relative to the chosen benchmark, not the entire economic effect of the announcement. Close-to-close daily data also include information arriving before and after the announcement within the same trading day. [Implementation](../rbi_intelligence/event_study.py) · [Full event results](tables/event_study.csv).

## 4. Event-level inference

Banks within one RBI announcement share the same policy news and market conditions. The inferential sampling unit is therefore the **policy event**. Bank CARs are averaged first; ordinary t-tests on all correlated bank rows are not used to manufacture a larger event sample.

Overall tests use the event means. Decision contrasts use Welch comparisons of event means. The percentile bootstrap resamples whole event means within each decision category, preserving the six-bank event cluster. Public/private comparisons use one paired public-minus-private contrast per event. With only four cuts, bootstrap intervals still reflect a very small observed support and cannot establish stability across monetary-policy cycles.

Holm adjustment is applied separately to the declared families: overall means across benchmarks/windows; decision contrasts across benchmarks/windows; paired signed public/private contrasts; and paired absolute-movement contrasts. Undefined singleton comparisons are not turned into valid tests. Bootstrap intervals are **pointwise exploratory intervals**, not simultaneous multiplicity-adjusted confidence bands. The resampling still assumes that observed events usefully represent the target population; year/regime confounding limits that assumption. [Inference implementation](../rbi_intelligence/statistics.py) · [Decision comparisons](tables/decision_comparisons.csv).

### Overall primary-window reaction

| Benchmark | Events | Mean CAR (%) | 95% lower (%) | 95% upper (%) | Raw p | Holm p |
| --- | --- | --- | --- | --- | --- | --- |
| ^NSEBANK | 18 | 0.0489 | -0.5303 | 0.6281 | 0.8606 | 1.0000 |
| ^NSEI | 18 | -0.0211 | -0.7783 | 0.7360 | 0.9537 | 1.0000 |

A nonsignificant mean is not evidence that every individual announcement had no effect. Opposite-signed reactions can cancel, and a small event sample provides limited precision.

### Cut minus hold

| Benchmark | Window | Cuts | Holds | Difference (pp) | Raw p | Holm p | Bootstrap lower (pp) | Bootstrap upper (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ^NSEBANK | [-1,+1] | 4 | 13 | -1.0592 | 0.0317 | 0.1584 | -1.9034 | -0.3240 |
| ^NSEBANK | [-2,+2] | 4 | 13 | -1.0056 | 0.0185 | 0.1109 | -1.7205 | -0.3392 |
| ^NSEBANK | [-5,+5] | 4 | 13 | -1.2327 | 0.0779 | 0.3115 | -2.5452 | -0.2028 |
| ^NSEI | [-1,+1] | 4 | 13 | -1.1688 | 0.0788 | 0.3115 | -2.2921 | -0.1376 |
| ^NSEI | [-2,+2] | 4 | 13 | -0.6006 | 0.4900 | 0.9801 | -1.9485 | 0.8476 |
| ^NSEI | [-5,+5] | 4 | 13 | 0.3778 | 0.7616 | 0.9801 | -1.6372 | 2.5233 |

`pp` means percentage points: a raw-return difference of −0.01 is −1 percentage point. Confidence intervals and p-values may disagree near a threshold because Welch and the small-sample percentile bootstrap make different approximations. The report shows both, retains all declared windows, and does not select the favorable result. The [leave-one-event-out table](tables/bootstrap_sensitivity.csv) records how each event changes the contrast; it is a sensitivity diagnostic rather than additional independent evidence.

### Public and private banks

| Benchmark | Outcome | Paired events | Public minus private (pp) | Raw p | Holm p |
| --- | --- | --- | --- | --- | --- |
| ^NSEBANK | absolute_car | 18 | 0.9918 | 0.0307 | 0.1229 |
| ^NSEI | absolute_car | 18 | 0.9064 | 0.0683 | 0.2049 |
| ^NSEBANK | car | 18 | 0.2519 | 0.7195 | 1.0000 |
| ^NSEI | car | 18 | 0.1597 | 0.8220 | 1.0000 |

Signed CAR and absolute CAR answer different questions. A bank can have a near-zero average signed reaction and large absolute movements. Public/private results describe these six selected banks, not every bank in either sector.

| Bank | Type | Events | Mean CAR (%) | Mean absolute CAR (%) | Mean daily GARCH volatility (%) |
| --- | --- | --- | --- | --- | --- |
| Axis Bank | Private | 18 | 0.0476 | 1.3650 | 1.4547 |
| Bank of Baroda | Public | 18 | -0.3119 | 1.9672 | 2.2120 |
| Canara Bank | Public | 18 | 0.0344 | 2.1310 | 2.3670 |
| HDFC Bank | Private | 18 | 0.2555 | 1.0710 | 1.3574 |
| ICICI Bank | Private | 18 | -0.6060 | 0.9252 | 1.1428 |
| State Bank of India | Public | 18 | 0.4536 | 1.9822 | 1.6929 |

## 5. Dividends and corporate-action sensitivity

An ex-dividend price decline is not itself a negative investor total return of the same size. Corporate actions can therefore alter a short price-return event window. The following actions overlap the primary window in this run:

| Event | Bank | Action date | Dividend per share (INR) | Split factor | Action |
| --- | --- | --- | --- | --- | --- |
| MPC_2023_08 | ICICI Bank | 2023-08-09 | 8.0000 | 0.0000 | dividend |
| MPC_2025_06 | Bank of Baroda | 2025-06-06 | 8.3500 | 0.0000 | dividend |

The complete [corporate-action overlap ledger](tables/corporate_action_overlaps.csv) also covers the wider windows. A nonzero dividend or split on any actual trading date in a bank's window triggers the exclusion sensitivity for that bank/window only. Splits are included as a conservative sensitivity screen even though the primary vendor Close is already split-adjusted.

Two separate checks are reported. **Adjusted-bank-return sensitivity** refits the model using bank Adjusted Close returns while retaining price-index benchmark returns. This is explicitly a **mixed-convention check**, not a consistent total-return study; proper bank and benchmark total-return series would be required for that claim. **Corporate-action exclusion sensitivity** removes affected bank-event-window rows and averages the remaining banks within each event. It changes portfolio composition, so the resulting estimates are not identical-sample comparisons.

| Scenario | Benchmark | Cut minus hold (pp) | Raw p | Joint sensitivity Holm p | Minimum banks/event | Bank-event exclusions |
| --- | --- | --- | --- | --- | --- | --- |
| primary_split_adjusted_price_returns | ^NSEBANK | -1.0592 | 0.0317 | 0.4728 | 6 | 0 |
| primary_split_adjusted_price_returns | ^NSEI | -1.1688 | 0.0788 | 0.8567 | 6 | 0 |
| adjusted_bank_returns_vs_price_index | ^NSEBANK | -0.9263 | 0.0296 | 0.4728 | 6 | 0 |
| adjusted_bank_returns_vs_price_index | ^NSEI | -1.0358 | 0.0983 | 0.8843 | 6 | 0 |
| exclude_window_corporate_actions | ^NSEBANK | -0.8879 | 0.0333 | 0.4728 | 5 | 2 |
| exclude_window_corporate_actions | ^NSEI | -0.9957 | 0.1094 | 0.8843 | 5 | 2 |

The [sensitivity summary](tables/sensitivity_summary.csv) provides full event counts, pointwise bootstrap intervals, within-scenario adjustment, and a joint sensitivity-family Holm adjustment. The [composition ledger](tables/composition_changes.csv) lists removed banks and events with no retained banks. Changed composition, altered return conventions, and the small event count prevent interpreting a favorable sensitivity as proof of a policy effect. Both checks are retained regardless of whether they strengthen or weaken the original result.

## 6. Conditional volatility and model checks

The volatility model is **GARCH(1,1) with Student-t innovations and a constant mean**. Returns are scaled to percentage units only during fitting for numerical stability; saved forecast volatility is converted back to a fractional daily standard deviation. At each event target, the model is refitted using all available earlier returns, with a minimum of 500 observations. Only event targets are fitted. No event-day return or full-sample fitted parameter enters a historical forecast.

Every forecast stores separate **origin** and **target** dates. The origin is the previous trading close and the target is the announcement trading day. This avoids the earlier ambiguity where a forecast labelled by its target date was joined as if its date were the information cutoff. The daily GARCH forecast and the two- or three-day CAR describe different horizons and are not interchangeable measures. [Volatility implementation](../rbi_intelligence/volatility.py) · [Forecasts and diagnostics](tables/event_volatility.csv).

This run has **108 converged, positive-variance forecasts out of 108 attempts**. Failed or insufficient-history fits are kept in the output, not silently removed:

| Status | Forecasts |
| --- | --- |
| ok | 108 |

Standardized residual diagnostics are recorded for each fitted model:

| Diagnostic | Available fitted models | Unadjusted p < 0.05 |
| --- | --- | --- |
| residual_ljung_box_p | 108 | 17 |
| squared_residual_ljung_box_p | 108 | 14 |
| arch_lm_p | 108 | 14 |

Convergence means the optimizer completed; it does not prove that the conditional variance model is adequate. Residual tests are diagnostic screens, involve repeated testing, and should not be interpreted as independent confirmations of model truth. Persistence, innovation degrees of freedom, AIC/BIC, and warnings remain in the full output.

### Comparison with a simple rolling-variance baseline

A past-only 20-day sample variance is the baseline. The ex-post target proxy is the event day's squared daily return. This is a noisy single-observation proxy for latent variance, not an observed true volatility value. QLIKE and variance squared error are scored on the same converged observations for both methods; lower values are better. QLIKE can be negative because it contains a log-variance term.

| Bank/group | Scored bank-events | Events | GARCH QLIKE | Rolling QLIKE | Difference |
| --- | --- | --- | --- | --- | --- |
| All banks | 108 | 18 | -7.5293 | -7.5326 | 0.0033 |
| AXISBANK.NS | 18 | 18 | -7.3891 | -7.3302 | -0.0590 |
| BANKBARODA.NS | 18 | 18 | -7.2650 | -7.5022 | 0.2372 |
| CANBK.NS | 18 | 18 | -7.2661 | -7.4748 | 0.2087 |
| HDFCBANK.NS | 18 | 18 | -8.0361 | -7.9255 | -0.1106 |
| ICICIBANK.NS | 18 | 18 | -7.9445 | -7.8590 | -0.0855 |
| SBIN.NS | 18 | 18 | -7.2750 | -7.1041 | -0.1709 |

These are descriptive paired scores across correlated bank-event observations, not a formal proof that one forecasting method dominates across future periods. A stronger volatility validation would add more policy cycles, realistic forecast origins, and a better realized-volatility measure where available.

## 7. Training-defined volatility categories

Low, Medium, High, and Very High refer to quartiles of valid **2023–2024 training-event GARCH volatility**. Those thresholds are frozen before applying them to 2025. They are relative positions in this training sample, not universal financial-risk ratings or predictions of loss. Absolute CAR is not used to assign the categories.

| Training quantile | Daily volatility threshold (%) | Cutoff | Training bank-events | Training events |
| --- | --- | --- | --- | --- |
| 0.2500 | 1.3209 | 2024-12-31 | 72 | 12 |
| 0.5000 | 1.5569 | 2024-12-31 | 72 | 12 |
| 0.7500 | 2.0671 | 2024-12-31 | 72 | 12 |

| Bank type | Volatility category | Observations |
| --- | --- | --- |
| Private | High | 5 |
| Private | Low | 31 |
| Private | Medium | 17 |
| Private | Very High | 1 |
| Public | High | 19 |
| Public | Low | 2 |
| Public | Medium | 8 |
| Public | Very High | 25 |

Training-period displayed categories are retrospective descriptions relative to the full training-period thresholds. Only their application to the later test period respects that frozen threshold timing. A historical live-monitoring simulation within 2023–2024 would instead need thresholds fitted using data available at each earlier origin. Failed or missing forecasts receive **Unavailable**, not an arbitrary high-risk label.

## 8. Previous-close prediction experiment

The prediction is made at the last trading close before the announcement. Its target is the sign of **Nifty 50 CAR[0,+1]**, so none of the target return interval has yet occurred. Realized cut/hold/hike is retained only as clearly named descriptive metadata. It is never included in the model's feature list; the actual decision is not known at a before-announcement forecast origin.

Features are bank type, the previous daily return, exact compounded five- and twenty-day returns, twenty- and sixty-day sample volatility, and the correctly aligned event-day GARCH volatility forecast. Compounded returns use the product of one plus daily simple returns, not their sum. Missing GARCH forecasts are retained and imputed inside the training-fitted pipeline, avoiding selective removal of test events. Numeric imputation, scaling, and category encoding are all fit only on training data.

The fixed models are logistic regression (`C=1`, up to 1,000 iterations) and a random forest (300 trees, depth 3, minimum leaf size 6, balanced class weights). The dummy predicts the **training-majority class**, while its probability is the **training positive-class prior**. Using the prior gives a meaningful probability baseline for Brier score and log loss, rather than an artificially overconfident 0/1 baseline. The split is 2023–2024 training and 2025 testing; all banks in one event stay together. [Prediction implementation](../rbi_intelligence/prediction.py) · [Features](tables/predictive_features.csv).

| Model | Accuracy | Balanced accuracy | ROC-AUC | Precision | Recall | F1 | Brier score | Log loss |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dummy_majority | 0.5000 | 0.5000 | 0.5000 | 0.0000 | 0.0000 | 0.0000 | 0.2517 | 0.6966 |
| logistic_regression | 0.3333 | 0.3333 | 0.2407 | 0.2857 | 0.2222 | 0.2500 | 0.3345 | 0.8821 |
| random_forest | 0.4722 | 0.4722 | 0.4691 | 0.4545 | 0.2778 | 0.3448 | 0.2654 | 0.7260 |

Accuracy, balanced accuracy, ROC-AUC, and F1 are better when higher; Brier score and log loss are better when lower. ROC-AUC is unavailable for a one-class test/resample. The [confusion matrices](tables/model_confusion_matrices.csv) and [per-observation predictions](tables/model_predictions.csv) retain information hidden by any single score.

### Event-cluster uncertainty

The bootstrap resamples whole test events with all their banks together. Models and baseline use the same sampled events for paired differences. The intervals describe variation conditional on these few observed test events; they do not estimate the full uncertainty of learning a model from new training data, selecting the project specification, or entering a new policy regime. Event-level resampling addresses dependence among banks within an announcement; it does not remove possible temporal dependence across announcements.

| Model | ROC-AUC | 95% lower | 95% upper | Valid resamples | Requested resamples |
| --- | --- | --- | --- | --- | --- |
| dummy_majority | 0.5000 | 0.5000 | 0.5000 | 2000 | 2000 |
| logistic_regression | 0.2407 | 0.0635 | 0.4540 | 2000 | 2000 |
| random_forest | 0.4691 | 0.3056 | 0.5802 | 2000 | 2000 |

| Model | Paired difference | Estimate | 95% lower | 95% upper |
| --- | --- | --- | --- | --- |
| logistic_regression | accuracy_minus_dummy | -0.1667 | -0.4722 | 0.1389 |
| logistic_regression | roc_auc_minus_dummy | -0.2593 | -0.4365 | -0.0460 |
| random_forest | accuracy_minus_dummy | -0.0278 | -0.1389 | 0.1111 |
| random_forest | roc_auc_minus_dummy | -0.0309 | -0.1944 | 0.0802 |

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
{
  "benchmarks": [
    "^NSEI",
    "^NSEBANK"
  ],
  "estimation_days": 250,
  "estimation_inclusive_relative_days": [
    -255,
    -6
  ],
  "garch_distribution": "Student-t",
  "garch_min_training_returns": 500,
  "inference_bootstrap_repetitions": 10000,
  "prediction_bootstrap_repetitions": 2000,
  "prediction_features": [
    "bank_type",
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "volatility_60d",
    "garch_volatility"
  ],
  "seed": 42,
  "target_window": "[0,+1]",
  "test_end": "2025-12-31",
  "test_start": "2025-01-01",
  "train_end": "2024-12-31",
  "windows": {
    "[-1,+1]": [
      -1,
      1
    ],
    "[-2,+2]": [
      -2,
      2
    ],
    "[-5,+5]": [
      -5,
      5
    ],
    "[0,+1]": [
      0,
      1
    ]
  }
}
```

**Numerical provenance:** all tables in this report are rendered from the supplied current-run result DataFrames. Missing results are shown as unavailable; raw-return fractions are multiplied by 100 only for columns explicitly labelled percent or percentage points.
