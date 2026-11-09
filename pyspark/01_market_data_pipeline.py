"""Optional Spark implementation of bank returns and full-window summaries.

Run from the repository root after downloading and validating market prices:
    python pyspark/01_market_data_pipeline.py
Requires PySpark and a compatible Java runtime. This is a small-data learning
implementation; distributed execution is not necessary for this study's scale.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run_pipeline(input_path: Path, output_path: Path, master: str = "local[2]", partitions: int = 6) -> None:
    from pyspark.sql import SparkSession, functions as F
    from pyspark.sql.window import Window

    if not input_path.is_file():
        raise FileNotFoundError(f"Input not found: {input_path}")
    if partitions < 1:
        raise ValueError("partitions must be positive")
    spark = SparkSession.builder.appName("RBI bank returns validation").master(master).getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    staging = None
    backup = None
    try:
        frame = spark.read.option("header", True).csv(str(input_path))
        required = {"date", "symbol", "asset_type", "close"}
        if not required.issubset(frame.columns):
            raise ValueError(f"Missing input columns: {sorted(required - set(frame.columns))}")
        frame = frame.filter(F.lower(F.col("asset_type")) == "bank").select(
            F.to_date("date").alias("date"),
            F.col("symbol"),
            F.col("close").cast("double").alias("close"),
        )
        if frame.count() == 0:
            raise ValueError("No bank rows in input")
        invalid = frame.filter(F.col("date").isNull() | F.col("symbol").isNull() | (F.trim("symbol") == "") | F.col("close").isNull() | F.isnan("close") | (F.abs(F.col("close")) == float("inf")) | (F.col("close") <= 0))
        if invalid.limit(1).count():
            raise ValueError("Missing/invalid date, symbol, or positive close in bank prices")
        if frame.groupBy("date", "symbol").count().filter("count > 1").limit(1).count():
            raise ValueError("Duplicate (date, symbol) keys in bank prices")
        ordered = Window.partitionBy("symbol").orderBy("date")
        rolling = ordered.rowsBetween(-19, 0)
        frame = frame.withColumn("previous_close", F.lag("close").over(ordered))
        frame = frame.withColumn("daily_return", F.col("close") / F.col("previous_close") - 1.0)
        frame = frame.withColumn("rolling_observations_20d", F.count("daily_return").over(rolling))
        complete = F.col("rolling_observations_20d") == 20
        frame = frame.withColumn("rolling_mean_return_20d", F.when(complete, F.avg("daily_return").over(rolling)))
        frame = frame.withColumn("rolling_volatility_20d", F.when(complete, F.stddev_samp("daily_return").over(rolling)))
        result = frame.select("date", "symbol", "close", "daily_return", "rolling_mean_return_20d", "rolling_volatility_20d", "rolling_observations_20d")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".spark-build-", dir=output_path.parent))
        staged_output = staging / "returns"
        result.repartition(partitions, "symbol").write.mode("error").option("header", True).csv(str(staged_output))
        if output_path.exists():
            backup = staging / "previous"
            output_path.rename(backup)
        try:
            staged_output.rename(output_path)
        except BaseException:
            if backup is not None and backup.exists():
                backup.rename(output_path)
            raise
        print(f"Saved {result.count()} bank-price rows (including initial null returns) to {output_path}")
        print("20-day rolling features require 20 non-null returns; rolling_mean_return_20d is a daily-return mean, not a cumulative return.")
    finally:
        spark.stop()
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/raw/market_prices_2021_2025.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/spark/bank_returns")
    parser.add_argument("--master", default="local[2]")
    parser.add_argument("--partitions", type=int, default=6)
    args = parser.parse_args()
    run_pipeline(args.input, args.output, args.master, args.partitions)


if __name__ == "__main__":
    main()
