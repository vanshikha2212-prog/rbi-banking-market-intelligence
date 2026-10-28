"""Analyze volatility clustering in banking returns."""

from pathlib import Path

import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox


PROCESSED_DIR = Path("data/processed")

BANK_FILE = (
    PROCESSED_DIR / "bank_returns_2021_2025.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "volatility_clustering.csv"
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
    """Test autocorrelation in squared returns."""

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

        squared_returns = (
            series ** 2
        )

        result = acorr_ljungbox(
            squared_returns,
            lags=[5, 10, 20],
            return_df=True,
        )

        for lag in result.index:

            rows.append(
                {
                    "symbol": symbol,
                    "lag": lag,
                    "ljung_box_statistic":
                        result.loc[
                            lag,
                            "lb_stat",
                        ],
                    "p_value":
                        result.loc[
                            lag,
                            "lb_pvalue",
                        ],
                }
            )

    output = pd.DataFrame(rows)

    output["significant_at_5pct"] = (
        output["p_value"] < 0.05
    )

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(
        "\n--- VOLATILITY CLUSTERING ---"
    )

    print(
        output.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()