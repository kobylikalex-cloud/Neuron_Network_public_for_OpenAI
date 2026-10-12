"""Public, standalone building blocks for reproducible data handling.

No models, feature engineering recipes, providers, or research signals are included.
"""

from .integrity import file_sha256, verify_file_sha256
from .provenance import ProvenanceRecord, make_record, read_record, verify_record, write_record
from .quality import ValidationReport, validate_csv

__version__ = "0.1.0"

__all__ = [
    "ProvenanceRecord",
    "ValidationReport",
    "file_sha256",
    "make_record",
    "read_record",
    "validate_csv",
    "verify_file_sha256",
    "verify_record",
    "write_record",
]
