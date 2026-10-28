# Research Design

## 1. Research Question

### Primary question

How do Reserve Bank of India (RBI) Monetary Policy Committee (MPC) announcements affect abnormal returns and volatility of major Indian banking stocks?

### Secondary questions

1. Do rate cuts, rate hikes, and policy holds produce different abnormal-return patterns?
2. Do public-sector and private-sector banks respond differently?
3. Are the results robust when Nifty Bank is used instead of Nifty 50 as the market benchmark?
4. Do banking-stock returns exhibit volatility clustering?
5. Can GARCH models provide useful event-period volatility estimates?
6. Can market, volatility, and policy features reliably predict the direction of event-window CAR?
7. Can the resulting analysis be transformed into an event-risk monitoring framework?

---

## 2. Study Period

### Policy events

RBI MPC announcements from:

**2023–2025**

Total events:

**18**

Decision distribution:

| Decision | Number of events |
|---|---:|
| Hold | 13 |
| Cut | 4 |
| Hike | 1 |

The `event_date` represents the date on which the policy decision was publicly announced to the market.

Meeting start and end dates are retained separately because an MPC meeting may span multiple days.

---

## 3. Banking Sample

Six large and liquid Indian banks are included.

### Private-sector banks

- HDFC Bank
- ICICI Bank
- Axis Bank

### Public-sector banks

- State Bank of India
- Bank of Baroda
- Canara Bank

The public/private classification is stored in the bank metadata table and is used for subgroup analysis.

---

## 4. Market Data Period

Daily market data covers:

**2021–2025**

The longer market-data period is required to provide sufficient observations for the 250-trading-day estimation window used in the event study.

### Benchmarks

Primary benchmark:

**Nifty 50**

Robustness benchmark:

**Nifty Bank**

---

## 5. Data Sources

### RBI policy data

RBI monetary-policy events are based on official RBI releases and schedules.

The event dataset records:

- Meeting dates
- Announcement date
- Repo rate before the decision
- Repo rate after the decision
- Rate change in basis points
- Policy decision
- Policy stance
- Source reference
- Notes

### Market data

The project uses NSE as the primary market-data reference.

`yfinance` is used as a programmatic acquisition and secondary cross-check layer.

The project does not treat Yahoo Finance as the primary institutional source for the market-data methodology.

---

## 6. Event Definition

The event is defined as the public announcement of an RBI MPC monetary-policy decision.

For each event:

- `meeting_start` = start of MPC meeting
- `meeting_end` = end of MPC meeting
- `event_date` = public announcement date

The announcement date is used as event day 0.

This distinction is important because the meeting itself may span multiple calendar days.

---

## 7. Event Windows

### Primary event window

\[
[-1,+1]
\]

This captures the trading day immediately before the announcement, the announcement day, and the following trading day.

### Robustness windows

\[
[-2,+2]
\]

and

\[
[-5,+5]
\]

The wider windows test whether the observed result depends strongly on the choice of event window.

---

## 8. Estimation Window

A 250-trading-day estimation window is used for each bank-event combination.

The estimation window ends at relative day:

\[
-6
\]

This creates a buffer between the estimation period and the event window.

The purpose is to avoid using observations immediately surrounding the event when estimating normal market relationships.

---

## 9. Market Model

The primary abnormal-return model is the market model:

\[
R_{i,t}
=
\alpha_i
+
\beta_i R_{m,t}
+
\epsilon_{i,t}
\]

where:

- \(R_{i,t}\) = return of bank \(i\)
- \(R_{m,t}\) = benchmark market return
- \(\alpha_i\) = estimated intercept
- \(\beta_i\) = estimated market sensitivity
- \(\epsilon_{i,t}\) = residual

The model is estimated separately for each bank-event combination.

---

## 10. Expected Return

Expected return is calculated as:

\[
E(R_{i,t})
=
\hat{\alpha}_i
+
\hat{\beta}_iR_{m,t}
\]

