"""Cross-project evidence and lineage references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


def _required(value: str, name: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError(f"{name} must not be blank")
    return normalized


class ProjectId(StrEnum):
    PROJECT_1 = "project_1"
    PROJECT_2 = "project_2"
    PROJECT_3 = "project_3"
    PROJECT_4 = "project_4"
    PROJECT_5 = "project_5"
    PROJECT_6 = "project_6"


class EvidenceKind(StrEnum):
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    URL = "url"
    DATASET = "dataset"
    CALCULATION = "calculation"
    MANAGEMENT_RESPONSE = "management_response"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """A lossless locator to evidence owned by any specialist project."""

    evidence_id: str
    source_project: ProjectId
    kind: EvidenceKind
    source_record_id: str | None = None
    document_id: str | None = None
    document_title: str | None = None
    page_numbers: tuple[int, ...] = ()
    physical_page_indexes: tuple[int, ...] = ()
    section: str | None = None
    table: str | None = None
    sheet_name: str | None = None
    cell_range: str | None = None
    row: str | None = None
    column: str | None = None
    chunk_id: str | None = None
    url: str | None = None
    excerpt: str | None = None
    project_evidence_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _required(self.evidence_id, "evidence_id"))
        if any(page < 1 for page in self.page_numbers):
            raise ValueError("page_numbers must be positive")
        if any(index < 0 for index in self.physical_page_indexes):
            raise ValueError("physical_page_indexes must be non-negative")
        if self.physical_page_indexes and len(self.physical_page_indexes) != len(self.page_numbers):
            raise ValueError("physical page indexes must align with page numbers")
        if self.kind is EvidenceKind.URL and self.url is None:
            raise ValueError("URL evidence requires url")


class LineageNodeKind(StrEnum):
    EVIDENCE = "evidence"
    SOURCE_FACT = "source_fact"
    SPECIALIST_OUTPUT = "specialist_output"
    RECONCILIATION = "reconciliation"
    SYNTHESIS = "synthesis"
    ANALYST_DECISION = "analyst_decision"


@dataclass(frozen=True, slots=True)
class LineageNode:
    node_id: str
    kind: LineageNodeKind
    source_project: ProjectId
    source_record_id: str
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LineageEdge:
    parent_node_id: str
    child_node_id: str
    relationship: str


@dataclass(frozen=True, slots=True)
class LineageGraph:
    nodes: tuple[LineageNode, ...] = ()
    edges: tuple[LineageEdge, ...] = ()

    def __post_init__(self) -> None:
        ids = tuple(node.node_id for node in self.nodes)
        if len(ids) != len(set(ids)):
            raise ValueError("lineage node IDs must be unique")
        known = set(ids)
        if any(
            edge.parent_node_id not in known or edge.child_node_id not in known
            for edge in self.edges
        ):
            raise ValueError("lineage edges must reference known nodes")
