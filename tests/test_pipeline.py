"""Integrity verification and safe publication are independent of model quality."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from rbi_intelligence.data import sha256_file
from rbi_intelligence.pipeline import _publish_directory, run_project, verify_outputs


@pytest.fixture
def recorded_run(tmp_path):
    root = tmp_path / "project"
    output = root / "outputs"
    output.mkdir(parents=True)
    (root / "data/raw").mkdir(parents=True)
    (root / "rbi_intelligence").mkdir()
    report = output / "RESEARCH_REPORT.md"
    source = root / "data/raw/events.csv"
    code = root / "rbi_intelligence/analysis.py"
    report.write_text("An evidenced research result.\n")
    source.write_text("event_id,event_date\nevent,2025-08-06\n")
    code.write_text("METHOD_VERSION = 2\n")
    manifest = {
        "artifacts_sha256": {"RESEARCH_REPORT.md": sha256_file(report)},
        "inputs_sha256": {"data/raw/events.csv": sha256_file(source)},
        "analysis_code_sha256": {"rbi_intelligence/analysis.py": sha256_file(code)},
    }
    (output / "run_manifest.json").write_text(json.dumps(manifest))
    return root, output, manifest


def test_verify_reports_exact_checked_scope(recorded_run):
    root, output, _ = recorded_run
    result = verify_outputs(root, output)
    assert result == {"status": "ok", "files_checked": 3, "local_regenerable_files_checked": 0, "database_present": False}


@pytest.mark.parametrize("relative", ["outputs/RESEARCH_REPORT.md", "data/raw/events.csv", "rbi_intelligence/analysis.py"])
def test_verify_rejects_artifact_input_or_analysis_changes(recorded_run, relative):
    root, output, _ = recorded_run
    path = root / relative
    path.write_text(path.read_text() + "changed\n")
    with pytest.raises(ValueError, match="Missing or changed file"):
        verify_outputs(root, output)


def test_verify_rejects_missing_analysis_source(recorded_run):
    root, output, _ = recorded_run
    (root / "rbi_intelligence/analysis.py").unlink()
    with pytest.raises(ValueError, match="Missing or changed file"):
        verify_outputs(root, output)


def test_verify_rejects_paths_outside_manifest_root(recorded_run):
    root, output, manifest = recorded_run
    outsider = root.parent / "outside.txt"
    outsider.write_text("outside")
    manifest["analysis_code_sha256"] = {"../outside.txt": sha256_file(outsider)}
    (output / "run_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="leaves its root"):
        verify_outputs(root, output)


def test_optional_database_is_checked_when_present(recorded_run):
    root, output, manifest = recorded_run
    database = output / "study.sqlite"
    database.write_bytes(b"database fixture")
    manifest["local_regenerable_artifacts_sha256"] = {"study.sqlite": sha256_file(database)}
    (output / "run_manifest.json").write_text(json.dumps(manifest))
    assert verify_outputs(root, output)["local_regenerable_files_checked"] == 1
    database.write_bytes(b"changed database")
    with pytest.raises(ValueError, match="Changed local artifact"):
        verify_outputs(root, output)
    database.unlink()
    assert verify_outputs(root, output)["database_present"] is False


def test_failed_output_install_restores_complete_previous_run(tmp_path, monkeypatch):
    destination, staging = tmp_path / "outputs", tmp_path / "stage"
    destination.mkdir()
    staging.mkdir()
    (destination / "report.md").write_text("previous complete run")
    (destination / "manifest.json").write_text("previous manifest")
    (staging / "report.md").write_text("new run")
    original_rename = Path.rename

    def fail_install(path, target):
        if path == staging:
            raise PermissionError("simulated stage installation failure")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_install)
    with pytest.raises(PermissionError, match="stage installation"):
        _publish_directory(staging, destination)
    assert (destination / "report.md").read_text() == "previous complete run"
    assert (destination / "manifest.json").read_text() == "previous manifest"
    assert not list(tmp_path.glob(".outputs-backup-*"))


def test_successful_publication_replaces_whole_run(tmp_path):
    destination, staging = tmp_path / "outputs", tmp_path / "stage"
    destination.mkdir()
    staging.mkdir()
    (destination / "stale.csv").write_text("old")
    (staging / "new.csv").write_text("new")
    _publish_directory(staging, destination)
    assert not (destination / "stale.csv").exists()
    assert (destination / "new.csv").read_text() == "new"
    assert not list(tmp_path.glob(".outputs-backup-*"))


@pytest.mark.parametrize("relative", ["data/raw/rebuild", "rbi_intelligence/generated", "tests/rebuild", "docs/generated", "sql/generated", "pyspark/generated", "sas/generated", "tableau/generated", ".git/generated", ".github/generated", ".venv/generated"])
def test_output_cannot_replace_descendants_of_source_directories(tmp_path, relative):
    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(ValueError, match="dedicated generated-output"):
        run_project(root, root / relative)
    assert not (root / relative).exists()


def test_cli_propagates_value_error_to_nonzero_exit():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, "-m", "rbi_intelligence", "run", "--output-dir", str(root)], cwd=root, capture_output=True, text=True)
    assert completed.returncode == 1
    assert "Build failed:" in completed.stderr
    assert "dedicated generated-output" in completed.stderr
