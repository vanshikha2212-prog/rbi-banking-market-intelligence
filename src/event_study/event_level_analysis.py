"""Run event-level inference for the RBI event study."""

from pathlib import Path

import pandas as pd
from scipy import stats


PROCESSED_DIR = Path("data/processed")

NIFTY50_FILE = (
    PROCESSED_DIR / "event_study_results.csv"
)

NIFTYBANK_FILE = (
    PROCESSED_DIR / "event_study_results_niftybank.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "event_level_results.csv"
)


CAR_COLUMN = "car_minus_1_plus_1"


def load_event_level_data(file_path):
    """Aggregate bank CARs to one observation per RBI event."""

    results = pd.read_csv(
        file_path,
        parse_dates=["event_date"],
    )

    event_level = (
        results
        .drop_duplicates(
            subset=["event_id", "bank_symbol"]
        )
        .groupby(
            [
                "event_id",
                "event_date",
                "decision",
            ],
            as_index=False,
        )[CAR_COLUMN]
        .mean()
        .rename(
            columns={
                CAR_COLUMN: "mean_car"
            }
        )
    )

    return event_level


def test_against_zero(values):
    """Test whether mean event CAR differs from zero."""

    values = values.dropna()

    statistic, p_value = stats.ttest_1samp(
        values,
        0,
    )

    mean = values.mean()

    standard_error = stats.sem(values)

    ci = stats.t.interval(
        0.95,
        len(values) - 1,
        loc=mean,
        scale=standard_error,
    )

    return {
        "n_events": len(values),
        "mean_car": mean,
        "t_statistic": statistic,
        "p_value": p_value,
        "ci_95_lower": ci[0],
        "ci_95_upper": ci[1],
    }


def compare_decisions(
    event_level,
    decision_a,
    decision_b,
):
    """Compare event-level CARs between two decisions."""

    a = event_level[
        event_level["decision"] == decision_a
    ]["mean_car"].dropna()

    b = event_level[
        event_level["decision"] == decision_b
    ]["mean_car"].dropna()

    statistic, p_value = stats.ttest_ind(
        a,
        b,
        equal_var=False,
    )

    return {
        "comparison": (
            f"{decision_a} vs {decision_b}"
        ),
        "n_a": len(a),
        "n_b": len(b),
        "mean_a": a.mean(),
        "mean_b": b.mean(),
        "difference": a.mean() - b.mean(),
        "t_statistic": statistic,
        "p_value": p_value,
    }


def main():
    """Run event-level analysis."""

    nifty50 = load_event_level_data(
        NIFTY50_FILE
    )

    niftybank = load_event_level_data(
        NIFTYBANK_FILE
    )

    print("\n--- NIFTY 50 EVENT-LEVEL RESULTS ---")

    overall_50 = test_against_zero(
        nifty50["mean_car"]
    )

    print(
        "Overall:",
        overall_50
    )

    print(
        "\nCut vs Hold:",
        compare_decisions(
            nifty50,
            "Cut",
            "Hold",
        )
    )

    print(
        "\nEvent-level CARs:"
    )

    print(
        nifty50.sort_values(
            "event_date"
        ).to_string(
            index=False
        )
    )

    print("\n--- NIFTY BANK EVENT-LEVEL RESULTS ---")

    overall_bank = test_against_zero(
        niftybank["mean_car"]
    )

    print(
        "Overall:",
        overall_bank
    )

    print(
        "\nCut vs Hold:",
        compare_decisions(
            niftybank,
            "Cut",
            "Hold",
        )
    )

    print(
        "\nEvent-level CARs:"
    )

    print(
        niftybank.sort_values(
            "event_date"
        ).to_string(
            index=False
        )
    )

    combined = nifty50.merge(
        niftybank,
        on=[
            "event_id",
            "event_date",
            "decision",
        ],
        suffixes=(
            "_nifty50",
            "_niftybank",
        ),
    )

    combined.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()