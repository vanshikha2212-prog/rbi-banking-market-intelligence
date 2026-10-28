from pathlib import Path
import sqlite3
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]

DATABASE_FILE = (
    ROOT_DIR
    / "data"
    / "database"
    / "rbi_market.db"
)

OUTPUT_DIR = (
    ROOT_DIR
    / "tableau"
    / "exports"
)


QUERIES = {

    "event_explorer.csv": """
        SELECT
            es.event_id,
            es.event_date,
            e.decision,
            e.rate_change_bps,
            e.stance,
            es.bank_symbol,
            es.bank_type,
            es.car_minus_1_plus_1,
            es.car_minus_2_plus_2,
            es.car_minus_5_plus_5
        FROM event_study_results es
        JOIN rbi_events e
            ON es.event_id = e.event_id
        ORDER BY es.event_date, es.bank_symbol;
    """,

    "bank_performance.csv": """
        SELECT
            bank_symbol,
            bank_type,
            COUNT(*) AS event_count,
            AVG(car_minus_1_plus_1) AS avg_car_1d,
            AVG(car_minus_2_plus_2) AS avg_car_5d,
            AVG(car_minus_5_plus_5) AS avg_car_11d
        FROM event_study_results
        GROUP BY bank_symbol, bank_type;
    """,

    "risk_analysis.csv": """
        SELECT
            erb.event_id,
            erb.event_date,
            erb.bank_symbol,
            bm.bank_name,
            bm.bank_type,
            erb.car,
            erb.absolute_car,
            erb.garch_volatility,
            erb.risk_level
        FROM event_risk_buckets erb
        JOIN bank_metadata bm
            ON erb.bank_symbol = bm.symbol
        ORDER BY erb.event_date, erb.bank_symbol;
    """,

    "garch_summary.csv": """
        SELECT
            gf.symbol,
            bm.bank_name,
            bm.bank_type,
            AVG(gf.garch_volatility_forecast)
                AS avg_garch_volatility,
            MAX(gf.garch_volatility_forecast)
                AS max_garch_volatility
        FROM garch_forecasts gf
        JOIN bank_metadata bm
            ON gf.symbol = bm.symbol
        GROUP BY
            gf.symbol,
            bm.bank_name,
            bm.bank_type;
    """
}


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    for filename, query in QUERIES.items():

        df = pd.read_sql_query(
            query,
            connection
        )

        output_file = OUTPUT_DIR / filename

        df.to_csv(
            output_file,
            index=False
        )

        print(
            f"{filename}: {len(df)} rows"
        )

    connection.close()

    print("\n--- TABLEAU EXPORT COMPLETE ---")
    print(OUTPUT_DIR)


if __name__ == "__main__":
    main()