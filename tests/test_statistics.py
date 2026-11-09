import numpy as np
import pandas as pd
import pytest
from scipy import stats

from rbi_intelligence.statistics import bootstrap_mean_difference, holm_adjust, run_inference


def observations():
    rows = []
    decisions = ["Cut"] * 4 + ["Hold"] * 13 + ["Hike"]
    means = np.array([-.01, -.015, -.004, -.02] + list(np.linspace(-.025, .035, 13)) + [.005])
    for i, (decision, value) in enumerate(zip(decisions, means)):
        for bank, kind, offset in (("A", "Public", .001 + i * .0001), ("B", "Private", -.001 - i * .0001)):
            rows.append({"event_id": f"E{i}", "event_date": pd.Timestamp("2023-01-01") + pd.Timedelta(days=i * 45),
                         "decision": decision, "bank_symbol": bank, "bank_type": kind,
                         "benchmark": "^NSEI", "window": "[-1,+1]", "car": value + offset})
    return pd.DataFrame(rows)


def test_welch_uses_four_and_thirteen_policy_events_not_bank_rows():
    data = observations()
    output = run_inference(data, n_bootstrap=200)
    result = output["decision_comparisons"].query("group_a == 'Cut' and group_b == 'Hold'").iloc[0]
    means = data.groupby(["event_id", "decision"]).car.mean().reset_index()
    expected = stats.ttest_ind(means.loc[means.decision.eq("Cut"), "car"],
                               means.loc[means.decision.eq("Hold"), "car"], equal_var=False)
    assert result.n_a_events == 4
    assert result.n_b_events == 13
    assert result.p_value == pytest.approx(expected.pvalue)
    assert output["overall_tests"].n_events.iloc[0] == 18


def test_replicating_banks_does_not_manufacture_additional_event_evidence():
    data = observations()
    copy = data.copy()
    copy["bank_symbol"] += "_copy"
    original = run_inference(data, n_bootstrap=100)["decision_comparisons"]
    repeated = run_inference(pd.concat([data, copy]), n_bootstrap=100)["decision_comparisons"]
    np.testing.assert_allclose(original.p_value, repeated.p_value, equal_nan=True)
    np.testing.assert_allclose(original.bootstrap_ci_lower, repeated.bootstrap_ci_lower, equal_nan=True)


def test_one_hike_is_descriptive_only_and_sector_contrasts_are_paired():
    output = run_inference(observations(), n_bootstrap=100)
    hike = output["decision_comparisons"].query("group_a == 'Hike'").iloc[0]
    assert hike.n_a_events == 1
    assert hike.status == "insufficient_events"
    assert np.isnan(hike.p_value) and np.isnan(hike.bootstrap_ci_lower)
    paired = output["paired_bank_comparisons"].query("outcome == 'car'").iloc[0]
    assert paired.n_events == 18
    assert paired["mean"] == pytest.approx(2 * np.mean(.001 + np.arange(18) * .0001))


def test_holm_and_event_bootstrap_are_reproducible():
    np.testing.assert_allclose(holm_adjust([.01, .04, .03, np.nan]), [.03, .06, .06, np.nan], equal_nan=True)
    a = bootstrap_mean_difference([-.02, -.01, 0, .01], [0, .02, .03], n_bootstrap=100, seed=9)
    b = bootstrap_mean_difference([-.02, -.01, 0, .01], [0, .02, .03], n_bootstrap=100, seed=9)
    assert a == b
    assert a["bootstrap_ci_lower"] < a["bootstrap_ci_upper"]


def test_duplicate_bank_event_rows_fail_instead_of_inflating_sample():
    data = observations()
    with pytest.raises(ValueError, match="Duplicate bank-event"):
        run_inference(pd.concat([data, data.iloc[[0]]]), n_bootstrap=20)
