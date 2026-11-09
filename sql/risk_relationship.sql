-- Descriptive association for one benchmark/window, using converged forecasts.
-- Different horizons: event-window absolute CAR versus one-day GARCH volatility.
-- This is not a predictive performance test or a causal relationship.
WITH pairs AS (
    SELECT r.absolute_car AS x, v.garch_volatility AS y
    FROM event_study_results r
    JOIN volatility_forecasts v
      ON v.event_id = r.event_id AND v.bank_symbol = r.bank_symbol
    WHERE r.benchmark = '^NSEI' AND r.window = '[-1,+1]'
      AND v.converged = 1 AND v.garch_volatility IS NOT NULL
)
SELECT COUNT(*) AS bank_event_pairs,
       AVG(x) AS mean_absolute_car, AVG(y) AS mean_garch_volatility,
       AVG(x*y) - AVG(x)*AVG(y) AS covariance_component,
       AVG(x*x) - AVG(x)*AVG(x) AS car_variance_component,
       AVG(y*y) - AVG(y)*AVG(y) AS volatility_variance_component
FROM pairs;
-- Pearson correlation = covariance_component /
-- sqrt(car_variance_component * volatility_variance_component), if both > 0.
-- Components avoid requiring an optional SQLite math extension.

SELECT b.bank_type, v.risk_level,
       COUNT(*) AS bank_event_forecasts,
       ROUND(100 * AVG(CASE WHEN v.converged = 1 THEN v.garch_volatility END), 4)
           AS mean_one_day_garch_volatility_pct
FROM volatility_forecasts v
JOIN bank_metadata b ON b.bank_symbol = v.bank_symbol
GROUP BY b.bank_type, v.risk_level;
-- risk_level is derived from training-reference volatility thresholds, never
-- from absolute CAR. It is not a credit rating or calibrated loss probability.
