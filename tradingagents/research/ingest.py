"""Validate and extract text from user-owned research uploads."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from . import DocumentKind

# Hard limits — alpha product, not a general file locker.
_MAX_BYTES = 5 * 1024 * 1024
_ALLOWED = {
    ".md": (DocumentKind.MARKDOWN, "text/markdown"),
    ".markdown": (DocumentKind.MARKDOWN, "text/markdown"),
    ".txt": (DocumentKind.TEXT, "text/plain"),
    ".csv": (DocumentKind.CSV, "text/csv"),
    ".pdf": (DocumentKind.PDF, "application/pdf"),
}
_PDF_MAGIC = b"%PDF"
_EXECUTABLE_MARKERS = (b"MZ", b"\x7fELF", b"#!/", b"<%", b"<script")


class UploadValidationError(ValueError):
    """Raised when an upload fails type, size, or malware-heuristic checks."""


@dataclass(frozen=True)
class ExtractedUpload:
    kind: DocumentKind
    content_type: str
    filename: str
    data: bytes
    extracted_text: str


def validate_and_extract(
    *,
    filename: str,
    data: bytes,
) -> ExtractedUpload:
    if not filename or "/" in filename or "\\" in filename:
        raise UploadValidationError("filename must be a bare file name")
    if not data:
        raise UploadValidationError("empty upload")
    if len(data) > _MAX_BYTES:
        raise UploadValidationError(f"file exceeds {_MAX_BYTES} byte limit")

    lower = filename.lower()
    suffix = ""
    for ext in _ALLOWED:
        if lower.endswith(ext):
            suffix = ext
            break
    if not suffix:
        raise UploadValidationError(
            f"unsupported file type for {filename!r}; allowed: {sorted(_ALLOWED)}"
        )

    kind, content_type = _ALLOWED[suffix]
    for marker in _EXECUTABLE_MARKERS:
        if data.startswith(marker) and kind is not DocumentKind.PDF:
            raise UploadValidationError("file looks like an executable or script")

    if kind is DocumentKind.PDF:
        if not data.startswith(_PDF_MAGIC):
            raise UploadValidationError("PDF magic header missing")
        text = _extract_pdf(data)
    elif kind is DocumentKind.CSV:
        text = _extract_csv(data)
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadValidationError("text uploads must be UTF-8") from exc
        if "\x00" in text:
            raise UploadValidationError("nul bytes are not allowed in text uploads")

    text = text.strip()
    if not text:
        raise UploadValidationError("no extractable text found")
    return ExtractedUpload(
        kind=kind,
        content_type=content_type,
        filename=filename,
        data=data,
        extracted_text=text,
    )


def _extract_csv(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadValidationError("CSV must be UTF-8") from exc
    reader = csv.reader(io.StringIO(text))
    rows = [" | ".join(cell.strip() for cell in row if cell.strip()) for row in reader]
    return "\n".join(row for row in rows if row)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise UploadValidationError(
            'PDF support requires pypdf: pip install "alphadesk[server]"'
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise UploadValidationError(f"unreadable PDF: {exc}") from exc
    chunks: list[str] = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    text = "\n".join(chunks).strip()
    # Collapse excessive whitespace from PDF extractors.
    return re.sub(r"[ \t]+", " ", text)
