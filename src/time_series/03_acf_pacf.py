"""Calculate ACF and PACF for banking return series."""

from pathlib import Path

import pandas as pd
from statsmodels.tsa.stattools import acf, pacf


PROCESSED_DIR = Path("data/processed")

BANK_FILE = (
    PROCESSED_DIR / "bank_returns_2021_2025.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "acf_pacf_results.csv"
)


BANKS = [
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "AXISBANK.NS",
    "SBIN.NS",
    "BANKBARODA.NS",
    "CANBK.NS",
]


def main():
    """Calculate autocorrelation statistics."""

    data = pd.read_csv(
        BANK_FILE,
        parse_dates=["date"],
    )

    rows = []

    for symbol in BANKS:

        series = (
            data[
                data["symbol"] == symbol
            ]["return"]
            .dropna()
        )

        acf_values = acf(
            series,
            nlags=10,
            fft=True,
        )

        pacf_values = pacf(
            series,
            nlags=10,
            method="ywm",
        )

        for lag in range(1, 11):

            rows.append(
                {
                    "symbol": symbol,
                    "lag": lag,
                    "acf": acf_values[lag],
                    "pacf": pacf_values[lag],
                }
            )

    output = pd.DataFrame(rows)

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\n--- ACF / PACF RESULTS ---")

    print(
        output.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()