# Data dictionary

This dictionary describes the corrected `rbi_intelligence` pipeline. Source evidence is in [data_sources.md](data_sources.md), formulas and inference rules in [research_design.md](research_design.md), and commands in [reproduction.md](reproduction.md). CSV schemas are long format: benchmark and window are explicit keys, rather than separate CAR columns.

## 1. Shared conventions

| Concept | Storage convention |
|---|---|
| Session dates | ISO `YYYY-MM-DD`, derived in `Asia/Kolkata`; timezone-free session labels after conversion |
| Retrieval/build timestamps | UTC timestamps, explicitly named as UTC |
| Bank prices and cash distributions | INR per share on the provider's stated share basis |
| Index levels | Index points, not INR |
| Returns, abnormal returns, CAR and daily volatility | Fractions: `0.015` means 1.5% |
| Difference between fractional returns | Multiply by 100 to display percentage points; `0.01` is one percentage point |
| Variance | Squared fractional-return units; daily, unannualized |
| Repo rate | Percentage level: `6.5` means 6.50% |
| Rate change | Signed basis points: `100 * (repo_after - repo_before)` |
| Probabilities and p-values | Values between 0 and 1 |
| Missing numeric values | Empty CSV cells; JSON null where applicable; not a numeric zero |
| Keys | Exact identifiers and compound keys below; never aggregate across benchmarks or windows without choosing the intended specification |

The same bank/event can have several benchmark/window rows. These are not independent policy observations. Mean absolute CAR is `mean(abs(car))`, not `abs(mean(car))`.

## 2. RBI policy events

**File:** `data/raw/rbi_mpc_events_2023_2025.csv`

**Grain/key:** One announcement; `event_id` primary key and `event_date` unique.

**Snapshot:** 18 rows, 13 holds, four cuts and one hike.

| Field | Type/unit | Meaning |
|---|---|---|
| `event_id` | String | Stable identifier, e.g. `MPC_2025_08` |
| `meeting_start`, `meeting_end` | Dates | Actual meeting boundaries; not a claim that every intervening date was a meeting day |
| `event_date` | Date | Public announcement, event day 0; August 2025 is `2025-08-06` |
| `repo_before`, `repo_after` | Percentage level | Repo rate immediately before and after the announcement |
| `rate_change_bps` | Signed integer | Change in basis points, consistent with the two rate levels |
| `decision` | `Cut`, `Hold`, `Hike` | Label determined by the sign of `rate_change_bps` |
| `stance` | String | Policy stance recorded from the linked RBI material |
| `source_url` | URL | Specific official RBI release, statement, minutes or publication containing the decision |
| `notes` | String | Source/date context, including meeting-day exceptions |

Validation checks identities, the frozen source-reconciled dates, rate continuity, arithmetic, decision signs, meeting boundaries and specific official source URLs. It does not re-fetch RBI pages on each offline run.

## 3. Asset universe

The canonical metadata are declared in `rbi_intelligence.data.ASSETS`.

| `symbol` | `bank_name` | `bank_type` | `asset_type` |
|---|---|---|---|
| `HDFCBANK.NS` | HDFC Bank | Private | bank |
| `ICICIBANK.NS` | ICICI Bank | Private | bank |
| `AXISBANK.NS` | Axis Bank | Private | bank |
| `SBIN.NS` | State Bank of India | Public | bank |
| `BANKBARODA.NS` | Bank of Baroda | Public | bank |
| `CANBK.NS` | Canara Bank | Public | bank |
| `^NSEI` | Nifty 50 | Empty | benchmark |
| `^NSEBANK` | Nifty Bank | Empty | benchmark |

The historical column name `bank_name` also holds the display name for index rows. Benchmark rows have no public/private classification.

## 4. Raw responses and canonical market panel

**Original responses:** `data/raw/yahoo_chart_2021_2025/*.json`

**Normalized vendor data, before repair:** `data/raw/market_prices_2021_2025.csv`

**Validated analytical panel:** `data/processed/market_panel.csv`

**Grain/key:** One asset/session; `(date, symbol)`.

**Frozen snapshot:** 1,236 dates per asset; 9,888 price rows; 7,416 bank price rows. First returns are unavailable, leaving 7,410 usable bank returns.

