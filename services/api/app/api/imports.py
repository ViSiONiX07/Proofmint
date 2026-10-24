"""Validated, provenance-preserving CSV ingestion for facts and terminology."""

import csv
import hashlib
import io
import logging
from hashlib import sha256
from collections.abc import Callable, Generator
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import settings
from app.core.database import DatabaseNotConfiguredError, get_db_session
from app.models.imports import ImportedFact, ImportedTerm
from app.models.workspace import Workspace
from app.schemas.imports import CsvImportResponse, ImportRowError, ImportSummary

router = APIRouter()
logger = logging.getLogger(__name__)

FACT_HEADERS = {
    "fact_id", "claim_type", "approved_statement", "source_document", "page_span",
    "verified_date", "status",
}
TERM_HEADERS = {"term", "preferred_form", "category", "usage_notes"}


class CsvFileError(ValueError):
    """An invalid CSV file that cannot be safely interpreted row by row."""


def get_import_db_session() -> Generator[Session, None, None]:
    """Translate missing persistence configuration into a clear service error."""
    try:
        yield from get_db_session()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured for CSV persistence.") from None


def _parse_csv(data: bytes, filename: str, allowed_headers: set[str], required_headers: set[str]):
    if not data:
        raise CsvFileError("CSV file is empty.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvFileError("CSV must be encoded as UTF-8.") from None
    if "\x00" in text:
        raise CsvFileError("CSV contains a NUL character and cannot be parsed safely.")

    # csv.reader skips blank physical lines, but whitespace-only lines are a
    # one-cell row; remove such lines only while locating the first header.
    lines = text.splitlines(keepends=True)
    while lines and not lines[0].strip():
        lines.pop(0)
    reader = csv.reader(io.StringIO("".join(lines), newline=""), strict=True)
    try:
        # Ignore only physically empty or whitespace-only leading lines. A
        # delimited row containing blank cells remains the header and is rejected.
        raw_headers = next(reader, None)
        while raw_headers is not None and len(raw_headers) == 1 and not raw_headers[0].strip():
            raw_headers = next(reader, None)
        if raw_headers is None or not raw_headers or all(not value.strip() for value in raw_headers):
            raise CsvFileError("CSV must contain a header row.")
        headers = [value.strip().lower() for value in raw_headers]
        if any(not header for header in headers):
            raise CsvFileError("CSV header names cannot be blank.")
        if len(headers) != len(set(headers)):
            raise CsvFileError("CSV contains duplicate header names.")
        missing = sorted(required_headers - set(headers))
        if missing:
            raise CsvFileError("CSV is missing required headers: " + ", ".join(missing) + ".")
        unknown = sorted(set(headers) - allowed_headers)
        if unknown:
            raise CsvFileError("CSV contains unsupported headers: " + ", ".join(unknown) + ".")

        rows: list[tuple[int, dict[str, str] | None, str | None]] = []
        for row_number, values in enumerate(reader, start=2):
            if row_number - 1 > settings.CSV_IMPORT_MAX_ROWS:
                raise HTTPException(status_code=413, detail=f"CSV exceeds the {settings.CSV_IMPORT_MAX_ROWS} data-row limit.")
            if len(values) != len(headers):
                rows.append((row_number, None, f"Expected {len(headers)} columns but found {len(values)}."))
            else:
                rows.append((row_number, dict(zip(headers, values)), None))
        if not rows:
            raise CsvFileError("CSV contains a header but no data rows.")
        return rows
    except csv.Error:
        raise CsvFileError("CSV syntax is malformed.") from None


def _text_value(row: dict[str, str], key: str, *, required: bool, max_length: int | None = None):
    value = row.get(key, "").strip()
    if not value:
        if required:
            raise ValueError(f"{key} is required and cannot be blank.")
        return None
    if max_length is not None and len(value) > max_length:
        raise ValueError(f"{key} must be at most {max_length} characters.")
    return value


def _validate_fact(row: dict[str, str]) -> dict[str, Any]:
    values: dict[str, Any] = {
        "external_fact_id": _text_value(row, "fact_id", required=False, max_length=100),
        "claim_type": _text_value(row, "claim_type", required=True, max_length=100),
        "approved_statement": _text_value(row, "approved_statement", required=True),
        "source_document": _text_value(row, "source_document", required=False, max_length=255),
        "source_page_span": _text_value(row, "page_span", required=False, max_length=100),
        "source_status": _text_value(row, "status", required=False, max_length=50),
    }
    date_value = _text_value(row, "verified_date", required=False)
    if date_value is not None:
        try:
            parsed_date = date.fromisoformat(date_value)
            if parsed_date.isoformat() != date_value:
                raise ValueError
            values["verified_date"] = parsed_date
        except ValueError:
            raise ValueError("verified_date must use YYYY-MM-DD format.") from None
    else:
        values["verified_date"] = None
    return values


def _validate_term(row: dict[str, str]) -> dict[str, Any]:
    return {
        "term": _text_value(row, "term", required=True, max_length=255),
        "preferred_form": _text_value(row, "preferred_form", required=False, max_length=255),
        "category": _text_value(row, "category", required=False, max_length=100),
        "usage_notes": _text_value(row, "usage_notes", required=False),
    }


async def _read_csv(upload: UploadFile) -> tuple[str, bytes]:
    filename = upload.filename or ""
    if not filename or len(filename) > 255 or any(ord(char) < 32 for char in filename):
        raise HTTPException(status_code=400, detail="A valid source filename of at most 255 characters is required.")
    data = await upload.read(settings.CSV_IMPORT_MAX_FILE_BYTES + 1)
    if len(data) > settings.CSV_IMPORT_MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail=f"CSV file exceeds the {settings.CSV_IMPORT_MAX_FILE_BYTES}-byte limit.")
    return filename, data


