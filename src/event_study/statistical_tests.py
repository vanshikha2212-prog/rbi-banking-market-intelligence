"""Test whether RBI-event abnormal returns are statistically significant."""

from pathlib import Path

import pandas as pd
from scipy import stats


PROCESSED_DIR = Path("data/processed")

INPUT_FILE = PROCESSED_DIR / "event_study_results.csv"
OUTPUT_FILE = PROCESSED_DIR / "statistical_results.csv"


CAR_COLUMNS = {
    "[-1,+1]": "car_minus_1_plus_1",
    "[-2,+2]": "car_minus_2_plus_2",
    "[-5,+5]": "car_minus_5_plus_5",
}


def load_results() -> pd.DataFrame:
    """Load event-study CAR results."""

    return pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )


def run_ttest(
    data: pd.DataFrame,
    column: str,
) -> dict:
    """Run a one-sample t-test of CAR against zero."""

    values = data[column].dropna()

    n = len(values)
    mean = values.mean()
    std = values.std(ddof=1)

    t_stat, p_value = stats.ttest_1samp(
        values,
        popmean=0,
    )

    standard_error = std / (n ** 0.5)

    confidence_interval = stats.t.interval(
        confidence=0.95,
        df=n - 1,
        loc=mean,
        scale=standard_error,
    )

    return {
        "n": n,
        "mean_car": mean,
        "std_car": std,
        "standard_error": standard_error,
        "t_statistic": t_stat,
        "p_value": p_value,
        "ci_95_lower": confidence_interval[0],
        "ci_95_upper": confidence_interval[1],
    }


def overall_tests(results: pd.DataFrame) -> pd.DataFrame:
    """Calculate overall significance tests for each event window."""

    rows = []

    for window_name, column in CAR_COLUMNS.items():

        result = run_ttest(
            results,
            column,
        )

        result["analysis"] = "Overall"
        result["group"] = "All events"
        result["event_window"] = window_name

        rows.append(result)

    return pd.DataFrame(rows)


def decision_tests(results: pd.DataFrame) -> pd.DataFrame:
    """Calculate CAR significance by RBI decision."""

    rows = []

    for decision, group in results.groupby("decision"):

        for window_name, column in CAR_COLUMNS.items():

            result = run_ttest(
                group,
                column,
            )

            result["analysis"] = "Decision"
            result["group"] = decision
            result["event_window"] = window_name

            rows.append(result)

    return pd.DataFrame(rows)


def bank_type_tests(results: pd.DataFrame) -> pd.DataFrame:
    """Calculate CAR significance for public and private banks."""

    private_banks = {
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "AXISBANK.NS",
    }

    results = results.copy()

    results["bank_type"] = results[
        "bank_symbol"
    ].apply(
        lambda symbol:
        "Private"
        if symbol in private_banks
        else "Public"
    )

    rows = []

    for bank_type, group in results.groupby(
        "bank_type"
    ):

        for window_name, column in CAR_COLUMNS.items():

            result = run_ttest(
                group,
                column,
            )

            result["analysis"] = "Bank Type"
            result["group"] = bank_type
            result["event_window"] = window_name

            rows.append(result)

    return pd.DataFrame(rows)


def main():
    """Run all statistical tests and save results."""

    results = load_results()

    overall = overall_tests(results)
    decisions = decision_tests(results)
    bank_types = bank_type_tests(results)

    statistical_results = pd.concat(
        [
            overall,
            decisions,
            bank_types,
        ],
        ignore_index=True,
    )

    statistical_results.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print("\n--- STATISTICAL TEST RESULTS ---")

    print(
        statistical_results[
            [
                "analysis",
                "group",
                "event_window",
                "n",
                "mean_car",
                "t_statistic",
                "p_value",
                "ci_95_lower",
                "ci_95_upper",
            ]
        ].to_string(index=False)
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()