| Field | Meaning |
|---|---|
| `date`, `symbol` | Session and asset identity |
| `bank_name`, `bank_type`, `asset_type` | Metadata from the universe above |
| `open`, `high`, `low`, `close` | Provider OHLC prices/levels; `close` is the vendor's split-adjusted price series |
| `adj_close` | Provider adjusted close; bank dividends/distributions may change it relative to Close |
| `volume` | Provider session volume; retained as reported, not used as a model feature |
| `dividends` | Cash distribution recorded for that session on the provider's stated share basis; zero means no returned dividend record |
| `stock_splits` | New-to-old share ratio on an action date, e.g. `5.0` for 5:1; zero means no returned share-ratio record |
| `source_provider` | Yahoo source by default; identifies the NSE source on the documented repaired index row |
| `return` | `close / previous_session_close - 1`, calculated separately by asset with no filling |
| `adj_return` | Same calculation using `adj_close`; separate sensitivity input |

Only the processed panel has the final two return columns. The normalized pre-repair CSV deliberately retains the original all-null Nifty Bank market row on `2025-02-01`; the processed panel replaces it with documented NSE values. Original source JSON is not overwritten by repair. Only the first return per asset may be missing in the validated analytical panel.

The `stock_splits` field is a vendor event category and share ratio; it does not distinguish every legal form of share adjustment. Zero action fields mean no action was returned by this source, not independent proof that no corporate event occurred.

### Corporate actions, repairs and selected price checks

| File | Grain and fields |
|---|---|
| `data/raw/corporate_actions_2021_2025.csv` | One returned action: `date`, `symbol`, `action_type`, `value`, `unit`, `source_provider`; this snapshot contains 28 dividends and two share-ratio actions |
| `data/raw/market_repairs.json` | One documented repair: identity, reason, `before`, `after`, official source URL/path/hash and method |
| `data/raw/nse_spot_checks/price_comparisons.csv` | One bank/date comparison: `nse_unadjusted_close`, `subsequent_vendor_split_ratio`, `nse_close_on_vendor_share_basis`, `yahoo_close`, signed `difference_inr`, `within_0_02_inr`, source URL |
| `data/raw/market_diagnostics.json` | Split-date return diagnostics, absolute daily returns over 10%, event-window dividend overlaps, selected NSE checks and validation limitations |

## 5. Event-study results

**File:** `outputs/tables/event_study.csv`

**Key:** `(event_id, bank_symbol, benchmark, window)`.

**Full-sample rows:** 864 = 18 × 6 × 2 × 4. Filtering to Nifty 50 and `[-1,+1]` yields 108 bank/event rows.

| Fields | Meaning/unit |
|---|---|
| `event_id`, `event_date`, `decision` | Policy identity and category |
| `bank_symbol`, `bank_name`, `bank_type` | Bank identity and classification |
| `benchmark`, `benchmark_name` | `^NSEI`/Nifty 50 or `^NSEBANK`/Nifty Bank |
| `window` | One of `[-1,+1]`, `[-2,+2]`, `[-5,+5]`, `[0,+1]` |
| `window_start_day`, `window_end_day` | Inclusive relative trading-session offsets |
| `car` | Sum of fitted abnormal returns across the window; fraction |
| `alpha` | OLS daily-return intercept; fraction per session |
| `beta` | OLS benchmark-return coefficient; dimensionless |
| `estimation_start`, `estimation_end`, `n_estimation` | Actual regression dates and count; exactly 250 over relative days `[-255,-6]` |
| `n_event` | Number of trading sessions in this window |
| `event_window_start`, `event_window_end` | First and last actual window session |
| `event_trading_dates` | Pipe-separated ISO dates for all sessions in the window |
| `return_unit` | Literal `fraction` |
| `ar_minus_1`, `ar_0`, `ar_plus_1` | Daily abnormal returns from the same fitted market model; `ar_minus_1` remains available as descriptive context on `[0,+1]` rows |

`absolute_car` is derived as `abs(car)` in database/dashboard exports and inferential aggregation. It is not a second independently fitted result.

