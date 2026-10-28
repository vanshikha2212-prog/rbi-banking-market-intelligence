"""Bootstrap event-level Cut vs Hold CAR differences."""

from pathlib import Path

import numpy as np
import pandas as pd


PROCESSED_DIR = Path("data/processed")

INPUT_FILE = (
    PROCESSED_DIR / "event_level_results.csv"
)

OUTPUT_FILE = (
    PROCESSED_DIR / "bootstrap_results.csv"
)

N_BOOTSTRAPS = 10000
RANDOM_SEED = 42


def bootstrap_difference(
    cut_values,
    hold_values,
):
    """Bootstrap mean Cut minus Hold difference."""

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    differences = []

    for _ in range(N_BOOTSTRAPS):

        cut_sample = rng.choice(
            cut_values,
            size=len(cut_values),
            replace=True,
        )

        hold_sample = rng.choice(
            hold_values,
            size=len(hold_values),
            replace=True,
        )

        difference = (
            cut_sample.mean()
            - hold_sample.mean()
        )

        differences.append(difference)

    differences = np.array(
        differences
    )

    lower = np.percentile(
        differences,
        2.5,
    )

    upper = np.percentile(
        differences,
        97.5,
    )

    return (
        differences.mean(),
        lower,
        upper,
    )


def main():
    """Run bootstrap analysis."""

    results = pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )

    rows = []

    for benchmark in [
        "nifty50",
        "niftybank",
    ]:

        column = (
            "mean_car_nifty50"
            if benchmark == "nifty50"
            else "mean_car_niftybank"
        )

        cut_values = results[
            results["decision"] == "Cut"
        ][column].dropna().to_numpy()

        hold_values = results[
            results["decision"] == "Hold"
        ][column].dropna().to_numpy()

        mean_difference = (
            cut_values.mean()
            - hold_values.mean()
        )

        bootstrap_mean, lower, upper = (
            bootstrap_difference(
                cut_values,
                hold_values,
            )
        )

        rows.append(
            {
                "benchmark": benchmark,
                "n_cut_events": len(
                    cut_values
                ),
                "n_hold_events": len(
                    hold_values
                ),
                "observed_difference":
                    mean_difference,
                "bootstrap_mean":
                    bootstrap_mean,
                "ci_95_lower":
                    lower,
                "ci_95_upper":
                    upper,
            }
        )

    output = pd.DataFrame(rows)

    output.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print(
        "\n--- BOOTSTRAP RESULTS ---"
    )

    print(
        output.to_string(
            index=False
        )
    )

    print("\nSaved:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()