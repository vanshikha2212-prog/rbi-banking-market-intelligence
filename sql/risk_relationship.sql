-- ============================================================
-- CAR vs GARCH VOLATILITY RELATIONSHIP ANALYSIS
-- ============================================================


-- ============================================================
-- QUERY 1: Components for CAR-GARCH correlation
-- ============================================================
-- SQLite on your system does not support the required
-- square-root calculation, so we calculate the three
-- components here and calculate the final correlation separately.

WITH stats AS (
    SELECT
        AVG(absolute_car) AS avg_car,
        AVG(garch_volatility) AS avg_vol
    FROM event_risk_analysis
),
components AS (
    SELECT
        (r.absolute_car - s.avg_car) *
        (r.garch_volatility - s.avg_vol) AS covariance_part,

        (r.absolute_car - s.avg_car) *
        (r.absolute_car - s.avg_car) AS car_squared,

        (r.garch_volatility - s.avg_vol) *
        (r.garch_volatility - s.avg_vol) AS vol_squared
    FROM event_risk_analysis r
    CROSS JOIN stats s
)
SELECT
    SUM(covariance_part) AS covariance_numerator,
    SUM(car_squared) AS car_variance_numerator,
    SUM(vol_squared) AS volatility_variance_numerator
FROM components;


-- ============================================================
-- QUERY 2: CAR and GARCH relationship by bank type
-- ============================================================

SELECT
    m.bank_type,
    COUNT(*) AS observations,
    ROUND(AVG(r.absolute_car) * 100, 3)
        AS avg_absolute_car_pct,
    ROUND(AVG(r.garch_volatility) * 100, 3)
        AS avg_garch_volatility_pct
FROM event_risk_analysis r
JOIN bank_metadata m
    ON r.bank_symbol = m.symbol
GROUP BY m.bank_type
ORDER BY avg_absolute_car_pct DESC;


-- ============================================================
-- QUERY 3: CAR and GARCH statistics by bank
-- ============================================================

SELECT
    bank_symbol,
    COUNT(*) AS observations,
    ROUND(AVG(garch_volatility) * 100, 3)
        AS avg_garch_volatility_pct,
    ROUND(AVG(absolute_car) * 100, 3)
        AS avg_absolute_car_pct
FROM event_risk_analysis
GROUP BY bank_symbol
ORDER BY avg_garch_volatility_pct DESC;


-- ============================================================
-- QUERY 4: Compare CAR across GARCH volatility quartiles
-- ============================================================

WITH ranked AS (
    SELECT
        *,
        NTILE(4) OVER (
            ORDER BY garch_volatility
        ) AS volatility_quartile
    FROM event_risk_analysis
)
SELECT
    volatility_quartile,
    COUNT(*) AS observations,
    ROUND(AVG(garch_volatility) * 100, 3)
        AS avg_garch_volatility_pct,
    ROUND(AVG(absolute_car) * 100, 3)
        AS avg_absolute_car_pct
FROM ranked
GROUP BY volatility_quartile
ORDER BY volatility_quartile;