## 6. Event-level inference tables

All files in this section are under `outputs/tables/`. Inference uses the three symmetric windows. Undefined tests preserve their descriptive estimates where available and use missing inferential values plus a `status`.

| File | Grain and main fields |
|---|---|
| `event_means.csv` | One event/benchmark/window: `mean_car`, `mean_absolute_car`, `n_banks`, event identity and decision |
| `overall_tests.csv` | One benchmark/window: `n_events`, `mean`, standard error, t-statistic, degrees of freedom, p-value and pointwise 95% CI |
| `decision_comparisons.csv` | One benchmark/window/decision contrast: `group_a`, `group_b`, `mean_a`, `mean_b`, `difference` = A minus B, `n_a_events`, `n_b_events`, Welch test and intervals |
| `paired_bank_comparisons.csv` | One benchmark/window/outcome (`car` or `absolute_car`): paired Public minus Private mean `mean`, `n_events`, `n_incomplete_pairs`, test and intervals |
| `bootstrap_sensitivity.csv` | Leave-one-event-out decision comparison: removed event and decision, `difference_without_event`, `full_sample_difference` |

Shared inferential fields are `standard_error`, `t_statistic`, `degrees_freedom`, `p_value`, `ci_lower`, `ci_upper` and `status`. Return estimates, standard errors and interval bounds are fractional units. `p_value_holm`, `multiple_testing_family` and `n_tests_in_family` identify family-wise adjustment. `sampling_unit` is `policy_event`; `interpretation` states the exploratory association boundary.

Decision bootstrap fields are `bootstrap_ci_lower`, `bootstrap_ci_upper`, `bootstrap_mean`, `bootstrap_unit`, `bootstrap_repetitions`, `bootstrap_seed` and `bootstrap_interval_type`. Paired-sector rows also report bootstrap bounds. Defaults are 10,000 whole-event resamples and seed 42; these are pointwise percentile intervals, not simultaneous confidence regions. One-hike comparisons are marked `insufficient_events`.

### Sensitivity tables

| File | Meaning |
|---|---|
| `adjusted_bank_event_results.csv`, `adjusted_bank_event_means.csv`, `adjusted_bank_decision_comparisons.csv` | Market models refitted using bank adjusted-close returns against unchanged price-index returns |
| `corporate_action_overlaps.csv` | Action date, cash amount/share ratio, action type and the affected event/bank/benchmark/window |
| `action_excluded_event_results.csv`, `action_excluded_event_means.csv`, `action_excluded_decision_comparisons.csv` | Retained price-return observations and their recalculated event means/comparisons after action-window exclusions |
| `composition_changes.csv` | Each event/benchmark/window: original/retained/excluded bank counts, pipe-separated bank lists, `composition_changed`, `all_banks_excluded`, original and retained mean CAR |
| `sensitivity_summary.csv` | Cut-minus-hold comparison for each scenario/benchmark/window with retained-event and changed-composition counts |

Scenario tables carry `scenario`, `return_convention` and `sensitivity_caveat`. Comparison outputs preserve `p_value_holm_within_scenario` and add `p_value_holm_across_sensitivity_family`, `sensitivity_multiplicity_family` and `n_tests_in_sensitivity_family`. The expanded family covers all estimable decision contrasts across the three scenarios, two benchmarks and three inference windows.

## 7. Volatility forecasts, diagnostics and labels

**File:** `outputs/tables/event_volatility.csv`

**Key:** `(event_id, bank_symbol)`; one attempted event-day forecast for every bank/event, including failures.

