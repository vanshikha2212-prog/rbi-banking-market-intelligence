-- Run: sqlite3 -header -column outputs/study.sqlite < sql/analysis_queries.sql
-- Explicitly select a benchmark/window before combining bank-event observations.

-- The primary study has one policy event per distinct event_id, not per bank row.
SELECT benchmark, window,
       COUNT(DISTINCT event_id) AS policy_events,
       COUNT(DISTINCT bank_symbol) AS banks,
       COUNT(*) AS bank_event_records,
       ROUND(100 * AVG(car), 4) AS mean_car_pct,
       ROUND(100 * AVG(absolute_car), 4) AS mean_absolute_car_pct
FROM event_study_results
GROUP BY benchmark, window
ORDER BY benchmark, window;

-- Descriptive bank means for the Nifty 50 three-trading-day event window.
SELECT bank_name, bank_type, COUNT(DISTINCT event_id) AS events,
       ROUND(100 * AVG(car), 4) AS mean_car_pct,
       ROUND(100 * AVG(absolute_car), 4) AS mean_absolute_car_pct
FROM event_explorer
WHERE benchmark = '^NSEI' AND window = '[-1,+1]'
GROUP BY bank_symbol, bank_name, bank_type
ORDER BY mean_absolute_car_pct DESC;

-- Announcement-level means: these, rather than all bank rows, are the
-- observational units of the simple decision comparison in the Python report.
WITH event_means AS (
    SELECT event_id, event_date, decision, AVG(car) AS mean_car
    FROM event_explorer
    WHERE benchmark = '^NSEI' AND window = '[-1,+1]'
    GROUP BY event_id, event_date, decision
)
SELECT decision, COUNT(*) AS policy_events,
       ROUND(100 * AVG(mean_car), 4) AS mean_event_car_pct
FROM event_means
GROUP BY decision;

-- Public/private differences paired within the same announcement.
SELECT event_id, event_date,
       ROUND(100 * AVG(CASE WHEN bank_type = 'Public' THEN car END), 4) AS public_mean_car_pct,
       ROUND(100 * AVG(CASE WHEN bank_type = 'Private' THEN car END), 4) AS private_mean_car_pct,
       ROUND(100 * (AVG(CASE WHEN bank_type = 'Public' THEN car END) -
                    AVG(CASE WHEN bank_type = 'Private' THEN car END)), 4) AS public_minus_private_pp
FROM event_explorer
WHERE benchmark = '^NSEI' AND window = '[-1,+1]'
GROUP BY event_id, event_date
ORDER BY event_date;

-- These are averages at announcement targets, not averages over every day.
SELECT b.bank_name, b.bank_type,
       COUNT(*) AS event_forecast_attempts,
       SUM(v.converged) AS converged_forecasts,
       ROUND(100 * AVG(CASE WHEN v.converged = 1 THEN v.garch_volatility END), 4)
           AS mean_event_day_garch_volatility_pct
FROM volatility_forecasts v
JOIN bank_metadata b ON b.bank_symbol = v.bank_symbol
GROUP BY b.bank_symbol, b.bank_name, b.bank_type
ORDER BY mean_event_day_garch_volatility_pct DESC;
