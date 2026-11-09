"""Pre-declared robustness checks that do not select a favorable result."""

from __future__ import annotations

import pandas as pd

from .event_study import DEFAULT_WINDOWS, run_event_study
from .statistics import holm_adjust, run_inference


def _decision_table(results, scenario, *, seed, n_bootstrap):
    table = run_inference(results, seed=seed, n_bootstrap=n_bootstrap)["decision_comparisons"].copy()
    table["scenario"] = scenario
    return table


def run_sensitivity(panel, events, primary_results, *, seed=42, n_bootstrap=10000) -> dict[str, pd.DataFrame]:
    """Vary estimation history and remove pre-specified stress/off-cycle events."""
    scenarios = []
    for days in (120, 180):
        result = run_event_study(panel, events, windows=DEFAULT_WINDOWS, estimation_days=days)
        scenarios.append(_decision_table(result, f"estimation_{days}_trading_days", seed=seed, n_bootstrap=n_bootstrap))
    scenarios.append(_decision_table(primary_results, "primary_estimation_250_trading_days", seed=seed, n_bootstrap=n_bootstrap))

    exclusion_specs = {
        "exclude_covid_emergency_2020_03_2020_05": {"MPC_2020_03", "MPC_2020_05"},
        "exclude_all_off_cycle_emergency": {"MPC_2020_03", "MPC_2020_05", "MPC_2022_05"},
        "exclude_covid_era_2020_2021": set(events.loc[pd.to_datetime(events.event_date).dt.year.isin([2020, 2021]), "event_id"]),
    }
    exclusion_tables = []
    for scenario, removed in exclusion_specs.items():
        retained = primary_results.loc[~primary_results.event_id.isin(removed)].copy()
        table = _decision_table(retained, scenario, seed=seed, n_bootstrap=n_bootstrap)
        table["removed_event_ids"] = "|".join(sorted(removed))
        table["n_events_retained"] = retained.event_id.nunique()
        exclusion_tables.append(table)

    estimation = pd.concat(scenarios, ignore_index=True)
    exclusions = pd.concat(exclusion_tables, ignore_index=True)
    summary = pd.concat([estimation, exclusions], ignore_index=True)
    summary["sensitivity_policy"] = "all_predeclared_scenarios_reported_no_result_selection"
    summary["p_value_holm_across_all_scenarios"] = holm_adjust(summary["p_value"])
    if "permutation_p_value" in summary:
        summary["permutation_p_value_holm_across_all_scenarios"] = holm_adjust(summary["permutation_p_value"])
    return {
        "estimation_window_sensitivity": estimation,
        "regime_exclusion_sensitivity": exclusions,
        "sensitivity_summary": summary,
    }
