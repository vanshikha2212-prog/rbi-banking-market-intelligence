# Data sources and provenance

## RBI policy registry

`data/raw/rbi_mpc_events_2016_2025.csv` contains every repo-rate decision announced by the RBI Monetary Policy Committee from its first meeting on 4 October 2016 through 5 December 2025. Each row records meeting dates, rates, decision, stance, and an event-specific official RBI URL.

The registry excludes the 3 November 2022 additional meeting because it did not announce a repo-rate decision. Emergency and off-cycle decisions in March 2020, May 2020, and May 2022 are retained and separately tested.

## Official NSE market history

`data/raw/nse_market_prices_2015_2025.csv` consolidates declared assets from official NSE daily bhavcopy and index archives. `scripts/fetch_nse_history.py` is the downloader; `data/raw/nse_market_retrieval_manifest.json` records source URLs, source-byte SHA-256 values, byte counts, dates, and the consolidated hash.

Bank returns use `close / previous_close - 1`; index returns use consecutive official closes. No price is forward-filled or interpolated.

## Limits

- Hashes identify bytes used; they do not independently certify every observation.
- The snapshot is end-of-day history, not announcement-minute data.
- Price returns retain dividend-related movements.
- This is not a live market-data feed.
