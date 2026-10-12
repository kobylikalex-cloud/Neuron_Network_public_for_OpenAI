"""Atomic JSON writing for portable provenance sidecars and reports."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(path: str | Path, data: Any) -> Path:
    """Write JSON via a temporary sibling file and atomic replace.

    Atomicity assumes source and target are on the same local filesystem.
    The durability of physical flushes is filesystem-dependent.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(data, handle, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
        temp_path = None
        return target
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def read_json(path: str | Path) -> Any:
    """Read UTF-8 JSON from an existing file."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
