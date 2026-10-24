"""Transient PDF ingestion for guideline source evidence."""

import hashlib
import logging
from collections.abc import Generator
from uuid import uuid4

import pymupdf
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import DatabaseNotConfiguredError, get_db_session
from app.models.guideline import CandidateRule, GuidelineDocument
from app.models.workspace import Workspace
from app.services.candidate_extraction import extract_candidate_rules
from app.schemas.guideline import (
    ExtractedPage,
    FileOutcome,
    GuidelineExtraction,
    GuidelineIngestionResponse,
    IngestionSummary,
    SourceSpan,
)

router = APIRouter()
logger = logging.getLogger(__name__)
READ_CHUNK_BYTES = 64 * 1024


def get_guideline_db_session() -> Generator[Session, None, None]:
    """Translate missing persistence configuration into a clear service error."""
    try:
        yield from get_db_session()
    except DatabaseNotConfiguredError:
        raise HTTPException(status_code=503, detail="PostgreSQL is not configured for guideline persistence.") from None


class IngestionError(Exception):
    def __init__(self, code: str, message: str, bytes_read: int = 0):
        super().__init__(message)
        self.code = code
        self.message = message
        self.bytes_read = bytes_read


async def _read_bounded(upload: UploadFile, remaining_request_bytes: int) -> bytes:
    """Read at most per-file limit + 1, without trusting Content-Length."""
    limit = min(settings.GUIDELINE_MAX_FILE_BYTES, remaining_request_bytes)
    chunks: list[bytes] = []
    total = 0
    while True:
        # Starlette's UploadFile wraps a local SpooledTemporaryFile. Reading the
        # bounded chunks directly avoids an executor hop for each tiny chunk.
        chunk = upload.file.read(min(READ_CHUNK_BYTES, limit - total + 1))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            if remaining_request_bytes <= settings.GUIDELINE_MAX_FILE_BYTES:
                raise IngestionError("request_too_large", "Aggregate upload size exceeds the configured limit.", total)
            raise IngestionError("file_too_large", "File exceeds the configured per-PDF size limit.", total)
    if total == 0:
        raise IngestionError("empty_file", "The uploaded file is empty.")
    return b"".join(chunks)


def _extract_pdf(filename: str, content_type: str | None, data: bytes) -> GuidelineExtraction:
    digest = hashlib.sha256(data).hexdigest()
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        logger.info("Rejected unreadable guideline PDF (%s): %s", filename, type(exc).__name__)
        raise IngestionError("invalid_pdf", "File content is not a readable PDF.") from None

    try:
        if document.needs_pass:
            raise IngestionError("password_protected", "Password-protected PDFs are not supported.")
        page_count = document.page_count
        if page_count > settings.GUIDELINE_MAX_PAGES:
            raise IngestionError("too_many_pages", "PDF exceeds the configured page-count limit.")

        pages: list[ExtractedPage] = []
        has_text = False
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            # sort=True requests a stable top-to-bottom, left-to-right reading order.
            blocks = page.get_text("dict", sort=True).get("blocks", [])
            lines: list[tuple[str, tuple[float, float, float, float] | None]] = []
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    value = "".join(span.get("text", "") for span in line.get("spans", []))
                    if value.strip():
                        bbox = line.get("bbox")
                        lines.append((value, tuple(float(v) for v in bbox) if bbox else None))

            page_text_parts: list[str] = []
            spans: list[SourceSpan] = []
            offset = 0
            for line_index, (line_text, bbox) in enumerate(lines):
                if page_text_parts:
                    page_text_parts.append("\n")
                    offset += 1
                start = offset
                page_text_parts.append(line_text)
                offset += len(line_text)
                spans.append(SourceSpan(
                    span_id=f"p{page_number}-line{line_index + 1}",
                    page_number=page_number,
                    start_offset=start,
                    end_offset=offset,
                    text=line_text,
                    bbox=bbox,
                ))
            page_text = "".join(page_text_parts)
            has_text = has_text or bool(page_text.strip())
            pages.append(ExtractedPage(page_number=page_number, text=page_text, spans=spans))

        if not has_text:
            raise IngestionError("no_extractable_text", "PDF contains no extractable text; scanned-image OCR is not supported.")
        return GuidelineExtraction(
            filename=filename,
            size_bytes=len(data),
            page_count=page_count,
            sha256=digest,
            pages=pages,
            declared_content_type=content_type,
        )
    except IngestionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected PDF extraction failure (%s): %s", filename, type(exc).__name__)
        raise IngestionError("extraction_failed", "PDF text extraction failed.") from None
    finally:
        document.close()


