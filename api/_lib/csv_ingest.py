import csv
import io
from typing import Any, Dict, List

REQUIRED_COLUMNS = {"subject", "description", "resolution"}


class CsvValidationError(ValueError):
    pass


def parse_tickets_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse an uploaded CSV of resolved tickets into row dicts ready for the Ticket model.

    Required columns: subject, description, resolution.
    Optional columns: id / external_id (an external ticket id is generated if absent).
    Rows missing any required field are skipped rather than failing the whole upload.
    """
    if not file_bytes or not file_bytes.strip():
        raise CsvValidationError("Uploaded file is empty.")

    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("Uploaded file is not valid UTF-8 text.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise CsvValidationError("Could not read a CSV header row.")

    header = {h.strip().lower() for h in reader.fieldnames if h}
    missing = REQUIRED_COLUMNS - header
    if missing:
        raise CsvValidationError(
            f"CSV is missing required columns: {', '.join(sorted(missing))}"
        )

    rows: List[Dict[str, Any]] = []
    for i, raw_row in enumerate(reader):
        row = {
            (k.strip().lower() if k else k): (v.strip() if isinstance(v, str) else v)
            for k, v in raw_row.items()
            if k
        }
        if not row.get("subject") or not row.get("description") or not row.get("resolution"):
            continue

        rows.append(
            {
                "external_id": row.get("id") or row.get("external_id") or f"TCK-{i + 1:03d}",
                "subject": row["subject"],
                "description": row["description"],
                "resolution": row["resolution"],
            }
        )

    if not rows:
        raise CsvValidationError("CSV contained a valid header but no usable ticket rows.")

    return rows
