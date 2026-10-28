"""Analyze Random Forest feature importance."""

from pathlib import Path

import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier


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
    """Train Random Forest and display feature importance."""

    df = pd.read_csv(
        INPUT_FILE,
        parse_dates=["event_date"],
    )

    df = df.sort_values(
        "event_date"
    ).reset_index(drop=True)

    train = df[
        df["event_date"].dt.year <= 2024
    ].copy()

    X_train = train[FEATURES]
    y_train = train[TARGET]

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

    # Get transformed feature names.
    feature_names = (
        model
        .named_steps["preprocessor"]
        .get_feature_names_out()
    )

    importances = (
        model
        .named_steps["classifier"]
        .feature_importances_
    )

    importance_df = pd.DataFrame(
        {
            "feature": feature_names,
            "importance": importances,
        }
    ).sort_values(
        "importance",
        ascending=False,
    )

    print("\n--- FEATURE IMPORTANCE ---")

    print(
        importance_df.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()