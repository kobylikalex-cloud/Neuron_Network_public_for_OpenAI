# The Edge Data Provenance

**Independent, open-source Python toolkit** for validating tabular time series,
recording source metadata, and verifying raw-file integrity.

This is a small, intentionally focused research utility. It is **not** a trading
system, predictive model, signal engine, data provider, or proof that a dataset
is accurate. It has no dependency on any private project.

## Features

- **CSV quality checks:** ISO dates, numerical parsing, missing values, duplicate
  timestamps, ascending ordering and optional D/W/M/Q/Y calendar gaps.
- **Provenance sidecars:** capture a dataset identifier, public source URL,
  retrieval timestamp, size, filename, optional data license and SHA-256 digest.
- **Verification:** detect changed file bytes using streaming SHA-256.
- **Minimal dependencies:** standard-library runtime, compatible with Python 3.10+.
- **Machine-readable output:** human-invocable CLI with JSON reports and exit codes.

## Install

From the project root:

```bash
python -m pip install -e .
```

For development and tests:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Quick start

The example file contains **fabricated values** for demonstration purposes.

```bash
edge-provenance validate examples/synthetic_monthly.csv \
  --date-column date \
  --value-column synthetic_index \
  --value-column synthetic_volume \
  --frequency M \
  --report validation-report.json
```

To generate and verify provenance for an actual downloaded dataset:

```bash
edge-provenance record path/to/download.csv \
  --dataset-id my-public-dataset \
  --source-url https://example.org/data/download.csv \
  --retrieved-at 2026-10-12T08:00:00Z \
  --output provenance.json

edge-provenance verify path/to/download.csv --record provenance.json
edge-provenance hash path/to/download.csv
```

Use `python -m edge_provenance` when a shell entry point is not available.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Passed check or command succeeded |
| `1` | Validation failed or checksum did not match |
| `2` | File / argument / input error |

### API usage

```python
from edge_provenance import validate_csv, file_sha256, make_record

report = validate_csv(
    "examples/synthetic_monthly.csv",
    timestamp_column="date",
    value_columns=["synthetic_index"],
    frequency="M",
)
assert report.passed
print(report.to_dict())
print(file_sha256("examples/synthetic_monthly.csv"))
```

## Scope and limitations

- **Calendar gaps are warnings**, not automatic evidence of missing source data.
  `D` means calendar days, **not trading days**. `W` uses Monday-aligned weeks.
  `M`, `Q` and `Y` compare calendar periods rather than exact days.
- Date parsing requires `YYYY-MM-DD`. Numeric values use decimal notation with
  `.` and no thousands separator. Empty observations are errors by default.
- The validator streams CSV rows but holds unique dates in memory to detect
  duplicates and gaps; it is not yet optimized for billion-row datasets.
- SHA-256 covers **raw bytes**, not semantic equivalence. Reordering rows or
  changing CSV formatting changes the checksum. It does not certify provenance,
  authenticity, authoritativeness, or economic accuracy.
- Provenance metadata is **self-declared**. This tool does not independently
  fetch or authenticate source URLs.
- The file size and SHA-256 are obtained in separate file reads. For files
  changing concurrently, take an immutable snapshot before creating a record.
- Only HTTP(S) source URLs without embedded credentials, query strings or
  fragments are accepted. **Never place signed URLs, API keys, tokens, private
  URLs or sensitive data** into source metadata.
- `record` writes a JSON sidecar but never copies data from private systems.
- Parquet files can be hashed and documented; CSV-only validation is supported
  in this initial release. Parquet inspection may be added separately.

## Security and responsible use

This repository is deliberately standalone and uses entirely synthetic examples.
Do not commit personal data, credentials, proprietary formulas, nonredistributable
source data, access tokens or private research configuration. Use the reporting
functionality only on datasets for which you hold the relevant rights.

See [SECURITY.md](SECURITY.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT; see [LICENSE](LICENSE). Dataset licenses remain independent of this code
license. No real-world research or investment outcome is claimed.
