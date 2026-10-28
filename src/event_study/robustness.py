"""Run robustness and subgroup comparisons for the RBI event study."""

from pathlib import Path

import pandas as pd
from scipy import stats


PROCESSED_DIR = Path("data/processed")

INPUT_FILE = PROCESSED_DIR / "event_study_results.csv"
OUTPUT_FILE = PROCESSED_DIR / "robustness_results.csv"

CAR_COLUMN = "car_minus_1_plus_1"

PRIVATE_BANKS = {
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "AXISBANK.NS",
}


def load_results():
    """Load event-study results."""

    return pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )


def add_bank_type(results):
    """Classify banks as private or public."""

    results = results.copy()

    results["bank_type"] = results[
        "bank_symbol"
    ].apply(
        lambda symbol:
        "Private"
        if symbol in PRIVATE_BANKS
        else "Public"
    )

    return results


def compare_groups(
    group_a,
    group_b,
    label_a,
    label_b,
):
    """Compare mean CAR between two independent groups."""

    values_a = group_a[CAR_COLUMN].dropna()
    values_b = group_b[CAR_COLUMN].dropna()

    statistic, p_value = stats.ttest_ind(
        values_a,
        values_b,
        equal_var=False,
    )

    return {
        "comparison": f"{label_a} vs {label_b}",
        "group_a": label_a,
        "group_b": label_b,
        "n_a": len(values_a),
        "n_b": len(values_b),
        "mean_a": values_a.mean(),
        "mean_b": values_b.mean(),
        "difference": values_a.mean() - values_b.mean(),
        "t_statistic": statistic,
        "p_value": p_value,
    }


def decision_comparisons(results):
    """Compare CAR between RBI decision categories."""

    rows = []

    groups = {
        decision: group
        for decision, group
        in results.groupby("decision")
    }

    comparisons = [
        ("Cut", "Hold"),
        ("Cut", "Hike"),
        ("Hold", "Hike"),
    ]

    for label_a, label_b in comparisons:

        if label_a not in groups or label_b not in groups:
            continue

        rows.append(
            compare_groups(
                groups[label_a],
                groups[label_b],
                label_a,
                label_b,
            )
        )

    return pd.DataFrame(rows)


def bank_type_comparison(results):
    """Compare private and public bank CARs."""

    private = results[
        results["bank_type"] == "Private"
    ]

    public = results[
        results["bank_type"] == "Public"
    ]

    result = compare_groups(
        private,
        public,
        "Private",
        "Public",
    )

    return pd.DataFrame([result])


def individual_event_analysis(results):
    """Summarize CAR by individual RBI event."""

    summary = (
        results
        .groupby(
            [
                "event_id",
                "event_date",
                "decision",
            ],
            as_index=False,
        )[CAR_COLUMN]
        .agg(
            mean_car="mean",
            median_car="median",
            std_car="std",
            min_car="min",
            max_car="max",
        )
    )

    return summary.sort_values(
        "mean_car"
    )


def main():
    """Run robustness analysis."""

    results = load_results()

    results = add_bank_type(results)

    decision_results = decision_comparisons(
        results
    )

    bank_type_results = bank_type_comparison(
        results
    )

    event_results = individual_event_analysis(
        results
    )

    decision_path = (
        PROCESSED_DIR
        / "decision_comparisons.csv"
    )

    bank_type_path = (
        PROCESSED_DIR
        / "bank_type_comparison.csv"
    )

    event_path = (
        PROCESSED_DIR
        / "individual_event_analysis.csv"
    )

    decision_results.to_csv(
        decision_path,
        index=False,
    )

    bank_type_results.to_csv(
        bank_type_path,
        index=False,
    )

    event_results.to_csv(
        event_path,
        index=False,
    )

    print("\n--- DECISION COMPARISONS ---")
    print(
        decision_results.to_string(
            index=False
        )
    )

    print("\n--- PRIVATE VS PUBLIC ---")
    print(
        bank_type_results.to_string(
            index=False
        )
    )

    print("\n--- INDIVIDUAL EVENT CARs ---")
    print(
        event_results.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(decision_path)
    print(bank_type_path)
    print(event_path)


if __name__ == "__main__":
    main()