This represents the return expected from the bank's estimated relationship with the market benchmark in the absence of the event.

---

## 11. Abnormal Return

Abnormal return is:

\[
AR_{i,t}
=
R_{i,t}
-
E(R_{i,t})
\]

A positive abnormal return indicates that the bank performed above its model-implied market-adjusted return.

A negative abnormal return indicates underperformance relative to the model expectation.

---

## 12. Cumulative Abnormal Return

For an event window \([a,b]\):

\[
CAR_{i,[a,b]}
=
\sum_{t=a}^{b} AR_{i,t}
\]

CAR is calculated for:

- [-1,+1]
- [-2,+2]
- [-5,+5]

The primary outcome is the [-1,+1] CAR.

---

## 13. Statistical Inference

The project evaluates whether observed CARs differ systematically from zero.

Methods include:

- One-sample t-tests
- Confidence intervals
- Decision-group comparisons
- Public/private comparisons
- Event-level analysis
- Bootstrap confidence intervals

Comparisons include:

- Cut vs Hold
- Cut vs Hike
- Hold vs Hike
- Public vs Private

Because the event sample is small, particularly for hikes and cuts, statistical results are interpreted cautiously.

---

## 14. Benchmark Robustness

The primary analysis uses Nifty 50.

A separate event-study implementation uses Nifty Bank as a robustness benchmark.

This allows the direction and magnitude of results to be compared across two market benchmarks.

The Nifty Bank result is treated as robustness evidence rather than replacing the primary Nifty 50 specification.

---

## 15. Confounding Events and Causal Interpretation

Other market-moving information may arrive around RBI announcements.

Potential sources of confounding include:

- Corporate announcements
- Global market movements
- Macroeconomic releases
- Banking-sector developments
- Other domestic policy announcements

Therefore, the event-study results are interpreted as **abnormal market movements around RBI announcements**, rather than as definitive causal estimates.

The project does not claim that an RBI decision mechanically caused a specific bank's return.

---

# Time-Series Analysis

## 16. Return Stationarity

Daily returns are tested using the Augmented Dickey-Fuller (ADF) test.

The analysed return series were stationary at the 5% significance level.

---

## 17. Rolling Statistics

Rolling statistics are calculated to examine changes in:

- Mean returns
- 20-day volatility
- 60-day volatility

These measures provide a descriptive view of changing market conditions over time.

---

## 18. ACF and PACF

Autocorrelation and partial autocorrelation functions are examined for daily returns.

The results show limited linear autocorrelation at short lags.

Therefore, an ARIMA-style return model was not forced into the project solely for methodological completeness.

---

## 19. Volatility Clustering

Ljung-Box tests are applied to squared returns.

Significant results across the banking-stock series indicate the presence of volatility clustering.

This motivates the use of conditional-volatility modelling.

---

# GARCH Analysis

## 20. GARCH Model

A GARCH(1,1) specification is used to model conditional volatility:

\[
\sigma_t^2
=
\omega
+
\alpha\epsilon_{t-1}^2
+
\beta\sigma_{t-1}^2
\]

where:

- \(\sigma_t^2\) = conditional variance
- \(\omega\) = baseline variance component
- \(\alpha\) = response to recent shocks
- \(\beta\) = persistence of volatility

One-step-ahead volatility forecasts are generated for use in event-risk analysis.

---

## 21. Event-Risk Analysis

Each bank-event observation is evaluated using:

- CAR
- Absolute CAR
- GARCH volatility

Absolute CAR is used to measure the magnitude of the event-window abnormal movement regardless of direction.

GARCH volatility represents the modelled level of conditional market risk.

These are related but distinct concepts.

A high-volatility observation does not necessarily imply a large abnormal return.

---

## 22. Risk Buckets

Event observations are grouped into four equal-frequency risk buckets using absolute CAR:

- Low
- Medium
- High
- Very High

