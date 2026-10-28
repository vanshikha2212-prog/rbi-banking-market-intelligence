from pathlib import Path

import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

PANDAS_FILE = (
    ROOT_DIR
    / "data"
    / "processed"
    / "bank_returns_2021_2025.csv"
)

SPARK_DIR = (
    ROOT_DIR
    / "data"
    / "processed"
    / "pyspark"
    / "bank_returns_spark"
)


# ============================================================
# 1. LOAD PANDAS OUTPUT
# ============================================================

pandas_df = pd.read_csv(PANDAS_FILE)

pandas_df["date"] = pd.to_datetime(pandas_df["date"])

pandas_df = pandas_df[
    ["date", "symbol", "return"]
].copy()

pandas_df = pandas_df.rename(
    columns={"return": "pandas_return"}
)


# ============================================================
# 2. LOAD SPARK OUTPUT
# ============================================================

spark_files = list(
    SPARK_DIR.glob("part-*.csv")
)

if not spark_files:
    raise FileNotFoundError(
        "No Spark CSV output found."
    )

spark_df = pd.read_csv(
    spark_files[0]
)

spark_df["date"] = pd.to_datetime(
    spark_df["date"]
)

spark_df = spark_df[
    ["date", "symbol", "daily_return"]
].copy()

spark_df = spark_df.rename(
    columns={"daily_return": "spark_return"}
)


# ============================================================
# 3. MERGE RESULTS
# ============================================================

comparison = pandas_df.merge(
    spark_df,
    on=["date", "symbol"],
    how="inner"
)


# ============================================================
# 4. CALCULATE DIFFERENCE
# ============================================================

comparison["absolute_difference"] = (
    comparison["pandas_return"]
    - comparison["spark_return"]
).abs()


# ============================================================
# 5. VALIDATION RESULTS
# ============================================================

print("\n--- VALIDATION RESULTS ---")

print(
    "Pandas observations:",
    len(pandas_df)
)

print(
    "Spark observations:",
    len(spark_df)
)

print(
    "Matched observations:",
    len(comparison)
)

print(
    "Maximum absolute difference:",
    comparison["absolute_difference"].max()
)

print(
    "Mean absolute difference:",
    comparison["absolute_difference"].mean()
)


# ============================================================
# 6. CHECK WHETHER RESULTS MATCH
# ============================================================

tolerance = 1e-10

max_difference = (
    comparison["absolute_difference"].max()
)

if max_difference < tolerance:

    print(
        "\nVALIDATION PASSED:"
        " Spark and Pandas returns match."
    )

else:

    print(
        "\nVALIDATION WARNING:"
        " Differences detected between Spark and Pandas."
    )


# ============================================================
# 7. SHOW LARGEST DIFFERENCES
# ============================================================

print(
    "\n--- LARGEST DIFFERENCES ---"
)

print(
    comparison
    .sort_values(
        "absolute_difference",
        ascending=False
    )
    .head(10)
    .to_string(index=False)
)