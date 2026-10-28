"""Download and validate historical market data.

Primary research provenance: NSE historical archives.
Programmatic acquisition/cross-check layer: Yahoo Finance via yfinance.

This script does not claim Yahoo Finance is the primary research source.
It creates raw CSVs under data/raw when run locally.
"""

from pathlib import Path

import pandas as pd
import yfinance as yf

START_DATE = "2021-01-01"
END_DATE = "2026-01-01"  # end date is exclusive in yfinance

BANKS = {
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "AXISBANK.NS": "Axis Bank",
    "SBIN.NS": "State Bank of India",
    "BANKBARODA.NS": "Bank of Baroda",
    "CANBK.NS": "Canara Bank",
}

BENCHMARKS = {
    "^NSEI": "Nifty 50",
    "^NSEBANK": "Nifty Bank",
}

RAW_DIR = Path("data/raw")


def download_prices(tickers: dict[str, str], asset_type: str) -> pd.DataFrame:
    """Download daily OHLCV data and return it in tidy/long format."""
    raw = yf.download(
        tickers=list(tickers),
        start=START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=False,
        actions=False,
        group_by="ticker",
        progress=True,
        threads=True,
    )

    if raw.empty:
        raise RuntimeError(f"No market data returned for {asset_type}.")

    frames = []

    for ticker, name in tickers.items():
        if ticker not in raw.columns.get_level_values(0):
            raise RuntimeError(
                f"Ticker {ticker} was not returned by Yahoo Finance."
            )

        ticker_df = raw[ticker].copy().reset_index()

        ticker_df.columns = [
            str(column).lower().replace(" ", "_")
            for column in ticker_df.columns
        ]

        ticker_df["symbol"] = ticker
        ticker_df["name"] = name
        ticker_df["asset_type"] = asset_type

        frames.append(
            ticker_df[
                [
                    "date",
                    "symbol",
                    "name",
                    "asset_type",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adj_close",
                    "volume",
                ]
            ]
        )

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(["symbol", "date"]).reset_index(drop=True)
    return result


def validate_market_data(df: pd.DataFrame) -> None:
    """Run structural and OHLC integrity checks on actual observations."""
    required_columns = {
        "date",
        "symbol",
        "name",
        "asset_type",
        "open",
        "high",
        "low",
        "close",
        "adj_close",
        "volume",
    }

    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if df["date"].isna().any():
        raise ValueError("Missing dates detected.")

    # A row with all market fields missing represents a date where
    # the asset had no trading observation. It must not be treated
    # as a zero return or interpolated value.
    price_columns = ["open", "high", "low", "close", "adj_close", "volume"]

    empty_observations = df[price_columns].isna().all(axis=1)

    if empty_observations.any():
        print(
            f"Removing {empty_observations.sum()} non-trading "
            "observation(s) with no market data."
        )
        df.drop(
            index=df.index[empty_observations],
            inplace=True,
        )

    # Partial missing values are different from a completely absent
    # trading observation and should cause the pipeline to stop.
    partial_missing = df[price_columns].isna().any(axis=1)

    if partial_missing.any():
        raise ValueError(
            "Partial missing market values detected after removing "
            "empty observations."
        )

    if (df["high"] < df["low"]).any():
        raise ValueError("Invalid OHLC data: high is below low.")

    if (df["close"] > df["high"]).any():
        raise ValueError("Invalid OHLC data: close is above high.")

    if (df["close"] < df["low"]).any():
        raise ValueError("Invalid OHLC data: close is below low.")

    duplicate_count = df.duplicated(
        subset=["date", "symbol"]
    ).sum()

    if duplicate_count:
        raise ValueError(
            f"Duplicate date/symbol observations detected: "
            f"{duplicate_count}"
        )


def main() -> None:
    """Download, validate, and save raw bank/index market data."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    bank_prices = download_prices(BANKS, "bank")
    index_prices = download_prices(BENCHMARKS, "benchmark")

    validate_market_data(bank_prices)
    validate_market_data(index_prices)

    bank_path = RAW_DIR / "bank_prices_2021_2025.csv"
    index_path = RAW_DIR / "index_prices_2021_2025.csv"

    bank_prices.to_csv(bank_path, index=False)
    index_prices.to_csv(index_path, index=False)

    print("\n--- MARKET DATA SUMMARY ---")
    print("Bank rows:", len(bank_prices))
    print("Index rows:", len(index_prices))
    print("Bank date range:", bank_prices["date"].min(), "to", bank_prices["date"].max())
    print("Index date range:", index_prices["date"].min(), "to", index_prices["date"].max())
    print("Bank symbols:", bank_prices["symbol"].nunique())
    print("Index symbols:", index_prices["symbol"].nunique())

    print("\nSaved:")
    print(bank_path)
    print(index_path)


if __name__ == "__main__":
    main()
