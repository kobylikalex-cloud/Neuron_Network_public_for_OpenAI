import hashlib

import pytest

from edge_provenance.integrity import file_sha256, verify_file_sha256


def test_file_hash_matches_standard_library(tmp_path):
    data = b"\x00abc\x80" * 1000
    path = tmp_path / "content.bin"
    path.write_bytes(data)
    assert file_sha256(path, chunk_size=17) == hashlib.sha256(data).hexdigest()
    assert verify_file_sha256(path, hashlib.sha256(data).hexdigest().upper())
    assert file_sha256(path) != hashlib.sha256(b"different").hexdigest()


def test_checksum_validation_and_changes(tmp_path):
    path = tmp_path / "content.txt"
    path.write_text("original")
    sha = file_sha256(path)
    path.write_text("modified")
    assert not verify_file_sha256(path, sha)
    with pytest.raises(ValueError, match="64-character"):
        verify_file_sha256(path, "wrong")
    with pytest.raises(ValueError, match="positive"):
        file_sha256(path, chunk_size=0)
    with pytest.raises(FileNotFoundError):
        file_sha256(tmp_path / "missing")
