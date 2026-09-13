"""SQLite persistence for local processing jobs."""

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from subtitle_forge_api.domain import (
    ArtifactManifestEntry,
    JobError,
    JobStage,
    SourceType,
)


class JobAlreadyExistsError(RuntimeError):
    pass


class JobNotFoundError(RuntimeError):
    pass


class JobRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str = Field(min_length=1)
    source_type: SourceType
    stage: JobStage = JobStage.PENDING
    progress: int = Field(default=0, ge=0, le=100)
    source_metadata: dict[str, str] = Field(default_factory=dict)
    error: JobError | None = None
    artifacts: tuple[ArtifactManifestEntry, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class JobRepository(Protocol):
    def create(self, record: JobRecord) -> None: ...

    def get(self, job_id: str) -> JobRecord | None: ...

    def update(self, record: JobRecord) -> None: ...

    def list_by_stages(self, stages: Iterable[JobStage]) -> tuple[JobRecord, ...]: ...


class SQLiteJobRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._connection: sqlite3.Connection | None = None
        self._lock = RLock()

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            connection = sqlite3.connect(
                self._database_path,
                check_same_thread=False,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL CHECK (progress BETWEEN 0 AND 100),
                    source_metadata_json TEXT NOT NULL,
                    error_json TEXT,
                    artifacts_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()
            self._connection = connection

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def create(self, record: JobRecord) -> None:
        with self._lock:
            connection = self._require_connection()
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO jobs (
                            job_id, source_type, stage, progress, source_metadata_json,
                            error_json, artifacts_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        self._parameters(record),
                    )
            except sqlite3.IntegrityError as error:
                raise JobAlreadyExistsError(record.job_id) from error

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            row = (
                self._require_connection()
                .execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                .fetchone()
            )
        return None if row is None else self._record_from_row(row)

    def update(self, record: JobRecord) -> None:
        with self._lock:
            connection = self._require_connection()
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE jobs SET
                        source_type = ?, stage = ?, progress = ?, source_metadata_json = ?,
                        error_json = ?, artifacts_json = ?, created_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (*self._parameters(record)[1:], record.job_id),
                )
                if cursor.rowcount != 1:
                    raise JobNotFoundError(record.job_id)

    def list_by_stages(self, stages: Iterable[JobStage]) -> tuple[JobRecord, ...]:
        stage_values = tuple(stage.value for stage in stages)
        if not stage_values:
            return ()
        placeholders = ", ".join("?" for _ in stage_values)
        with self._lock:
            rows = self._require_connection().execute(
                f"SELECT * FROM jobs WHERE stage IN ({placeholders}) ORDER BY created_at",
                stage_values,
            )
            return tuple(self._record_from_row(row) for row in rows)

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("job repository is not initialized")
        return self._connection

    @staticmethod
    def _parameters(record: JobRecord) -> tuple[object, ...]:
        error_json = None if record.error is None else record.error.model_dump_json()
        artifacts_json = json.dumps(
            [artifact.model_dump(mode="json") for artifact in record.artifacts],
            ensure_ascii=False,
        )
        return (
            record.job_id,
            record.source_type.value,
            record.stage.value,
            record.progress,
            json.dumps(record.source_metadata, ensure_ascii=False),
            error_json,
            artifacts_json,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
        )

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> JobRecord:
        error_json = row["error_json"]
        return JobRecord(
            job_id=row["job_id"],
            source_type=row["source_type"],
            stage=row["stage"],
            progress=row["progress"],
            source_metadata=json.loads(row["source_metadata_json"]),
            error=None if error_json is None else JobError.model_validate_json(error_json),
            artifacts=tuple(
                ArtifactManifestEntry.model_validate(item)
                for item in json.loads(row["artifacts_json"])
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
