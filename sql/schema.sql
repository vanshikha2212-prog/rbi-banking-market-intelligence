-- ============================================================
-- RBI POLICY IMPACT & BANKING MARKET INTELLIGENCE SYSTEM
-- Database Schema
-- ============================================================


-- ============================================================
-- 1. RBI MONETARY POLICY EVENTS
-- ============================================================

CREATE TABLE rbi_events (
    event_id TEXT PRIMARY KEY,
    meeting_start DATE NOT NULL,
    meeting_end DATE NOT NULL,
    event_date DATE NOT NULL,
    repo_before NUMERIC NOT NULL,
    repo_after NUMERIC NOT NULL,
    rate_change_bps INTEGER NOT NULL,
    decision TEXT NOT NULL,
    stance TEXT,
    source_url TEXT,
    notes TEXT
);


-- ============================================================
-- 2. BANK METADATA
-- ============================================================

CREATE TABLE bank_metadata (
    symbol TEXT PRIMARY KEY,
    bank_name TEXT NOT NULL,
    bank_type TEXT NOT NULL
);


-- ============================================================
-- 3. BANK STOCK PRICES
-- ============================================================

CREATE TABLE stock_prices (
    date DATE NOT NULL,
    symbol TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    PRIMARY KEY (date, symbol),
    FOREIGN KEY (symbol)
        REFERENCES bank_metadata(symbol)
);


-- ============================================================
-- 4. MARKET INDEX PRICES
-- ============================================================

CREATE TABLE market_indices (
    date DATE NOT NULL,
    index_name TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    PRIMARY KEY (date, index_name)
);


-- ============================================================
-- 5. BANK RETURNS
-- ============================================================

CREATE TABLE bank_returns (
    date DATE NOT NULL,
    symbol TEXT NOT NULL,
    return NUMERIC,
    PRIMARY KEY (date, symbol),
    FOREIGN KEY (symbol)
        REFERENCES bank_metadata(symbol)
);


-- ============================================================
-- 6. INDEX RETURNS
-- ============================================================

CREATE TABLE index_returns (
    date DATE NOT NULL,
    symbol TEXT NOT NULL,
    return NUMERIC,
    PRIMARY KEY (date, symbol)
);


-- ============================================================
-- 7. EVENT STUDY RESULTS
-- ============================================================

CREATE TABLE event_study_results (
    event_id TEXT NOT NULL,
    event_date DATE NOT NULL,
    bank_symbol TEXT NOT NULL,
    bank_type TEXT NOT NULL,

    alpha NUMERIC,
    beta NUMERIC,

    car_minus_1_plus_1 NUMERIC,
    car_minus_2_plus_2 NUMERIC,
    car_minus_5_plus_5 NUMERIC,

    ar_minus_1 NUMERIC,
    ar_0 NUMERIC,
    ar_plus_1 NUMERIC,

    PRIMARY KEY (event_id, bank_symbol),

    FOREIGN KEY (event_id)
        REFERENCES rbi_events(event_id),

    FOREIGN KEY (bank_symbol)
        REFERENCES bank_metadata(symbol)
);


-- ============================================================
-- 8. GARCH VOLATILITY FORECASTS
-- ============================================================

CREATE TABLE garch_forecasts (
    date DATE NOT NULL,
    symbol TEXT NOT NULL,
    garch_volatility_forecast NUMERIC,

    PRIMARY KEY (date, symbol),

    FOREIGN KEY (symbol)
        REFERENCES bank_metadata(symbol)
);


-- ============================================================
-- 9. EVENT RISK ANALYSIS
-- ============================================================

CREATE TABLE event_risk_analysis (
    event_id TEXT NOT NULL,
    event_date DATE NOT NULL,
    bank_symbol TEXT NOT NULL,

    car NUMERIC,
    absolute_car NUMERIC,
    garch_volatility NUMERIC,

    PRIMARY KEY (event_id, bank_symbol),

    FOREIGN KEY (event_id)
        REFERENCES rbi_events(event_id),

    FOREIGN KEY (bank_symbol)
        REFERENCES bank_metadata(symbol)
);


-- ============================================================
-- 10. EVENT RISK BUCKETS
-- ============================================================

CREATE TABLE event_risk_buckets (
    event_id TEXT NOT NULL,
    event_date DATE NOT NULL,
    bank_symbol TEXT NOT NULL,

    car NUMERIC,
    absolute_car NUMERIC,
    garch_volatility NUMERIC,
    risk_level TEXT NOT NULL,

    PRIMARY KEY (event_id, bank_symbol),

    FOREIGN KEY (event_id)
        REFERENCES rbi_events(event_id),

    FOREIGN KEY (bank_symbol)
        REFERENCES bank_metadata(symbol)
);