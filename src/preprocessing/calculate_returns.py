"""Prepare market data and calculate daily returns."""

from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


def load_market_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw bank and benchmark market data."""

    bank_path = RAW_DIR / "bank_prices_2021_2025.csv"
    index_path = RAW_DIR / "index_prices_2021_2025.csv"

    banks = pd.read_csv(bank_path, parse_dates=["date"])
    indices = pd.read_csv(index_path, parse_dates=["date"])

    return banks, indices


def calculate_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily simple returns for each security."""

    df = df.sort_values(["symbol", "date"]).copy()

    df["return"] = (
        df.groupby("symbol")["close"]
        .pct_change()
    )

    return df


def validate_returns(df: pd.DataFrame) -> None:
    """Run basic checks on the calculated returns."""

    if df["return"].isna().all():
        raise ValueError("No returns were calculated.")

    if df["return"].dropna().isin([float("inf"), float("-inf")]).any():
        raise ValueError("Infinite returns detected.")

    duplicate_count = df.duplicated(
        subset=["date", "symbol"]
    ).sum()

    if duplicate_count:
        raise ValueError(
            f"Duplicate date/symbol observations detected: "
            f"{duplicate_count}"
        )


def main() -> None:
    """Load raw data, calculate returns, validate, and save."""

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    banks, indices = load_market_data()

    banks = calculate_returns(banks)
    indices = calculate_returns(indices)

    validate_returns(banks)
    validate_returns(indices)

    bank_path = PROCESSED_DIR / "bank_returns_2021_2025.csv"
    index_path = PROCESSED_DIR / "index_returns_2021_2025.csv"

    banks.to_csv(bank_path, index=False)
    indices.to_csv(index_path, index=False)

    print("\n--- RETURN DATA SUMMARY ---")

    print("Bank rows:", len(banks))
    print("Index rows:", len(indices))

    print(
        "Bank return observations:",
        banks["return"].notna().sum()
    )

    print(
        "Index return observations:",
        indices["return"].notna().sum()
    )

    print(
        "Bank return range:",
        banks["return"].min(),
        "to",
        banks["return"].max(),
    )

    print(
        "Index return range:",
        indices["return"].min(),
        "to",
        indices["return"].max(),
    )

    print("\nSaved:")
    print(bank_path)
    print(index_path)


if __name__ == "__main__":
    main()