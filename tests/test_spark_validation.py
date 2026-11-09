"""Regression tests for full-partition Spark/Pandas equivalence checks."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "pyspark/02_validate_against_pandas.py"
SPEC = importlib.util.spec_from_file_location("spark_validation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@pytest.fixture
def return_files(tmp_path):
    pandas_path = tmp_path / "panel.csv"
    directory = tmp_path / "parts"
    directory.mkdir()
    pd.DataFrame({"date": ["2025-01-01", "2025-01-02", "2025-01-03"], "symbol": ["A"] * 3, "return": [None, .01, -.02]}).to_csv(pandas_path, index=False)
    pd.DataFrame({"date": ["2025-01-01", "2025-01-02"], "symbol": ["A"] * 2, "daily_return": [None, .01]}).to_csv(directory / "part-000.csv", index=False)
    pd.DataFrame({"date": ["2025-01-03"], "symbol": ["A"], "daily_return": [-.02]}).to_csv(directory / "part-001.csv", index=False)
    return pandas_path, directory


def test_reads_all_partitions_and_accounts_for_initial_nulls(return_files):
    result = MODULE.validate_returns(*return_files)
    assert result["matched_rows"] == 3
    assert result["parts_read"] == 2
    assert result["non_null_returns"] == 2
    assert result["initial_null_returns"] == 1


def test_missing_partition_fails_full_key_coverage(return_files):
    path, directory = return_files
    (directory / "part-001.csv").unlink()
    with pytest.raises(ValueError, match="Incomplete key coverage"):
        MODULE.validate_returns(path, directory)


def test_duplicate_keys_fail_instead_of_multiplying_matches(return_files):
    path, directory = return_files
    (directory / "part-002.csv").write_text((directory / "part-001.csv").read_text())
    with pytest.raises(ValueError, match="duplicate"):
        MODULE.validate_returns(path, directory)


def test_return_missingness_cannot_be_hidden_by_inner_join(return_files):
    path, directory = return_files
    part = pd.read_csv(directory / "part-000.csv")
    part.loc[0, "daily_return"] = .0
    part.to_csv(directory / "part-000.csv", index=False)
    with pytest.raises(ValueError, match="missing-return masks differ"):
        MODULE.validate_returns(path, directory)


def test_numeric_mismatch_returns_nonzero_exit(return_files):
    path, directory = return_files
    frame = pd.read_csv(directory / "part-001.csv")
    frame["daily_return"] = .25
    frame.to_csv(directory / "part-001.csv", index=False)
    completed = subprocess.run([sys.executable, str(SCRIPT), "--pandas", str(path), "--spark-dir", str(directory)], capture_output=True, text=True)
    assert completed.returncode != 0
    assert '"status": "failed"' in completed.stderr
