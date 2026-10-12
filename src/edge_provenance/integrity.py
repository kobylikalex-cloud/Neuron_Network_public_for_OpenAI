"""Small, streaming SHA-256 helpers for ordinary files."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

_HEX_256 = re.compile(r"^[a-fA-F0-9]{64}$")


def file_sha256(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a raw *file-byte* SHA-256 checksum using bounded memory.

    This is NOT a semantic checksum: a byte-order, encoding, or row-order change
    may produce a different hash even if the economic meaning is unchanged.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def verify_file_sha256(path: str | Path, expected_sha256: str) -> bool:
    """Compare a file with an expected SHA-256 hex digest."""
    if not isinstance(expected_sha256, str) or not _HEX_256.fullmatch(expected_sha256):
        raise ValueError("expected_sha256 must be a 64-character hexadecimal string")
    return file_sha256(path) == expected_sha256.lower()
