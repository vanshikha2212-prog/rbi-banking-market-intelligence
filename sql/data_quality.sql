-- ============================================================
-- RBI BANKING MARKET INTELLIGENCE
-- SQL DATA QUALITY CHECKS
-- ============================================================

-- 1. Row counts for every table
SELECT 'rbi_events' AS table_name, COUNT(*) AS row_count
FROM rbi_events

UNION ALL

SELECT 'bank_metadata', COUNT(*)
FROM bank_metadata

UNION ALL

SELECT 'stock_prices', COUNT(*)
FROM stock_prices

UNION ALL

SELECT 'market_indices', COUNT(*)
FROM market_indices

UNION ALL

SELECT 'bank_returns', COUNT(*)
FROM bank_returns

UNION ALL

SELECT 'index_returns', COUNT(*)
FROM index_returns

UNION ALL

SELECT 'event_study_results', COUNT(*)
FROM event_study_results

UNION ALL

SELECT 'garch_forecasts', COUNT(*)
FROM garch_forecasts

UNION ALL

SELECT 'event_risk_analysis', COUNT(*)
FROM event_risk_analysis

UNION ALL

SELECT 'event_risk_buckets', COUNT(*)
FROM event_risk_buckets;


-- 2. Check for duplicate RBI events
SELECT
    event_id,
    COUNT(*) AS duplicate_count
FROM rbi_events
GROUP BY event_id
HAVING COUNT(*) > 1;


-- 3. Check for duplicate bank-event observations
SELECT
    event_id,
    bank_symbol,
    COUNT(*) AS duplicate_count
FROM event_study_results
GROUP BY event_id, bank_symbol
HAVING COUNT(*) > 1;


-- 4. Check for missing values in event-study results
SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN event_id IS NULL THEN 1 ELSE 0 END) AS missing_event_id,
    SUM(CASE WHEN bank_symbol IS NULL THEN 1 ELSE 0 END) AS missing_bank,
    SUM(CASE WHEN car_minus_1_plus_1 IS NULL THEN 1 ELSE 0 END) AS missing_car
FROM event_study_results;


-- 5. Check that every event-study event exists in RBI events
SELECT
    e.event_id
FROM event_study_results e
LEFT JOIN rbi_events r
    ON e.event_id = r.event_id
WHERE r.event_id IS NULL;


-- 6. Check that every bank in event-study results exists in metadata
SELECT
    e.bank_symbol
FROM event_study_results e
LEFT JOIN bank_metadata b
    ON e.bank_symbol = b.symbol
WHERE b.symbol IS NULL;


-- 7. Check decision distribution
SELECT
    decision,
    COUNT(*) AS event_count
FROM rbi_events
GROUP BY decision
ORDER BY event_count DESC;


-- 8. Check risk bucket distribution
SELECT
    risk_level,
    COUNT(*) AS observation_count
FROM event_risk_buckets
GROUP BY risk_level
ORDER BY
    CASE risk_level
        WHEN 'Low' THEN 1
        WHEN 'Medium' THEN 2
        WHEN 'High' THEN 3
        WHEN 'Very High' THEN 4
    END;


-- 9. Check date range of bank returns
SELECT
    MIN(date) AS first_date,
    MAX(date) AS last_date,
    COUNT(DISTINCT symbol) AS banks
FROM bank_returns;


-- 10. Check public/private bank distribution
SELECT
    bank_type,
    COUNT(*) AS bank_count
FROM bank_metadata
GROUP BY bank_type;