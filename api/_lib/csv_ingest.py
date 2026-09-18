import csv
import io
from typing import Any, Dict, List

SUBJECT_ALIASES = ("subject", "title")
ID_ALIASES = ("id", "external_id", "ticket_id")

# Below this many usable tickets, clustering can't produce a meaningful
# multi-theme split (see api/_lib/clustering.py).
MIN_TICKETS = 3


class CsvValidationError(ValueError):
    pass


def _first_present(row: Dict[str, Any], aliases) -> str:
    for key in aliases:
        value = row.get(key)
        if value:
            return value
    return ""


def parse_tickets_csv(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse an uploaded CSV of resolved tickets into row dicts ready for clustering.

    Required per row: a ticket identifier (id / external_id / ticket_id), a
    title (subject / title), and a resolution. `description` is optional
    supporting context. Rows missing any required field are skipped rather
    than failing the whole upload; the whole upload fails if the header is
    missing a required column outright, or if too few usable rows remain.
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

    missing = []
    if "resolution" not in header:
        missing.append("resolution")
    if not header & set(SUBJECT_ALIASES):
        missing.append("subject (or title)")
    if not header & set(ID_ALIASES):
        missing.append("id (or ticket_id / external_id)")
    if missing:
        raise CsvValidationError(f"CSV is missing required columns: {', '.join(missing)}")

    rows: List[Dict[str, Any]] = []
    for raw_row in reader:
        row = {
            (k.strip().lower() if k else k): (v.strip() if isinstance(v, str) else v)
            for k, v in raw_row.items()
            if k
        }
        external_id = _first_present(row, ID_ALIASES)
        subject = _first_present(row, SUBJECT_ALIASES)
        resolution = row.get("resolution") or ""
        if not external_id or not subject or not resolution:
            continue

        rows.append(
            {
                "external_id": external_id,
                "subject": subject,
                "description": row.get("description") or "",
                "resolution": resolution,
            }
        )

    if len(rows) < MIN_TICKETS:
        raise CsvValidationError(
            f"At least {MIN_TICKETS} valid tickets (with id, subject/title, and "
            f"resolution) are required to detect recurring themes - found {len(rows)}."
        )

    return rows
