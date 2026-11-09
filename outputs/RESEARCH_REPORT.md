# RBI monetary policy and Indian bank stocks — extended study

**Generated:** 2026-11-09T12:09:35.527364+00:00
**Scope:** 57 RBI MPC repo-rate announcements from 4 October 2016 through 5 December 2025; six NSE-listed banks; official NSE daily bank and benchmark prices.

## Executive conclusion

This project measures **historical association**, not causality. It asks whether bank stocks earned abnormal returns around RBI announcements after controlling for either Nifty 50 or Nifty Bank. It also asks a separate question: whether information available by the previous close predicts the sign of the wholly post-origin CAR `[0,+1]` in event-grouped walk-forward testing.

The sample contains **8 hikes, 13 cuts, and 36 holds**. The primary Nifty 50 `[-1,+1]` decision contrasts are below. Raw, Holm-adjusted, permutation, bootstrap, and leave-one-event-out results are all retained; no specification is selected because it looks favorable.

| comparison | n_a_events | n_b_events | Difference (pp) | 95% CI low (pp) | 95% CI high (pp) | p_value | p_value_holm | permutation_p_value | permutation_p_value_holm | Bootstrap low (pp) | Bootstrap high (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cut minus Hold | 13 | 36 | -1.0500 | -1.9042 | -0.1958 | 0.0174 | 0.3135 | 0.0450 | 0.7200 | -1.8643 | -0.2508 |
| Hike minus Hold | 8 | 36 | -0.3618 | -1.6215 | 0.8980 | 0.5447 | 1.0000 | 0.6196 | 1.0000 | -1.4162 | 0.7360 |
| Cut minus Hike | 13 | 8 | -0.6882 | -1.9539 | 0.5775 | 0.2590 | 1.0000 | 0.2162 | 1.0000 | -1.8060 | 0.3349 |

The overall mean-CAR test and paired public/private comparison answer different questions:

| outcome | n_events | mean | ci_lower | ci_upper | p_value | p_value_holm |
| --- | --- | --- | --- | --- | --- | --- |
| mean_car | 57 | 0.0186 | -0.4160 | 0.4531 | 0.9322 | 1.0000 |

| outcome | comparison | n_events | mean | ci_lower | ci_upper | p_value | p_value_holm | wilcoxon_p_value | wilcoxon_p_value_holm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| absolute_car | Public minus Private (paired by event) | 57 | 0.9394 | 0.4712 | 1.4076 | 0.0002 | 0.0005 | 0.0001 | 0.0002 |
| car | Public minus Private (paired by event) | 57 | 0.1689 | -0.6502 | 0.9880 | 0.6812 | 1.0000 | 0.9398 | 1.0000 |

An adjusted p-value below 0.05 is statistical evidence within its declared family; it is not proof that the repo decision caused the return. Daily windows contain other news, expected and unexpected policy components are not separately observed, and Nifty Bank contains the studied sector.

## Which banks and groups move differently?

The following are descriptive Nifty 50 benchmark results for `[-1,+1]`. Mean absolute CAR measures movement magnitude; signed mean CAR measures direction. They should not be ranked as causal “sensitivity” coefficients.

| bank_name | bank_type | events | Mean CAR (%) | Mean |CAR| (%) |
| --- | --- | --- | --- | --- |
| Axis Bank | Private | 57 | -0.0717 | 1.7967 |
| Bank of Baroda | Public | 57 | -0.2051 | 2.6433 |
| Canara Bank | Public | 57 | 0.3249 | 2.4606 |
| HDFC Bank | Private | 57 | -0.0650 | 1.2373 |
| ICICI Bank | Private | 57 | -0.0609 | 1.4537 |
| State Bank of India | Public | 57 | 0.1891 | 2.2021 |

Public versus private inference is paired within the same announcement, so each policy event contributes one public-minus-private difference. This is preferable to treating 342 bank-event rows as independent policy shocks.

## Predictive performance — separate from inference

The evaluated learned models do not show a robust out-of-sample advantage over the rolling majority-class baseline.

| model | n_test_events | n_test_rows | accuracy | balanced_accuracy | roc_auc | brier_score | log_loss | expected_calibration_error_5bin | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bank_historical_rate | 33 | 198 | 52.5253 | 51.7157 | 0.4936 | 0.2547 | 0.7030 | 0.0368 | exploratory_out_of_sample |
| dummy_majority | 33 | 198 | 51.5152 | 50.0000 | 0.4553 | 0.2525 | 0.6982 | 0.0395 | exploratory_out_of_sample |
| last_event_persistence | 33 | 198 | 45.4545 | 45.4044 | 0.4540 | 0.5455 | 19.6602 | 0.5455 | exploratory_out_of_sample |
| hist_gradient_boosting | 33 | 198 | 44.9495 | 44.8223 | 0.4671 | 0.2571 | 0.7075 | 0.0380 | exploratory_out_of_sample |
| elastic_net | 33 | 198 | 41.9192 | 41.9118 | 0.4397 | 0.2616 | 0.7170 | 0.0230 | exploratory_out_of_sample |
| random_forest | 33 | 198 | 41.9192 | 41.6360 | 0.4092 | 0.2639 | 0.7216 | 0.0523 | exploratory_out_of_sample |
| logistic_l2 | 33 | 198 | 41.4141 | 41.3603 | 0.4009 | 0.2689 | 0.7319 | 0.0437 | exploratory_out_of_sample |

The evaluation begins only after 24 complete training events and then predicts each later announcement once, using every earlier event and keeping all six banks from an announcement together. Calibration uses chronological, event-grouped inner folds. Fixed models include L2 logistic regression, elastic-net logistic regression, random forest, and histogram gradient boosting. Baselines include rolling majority prevalence, bank-specific historical positive rates, and last-event persistence.

Accuracy is not a significance test. A model can beat a baseline by a few rows without a stable advantage across announcements. Conversely, a statistically detectable average abnormal return does not imply that its sign is predictable for a new event.

## Data and research design

| Year | Cut | Hike | Hold |
| --- | --- | --- | --- |
| 2016 | 1 | 0 | 1 |
| 2017 | 1 | 0 | 5 |
| 2018 | 0 | 2 | 4 |
| 2019 | 5 | 0 | 1 |
| 2020 | 2 | 0 | 4 |
| 2021 | 0 | 0 | 6 |
| 2022 | 0 | 5 | 2 |
| 2023 | 0 | 1 | 5 |
| 2024 | 0 | 0 | 6 |
| 2025 | 4 | 0 | 2 |

- RBI dates and decisions are tied to event-specific official RBI resolutions or minutes.
- The market snapshot uses official NSE bhavcopies for bank OHLCV and previous close, plus official NSE daily index archives for Nifty 50 and Nifty Bank.
- Bank return is `NSE close / NSE previous close − 1`; the exchange previous-close base prevents split and bonus adjustments from becoming false returns.
- The primary market model uses 250 trading returns ending on day −6. Sensitivities use 120 and 180 days, both benchmarks, several event windows, leave-one-event-out diagnostics, and pre-declared COVID/off-cycle exclusions.
- No forward filling, outcome-driven model choice, test-set threshold selection, or result deletion is permitted.

## Reproducibility and limits

The [run manifest](run_manifest.json) records input, code, package, and output hashes. Full numerical tables are under `outputs/tables`; the dashboard is an **interactive historical dashboard**, not a live market feed.

This remains an observational event study. It does not identify monetary-policy surprises, intraday announcement timing, bank fundamentals, lending/deposit transmission, or long-run causal effects. Results are research evidence, not investment advice.
