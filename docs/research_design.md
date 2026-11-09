# Research design

## Purpose and interpretation

This project measures market-adjusted banking-stock returns around RBI monetary-policy announcements and evaluates a small, chronological prediction experiment. Its empirical estimand is an **association around an announcement**, not the causal effect of a surprise interest-rate change. A repo-rate hold can still convey news about the outlook, liquidity or policy stance; the dataset does not contain a measured policy-surprise variable.

The implementation is in `rbi_intelligence/`. Current numerical findings are generated from retained snapshots in `outputs/RESEARCH_REPORT.md`; this document defines the methods rather than preserving results from an earlier dataset. [Data sources](data_sources.md), the [data dictionary](data_dictionary.md), and [reproduction instructions](reproduction.md) describe the evidence and execution contract.

## 1. Sample, sources and event timing

The policy sample contains 18 announcements in 2023–2025: 13 holds, four cuts and one hike. Each row links to event-specific official RBI material. The August 2025 announcement is **6 August**, following the actual 4–6 August meeting, as stated in the [RBI resolution](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60957). Meeting boundaries, announcement dates and later publication dates of minutes are distinct concepts.

The bank universe comprises HDFC Bank, ICICI Bank and Axis Bank (`Private`), and State Bank of India, Bank of Baroda and Canara Bank (`Public`). This is a selected six-bank sample, not a representative sample of all Indian banks. Nifty 50 (`^NSEI`) is the primary benchmark; Nifty Bank (`^NSEBANK`) is a banking-sector sensitivity benchmark. Nifty Bank addresses a different relative-performance question, but banking constituents can share the policy exposure being studied.

Daily observations span 1 January 2021 through 31 December 2025. The primary acquisition source is **Yahoo Finance's chart endpoint**, with original JSON, query parameters, retrieval times and hashes retained. One missing Nifty Bank observation is repaired from an official NSE daily index archive. Twelve selected bank closes and one Nifty 50 close are independently compared with retained NSE observations. These checks support the selected observations and adjustment convention; they do not authenticate every historical price. The full source map and repair values are in [data_sources.md](data_sources.md).

The primary return convention is vendor-returned split-adjusted closing-price return:

\[
R_{i,t}=P_{i,t}/P_{i,t-1}-1.
\]

Both bank and benchmark returns therefore use a price convention. Cash dividends are not included in the primary shareholder return. An ex-dividend price movement can affect an event-window CAR and is examined explicitly below. Adjusted-close returns are retained separately rather than silently substituting them for price returns.

Timestamps are converted to `Asia/Kolkata` session dates. All eight series must have the same observed date set after the documented repair. Returns use `pct_change(fill_method=None)`, and missing prices or returns inside a series cause failure. A date jointly omitted from all eight series would not be detected by this comparison; a complete independent NSE session calendar is not reconstructed. Large movements are flagged and retained, not automatically winsorized.

## 2. Market-model event study

Event day 0 is the public announcement date. Relative days refer to positions in the common **trading-session calendar**, not calendar-day offsets. No announcement is silently moved to a nearby session.

| Purpose | Trading-day window | Observations per bank/event |
|---|---|---:|
| Primary descriptive and inferential outcome | `[-1,+1]` | 3 |
| Window sensitivity | `[-2,+2]` | 5 |
| Wider-window sensitivity | `[-5,+5]` | 11 |
| Wholly future prediction label, from the previous close | `[0,+1]` | 2 |

For each bank, event and benchmark, ordinary least squares fits exactly **250 returns over inclusive relative days `[-255,-6]`**:

\[
R_{i,t}=\alpha_i+\beta_iR_{m,t}+\epsilon_{i,t}.
\]

The model is refitted for each bank/event/benchmark. This period ends before the widest event window and does not use event-window outcomes. Both benchmarks use the same estimation rules. Insufficient history, missing values, duplicate keys or a degenerate benchmark regression cause an explicit error.

The fitted market relationship defines expected return and abnormal return:

\[
\widehat R_{i,t}=\widehat\alpha_i+\widehat\beta_iR_{m,t},
\qquad AR_{i,t}=R_{i,t}-\widehat R_{i,t}.
\]

Cumulative abnormal return is the **sum** of abnormal returns in a window:

\[
CAR_{i,[a,b]}=\sum_{t=a}^{b}AR_{i,t}.
\]

It is neither a compounded investment return nor an estimate of a causal counterfactual. Positive CAR means performance above the fitted benchmark relationship. Long-format results retain the benchmark, window, actual estimation and event-window dates, and observation counts. With the full sample, 18 events × six banks × two benchmarks × four windows produce 864 result rows. There are only 108 distinct bank/event pairs; additional windows and benchmarks are alternative measurements of those pairs.

## 3. Statistical inference and uncertainty

