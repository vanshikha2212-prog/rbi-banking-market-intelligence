-- Run: sqlite3 -header -column outputs/study.sqlite < sql/data_quality.sql
-- The Python builder enforces these invariants before replacing an existing DB.
PRAGMA integrity_check;
PRAGMA foreign_key_check;

SELECT 'rbi_events' AS table_name, COUNT(*) AS row_count FROM rbi_events
UNION ALL SELECT 'bank_metadata', COUNT(*) FROM bank_metadata
UNION ALL SELECT 'event_study_results', COUNT(*) FROM event_study_results
UNION ALL SELECT 'volatility_forecasts', COUNT(*) FROM volatility_forecasts
UNION ALL SELECT 'market_data', COUNT(*) FROM market_data;

-- All following exception queries should return zero rows.
SELECT event_id, bank_symbol, benchmark, window, COUNT(*) AS records
FROM event_study_results
GROUP BY event_id, bank_symbol, benchmark, window
HAVING COUNT(*) <> 1;

SELECT r.event_id, r.bank_symbol, r.benchmark, r.window
FROM event_study_results r
WHERE r.car IS NULL OR r.absolute_car IS NULL
   OR ABS(r.absolute_car - ABS(r.car)) > 1e-12;

SELECT v.event_id, v.bank_symbol, v.forecast_origin_date,
       v.forecast_target_date, e.event_date
FROM volatility_forecasts v
JOIN rbi_events e ON e.event_id = v.event_id
WHERE v.forecast_origin_date >= v.forecast_target_date
   OR v.forecast_target_date <> e.event_date
   OR (v.converged = 1 AND v.garch_volatility IS NULL);

SELECT event_id, repo_before, repo_after, rate_change_bps
FROM rbi_events
WHERE ABS((repo_after - repo_before) * 100 - rate_change_bps) > 1e-8;

-- Counts are descriptive; they are not tests of statistical independence.
SELECT decision, COUNT(*) AS policy_events FROM rbi_events GROUP BY decision;
SELECT bank_type, COUNT(*) AS banks FROM bank_metadata GROUP BY bank_type;
SELECT benchmark, window, COUNT(DISTINCT event_id) AS events,
       COUNT(*) AS bank_event_rows
FROM event_study_results GROUP BY benchmark, window;
