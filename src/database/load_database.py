"""Create and populate the RBI market intelligence SQLite database."""

from pathlib import Path
import sqlite3

import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SQL_DIR = ROOT_DIR / "sql"

DATABASE_DIR = ROOT_DIR / "data" / "database"
DATABASE_FILE = DATABASE_DIR / "rbi_market.db"

SCHEMA_FILE = SQL_DIR / "schema.sql"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_csv(filename):
    """Load a CSV file from the processed data directory."""

    return pd.read_csv(
        PROCESSED_DIR / filename
    )


def keep_columns(df, columns, table_name):
    """Keep only columns required by the SQL table."""

    missing = [
        column
        for column in columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{table_name}: missing required columns: "
            f"{missing}"
        )

    return df[columns].copy()


# ============================================================
# MAIN
# ============================================================

def main():
    """Create the database and load project datasets."""

    DATABASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # CONNECT TO DATABASE
    # --------------------------------------------------------

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    cursor = connection.cursor()

    cursor.execute(
        "PRAGMA foreign_keys = ON;"
    )

    # --------------------------------------------------------
    # CREATE TABLES
    # --------------------------------------------------------

    schema = SCHEMA_FILE.read_text()

    cursor.executescript(
        schema
    )

    connection.commit()

    print("\n--- DATABASE CREATED ---")
    print(DATABASE_FILE)

    # ========================================================
    # 1. BANK METADATA
    # ========================================================

    bank_metadata = pd.DataFrame(
        [
            {
                "symbol": "HDFCBANK.NS",
                "bank_name": "HDFC Bank",
                "bank_type": "Private",
            },
            {
                "symbol": "ICICIBANK.NS",
                "bank_name": "ICICI Bank",
                "bank_type": "Private",
            },
            {
                "symbol": "AXISBANK.NS",
                "bank_name": "Axis Bank",
                "bank_type": "Private",
            },
            {
                "symbol": "SBIN.NS",
                "bank_name": "State Bank of India",
                "bank_type": "Public",
            },
            {
                "symbol": "BANKBARODA.NS",
                "bank_name": "Bank of Baroda",
                "bank_type": "Public",
            },
            {
                "symbol": "CANBK.NS",
                "bank_name": "Canara Bank",
                "bank_type": "Public",
            },
        ]
    )

    bank_metadata.to_sql(
        "bank_metadata",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "bank_metadata:",
        len(bank_metadata),
        "rows",
    )

    # ========================================================
    # 2. RBI EVENTS
    # ========================================================

    events = pd.read_csv(
        RAW_DIR
        / "rbi_mpc_events_2023_2025.csv"
    )

    events["meeting_start"] = (
        pd.to_datetime(
            events["meeting_start"]
        ).dt.date
    )

    events["meeting_end"] = (
        pd.to_datetime(
            events["meeting_end"]
        ).dt.date
    )

    events["event_date"] = (
        pd.to_datetime(
            events["event_date"]
        ).dt.date
    )

    events = keep_columns(
        events,
        [
            "event_id",
            "meeting_start",
            "meeting_end",
            "event_date",
            "repo_before",
            "repo_after",
            "rate_change_bps",
            "decision",
            "stance",
            "source_url",
            "notes",
        ],
        "rbi_events",
    )

    events.to_sql(
        "rbi_events",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "rbi_events:",
        len(events),
        "rows",
    )

    # ========================================================
    # 3. BANK STOCK PRICES
    # ========================================================

    bank_prices = pd.read_csv(
        RAW_DIR
        / "bank_prices_2021_2025.csv"
    )

    bank_prices["date"] = (
        pd.to_datetime(
            bank_prices["date"]
        ).dt.date
    )

    bank_prices = keep_columns(
        bank_prices,
        [
            "date",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
        "stock_prices",
    )

    bank_prices.to_sql(
        "stock_prices",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "stock_prices:",
        len(bank_prices),
        "rows",
    )

    # ========================================================
    # 4. MARKET INDEX PRICES
    # ========================================================

    index_prices = pd.read_csv(
        RAW_DIR
        / "index_prices_2021_2025.csv"
    )

    index_prices["date"] = (
        pd.to_datetime(
            index_prices["date"]
        ).dt.date
    )

    index_prices = index_prices.rename(
        columns={
            "symbol": "index_name"
        }
    )

    index_prices = keep_columns(
        index_prices,
        [
            "date",
            "index_name",
            "open",
            "high",
            "low",
            "close",
        ],
        "market_indices",
    )

    index_prices.to_sql(
        "market_indices",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "market_indices:",
        len(index_prices),
        "rows",
    )

    # ========================================================
    # 5. BANK RETURNS
    # ========================================================

    bank_returns = load_csv(
        "bank_returns_2021_2025.csv"
    )

    bank_returns["date"] = (
        pd.to_datetime(
            bank_returns["date"]
        ).dt.date
    )

    bank_returns = keep_columns(
        bank_returns,
        [
            "date",
            "symbol",
            "return",
        ],
        "bank_returns",
    )

    bank_returns.to_sql(
        "bank_returns",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "bank_returns:",
        len(bank_returns),
        "rows",
    )

    # ========================================================
    # 6. INDEX RETURNS
    # ========================================================

    index_returns = load_csv(
        "index_returns_2021_2025.csv"
    )

    index_returns["date"] = (
        pd.to_datetime(
            index_returns["date"]
        ).dt.date
    )

    index_returns = keep_columns(
        index_returns,
        [
            "date",
            "symbol",
            "return",
        ],
        "index_returns",
    )

    index_returns.to_sql(
        "index_returns",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "index_returns:",
        len(index_returns),
        "rows",
    )

    # ========================================================
    # 7. EVENT STUDY RESULTS
    # ========================================================

    event_study = load_csv(
        "event_study_results.csv"
    )

    event_study["event_date"] = (
        pd.to_datetime(
            event_study["event_date"]
        ).dt.date
    )

    # Add bank type from bank metadata.
    bank_type_map = dict(
        zip(
            bank_metadata["symbol"],
            bank_metadata["bank_type"],
        )
    )

    event_study["bank_type"] = (
        event_study["bank_symbol"]
        .map(bank_type_map)
    )

    if event_study["bank_type"].isna().any():
        raise ValueError(
            "event_study_results: "
            "bank_type could not be assigned "
            "to one or more bank symbols."
        )

    # Rename abnormal-return columns.
    event_study = event_study.rename(
        columns={
            "ar_-1": "ar_minus_1",
            "ar_1": "ar_plus_1",
        }
    )

    event_study = keep_columns(
        event_study,
        [
            "event_id",
            "event_date",
            "bank_symbol",
            "bank_type",
            "alpha",
            "beta",
            "car_minus_1_plus_1",
            "car_minus_2_plus_2",
            "car_minus_5_plus_5",
            "ar_minus_1",
            "ar_0",
            "ar_plus_1",
        ],
        "event_study_results",
    )

    event_study.to_sql(
        "event_study_results",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "event_study_results:",
        len(event_study),
        "rows",
    )

    # ========================================================
    # 8. GARCH FORECASTS
    # ========================================================

    garch = load_csv(
        "garch_forecasts.csv"
    )

    garch["date"] = (
        pd.to_datetime(
            garch["date"]
        ).dt.date
    )

    garch = keep_columns(
        garch,
        [
            "date",
            "symbol",
            "garch_volatility_forecast",
        ],
        "garch_forecasts",
    )

    garch.to_sql(
        "garch_forecasts",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "garch_forecasts:",
        len(garch),
        "rows",
    )

    # ========================================================
    # 9. EVENT RISK ANALYSIS
    # ========================================================

    risk_analysis = load_csv(
        "event_risk_analysis.csv"
    )

    risk_analysis["event_date"] = (
        pd.to_datetime(
            risk_analysis["event_date"]
        ).dt.date
    )

    risk_analysis = keep_columns(
        risk_analysis,
        [
            "event_id",
            "event_date",
            "bank_symbol",
            "car",
            "absolute_car",
            "garch_volatility",
        ],
        "event_risk_analysis",
    )

    risk_analysis.to_sql(
        "event_risk_analysis",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "event_risk_analysis:",
        len(risk_analysis),
        "rows",
    )

    # ========================================================
    # 10. EVENT RISK BUCKETS
    # ========================================================

    risk_buckets = load_csv(
        "event_risk_buckets.csv"
    )

    risk_buckets["event_date"] = (
        pd.to_datetime(
            risk_buckets["event_date"]
        ).dt.date
    )

    risk_buckets = keep_columns(
        risk_buckets,
        [
            "event_id",
            "event_date",
            "bank_symbol",
            "car",
            "absolute_car",
            "garch_volatility",
            "risk_level",
        ],
        "event_risk_buckets",
    )

    risk_buckets.to_sql(
        "event_risk_buckets",
        connection,
        if_exists="append",
        index=False,
    )

    print(
        "event_risk_buckets:",
        len(risk_buckets),
        "rows",
    )

    # ========================================================
    # CLOSE DATABASE
    # ========================================================

    connection.close()

    print(
        "\n--- DATABASE LOAD COMPLETE ---"
    )

    print(
        "Database:",
        DATABASE_FILE,
    )


if __name__ == "__main__":
    main()