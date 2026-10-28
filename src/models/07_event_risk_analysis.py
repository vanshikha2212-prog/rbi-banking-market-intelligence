"""Analyze volatility and abnormal-return risk around RBI events."""

from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")

EVENT_STUDY_FILE = (
    PROCESSED_DIR / "event_study_results.csv"
)

GARCH_FILE = (
    PROCESSED_DIR / "garch_forecasts.csv"
)


def main():
    """Combine event-study and volatility information."""

    event_study = pd.read_csv(
        EVENT_STUDY_FILE,
        parse_dates=["event_date"],
    )

    garch = pd.read_csv(
        GARCH_FILE,
        parse_dates=["date"],
    )

    # Keep one observation per bank-event.
    event_study = (
        event_study
        .drop_duplicates(
            subset=[
                "event_id",
                "bank_symbol",
            ]
        )
    )

    rows = []

    for _, event in event_study.iterrows():

        bank_symbol = event["bank_symbol"]
        event_date = event["event_date"]

        available = garch[
            (garch["symbol"] == bank_symbol)
            & (garch["date"] < event_date)
        ].sort_values("date")

        if available.empty:
            continue

        latest_forecast = (
            available[
                "garch_volatility_forecast"
            ].iloc[-1]
        )

        rows.append(
            {
                "event_id":
                    event["event_id"],

                "event_date":
                    event_date,

                "bank_symbol":
                    bank_symbol,

                "car":
                    event["car_minus_1_plus_1"],

                "absolute_car":
                    abs(
                        event[
                            "car_minus_1_plus_1"
                        ]
                    ),

                "garch_volatility":
                    latest_forecast,
            }
        )

    output = pd.DataFrame(rows)

    print(
        "\n--- EVENT RISK ANALYSIS ---"
    )

    print(
        "Observations:",
        len(output),
    )

    print(
        "\nAverage absolute CAR:",
        round(
            output["absolute_car"].mean(),
            6,
        ),
    )

    print(
        "Average GARCH volatility:",
        round(
            output["garch_volatility"].mean(),
            6,
        ),
    )

    print(
        "\nHighest-risk observations:"
    )

    print(
        output
        .sort_values(
            "garch_volatility",
            ascending=False,
        )
        .head(10)
        .to_string(
            index=False
        )
    )

    output_file = (
        PROCESSED_DIR
        / "event_risk_analysis.csv"
    )

    output.to_csv(
        output_file,
        index=False,
    )

    print("\nSaved:")
    print(output_file)


if __name__ == "__main__":
    main()