| Fields | Meaning/unit |
|---|---|
| Policy and bank identity fields | Same definitions as event-study results |
| `forecast_origin_date` | Last observed training-return session, strictly before the announcement |
| `forecast_target_date` | Announcement session whose one-day variance is forecast |
| `training_start`, `n_training` | Beginning and number of historical returns used; minimum 500 |
| `model`, `innovation_distribution` | `GARCH(1,1)` and `t` (Student-t) |
| `rolling_window` | Baseline lookback, 20 sessions |
| `garch_variance`, `rolling_variance` | Forecast variance and origin-available baseline sample variance; squared fractional units |
| `garch_volatility`, `rolling_volatility` | Square roots of the corresponding variance; daily fractions, not annualized |
| `forecast_mean`, `omega`, `alpha_1`, `beta_1` | Constant return mean, variance intercept, and GARCH coefficients; mean is fractional and omega is fraction-squared |
| `persistence` | `alpha_1 + beta_1` |
| `student_t_degrees_freedom` | Estimated innovation degrees of freedom |
| `convergence_flag`, `converged`, `status`, `error`, `fit_warnings` | Numerical fit state and visible diagnostics; boolean convergence requires flag zero and finite positive variance |
| `log_likelihood`, `aic`, `bic` | Fit diagnostics from the model estimated on percentage-scaled returns |
| `diagnostic_lags`, `residual_ljung_box_p`, `squared_residual_ljung_box_p`, `arch_lm_p` | Standardized-residual diagnostic lag and p-values |
| `realized_return` | Event-day return, attached only for retrospective scoring |
| `realized_squared_return_proxy`, `variance_proxy_caveat` | Squared event-day return and explicit noisy-proxy warning |
| `garch_qlike`, `rolling_qlike` | `log(variance) + squared_return_proxy / variance`; lower is better on comparable observations |
| `garch_variance_squared_error`, `rolling_variance_squared_error` | `(squared_return_proxy - variance)^2` |
| `risk_level` | `Low`, `Medium`, `High`, `Very High` or `Unavailable` based on forecast volatility |
| `threshold_training_cutoff`, `risk_basis` | `2024-12-31` and training-sample GARCH-volatility quartiles |

Non-success statuses include `insufficient_history`, `missing_target_trading_date`, `missing_training_return`, `fit_failed` and `nonconverged_or_invalid_variance`. Unavailable forecasts remain in the dataset and receive `Unavailable` risk labels.

**`volatility_thresholds.csv`:** Three rows with `quantile` (0.25/0.50/0.75), fractional `threshold`, `training_cutoff`, `n_training_rows`, `n_training_events` and `classification_basis`. Values equal to a threshold enter the lower category. These thresholds are fit on usable 2023–2024 forecasts and fixed for 2025; labels are relative volatility descriptions, not financial-risk ratings.

**`volatility_forecast_evaluation.csv`:** One overall and one per-bank row. Fields include `n_attempted`, `n_scored`, `n_events_scored`, mean QLIKE for both models, `garch_minus_rolling_qlike`, and variance RMSE for both models. Scores use matched usable observations. Variance RMSE is in squared fractional-return units, not volatility units.

## 8. Predictive features and held-out evaluation

**Features file:** `outputs/tables/predictive_features.csv`

**Key:** `(event_id, bank_symbol)`; 108 rows. `benchmark` is `^NSEI`; `target_window` is `[0,+1]`.

| Field | Role/definition |
|---|---|
| `event_id`, `event_date`, bank identity | Join and descriptive metadata, except `bank_type` below |
| `feature_cutoff_date` | Previous trading close; must precede event day 0 and target-window start |
| `forecast_origin_date`, `forecast_target_date`, `garch_status` | GARCH timing and fit diagnostics |
| `bank_type` | Categorical model input |
| `return_1d` | Most recent pre-event daily price return |
| `return_5d`, `return_20d` | Products of `1 + daily_return` over the latest five/20 sessions, minus one |
| `volatility_20d`, `volatility_60d` | Sample standard deviation of the latest 20/60 returns, `ddof=1` |
| `garch_volatility` | Past-only event-day volatility forecast; may be missing after a failed fit |
| `car_0_plus_1` | Ex-post Nifty-50 market-model CAR over `[0,+1]`; target information only |
| `positive_car` | Binary target: 1 for strictly positive `car_0_plus_1`, otherwise 0 |
| `realized_decision_metadata_only` | Observed RBI decision, explicitly excluded from the input features |

Only the categorical bank type and six numerical inputs enter the model matrix. The 2023–2024 training partition has 72 rows across 12 events; the 2025 test partition has 36 rows across six events. Median imputation, missingness indicators, scaling and encoding are fit only on training data.

