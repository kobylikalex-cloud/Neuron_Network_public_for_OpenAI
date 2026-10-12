import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "edge_provenance", *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def test_workflow(tmp_path):
    path = tmp_path / "demo.csv"
    path.write_text("date,value\n2026-01-01,1\n2026-02-01,2\n")
    report_file = tmp_path / "report.json"
    r = cli("validate", path, "--date-column", "date", "--value-column", "value", "--frequency", "M", "--report", report_file)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["passed"] and json.loads(report_file.read_text())["passed"]

    checksum = cli("hash", path)
    assert checksum.returncode == 0 and len(checksum.stdout.strip()) == 64
    manifest = tmp_path / "sidecar.json"
    r = cli("record", path, "--dataset-id", "demo", "--source-url", "https://example.org/data", "--output", manifest)
    assert r.returncode == 0, r.stderr
    assert cli("verify", path, "--record", manifest).returncode == 0
    path.write_text("changed")
    r = cli("verify", path, "--record", manifest)
    assert r.returncode == 1 and "MISMATCH" in r.stdout


def test_failed_validation_and_error_exits(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("date,value\n2026-01-01,nope\n")
    r = cli("validate", path, "--date-column", "date", "--value-column", "value")
    assert r.returncode == 1 and json.loads(r.stdout)["error_count"] == 1
    r = cli("hash", tmp_path / "does_not_exist")
    assert r.returncode == 2 and "ERROR" in r.stderr
