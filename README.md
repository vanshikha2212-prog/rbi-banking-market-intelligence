# RBI Banking Market Intelligence System

## Monetary Policy Transmission in India: How Do RBI Policy Decisions Affect Indian Banking Stocks?

A research-driven market intelligence system studying how Reserve Bank of India (RBI) monetary-policy announcements are associated with abnormal returns and volatility in major Indian banking stocks.

The project combines event-study methodology, statistical inference, time-series volatility modelling, machine learning, SQL analytics, PySpark processing, and Tableau visualization.

---

## 1. Problem Statement

RBI monetary-policy decisions can influence interest-rate expectations, liquidity conditions, bank profitability expectations, and investor sentiment.

However, the market response is not necessarily uniform across banks.

This project investigates:

> **How do RBI monetary-policy announcements affect Indian banking stocks, and which banks exhibit greater abnormal return and volatility around these events?**

---

## 2. Research Objectives

The project aims to:

1. Measure abnormal returns around RBI Monetary Policy Committee (MPC) announcements.
2. Compare market reactions across rate cuts, hikes, and holds.
3. Compare public-sector and private-sector banks.
4. Test whether results remain consistent under alternative market benchmarks.
5. Analyse banking-stock volatility using time-series methods.
6. Model volatility using GARCH.
7. Test whether market and policy features can predict the direction of abnormal returns.
8. Build an event-risk monitoring framework.
9. Create a SQL-based analytical layer.
10. Demonstrate scalable market-data processing using PySpark.
11. Present results through an interactive Tableau dashboard.

---

## 3. Study Design

### Policy events

The study covers scheduled RBI MPC announcements from:

**2023–2025**

Total events:

**18**

Decision distribution:

| Decision | Events |
|---|---:|
| Hold | 13 |
| Cut | 4 |
| Hike | 1 |

The event date represents the date on which the monetary-policy decision became publicly available to the market.

---

## 4. Banking Sample

Six large and liquid Indian banks are analysed.

### Private-sector banks

- HDFC Bank
- ICICI Bank
- Axis Bank

### Public-sector banks

- State Bank of India
- Bank of Baroda
- Canara Bank

---

## 5. Market Data

The market-data study period is:

**2021–2025**

The longer history provides sufficient observations for the 250-trading-day estimation window used in the event study.

### Benchmarks

Primary benchmark:

**Nifty 50**

Robustness benchmark:

**Nifty Bank**

### Data sources

RBI policy information is based on official RBI materials.

NSE is the preferred primary source for market data.

`yfinance` is used as a programmatic/secondary acquisition and cross-check layer rather than being presented as the primary research source.

---

## 6. Event Study Methodology

The primary event window is:

**[-1, +1] trading days**

Robustness windows:

- [-2, +2]
- [-5, +5]

A 250-trading-day estimation window is used, ending at relative day -6.

For each bank:

\[
R_{i,t} = \alpha_i + \beta_i R_{m,t} + \epsilon_{i,t}
\]

where:

- \(R_{i,t}\) = bank return
- \(R_{m,t}\) = benchmark market return
- \(\alpha_i\) = estimated intercept
- \(\beta_i\) = market sensitivity
- \(\epsilon_{i,t}\) = residual

Expected return:

\[
E(R_{i,t}) = \hat{\alpha}_i + \hat{\beta}_i R_{m,t}
\]

Abnormal return:

\[
AR_{i,t} = R_{i,t} - E(R_{i,t})
\]

Cumulative abnormal return:

\[
CAR_{i,[a,b]} = \sum_{t=a}^{b} AR_{i,t}
\]

---

## 7. Statistical Analysis

The project evaluates:

- Mean abnormal returns
- Mean CAR
- One-sample t-tests
- Confidence intervals
- Cut vs hold comparisons
- Hike vs hold comparisons
- Public vs private comparisons
- Alternative event windows
- Nifty 50 vs Nifty Bank robustness
- Bootstrap confidence intervals

### Key finding

Across all events, the average [-1,+1] abnormal return was not statistically different from zero.

However, rate-cut events showed more negative short-window abnormal returns than hold events.

For the Nifty 50 benchmark:

**Cut vs Hold difference ≈ -1.18 percentage points**

For the Nifty Bank benchmark:

**Cut vs Hold difference ≈ -1.06 percentage points**

The negative difference remained supported by bootstrap confidence intervals.

The inference should be interpreted cautiously because only four rate-cut events are present in the sample.

---

## 8. Time-Series Analysis

The project evaluates the statistical properties of daily returns using:

- Augmented Dickey-Fuller stationarity tests
- Rolling mean
- Rolling volatility
- ACF
- PACF
- Ljung-Box tests on squared returns

All analysed return series were stationary at the 5% level.

The ACF/PACF analysis showed limited linear autocorrelation in daily returns, while squared-return tests indicated volatility clustering.

This motivated the use of GARCH rather than forcing an ARIMA-style return model.

---

## 9. GARCH Volatility Modelling

A GARCH(1,1) framework is used to model conditional volatility.

The general form is:

\[
\sigma_t^2 =
\omega +
\alpha\epsilon_{t-1}^2 +
\beta\sigma_{t-1}^2
\]

The resulting one-step-ahead volatility forecasts are used as features in the event-risk analysis. The resulting risk buckets are sample-relative classifications; they should not be interpreted as formal risk ratings or as evidence that volatility alone predicts the size of an event reaction.

### Average GARCH volatility

| Bank | Avg. GARCH volatility |
|---|---:|
| Canara Bank | 2.367% |
| Bank of Baroda | 2.188% |
| SBI | 1.775% |
| Axis Bank | 1.489% |
| HDFC Bank | 1.457% |
| ICICI Bank | 1.098% |

