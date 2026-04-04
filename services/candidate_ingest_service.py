"""
候选知识摄取服务 - 从外部接收候选知识，创建待审记录
"""
from __future__ import annotations
import uuid
from typing import Optional, List, Dict, Any

from ..storage.models import CandidateRecord, CandidateStatus
from ..storage.review_store import ReviewStore


class CandidateIngestService:
    def __init__(self, store: ReviewStore):
        self.store = store

    def ingest(
        self,
        raw_text: str,
        source_plugin: str = "manual",
        source_session: Optional[str] = None,
        source_user: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CandidateRecord:
        """接受一条原始文本，创建候选记录（status=new）"""
        candidate_id = uuid.uuid4().hex
        # scope_key 存 source_session; schema_data 存 metadata
        scope_key = source_session or ""
        schema_data = metadata or {}
        if source_user:
            schema_data = dict(schema_data)
            schema_data["_source_user"] = source_user
        record = CandidateRecord(
            id=candidate_id,
            raw_text=raw_text,
            source_plugin=source_plugin,
            scope_key=scope_key,
            schema_data=schema_data,
            status=CandidateStatus.NEW,
        )
        self.store.create_candidate(record)
        return record

    def ingest_batch(
        self,
        items: List[Dict[str, Any]],
        source_plugin: str = "batch_import",
    ) -> List[CandidateRecord]:
        """批量摄取"""
        results = []
        for item in items:
            r = self.ingest(
                raw_text=item.get("text", ""),
                source_plugin=source_plugin,
                source_session=item.get("session"),
                source_user=item.get("user"),
                metadata=item.get("metadata", {}),
            )
            results.append(r)
        return results
