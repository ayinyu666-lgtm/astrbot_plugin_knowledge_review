"""
审核服务 - 处理审核员的 approve/reject/modify 操作
"""
from __future__ import annotations
from typing import Optional, Dict, Any

from ..storage.models import CandidateRecord, CandidateStatus, ReviewLogEntry
from ..storage.review_store import ReviewStore


class ReviewService:
    def __init__(self, store: ReviewStore):
        self.store = store

    def approve(
        self,
        candidate_id: str,
        reviewer: str = "webui",
        notes: str = "",
        target_kb_id: Optional[str] = None,
        target_kb_name: Optional[str] = None,
    ) -> Optional[CandidateRecord]:
        record = self.store.get_candidate(candidate_id)
        if not record:
            return None
        if record.status not in (
            CandidateStatus.NEW,
            CandidateStatus.CLASSIFIED,
            CandidateStatus.NEEDS_REVIEW,
        ):
            return record

        updates: Dict[str, Any] = {"status": CandidateStatus.APPROVED}
        if target_kb_id:
            updates["target_kb"] = target_kb_id  # DB 列名是 target_kb

        self.store.update_candidate(candidate_id, updates)
        self.store.add_review_log(ReviewLogEntry(
            candidate_id=candidate_id,
            action="approve",
            operator=reviewer,   # ReviewLogEntry 字段是 operator
            note=notes,          # ReviewLogEntry 字段是 note
        ))
        return self.store.get_candidate(candidate_id)

    def reject(
        self,
        candidate_id: str,
        reviewer: str = "webui",
        reason: str = "",
    ) -> Optional[CandidateRecord]:
        record = self.store.get_candidate(candidate_id)
        if not record:
            return None
        self.store.update_candidate(candidate_id, {"status": CandidateStatus.REJECTED})
        self.store.add_review_log(ReviewLogEntry(
            candidate_id=candidate_id,
            action="reject",
            operator=reviewer,
            note=reason,
        ))
        return self.store.get_candidate(candidate_id)

    def modify_and_approve(
        self,
        candidate_id: str,
        new_rag_text: str,
        reviewer: str = "webui",
        notes: str = "",
        target_kb_id: Optional[str] = None,
        target_kb_name: Optional[str] = None,
    ) -> Optional[CandidateRecord]:
        """修改 RAG 文本后批准"""
        record = self.store.get_candidate(candidate_id)
        if not record:
            return None
        updates: Dict[str, Any] = {
            "status": CandidateStatus.APPROVED,
            "normalized_text": new_rag_text,  # DB 列名是 normalized_text
        }
        if target_kb_id:
            updates["target_kb"] = target_kb_id
        self.store.update_candidate(candidate_id, updates)
        self.store.add_review_log(ReviewLogEntry(
            candidate_id=candidate_id,
            action="modify_approve",
            operator=reviewer,
            note=notes,
        ))
        return self.store.get_candidate(candidate_id)