The buckets are descriptive classifications of the magnitude of event-window abnormal movement.

They should not be interpreted as externally calibrated financial risk ratings.

---

# Predictive Modelling

## 23. Predictive Objective

A machine-learning experiment tests whether available event and market features can predict whether the primary CAR will be positive.

The target is:

```text
positive_car = 1 if CAR[-1,+1] > 0
positive_car = 0 otherwise

## 24. Temporal Validation

The predictive experiment uses a chronological split:

### Training

2023–2024

### Testing

2025

Random shuffling is avoided to reduce temporal leakage.

---

## 25. Models Tested

The predictive layer includes:

- Baseline comparison
- Logistic Regression
- Random Forest
- Feature importance
- Permutation importance

The objective is not to maximize model complexity, but to determine whether the available features contain stable out-of-sample predictive information.

---

## 26. Predictive Result

The tested models did not demonstrate reliable out-of-sample prediction of CAR direction.

The Random Forest achieved an out-of-sample ROC-AUC of approximately:

**0.375**

Permutation importance did not identify stable positive predictive contributions from the tested features.

Therefore, the project does not present the predictive model as a successful forecasting system.

Instead, the analysis motivates a shift toward event-risk and volatility monitoring.

---

# SQL Analytical Layer

## 27. Relational Database

SQLite is used to create a structured analytical database containing:

- RBI events
- Bank metadata
- Stock prices
- Market indices
- Bank returns
- Index returns
- Event-study results
- GARCH forecasts
- Event-risk analysis
- Event-risk buckets

SQL is used for:

- Data-quality validation
- Aggregation
- Bank-level analysis
- Decision-level comparisons
- Event ranking
- Risk analysis
- CAR-GARCH relationship analysis

---

# PySpark

## 28. Scalable Processing

PySpark is used to demonstrate scalable processing of market data.

The pipeline calculates:

- Daily returns
- 20-day rolling returns
- 20-day rolling volatility
- Bank-level summaries

The Spark implementation is validated against the Pandas implementation.

The validation matched all 7,416 market observations, with numerical differences at floating-point precision level.

This demonstrates consistency between the two processing implementations.

---

# SAS

## 29. SAS Validation Layer

A SAS validation script has been prepared as an optional secondary statistical-validation layer.

SAS was not executed in the local development environment because a local SAS installation was unavailable.

Therefore, SAS is not presented as an executed component of the final empirical results.

---

# Tableau Decision-Support Layer

## 30. Dashboard

The final Tableau dashboard provides an interactive view of:

- RBI policy-event impact
- Average CAR by bank
- Event risk
- Bank volatility/risk profile

Filters include:

- Decision
- Event date
- Bank type

The dashboard acts as the presentation and decision-support layer of the analytical pipeline.

---

# Research Interpretation

The project is designed as an empirical market-reaction study rather than a causal identification strategy.

The main interpretation is:

> RBI monetary-policy announcements were associated with different abnormal-return patterns across decision types and banking groups, while the broader sample did not exhibit a statistically significant average abnormal return.

Rate-cut events showed more negative short-window abnormal returns than hold events, although the small number of rate-cut events limits the strength of generalization.

Public-sector banks also displayed higher average modelled volatility and larger average absolute event-window movements than private-sector banks in this sample.

The predictive modelling experiment did not provide reliable out-of-sample CAR-direction forecasts, leading the project toward a volatility-aware event-risk monitoring framework.

---

# Limitations

1. Only 18 MPC events are included.
2. Only four events are rate cuts.
3. Only one event is a rate hike.
4. The sample contains only six banks.
5. Other information may overlap with RBI announcement windows.
6. RBI policy is endogenous to broader economic and financial conditions.
7. Event-study results do not establish causality by themselves.
8. The predictive sample is relatively small.
9. Credible policy-expectations data were not available for constructing a policy-surprise measure.
10. Risk buckets are descriptive and are not externally calibrated financial-risk ratings.