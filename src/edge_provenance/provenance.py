"""Minimal provenance sidecars with explicit source and integrity metadata."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import urlsplit

from .integrity import file_sha256
from .storage import atomic_write_json, read_json


@dataclass(frozen=True)
class ProvenanceRecord:
    schema_version: int
    dataset_id: str
    source_url: str
    retrieved_at: str
    file_name: str
    file_size_bytes: int
    content_sha256: str
    license_id: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("Unsupported schema version")
        if not isinstance(self.dataset_id, str) or not self.dataset_id.strip():
            raise ValueError("dataset_id must not be empty")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.dataset_id):
            raise ValueError("dataset_id must be a simple ASCII identifier")
        if (
            not isinstance(self.file_name, str) or not self.file_name
            or Path(self.file_name).name != self.file_name
            or "\\" in self.file_name or self.file_name in {".", ".."}
        ):
            raise ValueError("file_name must be a plain filename")
        if type(self.file_size_bytes) is not int or self.file_size_bytes < 0:
            raise ValueError("file_size_bytes must be nonnegative")
        if (not isinstance(self.content_sha256, str) or len(self.content_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.content_sha256)):
            raise ValueError("content_sha256 must be lowercase SHA-256")
        if not isinstance(self.source_url, str):
            raise ValueError("source_url must be a string")
        try:
            url = urlsplit(self.source_url)
            hostname = url.hostname
        except ValueError as exc:
            raise ValueError("source_url is malformed") from exc
        if url.scheme not in {"http", "https"} or not hostname or url.username or url.password:
            raise ValueError("source_url must be a valid HTTP(S) URL without embedded credentials")
        if url.query or url.fragment:
            raise ValueError("source_url must omit query parameters and fragments (may contain secrets)")
        try:
            stamp = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("retrieved_at must be an ISO 8601 timestamp") from exc
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("retrieved_at requires timezone information")
        if self.license_id is not None and (not isinstance(self.license_id, str) or len(self.license_id) > 128):
            raise ValueError("license_id must be a short text identifier")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProvenanceRecord":
        if not isinstance(data, dict):
            raise ValueError("Provenance sidecar must be a JSON object")
        try:
            return cls(**data)
        except TypeError as exc:
            raise ValueError("Provenance sidecar has missing or unexpected fields") from exc


def make_record(
    path: str | Path, *, dataset_id: str, source_url: str,
    retrieved_at: str | None = None, license_id: str | None = None,
) -> ProvenanceRecord:
    """Describe a local file and where it was obtained.

    Metadata is asserted by the caller, not independently verified. A checksum
    detects changed bytes, not whether a source is authoritative or accurate.
    """
    source = Path(path)
    stat = source.stat()
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    return ProvenanceRecord(
        schema_version=1, dataset_id=dataset_id, source_url=source_url,
        retrieved_at=timestamp, file_name=source.name,
        file_size_bytes=stat.st_size, content_sha256=file_sha256(source),
        license_id=license_id,
    )


def write_record(path: str | Path, record: ProvenanceRecord) -> Path:
    return atomic_write_json(path, record.to_dict())


def read_record(path: str | Path) -> ProvenanceRecord:
    return ProvenanceRecord.from_dict(read_json(path))


def verify_record(path: str | Path, record: ProvenanceRecord) -> bool:
    """Verify filename, file size and raw byte checksum match a sidecar."""
    source = Path(path)
    return (
        source.name == record.file_name
        and source.stat().st_size == record.file_size_bytes
        and file_sha256(source) == record.content_sha256
    )
