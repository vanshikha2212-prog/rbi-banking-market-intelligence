"""Run RBI event study using Nifty Bank as the market benchmark."""

from pathlib import Path

import numpy as np
import pandas as pd


PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")

EVENT_FILE = RAW_DIR / "rbi_mpc_events_2023_2025.csv"
BANK_FILE = PROCESSED_DIR / "bank_returns_2021_2025.csv"
INDEX_FILE = PROCESSED_DIR / "index_returns_2021_2025.csv"

OUTPUT_FILE = PROCESSED_DIR / "event_study_results_niftybank.csv"

MARKET_SYMBOL = "^NSEBANK"

BANKS = {
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "AXISBANK.NS": "Axis Bank",
    "SBIN.NS": "State Bank of India",
    "BANKBARODA.NS": "Bank of Baroda",
    "CANBK.NS": "Canara Bank",
}


def load_data():
    """Load events, bank returns, and Nifty Bank returns."""

    events = pd.read_csv(
        EVENT_FILE,
        parse_dates=["event_date"],
    )

    banks = pd.read_csv(
        BANK_FILE,
        parse_dates=["date"],
    )

    indices = pd.read_csv(
        INDEX_FILE,
        parse_dates=["date"],
    )

    market = indices[
        indices["symbol"] == MARKET_SYMBOL
    ].copy()

    return events, banks, market


def fit_market_model(
    bank_returns,
    market_returns,
):
    """Estimate alpha and beta using OLS."""

    data = pd.DataFrame(
        {
            "bank_return": bank_returns,
            "market_return": market_returns,
        }
    ).dropna()

    if len(data) < 100:
        raise ValueError(
            "Insufficient observations for estimation."
        )

    x = data["market_return"].to_numpy()
    y = data["bank_return"].to_numpy()

    beta, alpha = np.polyfit(x, y, 1)

    return alpha, beta


def main():
    """Run the Nifty Bank benchmark event study."""

    events, banks, market = load_data()

    results = []

    print(
        f"Processing {len(events)} RBI events "
        f"across {len(BANKS)} banks using Nifty Bank..."
    )

    for _, event in events.iterrows():

        event_id = event["event_id"]
        event_date = event["event_date"]

        for bank_symbol, bank_name in BANKS.items():

            bank = banks[
                banks["symbol"] == bank_symbol
            ].copy()

            merged = pd.merge(
                bank[
                    [
                        "date",
                        "return",
                    ]
                ],
                market[
                    [
                        "date",
                        "return",
                    ]
                ].rename(
                    columns={
                        "return": "market_return"
                    }
                ),
                on="date",
                how="inner",
            ).sort_values("date")

            trading_dates = merged[
                "date"
            ].reset_index(drop=True)

            matching_dates = np.where(
                trading_dates == event_date
            )[0]

            if len(matching_dates) == 0:
                raise ValueError(
                    f"Event date {event_date.date()} "
                    f"not found for {bank_symbol}."
                )

            event_position = matching_dates[0]

            estimation_end = (
                event_position - 6
            )

            estimation_start = (
                estimation_end - 250
            )

            if estimation_start < 0:
                raise ValueError(
                    f"Not enough estimation data "
                    f"for {bank_symbol} "
                    f"around {event_date.date()}."
                )

            estimation = merged.iloc[
                estimation_start:estimation_end
            ]

            alpha, beta = fit_market_model(
                estimation["return"],
                estimation["market_return"],
            )

            event_start = event_position - 5
            event_end = event_position + 5

            event_window = merged.iloc[
                event_start:event_end + 1
            ].copy()

            event_window["expected_return"] = (
                alpha
                + beta
                * event_window["market_return"]
            )

            event_window["abnormal_return"] = (
                event_window["return"]
                - event_window["expected_return"]
            )

            event_window["relative_day"] = (
                np.arange(
                    -5,
                    6,
                )
            )

            car_minus_1_plus_1 = (
                event_window.loc[
                    event_window["relative_day"].between(
                        -1,
                        1,
                    ),
                    "abnormal_return",
                ].sum()
            )

            car_minus_2_plus_2 = (
                event_window.loc[
                    event_window["relative_day"].between(
                        -2,
                        2,
                    ),
                    "abnormal_return",
                ].sum()
            )

            car_minus_5_plus_5 = (
                event_window[
                    "abnormal_return"
                ].sum()
            )

            event_days = event_window[
                event_window["relative_day"].isin(
                    [-1, 0, 1]
                )
            ]

            for _, row in event_days.iterrows():

                results.append(
                    {
                        "event_id": event_id,
                        "event_date": event_date,
                        "decision": event["decision"],
                        "bank_symbol": bank_symbol,
                        "bank_name": bank_name,
                        "bank_type": (
                            "Private"
                            if bank_symbol
                            in {
                                "HDFCBANK.NS",
                                "ICICIBANK.NS",
                                "AXISBANK.NS",
                            }
                            else "Public"
                        ),
                        "relative_day": row[
                            "relative_day"
                        ],
                        "actual_return": row[
                            "return"
                        ],
                        "expected_return": row[
                            "expected_return"
                        ],
                        "abnormal_return": row[
                            "abnormal_return"
                        ],
                        "alpha": alpha,
                        "beta": beta,
                        "car_minus_1_plus_1":
                            car_minus_1_plus_1,
                        "car_minus_2_plus_2":
                            car_minus_2_plus_2,
                        "car_minus_5_plus_5":
                            car_minus_5_plus_5,
                    }
                )

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\n--- NIFTY BANK EVENT STUDY SUMMARY ---")

    print(
        "RBI events:",
        results_df["event_id"].nunique(),
    )

    print(
        "Banks:",
        results_df["bank_symbol"].nunique(),
    )

    print(
        "Event-bank observations:",
        len(
            results_df[
                results_df["relative_day"] == 0
            ]
        ),
    )

    print(
        "Average CAR [-1,+1]:",
        results_df[
            "car_minus_1_plus_1"
        ].mean(),
    )

    print(
        "Average CAR [-2,+2]:",
        results_df[
            "car_minus_2_plus_2"
        ].mean(),
    )

    print(
        "Average CAR [-5,+5]:",
        results_df[
            "car_minus_5_plus_5"
        ].mean(),
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()