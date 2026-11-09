import numpy as np
import pandas as pd

from rbi_intelligence.event_study import run_event_study
from rbi_intelligence.sensitivity import run_sensitivity


def fixture():
    dates = pd.bdate_range("2018-01-01", periods=800)
    market = .002 * np.sin(np.arange(len(dates)) / 9) + .001 * np.cos(np.arange(len(dates)) / 13)
    frames = []
    for symbol, bank_type in (("A", "Private"), ("B", "Public"), ("^NSEI", ""), ("^NSEBANK", "")):
        values = market if not bank_type else .0001 + (1.1 if symbol == "A" else .9) * market
        frames.append(pd.DataFrame({"date": dates, "symbol": symbol, "return": values,
                                    "bank_name": symbol, "bank_type": bank_type,
                                    "asset_type": "bank" if bank_type else "benchmark"}))
    event_indices = [300, 370, 440, 510, 580, 650]
    ids = ["MPC_2020_03", "MPC_2020_05", "MPC_2022_05", "E4", "E5", "E6"]
    events = pd.DataFrame({"event_id": ids, "event_date": dates[event_indices],
                           "decision": ["Cut", "Cut", "Hike", "Hold", "Hold", "Hike"]})
    panel = pd.concat(frames, ignore_index=True)
    return panel, events, run_event_study(panel, events)


def test_all_predeclared_sensitivity_scenarios_are_retained():
    panel, events, primary = fixture()
    output = run_sensitivity(panel, events, primary, n_bootstrap=20)
    scenarios = set(output["sensitivity_summary"].scenario)
    assert {"estimation_120_trading_days", "estimation_180_trading_days",
            "primary_estimation_250_trading_days", "exclude_covid_emergency_2020_03_2020_05",
            "exclude_all_off_cycle_emergency", "exclude_covid_era_2020_2021"}.issubset(scenarios)
    assert output["sensitivity_summary"].sensitivity_policy.eq(
        "all_predeclared_scenarios_reported_no_result_selection").all()


def test_off_cycle_exclusion_reports_removed_ids_and_event_count():
    panel, events, primary = fixture()
    output = run_sensitivity(panel, events, primary, n_bootstrap=10)
    rows = output["regime_exclusion_sensitivity"].query("scenario == 'exclude_all_off_cycle_emergency'")
    assert rows.removed_event_ids.str.contains("MPC_2022_05").all()
    assert rows.n_events_retained.eq(3).all()
