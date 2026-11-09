-- Schema used by rbi_intelligence.database.build_database.
-- Use the Python builder for atomic validated builds; this is the schema reference.
PRAGMA foreign_keys = ON;

CREATE TABLE run_metadata (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
CREATE TABLE rbi_events (
    event_id TEXT PRIMARY KEY,
    event_date TEXT NOT NULL UNIQUE,
    decision TEXT NOT NULL CHECK (decision IN ('Cut', 'Hold', 'Hike')),
    repo_before REAL,
    repo_after REAL,
    rate_change_bps REAL,
    stance TEXT,
    source_url TEXT,
    details_json TEXT NOT NULL
);
CREATE TABLE bank_metadata (
    bank_symbol TEXT PRIMARY KEY,
    bank_name TEXT NOT NULL,
    bank_type TEXT NOT NULL
);
CREATE TABLE event_study_results (
    event_id TEXT NOT NULL REFERENCES rbi_events(event_id),
    bank_symbol TEXT NOT NULL REFERENCES bank_metadata(bank_symbol),
    benchmark TEXT NOT NULL,
    window TEXT NOT NULL,
    car REAL NOT NULL,
    absolute_car REAL NOT NULL CHECK (absolute_car >= 0),
    alpha REAL,
    beta REAL,
    estimation_start TEXT,
    estimation_end TEXT,
    n_estimation INTEGER CHECK (n_estimation > 0),
    n_event INTEGER CHECK (n_event > 0),
    details_json TEXT NOT NULL,
    PRIMARY KEY (event_id, bank_symbol, benchmark, window)
);
CREATE TABLE volatility_forecasts (
    event_id TEXT NOT NULL REFERENCES rbi_events(event_id),
    bank_symbol TEXT NOT NULL REFERENCES bank_metadata(bank_symbol),
    forecast_origin_date TEXT NOT NULL,
    forecast_target_date TEXT NOT NULL,
    garch_variance REAL CHECK (garch_variance >= 0),
    garch_volatility REAL CHECK (garch_volatility >= 0),
    rolling_variance REAL CHECK (rolling_variance >= 0),
    rolling_volatility REAL CHECK (rolling_volatility >= 0),
    n_training INTEGER CHECK (n_training > 0),
    convergence_flag INTEGER,
    converged INTEGER NOT NULL CHECK (converged IN (0, 1)),
    risk_level TEXT,
    status TEXT,
    details_json TEXT NOT NULL,
    PRIMARY KEY (event_id, bank_symbol),
    CHECK (forecast_origin_date < forecast_target_date)
);
CREATE TABLE market_data (
    date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT,
    close REAL,
    adj_close REAL,
    return REAL,
    adj_return REAL,
    details_json TEXT NOT NULL,
    PRIMARY KEY (date, symbol)
);
CREATE INDEX event_results_slice ON event_study_results(benchmark, window);
CREATE VIEW event_explorer AS
SELECT r.event_id, e.event_date, e.decision, e.rate_change_bps,
       b.bank_symbol, b.bank_name, b.bank_type, r.benchmark, r.window,
       r.car, r.absolute_car, r.alpha, r.beta,
       r.estimation_start, r.estimation_end, r.n_estimation, r.n_event,
       v.forecast_origin_date, v.forecast_target_date,
       v.garch_volatility, v.rolling_volatility, v.converged, v.risk_level
FROM event_study_results r
JOIN rbi_events e ON e.event_id = r.event_id
JOIN bank_metadata b ON b.bank_symbol = r.bank_symbol
LEFT JOIN volatility_forecasts v
  ON v.event_id = r.event_id AND v.bank_symbol = r.bank_symbol;
