"""Compare predictive model performance against simple baselines."""

from pathlib import Path

import pandas as pd

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    roc_auc_score,
)


PROCESSED_DIR = Path("data/processed")

INPUT_FILE = (
    PROCESSED_DIR / "predictive_features.csv"
)


TARGET = "positive_car"


def main():
    """Evaluate simple baselines on the 2025 test period."""

    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )

    df = df.sort_values(
        "event_date"
    ).reset_index(drop=True)

    # Same test period used by the logistic model.
    train = df[
        df["event_date"].dt.year <= 2024
    ]

    test = df[
        df["event_date"].dt.year == 2025
    ]

    y_train = train[TARGET]
    y_test = test[TARGET]

    print("\n--- BASELINE COMPARISON ---")

    print(
        "Training positive rate:",
        round(y_train.mean(), 4),
    )

    print(
        "Test positive rate:",
        round(y_test.mean(), 4),
    )

    # --------------------------------------------------
    # MAJORITY CLASS BASELINE
    # --------------------------------------------------

    majority_class = int(
        y_train.mean() >= 0.5
    )

    majority_predictions = [
        majority_class
    ] * len(y_test)

    majority_probabilities = [
        y_train.mean()
    ] * len(y_test)

    majority_accuracy = accuracy_score(
        y_test,
        majority_predictions,
    )

    majority_balanced_accuracy = (
        balanced_accuracy_score(
            y_test,
            majority_predictions,
        )
    )

    majority_auc = roc_auc_score(
        y_test,
        majority_probabilities,
    )

    print("\nMajority-class baseline")

    print(
        "Accuracy:",
        round(majority_accuracy, 4),
    )

    print(
        "Balanced Accuracy:",
        round(
            majority_balanced_accuracy,
            4,
        ),
    )

    print(
        "ROC-AUC:",
        round(majority_auc, 4),
    )

    # --------------------------------------------------
    # RANDOM 50% BASELINE
    # --------------------------------------------------

    random_probabilities = [
        0.5
    ] * len(y_test)

    random_auc = roc_auc_score(
        y_test,
        random_probabilities,
    )

    print("\nRandom probability baseline")

    print(
        "ROC-AUC:",
        round(random_auc, 4),
    )

    print("\n--- INTERPRETATION ---")

    print(
        "The logistic regression should be "
        "compared against these baselines."
    )

    print(
        "A useful model should demonstrate "
        "meaningful improvement over a trivial baseline."
    )


if __name__ == "__main__":
    main()