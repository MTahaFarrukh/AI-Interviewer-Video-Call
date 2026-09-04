"""Extract text from PDFs. pdfplumber first, pypdf fallback. Also writes simple text PDFs."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("firstround.prep.pdf")

GITHUB_RE = re.compile(
    r"(?:https?://(?:www\.)?)?github\.com/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?/?",
    re.I,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


class PdfExtractError(RuntimeError):
    pass


def extract_text(path: Path) -> tuple[str, str]:
    """Return (text, extractor_name). Raises PdfExtractError if empty/unreadable."""
    if not path.is_file():
        raise PdfExtractError(f"File not found: {path}")
    if path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            raise PdfExtractError(f"Empty text file: {path}")
        return text, "txt"

    text = _extract_pdfplumber(path)
    extractor = "pdfplumber"
    if _too_thin(text):
        fallback = _extract_pypdf(path)
        if not _too_thin(fallback):
            text = fallback
            extractor = "pypdf"
    if _too_thin(text):
        raise PdfExtractError(
            f"Could not extract usable text from {path.name}. "
            "The file may be empty, scanned, or invalid."
        )
    return text.strip(), extractor


def find_github_urls(text: str) -> list[str]:
    found = []
    for match in GITHUB_RE.findall(text or ""):
        url = match.rstrip("/")
        if not url.lower().startswith("http"):
            url = "https://" + url
        found.append(url)
    return list(dict.fromkeys(found))


def find_emails(text: str) -> list[str]:
    return list(dict.fromkeys(EMAIL_RE.findall(text or "")))


def redact_private_fields(text: str) -> str:
    redacted = PHONE_RE.sub("[redacted-phone]", text or "")
    return redacted


def write_text_pdf(path: Path, text: str) -> None:
    """Write a simple multi-page text PDF without extra writer libraries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _wrap_lines(text, width=90)
    pages: list[list[str]] = []
    page: list[str] = []
    for line in lines:
        page.append(line)
        if len(page) >= 42:
            pages.append(page)
            page = []
    if page:
        pages.append(page)
    if not pages:
        pages = [[""]]

    kids = " ".join(f"{3 + i} 0 R" for i in range(len(pages)))
    font_id = 3 + 2 * len(pages)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"),
    ]
    streams = [_page_stream(page_lines) for page_lines in pages]
    for index, stream in enumerate(streams):
        content_id = 3 + len(pages) + index
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode("ascii")
        )
    for stream in streams:
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    xref_positions = [0]
    buffer = bytearray(b"%PDF-1.4\n")
    for index, obj in enumerate(objects, start=1):
        xref_positions.append(len(buffer))
        buffer.extend(f"{index} 0 obj\n".encode("ascii"))
        buffer.extend(obj)
        buffer.extend(b"\nendobj\n")
    xref_start = len(buffer)
    buffer.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    buffer.extend(b"0000000000 65535 f \n")
    for pos in xref_positions[1:]:
        buffer.extend(f"{pos:010d} 00000 n \n".encode("ascii"))
    buffer.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(buffer))


def _too_thin(text: str) -> bool:
    return len((text or "").strip()) < 40


def _extract_pdfplumber(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber is not installed")
        return ""
    try:
        chunks: list[str] = []
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return ""
            for page in pdf.pages:
                chunk = page.extract_text(layout=True) or page.extract_text() or ""
                if chunk.strip():
                    chunks.append(chunk)
        return "\n".join(chunks)
    except Exception as exc:
        logger.warning("pdfplumber failed on %s: %s", path.name, type(exc).__name__)
        return ""


def _extract_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf is not installed")
        return ""
    try:
        reader = PdfReader(str(path), strict=False)
        chunks = [(page.extract_text() or "") for page in reader.pages]
        return "\n".join(chunks)
    except Exception as exc:
        logger.warning("pypdf failed on %s: %s", path.name, type(exc).__name__)
        return ""


def _wrap_lines(text: str, width: int) -> list[str]:
    wrapped: list[str] = []
    for raw in text.splitlines() or [""]:
        line = raw.rstrip()
        if not line:
            wrapped.append("")
            continue
        while len(line) > width:
            cut = line.rfind(" ", 0, width)
            if cut < 20:
                cut = width
            wrapped.append(line[:cut])
            line = line[cut:].lstrip()
        wrapped.append(line)
    return wrapped


def _page_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 11 Tf", "50 750 Td"]
    for line in lines:
        commands.append(f"({_pdf_escape(line)}) Tj")
        commands.append("0 -16 Td")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
