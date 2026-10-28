# Data Dictionary

This document defines the main fields used across the RBI policy, market-data, event-study, volatility, and risk-analysis layers.

---

# 1. RBI Events

| Field | Meaning | Type |
|---|---|---|
| event_id | Unique MPC event identifier | string |
| meeting_start | Start date of MPC meeting | date |
| meeting_end | End date of MPC meeting | date |
| event_date | Public policy announcement date used as event day 0 | date |
| repo_before | Repo rate before the decision | numeric |
| repo_after | Repo rate after the decision | numeric |
| rate_change_bps | Change in repo rate in basis points | integer |
| decision | Hike, Cut, or Hold | categorical |
| stance | RBI policy stance | categorical |
| source_url | RBI source reference | string |
| notes | Context or data-quality note | string |

---

# 2. Bank Metadata

| Field | Meaning | Type |
|---|---|---|
| symbol | Market ticker used in the dataset | string |
| bank_name | Full bank name | string |
| bank_type | Public or Private | categorical |

---

# 3. Stock Prices

| Field | Meaning | Type |
|---|---|---|
| date | Trading date | date |
| symbol | Bank market ticker | string |
| open | Opening price | numeric |
| high | Highest price during the session | numeric |
| low | Lowest price during the session | numeric |
| close | Closing price | numeric |
| volume | Trading volume | numeric |

Primary key: (date, symbol)

---

# 4. Market Indices

| Field | Meaning | Type |
|---|---|---|
| date | Trading date | date |
| index_name | Market index identifier | string |
| open | Opening index level | numeric |
| high | Highest index level | numeric |
| low | Lowest index level | numeric |
| close | Closing index level | numeric |

Benchmarks used:

- Nifty 50
- Nifty Bank

---

# 5. Bank Returns

| Field | Meaning | Type |
|---|---|---|
| date | Trading date | date |
| symbol | Bank market ticker | string |
| return | Daily simple return | numeric |

Returns are calculated from daily market prices.

Primary key: (date, symbol)

---

# 6. Index Returns

| Field | Meaning | Type |
|---|---|---|
| date | Trading date | date |
| symbol | Market-index identifier | string |
| return | Daily benchmark return | numeric |

---

# 7. Event Study Results

| Field | Meaning | Type |
|---|---|---|
| event_id | RBI MPC event identifier | string |
| event_date | Policy announcement date | date |
| bank_symbol | Bank ticker | string |
| bank_type | Public or Private | categorical |
| alpha | Market-model intercept estimate | numeric |
| beta | Market-model sensitivity estimate | numeric |
| car_minus_1_plus_1 | CAR over [-1,+1] | numeric |
| car_minus_2_plus_2 | CAR over [-2,+2] | numeric |
| car_minus_5_plus_5 | CAR over [-5,+5] | numeric |
| ar_minus_1 | Abnormal return on day -1 | numeric |
| ar_0 | Abnormal return on event day | numeric |
| ar_plus_1 | Abnormal return on day +1 | numeric |

---

# 8. GARCH Forecasts

| Field | Meaning | Type |
|---|---|---|
| date | Forecast date | date |
| symbol | Bank ticker | string |
| garch_volatility_forecast | One-step-ahead conditional volatility forecast | numeric |

The forecast is generated using a GARCH-based volatility model.

---

# 9. Event Risk Analysis

| Field | Meaning | Type |
|---|---|---|
| event_id | RBI MPC event identifier | string |
| event_date | Policy announcement date | date |
| bank_symbol | Bank ticker | string |
| car | Primary event-window CAR | numeric |
| absolute_car | Absolute value of CAR | numeric |
| garch_volatility | GARCH volatility associated with the observation | numeric |

absolute_car measures the magnitude of the abnormal movement regardless of direction.

---

# 10. Event Risk Buckets

| Field | Meaning | Type |
|---|---|---|
| event_id | RBI MPC event identifier | string |
| event_date | Policy announcement date | date |
| bank_symbol | Bank ticker | string |
| car | Primary event-window CAR | numeric |
| absolute_car | Absolute CAR | numeric |
| garch_volatility | GARCH volatility | numeric |
| risk_level | Descriptive event-risk bucket | categorical |

Risk levels:

- Low
- Medium
- High
- Very High

These are equal-frequency descriptive buckets based on absolute CAR and are not externally calibrated financial-risk ratings.

---

# 11. Predictive Modelling Features

The predictive modelling dataset contains features derived from market and policy information.

| Feature | Meaning |
|---|---|
| return_1d | Recent 1-day bank return |
| return_5d | Recent 5-day bank return |
| return_20d | Recent 20-day bank return |
| volatility_20d | 20-day rolling volatility |
| volatility_60d | 60-day rolling volatility |
| garch_volatility | GARCH volatility feature |
| bank_type | Public or Private |
| decision | RBI policy decision |
| car_minus_1_plus_1 | Primary event-window CAR |
| positive_car | Binary target: 1 if CAR > 0, otherwise 0 |

---

# 12. Units and Interpretation

Returns, CAR, and volatility are stored as decimal values in the analytical datasets.

For example:

0.015 = 1.5%

When presenting results to users, these values are converted to percentage form.

---

# 13. Key Relationships

The main analytical relationships are:

rbi_events
     |
     +---- event_study_results
     +---- event_risk_analysis
     +---- event_risk_buckets

Bank information connects through:

bank_metadata
     |
     +---- stock_prices
     +---- bank_returns
     +---- event_study_results
     +---- garch_forecasts
     +---- event_risk_analysis

Market benchmarks connect through:

market_indices
     |
     +---- index_returns
     +---- event-study market model