def _make_import_endpoint(model, allowed_headers: set[str], required_headers: set[str], validator: Callable):
    async def import_csv(file: UploadFile = File(...), workspace_id: UUID = Form(...), session: Session = Depends(get_import_db_session)) -> CsvImportResponse:
        try:
            filename, data = await _read_csv(file)
            rows = _parse_csv(data, filename, allowed_headers, required_headers)
        except CsvFileError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        finally:
            file.file.close()

        digest = hashlib.sha256(data).hexdigest()
        valid_rows: list[tuple[int, dict[str, Any]]] = []
        errors: list[ImportRowError] = []
        for row_number, row, structural_error in rows:
            if structural_error:
                errors.append(ImportRowError(row_number=row_number, errors={"row": structural_error}))
                continue
            try:
                values = validator(row)
                valid_rows.append((row_number, values))
            except ValueError as exc:
                message = str(exc)
                field = message.split(" ", 1)[0]
                errors.append(ImportRowError(row_number=row_number, errors={field: message}))

        skipped = 0
        objects = []
        try:
            with session.begin():
                workspace = session.get(Workspace, workspace_id)
                if workspace is None or workspace.kind == "legacy":
                    raise HTTPException(status_code=404, detail="Workspace was not found.")
                if valid_rows:
                    # Serialize imports of identical byte-for-byte files across
                    # workers. This uses PostgreSQL's transaction-scoped lock and
                    # requires no schema change; other dialects remain useful for
                    # isolated API tests.
                    bind = getattr(session, "bind", None)
                    if bind is not None and bind.dialect.name == "postgresql":
                        lock_key = int.from_bytes(sha256(f"proofmint-csv:{workspace_id}:{digest}".encode()).digest()[:8], "big", signed=True)
                        session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
                    imported_rows = set(session.scalars(
                        select(model.source_row_number).where(model.workspace_id == workspace_id, model.source_sha256 == digest)
                    ).all())
                    seen_payloads: set[tuple[tuple[str, Any], ...]] = set()
                    for row_number, values in valid_rows:
                        identity = tuple(sorted(values.items()))
                        if identity in seen_payloads:
                            skipped += 1
                            continue
                        seen_payloads.add(identity)
                        if row_number in imported_rows:
                            skipped += 1
                            continue
                        values.update(
                            source_filename=filename,
                            workspace_id=workspace_id,
                            source_row_number=row_number,
                            source_sha256=digest,
                            review_status="pending_review",
                        )
                        objects.append(model(**values))
                    if objects:
                        session.add_all(objects)
                        session.flush()
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error("CSV import database transaction failed (%s)", type(exc).__name__)
            raise HTTPException(status_code=503, detail="CSV rows could not be persisted; no rows from this import were committed.") from None

        return CsvImportResponse(
            summary=ImportSummary(
                rows_read=len(rows), rows_imported=len(objects), rows_skipped=skipped,
                rows_rejected=len(errors)
            ),
            errors=errors,
        )

    return import_csv


facts_import = _make_import_endpoint(
    ImportedFact, FACT_HEADERS, {"claim_type", "approved_statement"}, _validate_fact
)
terms_import = _make_import_endpoint(
    ImportedTerm, TERM_HEADERS, {"term"}, _validate_term
)

router.add_api_route(
    "/facts/import", facts_import, methods=["POST"], response_model=CsvImportResponse,
    summary="Import facts from CSV",
    description=(
        "Accepts a UTF-8 CSV, up to 5 MiB and 10,000 data rows. Rows are validated independently: "
        "valid rows are committed together and invalid rows are returned with their CSV row numbers. "
        "Duplicate rows within the upload and rows from an identical file already imported are counted as skipped. "
        "All imported facts remain pending_review. Required headers: claim_type, approved_statement. "
        "Optional headers: fact_id, source_document, page_span, verified_date (YYYY-MM-DD), status."
    ),
)
router.add_api_route(
    "/terms/import", terms_import, methods=["POST"], response_model=CsvImportResponse,
    summary="Import terminology from CSV",
    description=(
        "Accepts a UTF-8 CSV, up to 5 MiB and 10,000 data rows. Rows are validated independently: "
        "valid rows are committed together and invalid rows are returned with their CSV row numbers. "
        "Duplicate rows within the upload and rows from an identical file already imported are counted as skipped. "
        "All imported terms remain pending_review. Required header: term. "
        "Optional headers: preferred_form, category, usage_notes."
    ),
)
