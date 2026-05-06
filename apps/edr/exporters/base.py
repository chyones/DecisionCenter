from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ExportFormatType = Literal["md", "docx", "xlsx", "pdf", "pptx"]

MIME_TYPES: dict[str, str] = {
    "md": "text/markdown",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

FILE_EXTENSIONS: dict[str, str] = {
    "md": ".md",
    "docx": ".docx",
    "xlsx": ".xlsx",
    "pdf": ".pdf",
    "pptx": ".pptx",
}


@dataclass
class ExportResult:
    format: str
    content: bytes
    filename: str
    mime_type: str
