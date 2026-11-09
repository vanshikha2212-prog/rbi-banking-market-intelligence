"""Integration checks for safe database builds, data identity, and CSV grain."""
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from rbi_intelligence import database


@pytest.fixture
def study_frames():
    events = pd.DataFrame([
        {"event_id": "hold", "event_date": "2024-12-06", "decision": "Hold", "repo_before": 6.5, "repo_after": 6.5, "rate_change_bps": 0},
        {"event_id": "cut", "event_date": "2025-02-07", "decision": "Cut", "repo_before": 6.5, "repo_after": 6.25, "rate_change_bps": -25},
    ])
    results, forecasts = [], []
    for event in events.to_dict("records"):
        for symbol, name, bank_type, car in [("A", "Alpha Bank", "Private", .01), ("B", "Beta Bank", "Public", -.02)]:
            for benchmark in ["^NSEI", "^NSEBANK"]:
                for window, n_event in [("[-1,+1]", 3), ("[-2,+2]", 5)]:
                    results.append({**event, "bank_symbol": symbol, "bank_name": name, "bank_type": bank_type, "benchmark": benchmark, "window": window, "car": car, "alpha": .0001, "beta": 1.0, "estimation_start": "2023-01-01", "estimation_end": "2024-01-01", "n_estimation": 250, "n_event": n_event})
            forecasts.append({"event_id": event["event_id"], "event_date": event["event_date"], "bank_symbol": symbol, "forecast_origin_date": str((pd.Timestamp(event["event_date"]) - pd.offsets.BDay(1)).date()), "forecast_target_date": event["event_date"], "garch_volatility": .02, "garch_variance": .0004, "converged": True, "convergence_flag": 0, "risk_level": "Medium", "n_training": 500})
    return events, pd.DataFrame(results), pd.DataFrame(forecasts)


def test_database_rerun_preserves_grain_and_foreign_keys(tmp_path, study_frames):
    path = tmp_path / "study.sqlite"
    for _ in range(2):
        database.build_database(path, *study_frames, manifest={"source": "test fixture"})
        with sqlite3.connect(path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM event_study_results").fetchone()[0] == 16
            assert connection.execute("SELECT COUNT(*) FROM volatility_forecasts").fetchone()[0] == 4
            assert connection.execute("SELECT COUNT(DISTINCT event_id) FROM event_explorer").fetchone()[0] == 2
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_invalid_input_cannot_replace_existing_database(tmp_path, study_frames):
    path = database.build_database(tmp_path / "study.sqlite", *study_frames)
    original = path.read_bytes()
    events, results, forecasts = study_frames
    duplicated = pd.concat([results, results.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate keys"):
        database.build_database(path, events, duplicated, forecasts)
    assert path.read_bytes() == original


def test_mid_build_failure_keeps_original_and_removes_temporary_file(tmp_path, study_frames, monkeypatch):
    path = database.build_database(tmp_path / "study.sqlite", *study_frames)
    original = path.read_bytes()
    real_insert = database._insert

    def fail_during_results(connection, table, frame, columns):
        if table == "event_study_results":
            raise sqlite3.IntegrityError("simulated insert failure")
        return real_insert(connection, table, frame, columns)

    monkeypatch.setattr(database, "_insert", fail_during_results)
    with pytest.raises(sqlite3.IntegrityError, match="simulated"):
        database.build_database(path, *study_frames)
    assert path.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["study.sqlite"]


@pytest.mark.parametrize("field,value,message", [
    ("forecast_origin_date", "2025-02-07", "origin must precede"),
    ("forecast_target_date", "2025-02-06", "target must be the event date"),
])
def test_forecasts_cannot_use_future_or_stale_alignment(study_frames, field, value, message):
    events, results, forecasts = study_frames
    forecasts.loc[forecasts.event_id == "cut", field] = value
    with pytest.raises(ValueError, match=message):
        database.validate_inputs(events, results, forecasts)


def test_result_event_date_must_match_corrected_event_table(study_frames):
    events, results, forecasts = study_frames
    results.loc[0, "event_date"] = "2024-12-09"
    with pytest.raises(ValueError, match="event_date disagrees"):
        database.validate_inputs(events, results, forecasts)


def test_exports_keep_window_and_event_units_explicit(tmp_path, study_frames):
    paths = database.export_dashboard_data(tmp_path, *study_frames)
    assert len(pd.read_csv(paths["event_explorer.csv"])) == 16
    means = pd.read_csv(paths["sas_event_means.csv"])
    rows = pd.read_csv(paths["sas_event_results.csv"])
    assert len(means) == 2
    assert len(rows) == 4
    assert "bank_type" in rows
    assert set(means.window) == {"[-1,+1]"}
    assert set(means.benchmark) == {"^NSEI"}
    assert means.bank_count.tolist() == [2, 2]
    assert means.mean_car.tolist() == pytest.approx([-.005, -.005])
    performance = pd.read_csv(paths["bank_performance.csv"])
    assert {"mean_car", "mean_absolute_car", "window"}.issubset(performance)
    assert "avg_car_1d" not in performance


def test_nonconverged_forecast_is_retained_as_unavailable(study_frames):
    events, results, forecasts = study_frames
    forecasts.loc[0, ["converged", "convergence_flag", "garch_volatility", "garch_variance"]] = [False, 1, None, None]
    validated = database.validate_inputs(events, results, forecasts)
    assert len(validated.forecasts) == 4
    assert validated.forecasts.loc[0, "risk_level"] == "Unavailable"


def test_sql_reports_execute_against_built_schema(tmp_path, study_frames):
    path = database.build_database(tmp_path / "study.sqlite", *study_frames)
    root = Path(__file__).resolve().parents[1]
    with sqlite3.connect(path) as connection:
        for name in ["analysis_queries.sql", "data_quality.sql", "risk_relationship.sql"]:
            connection.executescript((root / "sql" / name).read_text())
