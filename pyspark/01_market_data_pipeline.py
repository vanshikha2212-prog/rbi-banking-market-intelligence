from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    lag,
    avg,
    stddev,
    round as spark_round,
)
from pyspark.sql.window import Window


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "raw"
    / "bank_prices_2021_2025.csv"
)

OUTPUT_DIR = (
    ROOT_DIR
    / "data"
    / "processed"
    / "pyspark"
)


# ============================================================
# START SPARK
# ============================================================

spark = (
    SparkSession.builder
    .appName("RBI Banking Market Intelligence")
    .master("local[*]")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")


# ============================================================
# 1. LOAD MARKET DATA
# ============================================================

df = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(str(INPUT_FILE))
)

print("\n--- RAW DATA ---")
print("Rows:", df.count())
print("Columns:", len(df.columns))

df.printSchema()


# ============================================================
# 2. SELECT REQUIRED COLUMNS
# ============================================================

df = df.select(
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


# ============================================================
# 3. REMOVE INVALID OBSERVATIONS
# ============================================================

df = df.dropna(
    subset=[
        "date",
        "symbol",
        "close",
    ]
)


# ============================================================
# 4. CALCULATE DAILY RETURNS
# ============================================================

window_spec = (
    Window
    .partitionBy("symbol")
    .orderBy("date")
)

df = df.withColumn(
    "previous_close",
    lag("close").over(window_spec)
)

df = df.withColumn(
    "daily_return",
    (col("close") / col("previous_close")) - 1
)


# ============================================================
# 5. CALCULATE ROLLING STATISTICS
# ============================================================

rolling_window = (
    Window
    .partitionBy("symbol")
    .orderBy("date")
    .rowsBetween(-19, 0)
)

df = df.withColumn(
    "rolling_return_20d",
    avg("daily_return").over(rolling_window)
)

df = df.withColumn(
    "rolling_volatility_20d",
    stddev("daily_return").over(rolling_window)
)


# ============================================================
# 6. SELECT FINAL OUTPUT
# ============================================================

result = df.select(
    "date",
    "symbol",
    "close",
    "daily_return",
    "rolling_return_20d",
    "rolling_volatility_20d",
)


# ============================================================
# 7. DISPLAY SAMPLE
# ============================================================

print("\n--- TRANSFORMED DATA ---")

result.orderBy(
    "symbol",
    "date"
).show(20, truncate=False)


# ============================================================
# 8. BANK-LEVEL SUMMARY
# ============================================================

summary = (
    result
    .groupBy("symbol")
    .agg(
        spark_round(avg("daily_return") * 100, 4)
        .alias("avg_daily_return_pct"),

        spark_round(
            avg("rolling_volatility_20d") * 100,
            4
        )
        .alias("avg_20d_volatility_pct"),
    )
    .orderBy(col("avg_20d_volatility_pct").desc())
)

print("\n--- BANK SUMMARY ---")

summary.show(
    truncate=False
)


# ============================================================
# 9. SAVE SPARK OUTPUT
# ============================================================

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

(
    result
    .write
    .mode("overwrite")
    .option("header", True)
    .csv(str(OUTPUT_DIR / "bank_returns_spark"))
)

(
    summary
    .write
    .mode("overwrite")
    .option("header", True)
    .csv(str(OUTPUT_DIR / "bank_summary_spark"))
)


print("\n--- PYSPARK PIPELINE COMPLETE ---")

spark.stop()