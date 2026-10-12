"""Console interface for validation, provenance capture, and integrity checking."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .integrity import file_sha256
from .provenance import make_record, read_record, verify_record, write_record
from .quality import validate_csv
from .storage import atomic_write_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="edge-provenance", description="Standalone quality and provenance tools for source datasets"
    )
    cmds = parser.add_subparsers(dest="action", required=True)
    validate = cmds.add_parser("validate", help="Check a CSV time series")
    validate.add_argument("file", type=Path)
    validate.add_argument("--date-column", required=True)
    validate.add_argument("--value-column", required=True, action="append", dest="value_columns")
    validate.add_argument("--frequency", choices=("D", "W", "M", "Q", "Y"))
    validate.add_argument("--allow-missing", action="store_true")
    validate.add_argument("--allow-duplicates", action="store_true")
    validate.add_argument("--allow-unsorted", action="store_true")
    validate.add_argument("--report", type=Path, help="Also write machine-readable JSON report")

    digest = cmds.add_parser("hash", help="Print raw file SHA-256")
    digest.add_argument("file", type=Path)

    record = cmds.add_parser("record", help="Create a provenance JSON sidecar")
    record.add_argument("file", type=Path)
    record.add_argument("--dataset-id", required=True)
    record.add_argument("--source-url", required=True)
    record.add_argument("--retrieved-at", help="Timezone-aware ISO timestamp; default: current UTC")
    record.add_argument("--license-id", default=None)
    record.add_argument("--output", type=Path, required=True)

    verify = cmds.add_parser("verify", help="Verify a file against a provenance JSON sidecar")
    verify.add_argument("file", type=Path)
    verify.add_argument("--record", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "validate":
            report = validate_csv(
                args.file, timestamp_column=args.date_column, value_columns=args.value_columns,
                frequency=args.frequency, allow_missing_values=args.allow_missing,
                allow_duplicate_timestamps=args.allow_duplicates,
                require_sorted=not args.allow_unsorted,
            )
            result = report.to_dict()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if args.report:
                atomic_write_json(args.report, result)
            return 0 if report.passed else 1
        if args.action == "hash":
            print(file_sha256(args.file))
            return 0
        if args.action == "record":
            result = make_record(
                args.file, dataset_id=args.dataset_id, source_url=args.source_url,
                retrieved_at=args.retrieved_at, license_id=args.license_id,
            )
            target = write_record(args.output, result)
            print(f"Provenance saved: {target}")
            return 0
        if args.action == "verify":
            match = verify_record(args.file, read_record(args.record))
            print("VERIFIED" if match else "MISMATCH")
            return 0 if match else 1
    except (OSError, ValueError, UnicodeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
