"""Fit GARCH(1,1) models to banking return series."""

from pathlib import Path

import pandas as pd
from arch import arch_model


PROCESSED_DIR = Path("data/processed")

BANK_FILE = (
    PROCESSED_DIR / "bank_returns_2021_2025.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "garch_results.csv"
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
    """Fit GARCH(1,1) to each bank."""

    data = pd.read_csv(
        BANK_FILE,
        parse_dates=["date"],
    )

    rows = []

    for symbol in BANKS:

        print(
            f"Fitting GARCH(1,1): {symbol}"
        )

        series = (
            data[
                data["symbol"] == symbol
            ]
            .sort_values("date")["return"]
            .dropna()
        )

        # Scale returns for numerical stability.
        series = series * 100

        model = arch_model(
            series,
            mean="Constant",
            vol="GARCH",
            p=1,
            q=1,
            dist="normal",
        )

        fitted = model.fit(
            disp="off"
        )

        params = fitted.params

        rows.append(
            {
                "symbol": symbol,
                "mu": params.get("mu"),
                "omega": params.get("omega"),
                "alpha_1": params.get("alpha[1]"),
                "beta_1": params.get("beta[1]"),
                "alpha_plus_beta": (
                    params.get("alpha[1]", 0)
                    + params.get("beta[1]", 0)
                ),
                "log_likelihood":
                    fitted.loglikelihood,
                "aic": fitted.aic,
                "bic": fitted.bic,
            }
        )

    output = pd.DataFrame(rows)

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\n--- GARCH(1,1) RESULTS ---")

    print(
        output.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()