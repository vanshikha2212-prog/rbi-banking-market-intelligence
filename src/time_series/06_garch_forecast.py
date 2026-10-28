"""Generate expanding-window one-day-ahead GARCH volatility forecasts."""

from pathlib import Path

import numpy as np
import pandas as pd
from arch import arch_model


PROCESSED_DIR = Path("data/processed")

BANK_FILE = (
    PROCESSED_DIR / "bank_returns_2021_2025.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "garch_forecasts.csv"
)

BANKS = [
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "AXISBANK.NS",
    "SBIN.NS",
    "BANKBARODA.NS",
    "CANBK.NS",
]

MIN_TRAINING_OBS = 500


def forecast_bank(symbol, data):
    """Generate one-day-ahead expanding-window forecasts."""

    bank = (
        data[data["symbol"] == symbol]
        .sort_values("date")
        .copy()
        .reset_index(drop=True)
    )

    bank["garch_volatility_forecast"] = np.nan

    returns = (
        bank["return"]
        .dropna()
        .reset_index()
    )

    for i in range(
        MIN_TRAINING_OBS,
        len(returns),
    ):

        training = (
            returns.loc[:i - 1, "return"] * 100
        )

        model = arch_model(
            training,
            mean="Constant",
            vol="GARCH",
            p=1,
            q=1,
            dist="normal",
        )

        fitted = model.fit(
            disp="off"
        )

        forecast = fitted.forecast(
            horizon=1
        )

        variance = forecast.variance.iloc[-1, 0]

        volatility = np.sqrt(
            variance
        ) / 100

        row_index = returns.loc[
            i,
            "index",
        ]

        bank.loc[
            row_index,
            "garch_volatility_forecast",
        ] = volatility

    return bank

def main():
    """Generate GARCH forecasts."""

    data = pd.read_csv(
        BANK_FILE,
        parse_dates=["date"],
    )

    results = []

    for symbol in BANKS:

        print(
            f"Forecasting GARCH volatility: {symbol}"
        )

        bank = forecast_bank(
            symbol,
            data,
        )

        results.append(bank)

    output = pd.concat(
        results,
        ignore_index=True,
    )

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(
        "\n--- GARCH FORECAST SUMMARY ---"
    )

    print(
        output[
            [
                "symbol",
                "date",
                "return",
                "garch_volatility_forecast",
            ]
        ]
        .dropna(
            subset=[
                "garch_volatility_forecast"
            ]
        )
        .tail(10)
        .to_string(index=False)
    )

    print("\nForecast observations:")

    print(
        output[
            "garch_volatility_forecast"
        ].notna().sum()
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()