# Version 2.0 — corrected project rebuild

This rebuild replaces the original main snapshot `9fcf90ab42d4ed91f5e136d0e2a055c98a68043f` with a reproducible research package. Original files remain available in Git history.

## Data and provenance

- Corrected the August 2025 announcement from 7 August to **6 August** and regenerated all dependent windows, features, forecasts, and results.
- Retrieved and preserved actual Yahoo Chart responses for all eight assets, with query bounds, retrieval timestamps, corporate actions, and checksums.
- Repaired the missing Nifty Bank observation on **1 February 2025** from an official NSE archive, preserving the original missing vendor row and a field-level repair ledger.
- Added independent NSE checks of 12 bank closes across two dividend-sensitive dates, with documented adjustment for later share-ratio events.
- Made primary split-adjusted price returns, adjusted-return sensitivity, units, and source-verification limits explicit.
- Added calendar equality, complete-window, missing/duplicate/nonfinite-value, OHLC, and corporate-action checks. No forward-filling.

## Statistical design

- Unified both benchmarks on the same 250-return inclusive estimation interval, **[−255, −6]**.
- Replaced comparisons that treated bank rows as separate policy experiments with announcement-level means and paired public/private differences.
- Added event bootstrap intervals, leave-one-event-out sensitivity, declared Holm families, and explicit unavailable inference for the single hike.
- Added dividend/split overlap ledgers, adjusted-bank-return sensitivity, and action-exclusion comparisons with changed-bank-count reporting.
- Kept all declared results, including weak and nonsignificant findings.

## Forecasting and model evaluation

- Stored distinct GARCH forecast origin and target dates and selected the forecast targeting the event day.
- Used Student-t GARCH(1,1), explicit convergence and residual diagnostics, and a rolling-variance baseline. This is a documented model-specification change from the earlier implementation.
- Fitted volatility-category thresholds on training-period forecasts and froze them for 2025. Categories describe daily conditional volatility, not absolute realised CAR or loss probability.
- Defined previous-close prediction of the wholly future **CAR[0,+1]** target.
- Removed realised policy decisions from predictive features and used training-only preprocessing.
- Added a fair training-prior probability baseline, chronological evaluation, complete metric tables, predictions, confusion matrices, and paired event-resampled uncertainty.
- Described the retrospective holdout and current-vintage prices honestly; no prospective predictive performance is claimed.

## Engineering and presentation

- Replaced independent, order-sensitive scripts with one maintained package and CLI.
- Pinned the tested core environment and added regression/invariant tests and GitHub Actions reproduction.
- Staged complete output replacement with rollback; built SQLite in one validated temporary-database transaction.
- Repaired Spark validation to inspect all partitions, complete key coverage, matching null masks, and numeric tolerance. The actual optional parity run passes.
- Repaired SAS inputs and script. SAS execution is still unavailable and is not claimed.
- Replaced stale tables and plots with regenerated outputs and a generated numerical report.
- Delivered an actual self-contained HTML dashboard, interactive filters and CSV download, plus accurate Tableau-ready exports. No Tableau workbook execution is claimed.
- Rewrote documentation to agree with the executable code and actual results.

## What is not solved by a code correction

The selected historical study still has 18 announcements, only four cuts, one hike, and six held-out events. Decision type is confounded with regime, and daily prices cannot isolate policy surprises from other news. Targeted exchange checks do not establish whole-history vendor accuracy. These are reported research limits, not hidden implementation defects.
