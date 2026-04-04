"""
SQLite 候选知识存储层
"""

import json
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

from .models import CandidateRecord, CandidateStatus, PublishLogEntry, ReviewLogEntry


DDL = """
CREATE TABLE IF NOT EXISTS candidate_knowledge (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT \'\',
    type TEXT NOT NULL DEFAULT \'faq_card\',
    base_type TEXT NOT NULL DEFAULT \'factual\',
    schema_data TEXT NOT NULL DEFAULT \'{}\',
    raw_text TEXT NOT NULL DEFAULT \'\',
    normalized_text TEXT NOT NULL DEFAULT \'\',
    keywords TEXT NOT NULL DEFAULT \'[]\',
    confidence REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT \'new\',
    scope_key TEXT NOT NULL DEFAULT \'\',
    source_plugin TEXT NOT NULL DEFAULT \'manual\',
    change_mode TEXT NOT NULL DEFAULT \'\',
    target_kb TEXT NOT NULL DEFAULT \'\',
    published_doc_id TEXT NOT NULL DEFAULT \'\',
    conflict_ids TEXT NOT NULL DEFAULT \'[]\',
    source_refs TEXT NOT NULL DEFAULT \'[]\',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_review_log (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    action TEXT NOT NULL,
    operator TEXT NOT NULL DEFAULT \'user\',
    before_data TEXT NOT NULL DEFAULT \'{}\',
    after_data TEXT NOT NULL DEFAULT \'{}\',
    note TEXT NOT NULL DEFAULT \'\',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_publish_log (
    id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    kb_id TEXT NOT NULL DEFAULT \'\',
    doc_id TEXT NOT NULL DEFAULT \'\',
    rendered_content TEXT NOT NULL DEFAULT \'\',
    result TEXT NOT NULL DEFAULT \'pending\',
    error_message TEXT NOT NULL DEFAULT \'\',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ck_status ON candidate_knowledge(status);
CREATE INDEX IF NOT EXISTS idx_ck_source_plugin ON candidate_knowledge(source_plugin);
CREATE INDEX IF NOT EXISTS idx_crl_candidate ON candidate_review_log(candidate_id);
CREATE INDEX IF NOT EXISTS idx_cpl_candidate ON candidate_publish_log(candidate_id);
"""


def _now() -> float:
    return time.time()


def _uid() -> str:
    return uuid.uuid4().hex


