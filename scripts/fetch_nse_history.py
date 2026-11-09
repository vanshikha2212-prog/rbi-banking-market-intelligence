#!/usr/bin/env python3
"""Fetch a reproducible 2015-2025 panel from official NSE daily archives.

The script keeps only the six declared bank rows and two benchmark rows, while
recording the URL and SHA-256 of every source file used. Missing archive URLs on
weekends and exchange holidays are expected and are not recorded as sources.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date, timedelta
import hashlib
from io import BytesIO, StringIO, TextIOWrapper
import json
from pathlib import Path
import subprocess
import zipfile


START = date(2015, 1, 1)
END = date(2025, 12, 31)
SYMBOLS = ("HDFCBANK", "ICICIBANK", "AXISBANK", "SBIN", "BANKBARODA", "CANBK")
INDEX_ALIASES = {"Nifty 50": "^NSEI", "CNX Nifty": "^NSEI", "Nifty Bank": "^NSEBANK", "CNX Bank": "^NSEBANK"}
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def _request(url: str) -> bytes | None:
    result = subprocess.run([
        "curl", "-L", "--fail", "--silent", "--show-error", "--compressed",
        "-A", USER_AGENT, url,
    ], capture_output=True)
    if result.returncode == 0:
        return result.stdout
    error = result.stderr.decode("utf-8", "replace")
    if "404" in error:
        return None
    raise RuntimeError(f"NSE download failed for {url}: {error.strip()}")


def _equity_url(day: date) -> tuple[str, str]:
    stamp = day.strftime("%d%m%Y")
    if day.year >= 2024:
        return (
            f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{stamp}.csv",
            "full_bhavcopy",
        )
    month = day.strftime("%b").upper()
    return (
        f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{day.year}/{month}/cm{day.strftime('%d%b%Y').upper()}bhav.csv.zip",
        "historical_bhavcopy",
    )


def _parse_equities(body: bytes, source_format: str, day: date) -> list[dict[str, object]]:
    if source_format == "historical_bhavcopy":
        with zipfile.ZipFile(BytesIO(body)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError(f"Expected one CSV in equity archive for {day}")
            reader = csv.DictReader(TextIOWrapper(archive.open(names[0]), encoding="utf-8-sig"))
            rows = [row for row in reader if row.get("SYMBOL") in SYMBOLS and row.get("SERIES") == "EQ"]
        mapping = {
            "open": "OPEN", "high": "HIGH", "low": "LOW", "close": "CLOSE",
            "previous_close": "PREVCLOSE", "volume": "TOTTRDQTY",
        }
    else:
        text = body.decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text), skipinitialspace=True)
        rows = []
        for original in reader:
            row = {str(key).strip(): str(value).strip() for key, value in original.items() if key is not None}
            if row.get("SYMBOL") in SYMBOLS and row.get("SERIES") == "EQ":
                rows.append(row)
        mapping = {
            "open": "OPEN_PRICE", "high": "HIGH_PRICE", "low": "LOW_PRICE", "close": "CLOSE_PRICE",
            "previous_close": "PREV_CLOSE", "volume": "TTL_TRD_QNTY",
        }
    if len(rows) != len(SYMBOLS):
        raise ValueError(f"Expected all six bank rows for {day}; found {len(rows)}")
    output = []
    for row in rows:
        output.append({
            "date": day.isoformat(), "symbol": f"{row['SYMBOL']}.NS", "source_provider": "NSE official bhavcopy",
            **{name: float(row[column]) for name, column in mapping.items()},
        })
    return output


def _parse_indices(body: bytes, day: date) -> list[dict[str, object]]:
    reader = csv.DictReader(StringIO(body.decode("utf-8-sig")))
    rows = [row for row in reader if row.get("Index Name") in INDEX_ALIASES]
    if len(rows) != 2 or len({INDEX_ALIASES[row["Index Name"]] for row in rows}) != 2:
        raise ValueError(f"Expected both index rows for {day}; found {len(rows)}")
    output = []
    for row in rows:
        output.append({
            "date": day.isoformat(),
            "symbol": INDEX_ALIASES[row["Index Name"]],
            "open": float(row["Open Index Value"]), "high": float(row["High Index Value"]),
            "low": float(row["Low Index Value"]), "close": float(row["Closing Index Value"]),
            "previous_close": "", "volume": float(row.get("Volume") or 0),
            "source_provider": "NSE official index archive",
        })
    return output


def fetch_day(day: date) -> tuple[list[dict[str, object]], list[dict[str, object]]] | None:
    index_url = f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{day.strftime('%d%m%Y')}.csv"
    index = _request(index_url)
    if index is None:
        return None
    equity_url, source_format = _equity_url(day)
    equity = _request(equity_url)
    if equity is None:
        raise ValueError(f"Index archive exists but equity archive is absent for {day}")
    rows = _parse_equities(equity, source_format, day) + _parse_indices(index, day)
    records = [
        {"date": day.isoformat(), "kind": "equity", "url": equity_url, "sha256": hashlib.sha256(equity).hexdigest(), "bytes": len(equity)},
        {"date": day.isoformat(), "kind": "index", "url": index_url, "sha256": hashlib.sha256(index).hexdigest(), "bytes": len(index)},
    ]
    return rows, records


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    raw = root / "data/raw"
    days = []
    current = START
    while current <= END:
        days.append(current)
        current += timedelta(days=1)
    rows: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    completed = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch_day, day): day for day in days}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                day_rows, day_records = result
                rows.extend(day_rows)
                records.extend(day_records)
            completed += 1
            if completed % 250 == 0:
                print(f"Checked {completed}/{len(days)} calendar dates; retained {len(rows) // 8} sessions", flush=True)
    rows.sort(key=lambda item: (str(item["date"]), str(item["symbol"])))
    records.sort(key=lambda item: (str(item["date"]), str(item["kind"])))
    if not rows or len(rows) % 8:
        raise ValueError("Incomplete NSE panel")
    sessions = sorted({str(item["date"]) for item in rows})
    year_counts = {str(year): sum(day.startswith(str(year)) for day in sessions) for year in range(START.year, END.year + 1)}
    if len(sessions) < 2700 or any(count < 240 for count in year_counts.values()):
        raise ValueError(f"Implausibly incomplete official NSE calendar: {year_counts}")
    columns = ["date", "symbol", "open", "high", "low", "close", "previous_close", "volume", "source_provider"]
    output = raw / "nse_market_prices_2015_2025.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "manifest_version": 1,
        "retrieval_scope": {"start_inclusive": START.isoformat(), "end_inclusive": END.isoformat()},
        "provider": "National Stock Exchange of India official public daily archives",
        "trading_sessions": len(rows) // 8,
        "trading_sessions_by_year": year_counts,
        "symbols": list(SYMBOLS),
        "indices": ["Nifty 50", "Nifty Bank"],
        "source_files": records,
        "consolidated_csv_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "note": "Source hashes identify the official daily bytes used; the consolidated CSV retains only declared study rows.",
    }
    (raw / "nse_market_retrieval_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output} with {len(rows)} rows across {len(rows) // 8} sessions", flush=True)


if __name__ == "__main__":
    main()
