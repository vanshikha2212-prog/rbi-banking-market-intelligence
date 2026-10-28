"""Build a leakage-safe dataset for RBI event prediction."""

from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")

EVENT_FILE = RAW_DIR / "rbi_mpc_events_2023_2025.csv"
EVENT_STUDY_FILE = (
    PROCESSED_DIR / "event_study_results.csv"
)
BANK_FILE = (
    PROCESSED_DIR / "bank_returns_2021_2025.csv"
)
GARCH_FILE = (
    PROCESSED_DIR / "garch_forecasts.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "predictive_features.csv"
)


BANKS = {
    "HDFCBANK.NS": "Private",
    "ICICIBANK.NS": "Private",
    "AXISBANK.NS": "Private",
    "SBIN.NS": "Public",
    "BANKBARODA.NS": "Public",
    "CANBK.NS": "Public",
}


def load_data():
    """Load all required datasets."""

    events = pd.read_csv(
        EVENT_FILE,
        parse_dates=["event_date"],
    )

    event_study = pd.read_csv(
        EVENT_STUDY_FILE,
        parse_dates=["event_date"],
    )

    returns = pd.read_csv(
        BANK_FILE,
        parse_dates=["date"],
    )

    garch = pd.read_csv(
        GARCH_FILE,
        parse_dates=["date"],
    )

    return events, event_study, returns, garch


def calculate_pre_event_features(
    bank_returns,
    event_date,
):
    """Calculate features using only information before the event."""

    bank_returns = (
        bank_returns
        .sort_values("date")
        .copy()
    )

    pre_event = bank_returns[
        bank_returns["date"] < event_date
    ].copy()

    if len(pre_event) < 60:
        return None

    recent_5 = pre_event.tail(5)
    recent_20 = pre_event.tail(20)
    recent_60 = pre_event.tail(60)

    return {
        "return_1d": pre_event["return"].iloc[-1],
        "return_5d": recent_5["return"].sum(),
        "return_20d": recent_20["return"].sum(),
        "volatility_20d": (
            recent_20["return"].std()
        ),
        "volatility_60d": (
            recent_60["return"].std()
        ),
    }


def get_garch_feature(
    garch,
    bank_symbol,
    event_date,
):
    """Get the latest GARCH forecast available before the event."""

    available = garch[
        (garch["symbol"] == bank_symbol)
        & (garch["date"] < event_date)
    ].sort_values("date")

    if available.empty:
        return None

    return available[
        "garch_volatility_forecast"
    ].iloc[-1]


def main():
    """Build the predictive dataset."""

    (
        events,
        event_study,
        returns,
        garch,
    ) = load_data()

    # Keep exactly one CAR observation
    # per bank-event.
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

    for _, event in events.iterrows():

        event_id = event["event_id"]
        event_date = event["event_date"]

        for bank_symbol, bank_type in BANKS.items():

            features = calculate_pre_event_features(
                returns[
                    returns["symbol"]
                    == bank_symbol
                ],
                event_date,
            )

            if features is None:
                continue

            garch_volatility = (
                get_garch_feature(
                    garch,
                    bank_symbol,
                    event_date,
                )
            )

            if garch_volatility is None:
                continue

            car_row = event_study[
                (event_study["event_id"] == event_id)
                & (
                    event_study["bank_symbol"]
                    == bank_symbol
                )
            ]

            if car_row.empty:
                continue

            car = car_row[
                "car_minus_1_plus_1"
            ].iloc[0]

            rows.append(
                {
                    "event_id": event_id,
                    "event_date": event_date,
                    "bank_symbol": bank_symbol,
                    "bank_type": bank_type,

                    # Policy feature
                    "decision": event["decision"],

                    # Pre-event market features
                    **features,

                    # Forward-looking volatility
                    "garch_volatility":
                        garch_volatility,

                    # Prediction target
                    "car_minus_1_plus_1": car,
                    "positive_car": int(car > 0),
                }
            )

    output = pd.DataFrame(rows)

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(
        "\n--- PREDICTIVE DATASET ---"
    )

    print(
        "Rows:",
        len(output),
    )

    print(
        "Columns:",
        len(output.columns),
    )

    print(
        "\nTarget distribution:"
    )

    print(
        output["positive_car"]
        .value_counts()
        .sort_index()
    )

    print(
        "\nPreview:"
    )

    print(
        output.head(10).to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()