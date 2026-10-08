"""Text/HTML ingestion plus an optional Project 1 PDF adapter."""

from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from ma_precedent_transactions.documents.models import (
    DealDocumentSource,
    DocumentFormat,
    ParsedDealDocument,
    ParsedDealPage,
)
from ma_precedent_transactions.documents.ports import PdfDocumentParser
from ma_precedent_transactions.errors import (
    DocumentUnavailableError,
    MalformedDocumentError,
    UnsupportedDocumentFormatError,
)


@dataclass(frozen=True, slots=True)
class DealDocumentIngestor:
    source_root: Path
    pdf_parser: PdfDocumentParser | None = None

    def ingest(self, source: DealDocumentSource) -> ParsedDealDocument:
        path = (self.source_root / source.location).resolve()
        root = self.source_root.resolve()
        if root not in path.parents and path != root:
            raise DocumentUnavailableError("document path escapes configured source root")
        if not path.is_file():
            raise DocumentUnavailableError(f"document is unavailable: {source.location}")
        if source.checksum_sha256 is not None and _sha256(path) != source.checksum_sha256:
            raise MalformedDocumentError(f"checksum mismatch for {source.source_id}")
        if source.document_format is DocumentFormat.PDF:
            if self.pdf_parser is None:
                raise UnsupportedDocumentFormatError(
                    "PDF ingestion requires the optional Project 1 adapter or another PDF parser"
                )
            return self.pdf_parser.parse(source, path)
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise MalformedDocumentError(
                f"document is not valid UTF-8: {source.location}"
            ) from error
        except OSError as error:
            raise DocumentUnavailableError(f"unable to read document: {source.location}") from error
        if source.document_format is DocumentFormat.HTML:
            parser = _DealHtmlParser()
            try:
                parser.feed(raw)
                parser.close()
            except Exception as error:
                raise MalformedDocumentError(f"unable to parse HTML: {source.location}") from error
            text = parser.text
        elif source.document_format is DocumentFormat.TEXT:
            text = raw
        else:
            raise UnsupportedDocumentFormatError(
                f"unsupported document format: {source.document_format.value}"
            )
        pages = _text_pages(text)
        return ParsedDealDocument(source.source_id, source, pages)


class Project1PdfParserAdapter:
    """Translate Project 1's proven PDF output without a hard package dependency."""

    def parse(self, source: DealDocumentSource, path: Path) -> ParsedDealDocument:
        try:
            module = importlib.import_module("ma_company_intelligence.ingestion.pdf")
            parser_type = module.PdfParser
            parsed: Any = parser_type().parse(path)
        except (ImportError, AttributeError) as error:
            raise UnsupportedDocumentFormatError(
                "Project 1 PDF parser is not installed in this environment"
            ) from error
        except Exception as error:
            raise MalformedDocumentError(f"Project 1 could not parse {path.name}") from error
        pages = tuple(
            ParsedDealPage(
                page_number=int(page.page_number),
                text=str(page.text),
                section=None,
            )
            for page in parsed.pages
            if str(page.text).strip()
        )
        warnings = tuple(str(warning.message) for warning in parsed.warnings)
        if not pages:
            raise MalformedDocumentError(f"PDF contains no extractable text: {path.name}")
        return ParsedDealDocument(source.source_id, source, pages, warnings)


class _DealHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._ignored_depth = 0
        self._heading: str | None = None
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        if tag in {"h1", "h2", "h3"} and not self._ignored_depth:
            self._heading = tag
            self._heading_parts = []
        if tag in {"p", "div", "br", "li", "tr"} and not self._ignored_depth:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        if self._heading == tag:
            heading = _normalize(" ".join(self._heading_parts))
            if heading:
                self._parts.append(f"\n[Section: {heading}]\n")
            self._heading = None
            self._heading_parts = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._heading is not None:
            self._heading_parts.append(data)
        else:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self._parts)


def _text_pages(text: str) -> tuple[ParsedDealPage, ...]:
    pages: list[ParsedDealPage] = []
    current_section: str | None = None
    for raw_page in text.split("\f"):
        normalized = _normalize(raw_page)
        if not normalized:
            continue
        match = re.search(r"\[Section:\s*([^\]]+)\]", normalized)
        if match:
            current_section = match.group(1).strip()
            normalized = re.sub(r"\[Section:\s*[^\]]+\]\s*", "", normalized)
        pages.append(ParsedDealPage(len(pages) + 1, normalized, current_section))
    if not pages:
        raise MalformedDocumentError("document contains no usable text")
    return tuple(pages)


def _normalize(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()