| Evaluation file | Grain and contents |
|---|---|
| `model_metrics.csv` | One model: training/test counts and positive rates, date cut-offs, features, target, seed, accuracy, balanced accuracy, ROC-AUC, precision, recall, F1, Brier score, log loss and status |
| `model_predictions.csv` | One model/held-out event/bank: `y_true`, `y_pred`, `probability_positive` |
| `model_confusion_matrices.csv` | One model/true class/predicted class: integer `count`, including zero cells |
| `model_uncertainty.csv` | One model/metric: point estimate, percentile bounds, valid/requested resample counts, held-out event count, seed, sampling unit and caveat/status |

Uncertainty covers accuracy, balanced accuracy, AUC and Brier score, plus their paired `*_minus_dummy` differences. The resampling unit is a complete held-out announcement including all its banks. Defaults are 2,000 resamples and seed 42. Higher accuracy/AUC is better; lower Brier score/log loss is better. All remain exploratory with six held-out announcements.

## 9. SQLite, dashboard and external-tool exports

**Database:** `outputs/study.sqlite`, regenerated by the core run. All tables preserve additional record fields in `details_json` where the fixed SQL schema does not expose them directly.

| Table/view | Primary key or grain |
|---|---|
| `run_metadata` | `key`; JSON manifest, table counts and schema version |
| `rbi_events` | `event_id`; unique announcement date |
| `bank_metadata` | `bank_symbol` |
| `market_data` | `(date, symbol)` |
| `event_study_results` | `(event_id, bank_symbol, benchmark, window)`; includes derived `absolute_car` |
| `volatility_forecasts` | `(event_id, bank_symbol)` |
| `event_explorer` view | Event-study grain, with event, bank and matching volatility metadata joined |

The schema enforces foreign keys and compound uniqueness. Forecast origin/target order, positive variance and variance/volatility consistency are checked before publication. The database is a generated local artifact and may be absent from a fresh checkout until `run` completes.

**Offline dashboard:** `outputs/dashboard.html`; embedded validated data, no external dashboard service required.

**Tableau-compatible CSVs:** `outputs/tableau/` contains `bank_performance.csv`, `event_means.csv`, `event_explorer.csv`, `rbi_events.csv`, `event_results.csv` and `volatility_forecasts.csv`. `bank_performance` remains split by benchmark/window/bank. Exported `event_means` includes all four windows and uses `bank_count`; inferential `outputs/tables/event_means.csv` includes three windows and uses `n_banks`. They should not be confused.

`sas_event_results.csv` and `sas_event_means.csv` restrict the optional SAS inputs to Nifty 50 and `[-1,+1]`. A SAS script is supplied but not claimed as executed. No native Tableau workbook is supplied or claimed as executed.

**Optional Spark output:** `outputs/spark/bank_returns/part-*.csv`; all parts together contain `(date, symbol, close, daily_return, rolling_mean_return_20d, rolling_volatility_20d, rolling_observations_20d)`. The rolling mean is an arithmetic daily-return mean, not a cumulative return. Both 20-session rolling summaries require 20 non-null returns. The parity check covers daily returns, all keys and initial-null masks; it does not validate every rolling statistic.

## 10. Provenance and run manifests

| File | Recorded evidence |
|---|---|
| `data/raw/yahoo_retrieval_records.json` | Per-asset URL, UTC retrieval time, HTTP status, relative path, SHA-256, bytes, provider metadata, timestamps and action counts |
| `data/raw/nse_retrieval_record.json`, `data/raw/nse_spot_checks/retrieval_records.json` | Official archive URLs, retrieval times, hashes and file sizes |
| `data/raw/market_manifest.json` | Query window, provider/convention, build library versions, per-asset coverage, action/repair/outlier counts, file hashes and validation limits |
| `outputs/run_manifest.json` | Build UTC time, version, packages, parameters, seeds, row counts, source/code hashes, table/artifact hashes and optional-component scope |

`verify` compares recorded bytes to hashes. It does not fetch sources or certify empirical conclusions. A successful check means the checked files match that manifest; it does not establish that an external provider is infallible. Numeric outputs are intended to reproduce with frozen inputs, the pinned environment and the same seeds; timestamps and manifests naturally change between fresh builds.
