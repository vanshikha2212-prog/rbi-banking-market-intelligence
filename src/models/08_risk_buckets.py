"""Create data-driven RBI event risk buckets."""

from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")

INPUT_FILE = (
    PROCESSED_DIR / "event_risk_analysis.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "event_risk_buckets.csv"
)


def main():
    """Create volatility-based risk categories."""

    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )

    # Calculate volatility quartiles.
    q1 = df[
        "garch_volatility"
    ].quantile(0.25)

    q2 = df[
        "garch_volatility"
    ].quantile(0.50)

    q3 = df[
        "garch_volatility"
    ].quantile(0.75)

    def classify_risk(volatility):

        if volatility <= q1:
            return "Low"

        if volatility <= q2:
            return "Medium"

        if volatility <= q3:
            return "High"

        return "Very High"

    df["risk_level"] = (
        df["garch_volatility"]
        .apply(classify_risk)
    )

    print("\n--- RISK THRESHOLDS ---")

    print(
        "Low / Medium threshold:",
        round(q1, 6),
    )

    print(
        "Medium / High threshold:",
        round(q2, 6),
    )

    print(
        "High / Very High threshold:",
        round(q3, 6),
    )

    print("\n--- RISK DISTRIBUTION ---")

    print(
        df["risk_level"]
        .value_counts()
        .sort_index()
    )

    print("\n--- HIGHEST-RISK EVENTS ---")

    print(
        df[
            df["risk_level"]
            == "Very High"
        ]
        .sort_values(
            "garch_volatility",
            ascending=False,
        )
        .head(15)
        .to_string(
            index=False
        )
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()