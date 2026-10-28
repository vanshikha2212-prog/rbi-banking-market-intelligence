"""Train and evaluate a time-based logistic regression model."""

from pathlib import Path

import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
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
    """Load data, split by event date, train, and evaluate."""

    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )

    # Sort chronologically.
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

    print(
        "Training period:",
        train["event_date"].min().date(),
        "to",
        train["event_date"].max().date(),
    )

    print(
        "Test period:",
        test["event_date"].min().date(),
        "to",
        test["event_date"].max().date(),
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
                StandardScaler(),
                NUMERICAL_FEATURES,
            ),
        ]
    )

    # --------------------------------------------------
    # LOGISTIC REGRESSION
    # --------------------------------------------------

    model = Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000
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

    print("\n--- MODEL PERFORMANCE ---")

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