class ReviewStore:
    """候选知识 SQLite 存储层"""

    def __init__(self, db_path: str):
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        for stmt in DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(stmt)
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    # ── Candidate CRUD ────────────────────────────────────────

    def create_candidate(self, rec: CandidateRecord) -> CandidateRecord:
        if not rec.id:
            rec.id = _uid()
        now = _now()
        if not rec.created_at:
            rec.created_at = now
        rec.updated_at = now
        self._conn.execute(
            """INSERT INTO candidate_knowledge
               (id, title, type, base_type, schema_data, raw_text, normalized_text,
                keywords, confidence, status, scope_key, source_plugin, change_mode,
                target_kb, published_doc_id, conflict_ids, source_refs, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rec.id, rec.title, rec.type, rec.base_type,
                json.dumps(rec.schema_data, ensure_ascii=False),
                rec.raw_text, rec.normalized_text,
                json.dumps(rec.keywords, ensure_ascii=False),
                rec.confidence, rec.status, rec.scope_key, rec.source_plugin,
                rec.change_mode, rec.target_kb, rec.published_doc_id,
                json.dumps(rec.conflict_ids, ensure_ascii=False),
                json.dumps(rec.source_refs, ensure_ascii=False),
                rec.created_at, rec.updated_at,
            )
        )
        self._conn.commit()
        return rec

    def get_candidate(self, candidate_id: str) -> Optional[CandidateRecord]:
        row = self._conn.execute(
            "SELECT * FROM candidate_knowledge WHERE id=?", (candidate_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_candidate(row)

    def list_candidates(
        self,
        status: Optional[str] = None,
        source_plugin: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CandidateRecord]:
        sql = "SELECT * FROM candidate_knowledge"
        params: List[Any] = []
        clauses = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if source_plugin:
            clauses.append("source_plugin=?")
            params.append(source_plugin)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_candidate(r) for r in rows]

    def count_candidates(self, status: Optional[str] = None) -> int:
        if status:
            return self._conn.execute(
                "SELECT COUNT(*) FROM candidate_knowledge WHERE status=?", (status,)
            ).fetchone()[0]
        return self._conn.execute("SELECT COUNT(*) FROM candidate_knowledge").fetchone()[0]

    def update_candidate(self, candidate_id: str, updates: Dict[str, Any]) -> bool:
        """更新候选知识的部分字段"""
        if not updates:
            return False
        updates["updated_at"] = _now()
        # JSON serialize complex fields
        for k in ("schema_data", "keywords", "conflict_ids", "source_refs"):
            if k in updates and not isinstance(updates[k], str):
                updates[k] = json.dumps(updates[k], ensure_ascii=False)
        set_clauses = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [candidate_id]
        self._conn.execute(
            f"UPDATE candidate_knowledge SET {set_clauses} WHERE id=?", values
        )
        self._conn.commit()
        return True

    def delete_candidate(self, candidate_id: str) -> bool:
        self._conn.execute("DELETE FROM candidate_knowledge WHERE id=?", (candidate_id,))
        self._conn.commit()
        return True

    # ── Review Log ────────────────────────────────────────────

    def add_review_log(self, entry: ReviewLogEntry) -> ReviewLogEntry:
        if not entry.id:
            entry.id = _uid()
        if not entry.created_at:
            entry.created_at = _now()
        self._conn.execute(
            """INSERT INTO candidate_review_log
               (id, candidate_id, action, operator, before_data, after_data, note, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                entry.id, entry.candidate_id, entry.action, entry.operator,
                json.dumps(entry.before_data, ensure_ascii=False),
                json.dumps(entry.after_data, ensure_ascii=False),
                entry.note, entry.created_at,
            )
        )
        self._conn.commit()
        return entry

    def get_review_logs(self, candidate_id: str) -> List[ReviewLogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM candidate_review_log WHERE candidate_id=? ORDER BY created_at ASC",
            (candidate_id,)
        ).fetchall()
        return [ReviewLogEntry(
            id=r["id"],
            candidate_id=r["candidate_id"],
            action=r["action"],
            operator=r["operator"],
            before_data=json.loads(r["before_data"] or "{}"),
            after_data=json.loads(r["after_data"] or "{}"),
            note=r["note"],
            created_at=r["created_at"],
        ) for r in rows]

    # ── Publish Log ───────────────────────────────────────────

    def add_publish_log(self, entry: PublishLogEntry) -> PublishLogEntry:
        if not entry.id:
            entry.id = _uid()
        if not entry.created_at:
            entry.created_at = _now()
        self._conn.execute(
            """INSERT INTO candidate_publish_log
               (id, candidate_id, kb_id, doc_id, rendered_content, result, error_message, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (entry.id, entry.candidate_id, entry.kb_id, entry.doc_id,
             entry.rendered_content, entry.result, entry.error_message, entry.created_at)
        )
        self._conn.commit()
        return entry

    def list_publish_logs(self, limit: int = 50, offset: int = 0) -> List[PublishLogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM candidate_publish_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        return [self._row_to_publish_log(r) for r in rows]

    def get_publish_logs_for_candidate(self, candidate_id: str) -> List[PublishLogEntry]:
        rows = self._conn.execute(
            "SELECT * FROM candidate_publish_log WHERE candidate_id=? ORDER BY created_at DESC",
            (candidate_id,)
        ).fetchall()
        return [self._row_to_publish_log(r) for r in rows]

    # ── Helpers ───────────────────────────────────────────────

    def _row_to_candidate(self, row: sqlite3.Row) -> CandidateRecord:
        return CandidateRecord(
            id=row["id"],
            title=row["title"],
            type=row["type"],
            base_type=row["base_type"],
            schema_data=json.loads(row["schema_data"] or "{}"),
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
            keywords=json.loads(row["keywords"] or "[]"),
            confidence=row["confidence"],
            status=row["status"],
            scope_key=row["scope_key"],
            source_plugin=row["source_plugin"],
            change_mode=row["change_mode"],
            target_kb=row["target_kb"],
            published_doc_id=row["published_doc_id"],
            conflict_ids=json.loads(row["conflict_ids"] or "[]"),
            source_refs=json.loads(row["source_refs"] or "[]"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_publish_log(self, row: sqlite3.Row) -> PublishLogEntry:
        return PublishLogEntry(
            id=row["id"],
            candidate_id=row["candidate_id"],
            kb_id=row["kb_id"],
            doc_id=row["doc_id"],
            rendered_content=row["rendered_content"],
            result=row["result"],
            error_message=row["error_message"],
            created_at=row["created_at"],
        )
