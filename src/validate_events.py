import pandas as pd

file_path = "data/raw/rbi_mpc_events_2023_2025.csv"
df = pd.read_csv(file_path)

date_columns = ["meeting_start", "meeting_end", "event_date"]
for column in date_columns:
    df[column] = pd.to_datetime(df[column])

print("\n--- DATASET ---")
print(df)
print("\n--- SHAPE ---")
print(df.shape)
print("\n--- COLUMNS ---")
print(df.columns.tolist())
print("\n--- DATA TYPES ---")
print(df.dtypes)
print("\n--- MISSING VALUES ---")
print(df.isna().sum())
print("\n--- DECISION COUNTS ---")
print(df["decision"].value_counts())
print("\n--- EVENTS BY YEAR ---")
print(df["event_date"].dt.year.value_counts().sort_index())

def check_data_quality(df):
    print("\n--- DATA QUALITY CHECKS ---")
    print("Number of events:", len(df))
    print("Duplicate event IDs:", df["event_id"].duplicated().sum())
    calculated_change = (df["repo_after"] - df["repo_before"]) * 100
    print("Incorrect rate changes:", (df["rate_change_bps"] != calculated_change).sum())
    valid_decisions = {"Hike", "Cut", "Hold"}
    print("Invalid decisions:", (~df["decision"].isin(valid_decisions)).sum())
    print("Invalid event dates:", df["event_date"].isna().sum())
    print("Missing repo rates:", (df["repo_before"].isna() | df["repo_after"].isna()).sum())

check_data_quality(df)
