import json

import pytest

from edge_provenance.integrity import file_sha256
from edge_provenance.provenance import ProvenanceRecord, make_record, read_record, verify_record, write_record
from edge_provenance.storage import atomic_write_json, read_json


def source(tmp_path):
    path = tmp_path / "synthetic.csv"
    path.write_text("date,value\n2026-01-01,1\n", encoding="utf-8")
    return path


def test_round_trip_and_integrity(tmp_path):
    path = source(tmp_path)
    record = make_record(
        path, dataset_id="synthetic-demo", source_url="https://example.org/data.csv",
        retrieved_at="2026-10-12T10:00:00+00:00", license_id="CC0-1.0",
    )
    assert record.content_sha256 == file_sha256(path)
    assert record.file_name == "synthetic.csv"
    assert record.file_size_bytes == path.stat().st_size
    manifest = tmp_path / "nested" / "record.json"
    write_record(manifest, record)
    assert read_record(manifest) == record
    assert verify_record(path, record)
    path.write_text("new file bytes")
    assert not verify_record(path, record)


def test_trust_boundaries(tmp_path):
    path = source(tmp_path)
    with pytest.raises(ValueError, match="HTTP"):
        make_record(path, dataset_id="x", source_url="file:///tmp/secret")
    with pytest.raises(ValueError, match="credentials"):
        make_record(path, dataset_id="x", source_url="https://user:password@example.org/file")
    with pytest.raises(ValueError, match="timezone"):
        make_record(path, dataset_id="x", source_url="https://example.org", retrieved_at="2026-01-01T00:00:00")
    with pytest.raises(ValueError, match="empty"):
        make_record(path, dataset_id="", source_url="https://example.org")


def test_sidecar_validation(tmp_path):
    path = source(tmp_path)
    record = make_record(path, dataset_id="demo", source_url="https://example.org", retrieved_at="2026-01-01T00:00:00Z")
    data = record.to_dict()
    for invalid in (
        {**data, "schema_version": 2},
        {**data, "file_size_bytes": -1},
        {**data, "file_name": "../another"},
        {**data, "content_sha256": "invalid"},
        {**data, "extra_private_field": "not permitted"},
    ):
        with pytest.raises(ValueError):
            ProvenanceRecord.from_dict(invalid)


def test_atomic_writer_and_json_errors(tmp_path):
    target = tmp_path / "manifest.json"
    atomic_write_json(target, {"x": 1})
    assert read_json(target) == {"x": 1}
    with pytest.raises(TypeError):
        atomic_write_json(target, {"not_serializable": object()})
    assert read_json(target) == {"x": 1}
    assert len(list(tmp_path.glob("*.tmp"))) == 0
    assert len(list(tmp_path.glob(".*.tmp"))) == 0


def test_metadata_does_not_accept_url_queries_or_paths(tmp_path):
    path = source(tmp_path)
    with pytest.raises(ValueError, match="query"):
        make_record(path, dataset_id="demo", source_url="https://example.org/file?token=hidden")
    with pytest.raises(ValueError, match="identifier"):
        make_record(path, dataset_id="../private", source_url="https://example.org")
    record = make_record(path, dataset_id="demo", source_url="https://example.org")
    with pytest.raises(ValueError, match="plain filename"):
        ProvenanceRecord.from_dict({**record.to_dict(), "file_name": r"C:\\private\\file.csv"})
