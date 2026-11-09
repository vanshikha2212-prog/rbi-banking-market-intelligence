# Data dictionary

All dates are ISO `YYYY-MM-DD`. Returns, abnormal returns, CAR, volatility and probabilities are stored as fractions. Repo rates are percentage levels; rate changes are signed basis points.

## Policy events

**File:** `data/raw/rbi_mpc_events_2016_2025.csv`
**Key:** `event_id`; 57 rows.

Important fields: `meeting_start`, `meeting_end`, `event_date`, `repo_before`, `repo_after`, `rate_change_bps`, `decision`, `stance`, `source_url`, `notes`.

## NSE market snapshot

**File:** `data/raw/nse_market_prices_2015_2025.csv`
**Key:** `(date, symbol)`.

Fields: `open`, `high`, `low`, `close`, `previous_close`, `volume`, and `source_provider`. The processed panel adds bank metadata, `return`, compatibility columns `adj_close`/`adj_return`, and zero-valued corporate-action placeholders. Bank `return` uses official NSE previous close; index return uses consecutive closes.

## Event-study results

**File:** `outputs/tables/event_study.csv`
**Key:** `(event_id, bank_symbol, benchmark, window)`.

`car` is cumulative abnormal return. `alpha` and `beta` are market-model coefficients. Estimation and event-window date fields preserve exact trading sessions. `ar_minus_1`, `ar_0`, and `ar_plus_1` retain daily abnormal returns.

## Inference

- `event_means.csv`: one event/benchmark/window.
- `decision_comparisons.csv`: decision contrasts with Welch, permutation, bootstrap, Holm, and leave-one-event-out evidence.
- `paired_bank_comparisons.csv`: public-minus-private paired event differences with t, Wilcoxon, bootstrap and Holm evidence.
- `estimation_window_sensitivity.csv`: 120/180/250-day specifications.
- `regime_exclusion_sensitivity.csv`: declared COVID and off-cycle exclusions.
- `sensitivity_summary.csv`: all declared scenarios together.

## Prediction

`predictive_features.csv` contains one bank/event row with a previous-close cutoff and binary `positive_car` target for CAR `[0,+1]`. Realized decision is metadata, never a feature.

- `model_metrics.csv`: pooled walk-forward accuracy, balanced accuracy, ROC AUC, Brier score, log loss, F1 and calibration error.
- `model_fold_metrics.csv`: one model/test-event score.
- `model_predictions.csv`: out-of-sample probabilities and labels.
- `model_calibration.csv`: predicted versus observed rates by probability bin.
- `model_uncertainty.csv`: whole-event bootstrap intervals and paired deltas versus majority baseline.
- `model_confusion_matrices.csv`: counts by actual/predicted label.

## Volatility

`event_volatility.csv` has one past-only GARCH attempt per bank/event. Origin, target, convergence, variance, volatility, diagnostics and like-for-like rolling-variance scores are explicit. Relative risk labels are sample quartiles, not loss probabilities.

## Manifest

`outputs/run_manifest.json` records parameters, counts, runtime versions, source/code/table/output hashes and validation scope. Missing numeric values are empty CSV cells or JSON null, never silently converted to zero.
