"""Transparent dividend/corporate-action sensitivities for an event study.

Adjusted bank returns with price-index benchmarks are deliberately labelled as
mixed-convention sensitivity checks, not a consistent total-return event study.
Excluding affected bank/window observations changes the portfolio composition;
the resulting comparisons must not be presented as identical-sample estimates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .event_study import INFERENCE_WINDOWS, bank_symbols, run_event_study
from .statistics import holm_adjust, run_inference


PRIMARY_SCENARIO = "primary_split_adjusted_price_returns"
ADJUSTED_SCENARIO = "adjusted_bank_returns_vs_price_index"
EXCLUDED_SCENARIO = "exclude_window_corporate_actions"
ADJUSTED_CONVENTION = "adjusted_bank_return_with_price_index_benchmark_mixed_convention_not_total_return_study"
PRICE_CONVENTION = "vendor_split_adjusted_bank_price_return_with_price_index_benchmark"
KEYS = ["event_id", "bank_symbol", "benchmark", "window"]


def _corporate_overlaps(panel, primary_results):
    """Match actions to the exact observed trading dates in each result window."""
    prices = panel.copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    for column in ("dividends", "stock_splits"):
        if column not in prices:
            raise ValueError(f"Corporate-action sensitivity requires {column}")
        prices[column] = pd.to_numeric(prices[column], errors="raise").fillna(0.0)
    actions = prices[prices["dividends"].ne(0) | prices["stock_splits"].ne(0)]
    grouped = {symbol: group for symbol, group in actions.groupby("symbol")}
    rows = []
    for result in primary_results.itertuples(index=False):
        action = grouped.get(result.bank_symbol)
        if action is None:
            continue
        if hasattr(result, "event_trading_dates"):
            trading_dates = pd.to_datetime(str(result.event_trading_dates).split("|"))
            overlap = action[action["date"].isin(trading_dates)]
        elif hasattr(result, "event_window_start") and hasattr(result, "event_window_end"):
            overlap = action[action["date"].between(pd.Timestamp(result.event_window_start), pd.Timestamp(result.event_window_end))]
        else:
            raise ValueError("Corporate-action matching requires actual event-window trading dates")
        for observed in overlap.itertuples(index=False):
            rows.append({
                "event_id": result.event_id, "event_date": result.event_date,
                "bank_symbol": result.bank_symbol, "bank_name": result.bank_name,
                "bank_type": result.bank_type, "benchmark": result.benchmark,
                "window": result.window, "action_date": observed.date,
                "dividend_cash_per_share": float(observed.dividends),
                "stock_split_factor": float(observed.stock_splits),
                "action_type": "dividend_and_split" if observed.dividends and observed.stock_splits else
                               "dividend" if observed.dividends else "split",
                "excluded_from_price_sensitivity": True,
            })
    columns = ["event_id", "event_date", "bank_symbol", "bank_name", "bank_type", "benchmark", "window",
               "action_date", "dividend_cash_per_share", "stock_split_factor", "action_type", "excluded_from_price_sensitivity"]
    return pd.DataFrame(rows, columns=columns)


def _composition(primary, retained):
    keys = ["event_id", "event_date", "decision", "benchmark", "window"]
    rows = []
    retained_lookup = {key: group for key, group in retained.groupby(keys, dropna=False)}
    for identity, group in primary.groupby(keys, dropna=False):
        remaining = retained_lookup.get(identity, group.iloc[0:0])
        original_banks = set(group.bank_symbol)
        remaining_banks = set(remaining.bank_symbol)
        removed = original_banks - remaining_banks
        rows.append({**dict(zip(keys, identity)),
                     "n_banks_original": len(original_banks), "n_banks_retained": len(remaining_banks),
                     "n_banks_excluded": len(removed),
                     "retained_bank_symbols": "|".join(sorted(remaining_banks)),
                     "excluded_bank_symbols": "|".join(sorted(removed)),
                     "composition_changed": bool(removed), "all_banks_excluded": not remaining_banks,
                     "original_mean_car": float(group.car.mean()),
                     "retained_mean_car": float(remaining.car.mean()) if len(remaining) else np.nan})
    return pd.DataFrame(rows)


def _annotate(frame, scenario, convention):
    frame = frame.copy()
    frame["scenario"] = scenario
    frame["return_convention"] = convention
    frame["sensitivity_caveat"] = (
        "mixed_bank_adjusted_and_index_price_conventions_not_a_consistent_total_return_study"
        if scenario == ADJUSTED_SCENARIO else
        "bank_composition_varies_by_event_and_window_not_identical_sample_comparison"
        if scenario == EXCLUDED_SCENARIO else "price_returns_include_ex_dividend_price_movements"
    )
    return frame


def run_sensitivity(panel, events, primary_results, *, seed=42, n_bootstrap=10000) -> dict[str, pd.DataFrame]:
    """Compare primary price results with two explicitly exploratory variants.

    Exclusions remove only bank-event-benchmark-window observations containing an
    action. Remaining banks are equally weighted within each event. Corporate
    action exclusions are a sensitivity choice even for splits already adjusted
    by the vendor. All event counts and composition changes remain visible.
    """
    if primary_results.empty or primary_results.duplicated(KEYS).any():
        raise ValueError("Primary results must be nonempty with unique bank-event-benchmark-window keys")
    if "adj_return" not in panel:
        raise ValueError("Adjusted-return sensitivity requires adj_return")
    adjusted_panel = panel.copy()
    banks = bank_symbols(adjusted_panel)
    is_bank = adjusted_panel["symbol"].isin(banks)
    adjusted_panel.loc[is_bank, "return"] = adjusted_panel.loc[is_bank, "adj_return"]
    # Keep index price returns unchanged. No unavailable total-return benchmark
    # is fabricated or silently substituted.
    windows = {
        row.window: (int(row.window_start_day), int(row.window_end_day))
        for row in primary_results[["window", "window_start_day", "window_end_day"]].drop_duplicates().itertuples(index=False)
    }
    estimation_counts = primary_results["n_estimation"].unique()
    if len(estimation_counts) != 1 or int(estimation_counts[0]) != 250:
        raise ValueError("Sensitivity comparison expects the declared common 250-day primary specification")
    adjusted = run_event_study(adjusted_panel, events,
                               benchmarks=tuple(primary_results["benchmark"].drop_duplicates()), windows=windows)
    overlaps = _corporate_overlaps(panel, primary_results)
    excluded_keys = pd.MultiIndex.from_frame(overlaps[KEYS].drop_duplicates())
    keep = ~pd.MultiIndex.from_frame(primary_results[KEYS]).isin(excluded_keys)
    retained = primary_results.loc[keep].copy()
    composition = _composition(primary_results, retained)
    primary_inference = run_inference(primary_results, seed=seed, n_bootstrap=n_bootstrap)
    adjusted_inference = run_inference(adjusted, seed=seed, n_bootstrap=n_bootstrap)
    if retained[retained.window.isin(INFERENCE_WINDOWS)].empty:
        unavailable = primary_inference["decision_comparisons"].copy()
        for column in ("mean_a", "mean_b", "difference", "standard_error", "t_statistic", "degrees_freedom",
                       "p_value", "p_value_holm", "ci_lower", "ci_upper", "bootstrap_ci_lower", "bootstrap_ci_upper", "bootstrap_mean"):
            unavailable[column] = np.nan
        unavailable[["n_a_events", "n_b_events", "n_tests_in_family"]] = 0
        unavailable["status"] = "no_eligible_bank_events"
        excluded_inference = {
            "event_means": primary_inference["event_means"].iloc[0:0].copy(),
            "decision_comparisons": unavailable,
        }
    else:
        excluded_inference = run_inference(retained, seed=seed, n_bootstrap=n_bootstrap)
    event_keys = ["event_id", "event_date", "decision", "benchmark", "window"]
    excluded_event_means = excluded_inference["event_means"].merge(
        composition, on=event_keys, how="left", validate="one_to_one")
    infer_by_scenario = {
        PRIMARY_SCENARIO: primary_inference,
        ADJUSTED_SCENARIO: adjusted_inference,
        EXCLUDED_SCENARIO: excluded_inference,
    }
    comparative = []
    for scenario, inference in infer_by_scenario.items():
        convention = ADJUSTED_CONVENTION if scenario == ADJUSTED_SCENARIO else PRICE_CONVENTION
        frame = _annotate(inference["decision_comparisons"], scenario, convention)
        frame["p_value_holm_within_scenario"] = frame["p_value_holm"]
        comparative.append(frame)
    all_comparisons = pd.concat(comparative, ignore_index=True)
    all_comparisons["p_value_holm_across_sensitivity_family"] = holm_adjust(all_comparisons["p_value"])
    all_comparisons["sensitivity_multiplicity_family"] = "all_decision_contrasts_all_scenarios_benchmarks_windows"
    all_comparisons["n_tests_in_sensitivity_family"] = int(all_comparisons["p_value"].notna().sum())
    summary_rows = []
    for row in all_comparisons.query("group_a == 'Cut' and group_b == 'Hold'").to_dict("records"):
        event_means = infer_by_scenario[row["scenario"]]["event_means"]
        group = event_means[event_means["benchmark"].eq(row["benchmark"]) & event_means["window"].eq(row["window"])]
        population = composition[composition["benchmark"].eq(row["benchmark"]) & composition["window"].eq(row["window"])]
        excluded = row["scenario"] == EXCLUDED_SCENARIO
        counts = population["n_banks_retained" if excluded else "n_banks_original"]
        row.update({
            "n_total_events_retained": len(group),
            "min_banks_per_original_event": int(counts.min()) if len(counts) else 0,
            "max_banks_per_original_event": int(counts.max()) if len(counts) else 0,
            "n_events_with_changed_bank_composition": int(population.composition_changed.sum()) if excluded else 0,
            "n_events_entirely_excluded": int(population.all_banks_excluded.sum()) if excluded else 0,
            "n_bank_event_observations_excluded": int(population.n_banks_excluded.sum()) if excluded else 0,
            "interpretation": "exploratory_sensitivity_no_causal_identification_no_favorable_result_selection",
        })
        summary_rows.append(row)
    output = {
        "adjusted_bank_event_results": _annotate(adjusted, ADJUSTED_SCENARIO, ADJUSTED_CONVENTION),
        "adjusted_bank_event_means": _annotate(adjusted_inference["event_means"], ADJUSTED_SCENARIO, ADJUSTED_CONVENTION),
        "adjusted_bank_decision_comparisons": all_comparisons[all_comparisons.scenario.eq(ADJUSTED_SCENARIO)].reset_index(drop=True),
        "corporate_action_overlaps": overlaps,
        "action_excluded_event_results": _annotate(retained, EXCLUDED_SCENARIO, PRICE_CONVENTION),
        "action_excluded_event_means": _annotate(excluded_event_means, EXCLUDED_SCENARIO, PRICE_CONVENTION),
        "action_excluded_decision_comparisons": all_comparisons[all_comparisons.scenario.eq(EXCLUDED_SCENARIO)].reset_index(drop=True),
        "composition_changes": composition,
        "sensitivity_summary": pd.DataFrame(summary_rows),
    }
    return output
