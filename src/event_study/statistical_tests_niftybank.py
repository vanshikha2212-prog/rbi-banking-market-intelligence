"""Statistical tests for the Nifty Bank benchmark event study."""

from pathlib import Path

import pandas as pd
from scipy import stats


PROCESSED_DIR = Path("data/processed")

INPUT_FILE = (
    PROCESSED_DIR
    / "event_study_results_niftybank.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR
    / "statistical_results_niftybank.csv"
)


WINDOWS = {
    "[-1,+1]": "car_minus_1_plus_1",
    "[-2,+2]": "car_minus_2_plus_2",
    "[-5,+5]": "car_minus_5_plus_5",
}


def run_test(values):
    """Run one-sample t-test against zero."""

    values = values.dropna()

    statistic, p_value = stats.ttest_1samp(
        values,
        0,
    )

    mean = values.mean()

    standard_error = stats.sem(values)

    confidence_interval = stats.t.interval(
        0.95,
        len(values) - 1,
        loc=mean,
        scale=standard_error,
    )

    return {
        "n": len(values),
        "mean_car": mean,
        "t_statistic": statistic,
        "p_value": p_value,
        "ci_95_lower": confidence_interval[0],
        "ci_95_upper": confidence_interval[1],
    }


def main():
    """Run statistical tests."""

    results = pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )
    results = results.drop_duplicates(
    subset=[
        "event_id",
        "bank_symbol",
    ]
    )

    rows = []

    groups = {
        "All events": results,
        "Cut": results[
            results["decision"] == "Cut"
        ],
        "Hike": results[
            results["decision"] == "Hike"
        ],
        "Hold": results[
            results["decision"] == "Hold"
        ],
        "Private": results[
            results["bank_type"] == "Private"
        ],
        "Public": results[
            results["bank_type"] == "Public"
        ],
    }

    for window, column in WINDOWS.items():

        for group_name, group in groups.items():

            test = run_test(
                group[column]
            )

            rows.append(
                {
                    "group": group_name,
                    "event_window": window,
                    **test,
                }
            )

    output = pd.DataFrame(rows)

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\n--- NIFTY BANK STATISTICAL TESTS ---")
    print(
        output.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()