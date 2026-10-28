-- ============================================================
-- RBI BANKING MARKET INTELLIGENCE
-- SQL ANALYTICAL QUERIES
-- ============================================================

.headers on
.mode column

-- ============================================================
-- 1. Average CAR by bank
-- ============================================================

SELECT
    bank_symbol,
    bank_type,
    ROUND(AVG(car_minus_1_plus_1) * 100, 3) AS avg_car_pct,
    ROUND(AVG(car_minus_2_plus_2) * 100, 3) AS avg_car_5day_pct,
    COUNT(*) AS event_count
FROM event_study_results
GROUP BY bank_symbol, bank_type
ORDER BY avg_car_pct DESC;


-- ============================================================
-- 2. Average CAR by RBI decision
-- ============================================================

SELECT
    e.decision,
    COUNT(*) AS observations,
    ROUND(AVG(es.car_minus_1_plus_1) * 100, 3) AS avg_car_pct,
    ROUND(AVG(es.car_minus_2_plus_2) * 100, 3) AS avg_car_5day_pct,
    ROUND(AVG(es.car_minus_5_plus_5) * 100, 3) AS avg_car_11day_pct
FROM event_study_results es
JOIN rbi_events e
    ON es.event_id = e.event_id
GROUP BY e.decision
ORDER BY avg_car_pct;


-- ============================================================
-- 3. Private vs Public banks
-- ============================================================

SELECT
    bank_type,
    COUNT(*) AS observations,
    ROUND(AVG(car_minus_1_plus_1) * 100, 3) AS avg_car_pct,
    ROUND(AVG(car_minus_2_plus_2) * 100, 3) AS avg_car_5day_pct,
    ROUND(AVG(car_minus_5_plus_5) * 100, 3) AS avg_car_11day_pct
FROM event_study_results
GROUP BY bank_type
ORDER BY avg_car_pct DESC;


-- ============================================================
-- 4. RBI events by year
-- ============================================================

SELECT
    strftime('%Y', event_date) AS year,
    COUNT(*) AS number_of_events,
    SUM(CASE WHEN decision = 'Cut' THEN 1 ELSE 0 END) AS cuts,
    SUM(CASE WHEN decision = 'Hike' THEN 1 ELSE 0 END) AS hikes,
    SUM(CASE WHEN decision = 'Hold' THEN 1 ELSE 0 END) AS holds
FROM rbi_events
GROUP BY year
ORDER BY year;


-- ============================================================
-- 5. Event-level CAR by RBI announcement
-- ============================================================

SELECT
    e.event_id,
    e.event_date,
    e.decision,
    e.rate_change_bps,
    ROUND(AVG(es.car_minus_1_plus_1) * 100, 3) AS avg_car_pct
FROM rbi_events e
JOIN event_study_results es
    ON e.event_id = es.event_id
GROUP BY
    e.event_id,
    e.event_date,
    e.decision,
    e.rate_change_bps
ORDER BY avg_car_pct;


-- ============================================================
-- 6. Average GARCH volatility by bank
-- ============================================================

SELECT
    symbol,
    COUNT(*) AS observations,
    ROUND(AVG(garch_volatility_forecast) * 100, 3) AS avg_garch_volatility_pct,
    ROUND(MAX(garch_volatility_forecast) * 100, 3) AS max_garch_volatility_pct
FROM garch_forecasts
GROUP BY symbol
ORDER BY avg_garch_volatility_pct DESC;


-- ============================================================
-- 7. Risk distribution
-- ============================================================

SELECT
    risk_level,
    COUNT(*) AS observations,
    ROUND(
        100.0 * COUNT(*) /
        (SELECT COUNT(*) FROM event_risk_buckets),
        2
    ) AS percentage
FROM event_risk_buckets
GROUP BY risk_level
ORDER BY
    CASE risk_level
        WHEN 'Low' THEN 1
        WHEN 'Medium' THEN 2
        WHEN 'High' THEN 3
        WHEN 'Very High' THEN 4
    END;


-- ============================================================
-- 8. Highest-risk bank/event combinations
-- ============================================================

SELECT
    event_id,
    event_date,
    bank_symbol,
    ROUND(car * 100, 3) AS car_pct,
    ROUND(absolute_car * 100, 3) AS absolute_car_pct,
    ROUND(garch_volatility * 100, 3) AS garch_volatility_pct,
    risk_level
FROM event_risk_buckets
ORDER BY absolute_car DESC
LIMIT 10;


-- ============================================================
-- 9. Risk by bank type
-- ============================================================

SELECT
    bm.bank_type,
    erb.risk_level,
    COUNT(*) AS observations
FROM event_risk_buckets erb
JOIN bank_metadata bm
    ON erb.bank_symbol = bm.symbol
GROUP BY
    bm.bank_type,
    erb.risk_level
ORDER BY
    bm.bank_type,
    CASE erb.risk_level
        WHEN 'Low' THEN 1
        WHEN 'Medium' THEN 2
        WHEN 'High' THEN 3
        WHEN 'Very High' THEN 4
    END;


-- ============================================================
-- 10. Biggest positive and negative CARs
-- ============================================================

SELECT
    event_id,
    event_date,
    bank_symbol,
    ROUND(car_minus_1_plus_1 * 100, 3) AS car_pct
FROM event_study_results
ORDER BY car_minus_1_plus_1 DESC
LIMIT 10;

SELECT
    event_id,
    event_date,
    bank_symbol,
    ROUND(car_minus_1_plus_1 * 100, 3) AS car_pct
FROM event_study_results
ORDER BY car_minus_1_plus_1 ASC
LIMIT 10;