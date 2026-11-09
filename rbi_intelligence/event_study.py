"""Market-model event studies on a common, explicit trading calendar.

Returns are fractions, not percentages.  The default 250-observation estimation
interval is [-255, -6], inclusive, for *both* benchmarks.  An absent bank return
never silently shortens a trading-day window.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd


DEFAULT_WINDOWS = {
    "[-1,+1]": (-1, 1),
    "[-2,+2]": (-2, 2),
    "[-5,+5]": (-5, 5),
    "[0,+1]": (0, 1),
}
INFERENCE_WINDOWS = ("[-1,+1]", "[-2,+2]", "[-5,+5]")
BENCHMARK_NAMES = {"^NSEI": "Nifty 50", "^NSEBANK": "Nifty Bank"}


def _prepare_inputs(returns: pd.DataFrame, events: pd.DataFrame):
    required = {"date", "symbol", "return", "bank_name", "bank_type"}
    missing = required.difference(returns.columns)
    if missing:
        raise ValueError(f"Return panel lacks columns: {sorted(missing)}")
    missing = {"event_id", "event_date"}.difference(events.columns)
    if missing:
        raise ValueError(f"Event table lacks columns: {sorted(missing)}")
    panel, policy = returns.copy(), events.copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="raise").dt.normalize()
    policy["event_date"] = pd.to_datetime(policy["event_date"], errors="raise").dt.normalize()
    if panel[["date", "symbol"]].isna().any().any():
        raise ValueError("Return panel has missing date or symbol identifiers")
    if policy[["event_id", "event_date"]].isna().any().any():
        raise ValueError("Event table has missing identifiers")
    if panel.duplicated(["date", "symbol"]).any():
        raise ValueError("Duplicate date/symbol rows in return panel")
    if policy["event_id"].duplicated().any() or policy["event_date"].duplicated().any():
        raise ValueError("Duplicate event identifiers or announcement dates")
    panel["return"] = pd.to_numeric(panel["return"], errors="raise")
    if np.isinf(panel["return"].to_numpy(dtype=float)).any():
        raise ValueError("Infinite return in panel")
    if "decision" not in policy:
        policy["decision"] = "Unknown"
    return panel.sort_values(["symbol", "date"]), policy.sort_values("event_date")


def bank_symbols(panel: pd.DataFrame, benchmarks: Sequence[str] = ("^NSEI", "^NSEBANK")):
    """Select bank securities, allowing empty metadata on index observations."""
    if "asset_type" in panel:
        mask = panel["asset_type"].astype(str).str.casefold().eq("bank")
        if mask.any():
            return sorted(panel.loc[mask, "symbol"].unique())
    mask = ~panel["symbol"].isin(benchmarks) & ~panel["symbol"].astype(str).str.startswith("^")
    return sorted(panel.loc[mask, "symbol"].unique())


def run_event_study(
    returns: pd.DataFrame,
    events: pd.DataFrame,
    *,
    benchmarks: Sequence[str] = ("^NSEI", "^NSEBANK"),
    windows: Mapping[str, tuple[int, int]] | None = None,
    estimation_days: int = 250,
    estimation_end_day: int = -6,
) -> pd.DataFrame:
    """Return one row per bank, event, benchmark, and outcome window.

    Fail explicitly on missing history, missing observations, non-trading event
    dates, duplicate identifiers, or an unidentified market regression.  The
    benchmark's observed trading dates define the calendar; bank-specific gaps
    cannot turn a three-trading-day event window into three arbitrary rows.
    """
    panel, policy = _prepare_inputs(returns, events)
    windows = dict(DEFAULT_WINDOWS if windows is None else windows)
    if estimation_days < 3 or not windows or not benchmarks:
        raise ValueError("At least three estimation observations and one window/benchmark are required")
    for label, bounds in windows.items():
        if len(bounds) != 2 or not all(isinstance(v, (int, np.integer)) for v in bounds):
            raise ValueError(f"Window {label} must contain two integer offsets")
        if bounds[0] > bounds[1]:
            raise ValueError(f"Window {label} has reversed bounds")
    first_day = min(a for a, _ in windows.values())
    last_day = max(b for _, b in windows.values())
    if estimation_end_day >= first_day:
        raise ValueError("Estimation interval must end before every outcome window")
    banks = bank_symbols(panel, benchmarks)
    if not banks:
        raise ValueError("Return panel contains no bank securities")
    indexed = {symbol: group.set_index("date") for symbol, group in panel.groupby("symbol")}
    rows = []
    for benchmark in benchmarks:
        if benchmark not in indexed:
            raise ValueError(f"Missing benchmark {benchmark}")
        market = indexed[benchmark]
        calendar = pd.DatetimeIndex(market.index).sort_values()
        for event in policy.itertuples(index=False):
            target = pd.Timestamp(event.event_date)
            if target not in calendar:
                raise ValueError(f"Event {event.event_id}: {target.date()} is not a {benchmark} trading date")
            position = int(calendar.get_loc(target))
            estimation_end = position + estimation_end_day
            estimation_start = estimation_end - estimation_days + 1
            if estimation_start < 0 or position + first_day < 0 or position + last_day >= len(calendar):
                raise ValueError(f"Insufficient calendar history for {event.event_id} / {benchmark}")
            estimation_dates = calendar[estimation_start:estimation_end + 1]
            outcome_dates = calendar[position + first_day:position + last_day + 1]
            for symbol in banks:
                bank = indexed[symbol]
                estimation = pd.DataFrame({
                    "bank": bank["return"].reindex(estimation_dates),
                    "market": market["return"].reindex(estimation_dates),
                })
                outcome = pd.DataFrame({
                    "bank": bank["return"].reindex(outcome_dates),
                    "market": market["return"].reindex(outcome_dates),
                })
                for name, frame in (("estimation", estimation), ("event", outcome)):
                    if not np.isfinite(frame.to_numpy(dtype=float)).all():
                        bad = frame.index[~np.isfinite(frame.to_numpy(dtype=float)).all(axis=1)]
                        raise ValueError(
                            f"Missing/non-finite {name} returns for {event.event_id} / {symbol} / "
                            f"{benchmark}: {', '.join(d.strftime('%Y-%m-%d') for d in bad)}"
                        )
                design = np.column_stack([np.ones(estimation_days), estimation["market"].to_numpy()])
                parameters, _, rank, _ = np.linalg.lstsq(design, estimation["bank"].to_numpy(), rcond=None)
                if rank < 2:
                    raise ValueError(f"Constant benchmark returns: unidentified market model for {event.event_id}")
                alpha, beta = (float(x) for x in parameters)
                expected = alpha + beta * outcome["market"]
                abnormal = outcome["bank"] - expected
                relative = pd.Series(np.arange(first_day, last_day + 1), index=outcome_dates)
                metadata = bank.iloc[0]
                for window, (start, end) in windows.items():
                    selected = relative.between(start, end)
                    dates = outcome_dates[selected.to_numpy()]
                    row = {
                        "event_id": event.event_id,
                        "event_date": target,
                        "decision": event.decision,
                        "bank_symbol": symbol,
                        "bank_name": metadata["bank_name"],
                        "bank_type": metadata["bank_type"],
                        "benchmark": benchmark,
                        "benchmark_name": BENCHMARK_NAMES.get(benchmark, benchmark),
                        "window": window,
                        "window_start_day": start,
                        "window_end_day": end,
                        "car": float(abnormal.loc[selected].sum()),
                        "alpha": alpha,
                        "beta": beta,
                        "estimation_start": estimation_dates[0],
                        "estimation_end": estimation_dates[-1],
                        "n_estimation": len(estimation),
                        "n_event": len(dates),
                        "event_window_start": dates[0],
                        "event_window_end": dates[-1],
                        "event_trading_dates": "|".join(d.strftime("%Y-%m-%d") for d in dates),
                        "return_unit": "fraction",
                    }
                    for day, column in ((-1, "ar_minus_1"), (0, "ar_0"), (1, "ar_plus_1")):
                        match = abnormal.loc[relative.eq(day)]
                        row[column] = float(match.iloc[0]) if not match.empty else np.nan
                    rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("No events were supplied")
    return result.sort_values(["event_date", "bank_symbol", "benchmark", "window"]).reset_index(drop=True)