The **policy announcement is the sampling unit**. Banks at the same event share information and market conditions, so six bank rows are not treated as six independent policy realizations. For each event, benchmark and inference window, the analysis first takes equally weighted mean CAR across banks. Inference uses the three symmetric windows; `[0,+1]` is reserved for prediction and descriptive output.

| Question | Implemented comparison | Effective units |
|---|---|---|
| Is average event CAR different from zero? | One-sample t-test of event mean CAR | 18 event means |
| Do cuts differ from holds? | Welch comparison of decision-group event means | Four cut events and 13 hold events |
| Do hikes differ from holds or cuts? | Descriptive difference retained; inferential fields unavailable if either group has fewer than two events | One hike cannot estimate a group variance |
| Do public and private banks differ? | Public-minus-private mean CAR within each event, then a one-sample test of paired differences | One paired difference per event |
| Do movement magnitudes differ? | The same paired procedure using mean absolute bank CAR | One paired difference per event |

Mean absolute CAR is the mean of the banks' absolute CAR values, **not** the absolute value of their mean CAR. Signed movements can offset each other, so the two summaries answer different questions.

Outputs include estimates, standard errors, t-statistics, degrees of freedom, raw p-values and pointwise 95% t intervals where estimable. Undefined tests remain missing with a diagnostic status. Holm adjustments cover four declared families, each spanning both benchmarks and the three inference windows:

1. All overall mean tests.
2. All estimable decision-group contrasts.
3. Public/private signed-CAR contrasts.
4. Public/private absolute-CAR contrasts.

The number of estimable tests is recorded. These adjustments do not convert the exercise into a confirmatory study: the sample and methods were examined during project development. All findings remain exploratory, including apparently small adjusted p-values.

Default bootstrap uncertainty uses **10,000 resamples and seed 42**. Decision comparisons resample complete event means separately within decision groups. Public/private comparisons resample paired event differences. Percentile intervals are pointwise, not simultaneous intervals adjusted for every comparison. A leave-one-event-out table shows how the cut-minus-hold estimate changes when each contributing announcement is removed.

Event aggregation addresses direct same-announcement dependence. It does not prove that distinct announcements are independent or remove macroeconomic regime confounding. All cuts occur in 2025; all 2024 events are holds. With four cuts and one hike, neither asymptotic tests nor the bootstrap creates a large amount of independent information.

## 4. Dividend and corporate-action sensitivities

The primary price-return specification is retained alongside two explicit alternatives:

| Scenario | Change | Interpretation constraint |
|---|---|---|
| `primary_split_adjusted_price_returns` | Bank Close returns against index Close returns | Ex-dividend price movements remain in the outcome |
| `adjusted_bank_returns_vs_price_index` | Replace bank returns with adjusted-close returns, leave index price returns unchanged, and refit | Mixed conventions; not a matched total-return study |
| `exclude_window_corporate_actions` | Remove bank/event/benchmark/window rows containing a recorded dividend or share-ratio action | Remaining banks are equally weighted, changing some event portfolios |

Actions are matched to the exact trading dates in each result window. The overlap ledger identifies the bank, event, window, action date and vendor amount/ratio. The composition ledger records retained and excluded banks, counts and event means. A wholly excluded event is visible rather than assigned a zero return.

The adjustment sensitivity is labelled as mixed convention because compatible total-return benchmark histories are not available in this snapshot. It diagnoses dividend sensitivity; it is not a fully matched total-return specification. Excluding already split-adjusted share-ratio dates is a sensitivity choice, not an assertion that every such date contains an error.

Sensitivity comparisons retain within-scenario Holm adjustment and add a Holm family across **all estimable decision contrasts, scenarios, benchmarks and inference windows**. No scenario is selected because it gives a preferred sign or p-value. The pipeline does not claim to have identified or excluded every earnings release, merger, macroeconomic announcement or liquidity measure.

## 5. Past-only volatility forecasts

The volatility module fits a constant-mean **Student-t GARCH(1,1)** model separately for each bank and announcement:

\[
\sigma_t^2=\omega+\alpha\epsilon_{t-1}^2+\beta\sigma_{t-1}^2.
\]

Training uses expanding return history strictly before the announcement, with at least **500 available returns**. Each fit produces a one-session-ahead forecast for event day 0. Origin is the previous trading close; target is the announcement session. Full-sample parameters and event-day returns do not enter fitting. Only the 108 event targets are fitted, rather than every daily date.

Returns are fitted in percentage units for numerical conditioning; reported variance and volatility are converted back to fractional units. Stored daily volatility is unannualized. Convergence flags, exceptions, warnings, parameters, persistence, Student-t degrees of freedom, likelihood criteria and residual diagnostics remain visible. Failed or invalid fits are not silently treated as successful forecasts.

