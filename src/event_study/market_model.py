"""Run the market-model event study for RBI monetary-policy events."""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

EVENT_FILE = RAW_DIR / "rbi_mpc_events_2023_2025.csv"
BANK_RETURNS_FILE = PROCESSED_DIR / "bank_returns_2021_2025.csv"
INDEX_RETURNS_FILE = PROCESSED_DIR / "index_returns_2021_2025.csv"

OUTPUT_FILE = PROCESSED_DIR / "event_study_results.csv"

ESTIMATION_DAYS = 250

EVENT_WINDOWS = {
    "minus_1_plus_1": (-1, 1),
    "minus_2_plus_2": (-2, 2),
    "minus_5_plus_5": (-5, 5),
}


def load_data():
    """Load RBI events and return datasets."""

    events = pd.read_csv(
        EVENT_FILE,
        parse_dates=["event_date"],
    )

    banks = pd.read_csv(
        BANK_RETURNS_FILE,
        parse_dates=["date"],
    )

    indices = pd.read_csv(
        INDEX_RETURNS_FILE,
        parse_dates=["date"],
    )

    return events, banks, indices


def prepare_market_data(banks, indices):
    """Merge bank returns with Nifty 50 market returns."""

    market = indices[
        indices["symbol"] == "^NSEI"
    ][["date", "return"]].copy()

    market = market.rename(
        columns={"return": "market_return"}
    )

    banks = banks[
        [
            "date",
            "symbol",
            "name",
            "return",
        ]
    ].copy()

    merged = banks.merge(
        market,
        on="date",
        how="inner",
    )

    return merged.sort_values(
        ["symbol", "date"]
    ).reset_index(drop=True)


def get_trading_dates(data):
    """Return sorted unique trading dates."""

    return (
        data["date"]
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )


def get_event_dates(
    trading_dates,
    event_date,
    start_day,
    end_day,
):
    """
    Convert relative event days into actual trading dates.

    Example:
        -1 = previous trading day
         0 = event trading day
        +1 = next trading day
    """

    trading_dates = pd.Series(trading_dates)

    matching = trading_dates[
        trading_dates == event_date
    ]

    if matching.empty:
        raise ValueError(
            f"Event date {event_date.date()} is not a trading day."
        )

    event_position = matching.index[0]

    start_position = event_position + start_day
    end_position = event_position + end_day

    if start_position < 0:
        raise ValueError(
            f"Not enough trading history before "
            f"{event_date.date()}."
        )

    if end_position >= len(trading_dates):
        raise ValueError(
            f"Not enough trading history after "
            f"{event_date.date()}."
        )

    selected = trading_dates.iloc[
        start_position:end_position + 1
    ]

    return selected.tolist(), event_position


def estimate_market_model(estimation_data):
    """Estimate alpha and beta using OLS."""

    estimation_data = estimation_data.dropna(
        subset=["return", "market_return"]
    )

    if len(estimation_data) < ESTIMATION_DAYS:
        raise ValueError(
            "Insufficient observations for market-model estimation."
        )

    X = sm.add_constant(
        estimation_data["market_return"]
    )

    y = estimation_data["return"]

    model = sm.OLS(y, X).fit()

    alpha = model.params["const"]
    beta = model.params["market_return"]

    return alpha, beta


def calculate_event_result(
    data,
    event_date,
    bank_symbol,
    event_id,
    decision,
    stance,
):
    """Calculate AR and CAR for one bank around one RBI event."""

    bank_data = data[
        data["symbol"] == bank_symbol
    ].copy()

    bank_data = bank_data.sort_values(
        "date"
    ).reset_index(drop=True)

    trading_dates = get_trading_dates(
        bank_data
    )

    # We use the widest window so all requested
    # event windows can be calculated from it.
    event_dates, event_position = get_event_dates(
        trading_dates,
        event_date,
        -5,
        5,
    )

    # Exclude the event period and the immediate
    # buffer before it from the estimation sample.
    estimation_end_position = (
        event_position - 6
    )

    estimation_start_position = (
        estimation_end_position
        - ESTIMATION_DAYS
        + 1
    )

    if estimation_start_position < 0:
        raise ValueError(
            f"Insufficient estimation history for "
            f"{bank_symbol} on "
            f"{event_date.date()}."
        )

    estimation_dates = trading_dates.iloc[
        estimation_start_position:
        estimation_end_position + 1
    ]

    estimation_data = bank_data[
        bank_data["date"].isin(
            estimation_dates
        )
    ].copy()

    alpha, beta = estimate_market_model(
        estimation_data
    )

    event_data = bank_data[
        bank_data["date"].isin(
            event_dates
        )
    ].copy()

    event_data["expected_return"] = (
        alpha
        + beta * event_data["market_return"]
    )

    event_data["abnormal_return"] = (
        event_data["return"]
        - event_data["expected_return"]
    )

    relative_day_map = {
        date: position - event_position
        for position, date in enumerate(
            trading_dates
        )
    }

    event_data["relative_day"] = (
        event_data["date"]
        .map(relative_day_map)
    )

    result = {
        "event_id": event_id,
        "event_date": event_date,
        "bank_symbol": bank_symbol,
        "decision": decision,
        "stance": stance,
        "alpha": alpha,
        "beta": beta,
    }

    for window_name, (
        start_day,
        end_day,
    ) in EVENT_WINDOWS.items():

        window_data = event_data[
            event_data["relative_day"].between(
                start_day,
                end_day,
            )
        ]

        result[
            f"car_{window_name}"
        ] = window_data[
            "abnormal_return"
        ].sum()

    for relative_day in [-1, 0, 1]:

        day_data = event_data[
            event_data["relative_day"]
            == relative_day
        ]

        if day_data.empty:
            result[
                f"ar_{relative_day}"
            ] = np.nan
        else:
            result[
                f"ar_{relative_day}"
            ] = day_data[
                "abnormal_return"
            ].iloc[0]

    return result


def main():
    """Run the complete event study."""

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    events, banks, indices = load_data()

    data = prepare_market_data(
        banks,
        indices,
    )

    results = []

    bank_symbols = sorted(
        data["symbol"].unique()
    )

    print(
        f"Processing {len(events)} RBI events "
        f"across {len(bank_symbols)} banks..."
    )

    for _, event in events.iterrows():

        for bank_symbol in bank_symbols:

            result = calculate_event_result(
                data=data,
                event_date=event["event_date"],
                bank_symbol=bank_symbol,
                event_id=event["event_id"],
                decision=event["decision"],
                stance=event["stance"],
            )

            results.append(result)

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\n--- EVENT STUDY SUMMARY ---")
    print("RBI events:", len(events))
    print("Banks:", len(bank_symbols))
    print(
        "Event-bank observations:",
        len(results_df),
    )

    print("\nAverage CAR:")
    print(
        results_df[
            "car_minus_1_plus_1"
        ].mean()
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