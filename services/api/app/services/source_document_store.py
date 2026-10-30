"""Private, content-addressed storage for original guideline PDFs."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID

import pymupdf

from app.core.config import settings

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class SourceDocumentError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def page_text(page: pymupdf.Page) -> str:
    """Return the canonical page text used by ingestion and citation offsets."""
    blocks = page.get_text("dict", sort=True).get("blocks", [])
    lines: list[str] = []
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            value = "".join(span.get("text", "") for span in line.get("spans", []))
            if value.strip():
                lines.append(value)
    return "\n".join(lines)


class SourceDocumentStore:
    """Filesystem store rooted outside web assets; callers use opaque document IDs."""

    def __init__(self, root: Path | None = None):
        configured = Path(root if root is not None else settings.SOURCE_DOCUMENT_STORAGE_DIR).expanduser()
        if not configured.is_absolute():
            configured = Path(__file__).resolve().parents[2] / configured
        self.root = configured.resolve()

    def path_for(self, workspace_id: UUID, document_id: UUID, sha256: str) -> Path:
        if not _SHA256.fullmatch(sha256):
            raise SourceDocumentError("source_metadata_invalid")
        return self.root / workspace_id.hex / f"{document_id.hex}-{sha256}.pdf"

    def object_exists(self, workspace_id: UUID, document_id: UUID, sha256: str) -> bool:
        return self.path_for(workspace_id, document_id, sha256).exists()

    def retain(self, workspace_id: UUID, document_id: UUID, sha256: str, data: bytes) -> str:
        """Persist new bytes or recover only a missing exact-hash source object."""
        if hashlib.sha256(data).hexdigest() != sha256:
            raise SourceDocumentError("uploaded_source_hash_mismatch")
        path = self.path_for(workspace_id, document_id, sha256)
        try:
            self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.parent.mkdir(mode=0o700, exist_ok=True)
            for private_dir in (self.root, path.parent):
                try:
                    os.chmod(private_dir, 0o700)
                except OSError:
                    pass
            if path.exists():
                existing = path.read_bytes()
                if hashlib.sha256(existing).hexdigest() != sha256:
                    raise SourceDocumentError("stored_source_hash_mismatch")
                return "already_retained"
            fd, temp_name = tempfile.mkstemp(prefix=".source-", suffix=".tmp", dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as target:
                    target.write(data)
                    target.flush()
                    os.fsync(target.fileno())
                try:
                    os.chmod(temp_name, 0o600)
                except OSError:
                    pass
                # Atomic create prevents a concurrent upload replacing another object's bytes.
                try:
                    os.link(temp_name, path)
                    status = "retained"
                except FileExistsError:
                    existing = path.read_bytes()
                    if hashlib.sha256(existing).hexdigest() != sha256:
                        raise SourceDocumentError("stored_source_hash_mismatch")
                    status = "already_retained"
                except OSError:
                    # Some Windows deployments deny hard-link creation. Same-volume
                    # rename is still atomic and, on Windows, fails if the destination
                    # already exists; this preserves the no-overwrite guarantee.
                    if os.name != "nt":
                        raise
                    try:
                        os.rename(temp_name, path)
                        status = "retained"
                    except FileExistsError:
                        existing = path.read_bytes()
                        if hashlib.sha256(existing).hexdigest() != sha256:
                            raise SourceDocumentError("stored_source_hash_mismatch")
                        status = "already_retained"
                return status
            finally:
                Path(temp_name).unlink(missing_ok=True)
        except SourceDocumentError:
            raise
        except OSError:
            raise SourceDocumentError("source_storage_unavailable") from None

    def read_verified(self, document) -> bytes:
        path = self.path_for(document.workspace_id, document.id, document.source_sha256)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            raise SourceDocumentError("source_document_not_retained") from None
        except OSError:
            raise SourceDocumentError("source_document_inaccessible") from None
        if len(data) != document.file_size_bytes or hashlib.sha256(data).hexdigest() != document.source_sha256:
            raise SourceDocumentError("source_hash_mismatch")
        return data

    def inspect_pdf(self, document, data: bytes) -> pymupdf.Document:
        try:
            pdf = pymupdf.open(stream=data, filetype="pdf")
        except Exception:
            raise SourceDocumentError("source_pdf_invalid") from None
        if pdf.needs_pass or pdf.page_count != document.page_count:
            pdf.close()
            raise SourceDocumentError("source_pdf_metadata_mismatch")
        return pdf