A **20-session rolling sample variance** at the same origin is the baseline. Event-day squared return is used only after forecasting as an explicitly noisy variance proxy. Losses are QLIKE, `log(forecast_variance) + squared_return / forecast_variance`, and squared variance error. Summary QLIKE and variance RMSE compare models on the same usable bank/event rows; attempted and scored counts remain visible. Lower loss is better, but daily squared return is not directly observed latent variance, and these descriptive scores do not alone establish forecast superiority.

Ljung–Box tests of standardized residuals and their squares, plus an ARCH LM test, provide diagnostics. These p-values are diagnostic rather than an unqualified set of discoveries. The corrected pipeline does not carry forward ADF, ACF/PACF or stationarity findings that it has not regenerated.

### Relative volatility labels

The 25th, 50th and 75th percentiles are fitted to usable GARCH volatility forecasts for **2023–2024 only**, pooled across banks. Thresholds are frozen for 2025. Labels are `Low`, `Medium`, `High` and `Very High`; unavailable fits are `Unavailable`.

These labels describe relative forecast volatility in the training sample. They are not buckets of realized absolute CAR, credit ratings, value-at-risk estimates or calibrated loss probabilities. Training-period labels use the complete 2023–2024 calibration sample and are descriptive; only 2025 classifications use thresholds fixed before their holdout period. `volatility_thresholds.csv` records values, the cut-off and fitting sample sizes.

## 6. Prediction experiment

The prediction time is the **last trading close before the announcement**. The label is:

```text
positive_car = 1 if Nifty-50-adjusted CAR[0,+1] > 0, else 0
```

Both target sessions are after the feature cut-off. The descriptive `[-1,+1]` window is not reused because its day −1 return is already known at that origin. The label uses future realized benchmark returns to define ex-post abnormal performance; this is a research classification task, not a specified executable trading payoff.

The seven inputs are bank type, the latest one-session return, compounded five- and 20-session returns, 20- and 60-session sample return volatility, and the past-only GARCH forecast. The realized decision is stored as `realized_decision_metadata_only` and **never enters the feature matrix**. Dates, event identifiers and future outcomes are not predictors.

Training is 2023–2024 (12 events; 72 bank/event rows). Testing is chronological 2025 (six events; 36 bank/event rows). Whole announcements remain in one partition. This is a holdout relative to model fitting, not a prospective experiment conducted before 2025; methods were rebuilt after the historical project was observed.

| Model | Fixed specification |
|---|---|
| Training-majority baseline | `DummyClassifier(strategy="prior")`: training-majority class and training-class-prior probabilities |
| Logistic regression | `C=1`, `max_iter=1000`, seed 42 |
| Random forest | 300 trees, maximum depth 3, minimum leaf size 6, balanced class weights, seed 42, one worker |

Numeric medians and missingness indicators are learned only on training data. Logistic-regression scaling and categorical encoding are also fitted only on training data. Failed GARCH features are imputed inside these pipelines; affected held-out events are not discarded. Specifications are fixed, with no test-set tuning, threshold selection or post-hoc prediction flipping.

Outputs include accuracy, balanced accuracy, ROC-AUC, precision, recall, F1, Brier score, log loss, confusion matrices and each held-out prediction. AUC and balanced accuracy are missing when two-class evaluation is unavailable. Probabilistic metrics use the baseline's training prior, avoiding artificially extreme baseline probabilities.

Default uncertainty uses **2,000 bootstrap resamples of six complete held-out events**, seed 42. All banks within an event travel together. Models and baseline use the same resamples, yielding paired differences for accuracy, balanced accuracy, AUC and Brier score. Intervals are pointwise and conditional on these few observed events; valid resample counts are shown. They do not refit models, estimate training-sample uncertainty, or establish cross-regime performance. No accuracy target or superiority claim is assumed.

## 7. Outputs and validation boundaries

The core build regenerates CSV tables, figures, an offline HTML dashboard, a SQLite database, a report and a run manifest. It validates staged outputs before publishing them. Database checks enforce identities, compound keys, foreign keys, forecast timing and numerical consistency. Dashboard and Tableau CSVs use the same validated results; display filters do not redefine statistical hypothesis families.

Optional PySpark separately calculates bank price returns and rolling statistics. Its parity validator reads every output part and checks complete key equality, null masks and daily-return numerical agreement against pandas. This verifies that calculation, not upstream price authenticity or every rolling field. SAS is an **unexecuted optional script** until an actual SAS log is retained. Tableau-compatible CSVs are provided; no native Tableau workbook or executed Tableau session is claimed.

Tests cover source hashes, data gaps, event dates, sample timing, statistical aggregation, uncertainty, leakage, persistence, exports and failure behavior. Such validation detects specified defects and preserves reproducibility; it cannot guarantee universal data accuracy or financial predictability. Further research requires broader source checks, additional policy regimes, coherent total-return indices, measured policy expectations, richer confounder data and prospective validation.
