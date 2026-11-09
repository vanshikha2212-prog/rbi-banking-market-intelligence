# RBI Banking Market Intelligence — Extended Study

A reproducible event study of RBI Monetary Policy Committee announcements and six Indian banking stocks, using **57 official RBI repo-rate decisions (2016–2025)** and **official NSE daily bank and benchmark archives (2015–2025)**.

This is an observational research project. It distinguishes three questions that are often confused:

1. Are RBI announcements associated with abnormal bank-stock returns?
2. Do individual banks and public/private groups respond differently?
3. Can information available before an announcement predict the sign of a future abnormal return better than simple baselines?

[Research report](outputs/RESEARCH_REPORT.md) · [Interactive historical dashboard](outputs/dashboard.html) · [Research design](docs/research_design.md) · [Data sources](docs/data_sources.md) · [Reproduction](docs/reproduction.md)

## Study scope

| Item | Extended design |
|---|---|
| Policy events | 57: 8 hikes, 13 cuts, 36 holds |
| Event period | 4 October 2016–5 December 2025 |
| Market history | 2015–2025 official NSE archives |
| Private banks | Axis Bank, HDFC Bank, ICICI Bank |
| Public banks | Bank of Baroda, Canara Bank, State Bank of India |
| Benchmarks | Nifty 50 (primary), Nifty Bank (sensitivity) |
| Primary event window | CAR [−1,+1] trading days |
| Prediction target | Sign of CAR [0,+1], wholly after the previous-close origin |
| Evaluation | Expanding event-grouped walk-forward testing after 24 prior events |

The six banks observed at one announcement are not six independent policy shocks. Statistical inference first aggregates to the event level; public/private comparisons are paired within the same event.

## What the extended sample finds

- In the primary Nifty 50 CAR [−1,+1] specification, cuts averaged **1.05 percentage points below holds** (raw Welch p=0.017; event-permutation p=0.045), but neither result survives the pre-declared 18-contrast Holm correction (adjusted p=0.313 and 0.720). Hikes were not distinguishable from holds.
- Public banks had **0.94 percentage points more absolute movement** than private banks within the same event (Holm-adjusted paired t p=0.0005), while their signed public-minus-private CAR difference was small and uncertain (0.17 percentage points; adjusted p=1.000). This supports a difference in movement magnitude, not a stable directional effect.
- The best simple baseline reached 52.5% accuracy and 51.7% balanced accuracy on 33 later announcements. The learned models reached 41.4%–44.9% accuracy, and none showed a robust paired advantage over the majority baseline.

These are historical associations. The corrected inference, sensitivity grid, confidence intervals, and prediction uncertainty are reported in full rather than selecting only favorable specifications.

## Methods

- **Event study:** a 250-trading-day market model ending on day −6; 120- and 180-day estimation sensitivities; multiple event windows and both benchmarks.
- **Inference:** event-level t and permutation tests, paired public/private t and Wilcoxon tests, event bootstrap intervals, Holm family-wise correction, and leave-one-event-out diagnostics.
- **Robustness:** pre-declared exclusions for COVID emergency meetings, off-cycle meetings, and the wider COVID era. Every scenario is retained regardless of the result.
- **Prediction:** majority prevalence, bank historical-rate, and persistence baselines versus L2 logistic regression, elastic net, random forest, and histogram gradient boosting.
- **Leakage control:** all rows from an announcement stay together; every outer test event is later than every training event; preprocessing and sigmoid calibration fit only on earlier complete events.
- **Uncertainty:** paired bootstrap resampling of whole out-of-sample announcements, not individual bank rows.

Predictive accuracy, statistical significance, and causality are reported separately. No model is claimed to be better unless its genuinely out-of-sample metrics support that conclusion; no significance or accuracy is guaranteed.

## Official data provenance

Each policy row links to an event-specific RBI resolution or official minutes. Bank OHLCV and previous close come from official NSE bhavcopies; Nifty 50 and Nifty Bank come from official NSE daily index archives.

Bank return is calculated as:

```text
official NSE close / official NSE previous close - 1
```

Using the exchange’s previous-close base prevents splits and bonus issues from appearing as artificial returns. The build does not forward-fill prices. The retrieval manifest records every official source URL and SHA-256 hash used to create the consolidated snapshot.

## Reproduce

The tested environment is Python 3.13.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m rbi_intelligence run
python -m rbi_intelligence verify
python -m pytest -q
```

The standard analysis is offline because the reviewed NSE snapshot is committed. To retrieve a new official vintage explicitly:

```bash
python -m rbi_intelligence refresh-data
python -m rbi_intelligence run
```

The dashboard is **interactive historical analysis**, not a live or real-time dashboard. It embeds the generated results and makes no market-data requests.

## Interpretation limits

Daily event windows contain other news, and the study does not observe the market’s pre-announcement policy expectation. A cut, hike, or hold therefore combines the decision with any surprise component, guidance, liquidity measures, and concurrent information. Nifty Bank also contains the studied sector. These results describe historical associations and out-of-sample prediction performance; they do not identify the causal economic effect of repo-rate changes or provide investment advice.
