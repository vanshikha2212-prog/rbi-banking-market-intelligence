"""Train and evaluate a time-based Random Forest model."""

from pathlib import Path

import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)


PROCESSED_DIR = Path("data/processed")

INPUT_FILE = (
    PROCESSED_DIR / "predictive_features.csv"
)


FEATURES = [
    "bank_type",
    "decision",
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "volatility_60d",
    "garch_volatility",
]

TARGET = "positive_car"


CATEGORICAL_FEATURES = [
    "bank_type",
    "decision",
]

NUMERICAL_FEATURES = [
    "return_1d",
    "return_5d",
    "return_20d",
    "volatility_20d",
    "volatility_60d",
    "garch_volatility",
]


def main():
    """Load data, train Random Forest, and evaluate."""

    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )

    df = df.sort_values(
        "event_date"
    ).reset_index(drop=True)

    # --------------------------------------------------
    # TIME-BASED SPLIT
    # --------------------------------------------------

    train = df[
        df["event_date"].dt.year <= 2024
    ].copy()

    test = df[
        df["event_date"].dt.year == 2025
    ].copy()

    X_train = train[FEATURES]
    y_train = train[TARGET]

    X_test = test[FEATURES]
    y_test = test[TARGET]

    print("\n--- DATA SPLIT ---")

    print(
        "Training events:",
        train["event_id"].nunique(),
    )

    print(
        "Training rows:",
        len(train),
    )

    print(
        "Test events:",
        test["event_id"].nunique(),
    )

    print(
        "Test rows:",
        len(test),
    )

    # --------------------------------------------------
    # PREPROCESSING
    # --------------------------------------------------

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore"
                ),
                CATEGORICAL_FEATURES,
            ),
            (
                "numerical",
                "passthrough",
                NUMERICAL_FEATURES,
            ),
        ]
    )

    # --------------------------------------------------
    # RANDOM FOREST
    # --------------------------------------------------

    model = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=4,
                    min_samples_leaf=4,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    model.fit(
        X_train,
        y_train,
    )

    # --------------------------------------------------
    # PREDICTIONS
    # --------------------------------------------------

    predictions = model.predict(
        X_test
    )

    probabilities = model.predict_proba(
        X_test
    )[:, 1]

    # --------------------------------------------------
    # EVALUATION
    # --------------------------------------------------

    accuracy = accuracy_score(
        y_test,
        predictions,
    )

    balanced_accuracy = (
        balanced_accuracy_score(
            y_test,
            predictions,
        )
    )

    auc = roc_auc_score(
        y_test,
        probabilities,
    )

    print("\n--- RANDOM FOREST PERFORMANCE ---")

    print(
        "Accuracy:",
        round(accuracy, 4),
    )

    print(
        "Balanced Accuracy:",
        round(balanced_accuracy, 4),
    )

    print(
        "ROC-AUC:",
        round(auc, 4),
    )

    print("\n--- CONFUSION MATRIX ---")

    print(
        confusion_matrix(
            y_test,
            predictions,
        )
    )

    print("\n--- CLASSIFICATION REPORT ---")

    print(
        classification_report(
            y_test,
            predictions,
            zero_division=0,
        )
    )


if __name__ == "__main__":
    main()