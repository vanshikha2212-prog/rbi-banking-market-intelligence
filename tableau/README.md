# Tableau exports and offline dashboard

The corrected pipeline writes fresh exports to `outputs/tableau/`. The completed,
self-contained interactive dashboard is `outputs/dashboard.html`; open it in a
browser without a server or account. It is an HTML dashboard, not a Tableau workbook.
No Tableau Public deployment is claimed.

| Export | Grain and purpose |
| --- | --- |
| `rbi_events.csv` | One row per actual RBI announcement; dates, decisions and sources |
| `event_results.csv` | One row per event, bank, benchmark and event window |
| `event_explorer.csv` | The same event-result grain, joined to event-date volatility forecasts |
| `bank_performance.csv` | Descriptive bank averages, separately for each benchmark/window |
| `event_means.csv` | One row per announcement, benchmark and window; bank-averaged CAR |
| `volatility_forecasts.csv` | One forecast attempt per event and bank, including unavailable fits |
| `sas_event_results.csv` | Nifty 50 `[-1,+1]` bank-event rows with bank metadata |
| `sas_event_means.csv` | Nifty 50 `[-1,+1]` event-level means for optional SAS checks |

All returns, CARs and volatilities are **decimal fractions**. Format them as
percentages in Tableau; do not multiply by 100 and apply percentage formatting
again. The `[-1,+1]` window contains **three trading days**. `mean_absolute_car` is
the average of absolute bank-event CAR values, not the absolute value of the mean.

If building a Tableau workbook, choose exactly one benchmark and one window for
each view, use `COUNTD(event_id)` for policy-event counts, and keep bank-event
counts separately labelled. A filter on bank type changes the banks included in
the event average. Do not join aggregated tables to row-level results without
checking the relationship grain. Exclude unconverged forecasts from volatility
averages and retain their missingness in coverage counts.

The HTML dashboard provides benchmark, window, decision, bank-type and actual
announcement filters, a filtered CSV download, data provenance, signed and
absolute CAR views, and a GARCH comparison with explicit horizon labels.
Volatility labels use the training-reference thresholds supplied by the corrected
analysis; they are descriptive categories, not financial ratings.

SAS remains an optional, unexecuted component unless a real SAS execution log is
provided. The Python pipeline is the reproducible reference implementation.