@router.post(
    "/guidelines/ingest",
    response_model=GuidelineIngestionResponse,
    summary="Extract text from guideline PDFs",
    description=(
        "Accepts one or more PDFs in repeated multipart `files` fields (maximum 5). "
        "Processing is partial-success: each file has an explicit success or error outcome. "
        "Per-file, aggregate, and page limits are 10 MiB, 20 MiB, and 200 pages by default. "
        "Multipart framing may add up to 256 KiB to the aggregate request-body cap. "
        "Page offsets are zero-based character offsets into that page's returned text; end offsets are exclusive. "
        "SHA-256 identifies the exact uploaded bytes. Successful PDF metadata is persisted together in one "
        "transaction; PDF bytes and extracted text are not stored. A database failure rolls back every document "
        "and candidate from the request and returns 503. Candidate rules are deterministic review suggestions "
        "and always start as pending_review; extraction does not approve rules or verify document claims."
    ),
    responses={413: {"description": "The request exceeds the configured file-count limit."}},
)
async def ingest_guidelines(
    files: list[UploadFile] = File(..., description="One or more guideline PDFs; max 5."),
    session: Session = Depends(get_guideline_db_session),
):
    """Extract PDF text and persist successful documents' metadata atomically."""
    if len(files) > settings.GUIDELINE_MAX_FILES:
        for upload in files:
            upload.file.close()
        raise HTTPException(status_code=413, detail="Too many files; request exceeds the configured file-count limit.")

    results: list[FileOutcome] = []
    workspace = Workspace(id=uuid4(), kind="session")
    documents_to_persist: list[tuple[GuidelineExtraction, GuidelineDocument, list[CandidateRule]]] = []
    total_bytes = 0
    for upload in files:
        filename = upload.filename or ""
        try:
            remaining = settings.GUIDELINE_MAX_REQUEST_BYTES - total_bytes
            if remaining <= 0:
                raise IngestionError("request_too_large", "Aggregate upload size exceeds the configured limit.")
            data = await _read_bounded(upload, remaining)
            total_bytes += len(data)
            extraction = _extract_pdf(filename, upload.content_type, data)
            try:
                candidates = extract_candidate_rules(
                    (page.page_number, page.text) for page in extraction.pages
                )
            except Exception as exc:
                logger.error("Candidate extraction failed (%s)", type(exc).__name__)
                raise IngestionError(
                    "candidate_extraction_failed", "Candidate rules could not be extracted from this PDF."
                ) from None
            document = GuidelineDocument(
                workspace_id=workspace.id,
                source_filename=extraction.filename,
                source_sha256=extraction.sha256,
                file_size_bytes=extraction.size_bytes,
                page_count=extraction.page_count,
            )
            candidate_rows = [
                CandidateRule(
                    rule_text=candidate.rule_text,
                    category=candidate.category,
                    source_page=candidate.source_page,
                    source_start_offset=candidate.source_start_offset,
                    source_end_offset=candidate.source_end_offset,
                    source_excerpt=candidate.source_excerpt,
                    review_status="pending_review",
                )
                for candidate in candidates
            ]
            documents_to_persist.append((extraction, document, candidate_rows))
            results.append(FileOutcome(filename=filename, status="success", extraction=extraction))
        except IngestionError as exc:
            results.append(FileOutcome(filename=filename, status="error", error_code=exc.code, message=exc.message))
            total_bytes += exc.bytes_read
            # If the aggregate cap is reached, subsequent files receive explicit outcomes too.
            if exc.code == "request_too_large":
                for pending in files[len(results):]:
                    results.append(FileOutcome(
                        filename=pending.filename or "", status="error",
                        error_code="request_too_large", message="File was not read because the aggregate upload limit was exceeded.",
                    ))
                    pending.file.close()
                break
        except Exception as exc:
            logger.exception("Unexpected guideline ingestion failure (%s): %s", filename, type(exc).__name__)
            results.append(FileOutcome(filename=filename, status="error", error_code="ingestion_failed", message="File could not be processed."))
        finally:
            upload.file.close()

    if documents_to_persist:
        try:
            with session.begin():
                session.add(workspace)
                session.flush()
                session.add_all([document for _, document, _ in documents_to_persist])
                session.flush()
                candidate_rows = []
                for _, document, candidates in documents_to_persist:
                    for candidate in candidates:
                        candidate.document_id = document.id
                    candidate_rows.extend(candidates)
                session.add_all(candidate_rows)
                session.flush()
                for _, document, _ in documents_to_persist:
                    session.refresh(document, attribute_names=["created_at"])
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error("Guideline metadata transaction failed (%s)", type(exc).__name__)
            raise HTTPException(
                status_code=503,
                detail="Guideline metadata could not be persisted; no documents from this request were committed.",
            ) from None

        for extraction, document, candidates in documents_to_persist:
            extraction.document_id = document.id
            extraction.created_at = document.created_at
            extraction.candidate_rule_count = len(candidates)

    succeeded = sum(result.status == "success" for result in results)
    return GuidelineIngestionResponse(
        workspace_id=workspace.id if documents_to_persist else None,
        summary=IngestionSummary(
            files_received=len(files),
            files_succeeded=succeeded,
            files_rejected=len(files) - succeeded,
            total_bytes_read=total_bytes,
        ),
        results=results,
    )
