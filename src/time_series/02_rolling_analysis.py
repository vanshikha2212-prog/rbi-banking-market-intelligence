"""Calculate rolling return and volatility measures."""

from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")

BANK_FILE = (
    PROCESSED_DIR / "bank_returns_2021_2025.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "rolling_statistics.csv"
)


WINDOWS = [20, 60]


def main():
    """Calculate rolling statistics."""

    data = pd.read_csv(
        BANK_FILE,
        parse_dates=["date"],
    )

    data = data.sort_values(
        ["symbol", "date"]
    )

    results = []

    for symbol, group in data.groupby(
        "symbol"
    ):

        group = group.copy()

        for window in WINDOWS:

            group[
                f"rolling_mean_{window}"
            ] = (
                group["return"]
                .rolling(window)
                .mean()
            )

            group[
                f"rolling_volatility_{window}"
            ] = (
                group["return"]
                .rolling(window)
                .std()
            )

        results.append(group)

    output = pd.concat(
        results,
        ignore_index=True,
    )

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(
        "\n--- ROLLING STATISTICS ---"
    )

    print(
        output[
            [
                "symbol",
                "date",
                "return",
                "rolling_mean_20",
                "rolling_volatility_20",
                "rolling_mean_60",
                "rolling_volatility_60",
            ]
        ].tail(10).to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()