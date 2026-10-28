"""Evaluate Random Forest feature importance on the unseen test set."""

from pathlib import Path

import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score


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
    """Train on 2023-2024 and evaluate feature importance on 2025."""

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

    # --------------------------------------------------
    # MODEL
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
    # BASELINE TEST PERFORMANCE
    # --------------------------------------------------

    baseline_probability = model.predict_proba(
        X_test
    )[:, 1]

    baseline_auc = roc_auc_score(
        y_test,
        baseline_probability,
    )

    print("\n--- TEST SET PERFORMANCE ---")

    print(
        "Baseline ROC-AUC:",
        round(baseline_auc, 4),
    )

    # --------------------------------------------------
    # PERMUTATION IMPORTANCE
    # --------------------------------------------------

    result = permutation_importance(
        model,
        X_test,
        y_test,
        scoring="roc_auc",
        n_repeats=30,
        random_state=42,
    )

    importance_df = pd.DataFrame(
        {
            "feature": X_test.columns,
            "importance_mean":
                result.importances_mean,
            "importance_std":
                result.importances_std,
        }
    ).sort_values(
        "importance_mean",
        ascending=False,
    )

    print(
        "\n--- OUT-OF-SAMPLE PERMUTATION IMPORTANCE ---"
    )

    print(
        importance_df.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()