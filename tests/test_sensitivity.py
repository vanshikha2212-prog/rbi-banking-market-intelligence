import numpy as np
import pandas as pd
import pytest

from rbi_intelligence.event_study import run_event_study
from rbi_intelligence.sensitivity import ADJUSTED_CONVENTION, EXCLUDED_SCENARIO, run_sensitivity


def sensitivity_fixture():
    dates = pd.bdate_range("2021-01-04", periods=420)
    market = .002 * np.sin(np.arange(420) / 6) + .001 * np.cos(np.arange(420) / 9)
    frames = []
    for symbol, kind in (("A", "Private"), ("B", "Public"), ("^NSEI", ""), ("^NSEBANK", "")):
        if kind:
            returns = .0001 + 1.2 * market
            adjusted = returns.copy()
            if symbol == "A":
                returns[300] -= .02
        else:
            returns = market.copy()
            adjusted = 2 * market  # must never replace price-index benchmark
        dividend, split = np.zeros(420), np.zeros(420)
        if symbol == "A":
            dividend[300] = 8.35  # exactly on announcement day
        if symbol == "B":
            split[296] = 2       # inside wide window, outside primary window
        frames.append(pd.DataFrame({"date": dates, "symbol": symbol, "return": returns,
                                    "adj_return": adjusted, "bank_name": symbol, "bank_type": kind,
                                    "dividends": dividend, "stock_splits": split}))
    events = pd.DataFrame({"event_id": ["E1", "E2"], "event_date": [dates[300], dates[330]], "decision": ["Cut", "Hold"]})
    panel = pd.concat(frames, ignore_index=True)
    return panel, events, run_event_study(panel, events), dates


def test_event_day_dividend_is_excluded_and_composition_change_is_visible():
    panel, events, primary, dates = sensitivity_fixture()
    output = run_sensitivity(panel, events, primary, n_bootstrap=20)
    overlaps = output["corporate_action_overlaps"]
    a = overlaps.query("event_id == 'E1' and bank_symbol == 'A' and window == '[-1,+1]'")
    assert len(a) == 2  # the two benchmarks
    assert a.action_date.eq(dates[300]).all()
    assert a.dividend_cash_per_share.eq(8.35).all()
    composition = output["composition_changes"].query("event_id == 'E1' and window == '[-1,+1]'")
    assert composition.n_banks_original.eq(2).all()
    assert composition.n_banks_retained.eq(1).all()
    assert composition.excluded_bank_symbols.eq("A").all()
    assert composition.composition_changed.all()
    means = output["action_excluded_event_means"].query("event_id == 'E1' and window == '[-1,+1]'")
    assert means.n_banks.eq(1).all()
    assert means.n_banks_excluded.eq(1).all()
    assert means.retained_bank_symbols.eq("B").all()


def test_exclusions_use_each_actual_trading_window_not_calendar_day_approximations():
    panel, events, primary, _ = sensitivity_fixture()
    output = run_sensitivity(panel, events, primary, n_bootstrap=20)
    b = output["corporate_action_overlaps"].query("event_id == 'E1' and bank_symbol == 'B'")
    assert set(b.window) == {"[-5,+5]"}
    wide = output["composition_changes"].query("event_id == 'E1' and window == '[-5,+5]'")
    assert wide.all_banks_excluded.all()
    assert wide.n_banks_retained.eq(0).all()
    assert wide.retained_mean_car.isna().all()
    narrow = output["action_excluded_event_results"].query("event_id == 'E1' and bank_symbol == 'B'")
    assert set(narrow.window) == {"[-1,+1]", "[-2,+2]", "[0,+1]"}


def test_adjusted_banks_keep_price_benchmarks_and_carry_explicit_mixed_convention_label():
    panel, events, primary, _ = sensitivity_fixture()
    output = run_sensitivity(panel, events, primary, n_bootstrap=20)
    adjusted = output["adjusted_bank_event_results"]
    target = adjusted.query("event_id == 'E1' and bank_symbol == 'A' and window == '[-1,+1]'")
    assert np.allclose(target.car, 0, atol=1e-12)
    assert np.allclose(target.beta, 1.2, atol=1e-10)  # .6 would mean adjusted index was substituted
    assert adjusted.return_convention.eq(ADJUSTED_CONVENTION).all()
    original = primary.query("event_id == 'E1' and bank_symbol == 'A' and window == '[-1,+1]'")
    assert np.allclose(original.car, -.02, atol=1e-12)
    summary = output["sensitivity_summary"]
    assert "p_value_holm_across_sensitivity_family" in summary
    excluded = summary[summary.scenario.eq(EXCLUDED_SCENARIO) & summary.window.eq("[-5,+5]")]
    assert excluded.n_events_entirely_excluded.eq(1).all()
    assert excluded.min_banks_per_original_event.eq(0).all()


def test_absent_corporate_action_input_cannot_be_mistaken_for_no_actions():
    panel, events, primary, _ = sensitivity_fixture()
    with pytest.raises(ValueError, match="requires dividends"):
        run_sensitivity(panel.drop(columns="dividends"), events, primary, n_bootstrap=20)


def test_all_excluded_events_are_reported_as_unavailable_not_omitted():
    panel, events, primary, _ = sensitivity_fixture()
    panel.loc[panel.symbol.isin(["A", "B"]) & panel.date.isin(events.event_date), "dividends"] = 1
    output = run_sensitivity(panel, events, primary, n_bootstrap=10)
    assert output["action_excluded_event_results"].empty
    summary = output["sensitivity_summary"].query("scenario == @EXCLUDED_SCENARIO")
    assert not summary.empty
    assert summary.status.eq("no_eligible_bank_events").all()
    assert summary.n_total_events_retained.eq(0).all()
    assert summary.p_value.isna().all()
