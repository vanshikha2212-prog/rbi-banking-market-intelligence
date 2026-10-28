import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

DATA_DIR = BASE_DIR / "data" / "processed"
OUTPUT_DIR = BASE_DIR / "outputs" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load event-study results
df = pd.read_csv(DATA_DIR / "event_study_results.csv")

# Convert CAR from decimal to percentage
df["car_pct"] = df["car_minus_1_plus_1"] * 100

# Average CAR by RBI decision
decision_order = ["Cut", "Hold", "Hike"]

summary = (
    df.groupby("decision", observed=True)["car_pct"]
    .mean()
    .reindex(decision_order)
)

# Create figure
plt.figure(figsize=(9, 6))

summary.plot(kind="bar")

plt.axhline(0, linewidth=1)

plt.title("Average Abnormal Return by RBI Policy Decision")
plt.xlabel("RBI Policy Decision")
plt.ylabel("Average CAR [-1,+1] (%)")
plt.xticks(rotation=0)

plt.tight_layout()

output_path = OUTPUT_DIR / "car_by_policy_decision.png"
plt.savefig(output_path, dpi=300, bbox_inches="tight")
plt.close()

print("Figure saved to:")
print(output_path)

print("\nValues:")
print(summary)


# ---------------------------------------------------------
# Figure 2: Public vs Private Bank CAR
# ---------------------------------------------------------

bank_type_df = pd.read_csv(
    DATA_DIR / "bank_type_comparison.csv"
)

row = bank_type_df.iloc[0]

bank_type_summary = pd.Series(
    {
        row["group_a"]: row["mean_a"] * 100,
        row["group_b"]: row["mean_b"] * 100,
    }
)

plt.figure(figsize=(9, 6))

bank_type_summary.plot(kind="bar")

plt.axhline(0, linewidth=1)

plt.title("Average Abnormal Return by Bank Type")
plt.xlabel("Bank Type")
plt.ylabel("Average CAR [-1,+1] (%)")
plt.xticks(rotation=0)

plt.tight_layout()

output_path = OUTPUT_DIR / "car_by_bank_type.png"
plt.savefig(output_path, dpi=300, bbox_inches="tight")
plt.close()

print("\nFigure 2 saved to:")
print(output_path)

print("\nBank type values:")
print(bank_type_summary)

print(f"\nPrivate vs Public p-value: {row['p_value']:.6f}")

# ---------------------------------------------------------
# Figure 3: GARCH Volatility by Bank
# ---------------------------------------------------------

risk_df = pd.read_csv(
    DATA_DIR / "event_risk_analysis.csv"
)

bank_volatility = (
    risk_df.groupby("bank_symbol")["garch_volatility"]
    .mean()
    .sort_values(ascending=True)
)

# Convert decimal volatility to percentage
bank_volatility_pct = bank_volatility * 100

# Cleaner bank names
bank_names = {
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "AXISBANK.NS": "Axis Bank",
    "SBIN.NS": "SBI",
    "BANKBARODA.NS": "Bank of Baroda",
    "CANBK.NS": "Canara Bank",
}

bank_volatility_pct.index = [
    bank_names.get(symbol, symbol)
    for symbol in bank_volatility_pct.index
]

plt.figure(figsize=(10, 6))

bank_volatility_pct.plot(kind="barh")

plt.title("Average GARCH Volatility by Bank")
plt.xlabel("Average Conditional Volatility (%)")
plt.ylabel("Bank")

plt.tight_layout()

output_path = OUTPUT_DIR / "garch_volatility_by_bank.png"
plt.savefig(output_path, dpi=300, bbox_inches="tight")
plt.close()

print("\nFigure 3 saved to:")
print(output_path)

print("\nAverage GARCH volatility:")
print(bank_volatility_pct)