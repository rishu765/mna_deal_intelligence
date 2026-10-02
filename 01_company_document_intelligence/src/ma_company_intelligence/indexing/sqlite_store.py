"""Inspectable SQLite persistence for vector records."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from types import TracebackType

from ma_company_intelligence.domain import (
    ChunkPageReference,
    DocumentChunk,
    DocumentMetadata,
    DocumentSource,
    EmbeddingVector,
    VectorRecord,
)
from ma_company_intelligence.indexing.errors import (
    IndexCompatibilityError,
    VectorDimensionError,
    VectorStoreError,
)

_SCHEMA_VERSION = 1


class SQLiteVectorStore:
    """Persist complete vector records with chunk IDs as upsert keys."""

    def __init__(
        self,
        path: Path,
        *,
        provider_name: str,
        model_name: str,
        dimension: int,
    ) -> None:
        if not provider_name.strip() or not model_name.strip():
            raise ValueError("provider_name and model_name must not be blank")
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self.path = path.resolve()
        self._provider_name = provider_name
        self._model_name = model_name
        self._dimension = dimension
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._connection = sqlite3.connect(self.path)
            self._connection.row_factory = sqlite3.Row
            self._initialize()
        except sqlite3.Error as error:
            raise VectorStoreError(f"could not open vector store at {self.path}") from error

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _initialize(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS index_manifest (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    schema_version INTEGER NOT NULL,
                    provider_name TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    dimension INTEGER NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_records (
                    record_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    source_json TEXT NOT NULL,
                    page_references_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    section TEXT,
                    vector_json TEXT NOT NULL,
                    provider_name TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    dimension INTEGER NOT NULL
                )
                """
            )

        manifest = self._connection.execute(
            "SELECT schema_version, provider_name, model_name, dimension "
            "FROM index_manifest WHERE singleton = 1"
        ).fetchone()
        if manifest is None:
            with self._connection:
                self._connection.execute(
                    "INSERT INTO index_manifest VALUES (1, ?, ?, ?, ?)",
                    (_SCHEMA_VERSION, self.provider_name, self.model_name, self.dimension),
                )
            return

        actual = (
            manifest["schema_version"],
            manifest["provider_name"],
            manifest["model_name"],
            manifest["dimension"],
        )
        expected = (_SCHEMA_VERSION, self.provider_name, self.model_name, self.dimension)
        if actual != expected:
            raise IndexCompatibilityError(
                "existing vector store manifest is incompatible: "
                f"found {actual}, expected {expected}"
            )

    def upsert(self, records: tuple[VectorRecord, ...]) -> int:
        """Atomically insert or replace records keyed by stable chunk ID."""

        for record in records:
            self._validate_record(record)
        parameters = tuple(self._serialize(record) for record in records)
        try:
            with self._connection:
                self._connection.executemany(
                    """
                    INSERT INTO vector_records (
                        record_id, document_id, chunk_index, chunk_text, source_json,
                        page_references_json, metadata_json, section, vector_json,
                        provider_name, model_name, dimension
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(record_id) DO UPDATE SET
                        document_id = excluded.document_id,
                        chunk_index = excluded.chunk_index,
                        chunk_text = excluded.chunk_text,
                        source_json = excluded.source_json,
                        page_references_json = excluded.page_references_json,
                        metadata_json = excluded.metadata_json,
                        section = excluded.section,
                        vector_json = excluded.vector_json,
                        provider_name = excluded.provider_name,
                        model_name = excluded.model_name,
                        dimension = excluded.dimension
                    """,
                    parameters,
                )
        except sqlite3.Error as error:
            raise VectorStoreError(f"could not write vector records to {self.path}") from error
        return len(records)

    def count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM vector_records").fetchone()
        if row is None:
            raise VectorStoreError("vector store count query returned no result")
        return int(row["count"])

    def get(self, record_id: str) -> VectorRecord | None:
        row = self._connection.execute(
            "SELECT * FROM vector_records WHERE record_id = ?", (record_id,)
        ).fetchone()
        return None if row is None else self._deserialize(row)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> SQLiteVectorStore:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _validate_record(self, record: VectorRecord) -> None:
        embedding = record.embedding
        if embedding.dimension != self.dimension or len(embedding.values) != self.dimension:
            raise VectorDimensionError(
                f"record {record.record_id!r} has dimension {embedding.dimension}; "
                f"expected {self.dimension}"
            )
        if embedding.provider != self.provider_name or embedding.model != self.model_name:
            raise IndexCompatibilityError(
                f"record {record.record_id!r} uses {embedding.provider}/{embedding.model}; "
                f"store expects {self.provider_name}/{self.model_name}"
            )

    @staticmethod
    def _serialize(record: VectorRecord) -> tuple[object, ...]:
        chunk = record.chunk
        return (
            record.record_id,
            chunk.document_id,
            chunk.chunk_index,
            chunk.text,
            json.dumps(asdict(chunk.source), default=str, sort_keys=True),
            json.dumps([asdict(reference) for reference in chunk.page_references], sort_keys=True),
            json.dumps(asdict(chunk.metadata), sort_keys=True),
            chunk.section,
            json.dumps(record.embedding.values, allow_nan=False),
            record.embedding.provider,
            record.embedding.model,
            record.embedding.dimension,
        )

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> VectorRecord:
        source_values = json.loads(row["source_json"])
        metadata_values = json.loads(row["metadata_json"])
        page_values = json.loads(row["page_references_json"])
        chunk = DocumentChunk(
            chunk_id=row["record_id"],
            document_id=row["document_id"],
            chunk_index=row["chunk_index"],
            text=row["chunk_text"],
            source=DocumentSource(
                filename=source_values["filename"],
                path=Path(source_values["path"]),
                media_type=source_values["media_type"],
                size_bytes=source_values["size_bytes"],
                sha256=source_values["sha256"],
            ),
            page_references=tuple(ChunkPageReference(**values) for values in page_values),
            metadata=DocumentMetadata(**metadata_values),
            section=row["section"],
        )
        embedding = EmbeddingVector(
            provider=row["provider_name"],
            model=row["model_name"],
            dimension=row["dimension"],
            values=tuple(json.loads(row["vector_json"])),
        )
        return VectorRecord(record_id=row["record_id"], chunk=chunk, embedding=embedding)
