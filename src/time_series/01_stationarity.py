"""Test stationarity of banking stock and market return series."""

from pathlib import Path

import pandas as pd
from statsmodels.tsa.stattools import adfuller


PROCESSED_DIR = Path("data/processed")

BANK_FILE = (
    PROCESSED_DIR / "bank_returns_2021_2025.csv"
)

INDEX_FILE = (
    PROCESSED_DIR / "index_returns_2021_2025.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "stationarity_results.csv"
)


BANKS = [
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "AXISBANK.NS",
    "SBIN.NS",
    "BANKBARODA.NS",
    "CANBK.NS",
]

INDICES = [
    "^NSEI",
    "^NSEBANK",
]


def adf_test(series):
    """Run Augmented Dickey-Fuller test."""

    series = series.dropna()

    result = adfuller(
        series,
        autolag="AIC",
    )

    return {
        "adf_statistic": result[0],
        "p_value": result[1],
        "used_lags": result[2],
        "observations": result[3],
        "critical_1pct": result[4]["1%"],
        "critical_5pct": result[4]["5%"],
        "critical_10pct": result[4]["10%"],
    }


def main():
    """Run stationarity tests."""

    banks = pd.read_csv(
        BANK_FILE,
        parse_dates=["date"],
    )

    indices = pd.read_csv(
        INDEX_FILE,
        parse_dates=["date"],
    )

    rows = []

    for symbol in BANKS:

        data = banks[
            banks["symbol"] == symbol
        ]

        result = adf_test(
            data["return"]
        )

        rows.append(
            {
                "symbol": symbol,
                "asset_type": "Bank",
                **result,
            }
        )

    for symbol in INDICES:

        data = indices[
            indices["symbol"] == symbol
        ]

        result = adf_test(
            data["return"]
        )

        rows.append(
            {
                "symbol": symbol,
                "asset_type": "Index",
                **result,
            }
        )

    output = pd.DataFrame(rows)

    output["stationary_at_5pct"] = (
        output["p_value"] < 0.05
    )

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\n--- STATIONARITY TEST RESULTS ---")

    print(
        output.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()