Public-sector banks in this sample exhibited higher average modelled volatility than private-sector banks.

---

## 10. Predictive Modelling

A separate machine-learning experiment was conducted to test whether available market and policy features could predict whether a bank's event-window CAR would be positive.

Models tested include:

- Logistic Regression
- Random Forest
- Baseline comparisons
- Feature importance
- Permutation importance

The evaluation uses an out-of-time split:

**2023–2024 → training**

**2025 → testing**

Random train/test shuffling was avoided to reduce temporal leakage.

### Result

The models did not demonstrate reliable out-of-sample predictive performance.

The Random Forest achieved an out-of-sample ROC-AUC of approximately:

**0.375**

Permutation importance also showed no stable positive predictive contribution from the tested features.

Rather than forcing a predictive model with weak performance, the project therefore shifts toward **risk monitoring and volatility analytics**.

---

## 11. Event Risk Analytics

Each bank-event observation is evaluated using:

- Absolute CAR
- GARCH volatility
- Volatility risk classification

**Interpretation of risk buckets:** the risk categories are based on sample quartiles of GARCH forecast volatility. They are relative categories within this dataset, not universal risk thresholds, credit ratings, or direct predictions of losses. Absolute CAR measures the magnitude of the event-window abnormal return, while GARCH volatility measures modelled conditional volatility. These metrics describe different dimensions of risk, so a large absolute CAR can occur alongside a medium volatility-risk category.

The analysis shows that public-sector banks experienced larger average absolute event-window movements than private-sector banks.

Average absolute CAR:

| Bank Type | Average Absolute CAR |
|---|---:|
| Public | 2.027% |
| Private | 1.081% |

The descriptive correlation between absolute CAR and GARCH volatility is approximately:

**0.14**

This indicates only a weak positive relationship.

Therefore, GARCH volatility should be interpreted as a risk indicator rather than as a strong predictor of event impact.

---

## 12. SQL Analytics

The project uses SQLite as a relational analytical layer.

The database contains tables for:

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

SQL analysis covers:

- Bank-level CAR
- Decision-level comparisons
- Public/private comparisons
- Event rankings
- GARCH statistics
- Event-risk observations
- CAR-GARCH relationships
- Volatility quartile analysis

---

## 13. PySpark

PySpark is used to demonstrate scalable market-data processing.

The Spark pipeline calculates:

- Daily returns
- 20-day rolling returns
- 20-day rolling volatility
- Bank-level summary statistics

The Spark output was validated against the Pandas implementation.

Validation result:

- Pandas observations: **7,416**
- Spark observations: **7,416**
- Matched observations: **7,416**
- Maximum absolute difference: approximately **1 × 10⁻¹⁶**

This confirms numerical consistency between the Pandas and Spark implementations for the tested return calculation.

---

## 14. Tableau Dashboard

The project includes an interactive Tableau dashboard containing:

### KPI cards

- RBI policy events
- Banks analysed
- Average CAR

### Visualizations

- Average CAR by bank
- RBI policy event impact
- Event risk profile
- Bank risk profile

### Filters

- Decision
- Event date
- Bank type

The dashboard is intended as the decision-support layer of the project.

---

## 15. Key Findings

### 1. Overall market reaction

There was no statistically significant average abnormal return across all RBI events.

### 2. Rate cuts

Rate-cut events were associated with more negative short-window abnormal returns than hold events.

### 3. Public vs private banks

Public-sector banks exhibited larger average absolute event-window movements and higher modelled volatility than private-sector banks in this sample.

### 4. Volatility

Volatility clustering was present across the banking-stock return series.

### 5. Prediction

The tested machine-learning models did not provide reliable out-of-sample prediction of CAR direction.

### 6. Risk monitoring

Because predictive performance was weak, the project emphasizes volatility-aware event-risk monitoring rather than presenting an unreliable forecasting model.

---

## 16. Limitations

The findings should be interpreted within the study design.

Important limitations include:

- Only 18 RBI MPC events are analysed.
- Only four events were rate cuts.
- Only one event was a rate hike.
- RBI policy decisions may coincide with other market-moving events.
- Volatility-risk buckets are based on the distribution of this sample and may change with the sample period or selected banks; they are descriptive categories rather than universal thresholds.
- The RBI responds to macroeconomic and financial conditions, creating potential endogeneity.
- Event-study results indicate abnormal market movements around announcements but do not by themselves establish causality.
- The predictive dataset is relatively small.
- The machine-learning experiment therefore has limited statistical power.
- Policy-surprise measures were not constructed because a sufficiently credible expectations dataset was not available.

---

## 17. Technology Stack

**Python**

- pandas
- NumPy
- SciPy
- statsmodels
- scikit-learn
- arch
- yfinance

**SQL**

- SQLite

**Big Data**

- PySpark

**Visualization**

- Tableau

**Statistical / Enterprise Analytics**

- SAS validation script

---

## 18. Repository Structure

```text
rbi_ver3/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── external/
│   └── database/
│
├── sql/
│   ├── schema.sql
│   ├── data_quality.sql
│   ├── analysis_queries.sql
│   └── risk_relationship.sql
│
├── src/
│   ├── preprocessing/
│   ├── event_study/
│   ├── time_series/
│   ├── models/
│   └── database/
│
├── pyspark/
│   ├── 01_market_data_pipeline.py
│   └── 02_validate_against_pandas.py
│
├── sas/
│   └── 01_event_study_validation.sas
│
├── tableau/
│   └── exports/
│
├── docs/
│   ├── research_design.md
│   └── data_dictionary.md
│
├── tests/
├── requirements.txt
├── .gitignore
└── README.md