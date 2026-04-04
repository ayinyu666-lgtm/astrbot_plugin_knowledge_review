"""
发布服务 - 将已批准的候选知识发布到 AstrBot 知识库
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any

from ..storage.models import CandidateRecord, CandidateStatus, PublishLogEntry
from ..storage.review_store import ReviewStore
from ..integrations.astr_kb_client import AstrKBClient


class PublishService:
    def __init__(self, store: ReviewStore, astr_client: AstrKBClient):
        self.store = store
        self.client = astr_client

    async def publish(
        self,
        candidate_id: str,
        kb_id: Optional[str] = None,
        kb_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        将一条已批准的候选知识发布到 AstrBot KB。
        返回操作结果字典。
        """
        record = self.store.get_candidate(candidate_id)
        if not record:
            return {"ok": False, "error": "候选记录不存在"}
        if record.status != CandidateStatus.APPROVED:
            return {"ok": False, "error": f"候选状态不是 approved: {record.status}"}

        # normalized_text 优先，否则用 raw_text
        rag_text = record.normalized_text or record.raw_text
        if not rag_text or not rag_text.strip():
            return {"ok": False, "error": "RAG 文本为空"}

        # target_kb 是 DB 列名
        target_kb_id = kb_id or record.target_kb

        # 若还没有 kb_id，尝试按名称查找
        if not target_kb_id and kb_name:
            kbs = await self.client.list_kbs()
            for kb in kbs:
                if kb.get("kb_name") == kb_name:
                    target_kb_id = kb.get("kb_id")
                    break

        if not target_kb_id:
            return {"ok": False, "error": "未指定目标知识库"}

        file_name = f"krcand_{record.id[:8]}.txt"
        try:
            result = await self.client.import_chunks(
                kb_id=target_kb_id,
                file_name=file_name,
                chunks=[rag_text],
            )
            if isinstance(result, dict) and result.get("status") == "ok":
                task_id = result.get("data", {}).get("task_id", "") if isinstance(result.get("data"), dict) else ""
                self.store.update_candidate(candidate_id, {"status": CandidateStatus.PUBLISHED})
                self.store.add_publish_log(PublishLogEntry(
                    candidate_id=candidate_id,
                    kb_id=target_kb_id,
                    doc_id=task_id,           # task_id 存入 doc_id
                    rendered_content=rag_text,
                    result="success",
                ))
                return {"ok": True, "task_id": task_id, "kb_id": target_kb_id}
            else:
                error_msg = result.get("message", str(result)) if isinstance(result, dict) else str(result)
                self.store.update_candidate(candidate_id, {"status": CandidateStatus.PUBLISH_FAILED})
                self.store.add_publish_log(PublishLogEntry(
                    candidate_id=candidate_id,
                    kb_id=target_kb_id,
                    result="failed",
                    error_message=error_msg,
                ))
                return {"ok": False, "error": error_msg}
        except Exception as e:
            self.store.update_candidate(candidate_id, {"status": CandidateStatus.PUBLISH_FAILED})
            self.store.add_publish_log(PublishLogEntry(
                candidate_id=candidate_id,
                kb_id=target_kb_id,
                result="failed",
                error_message=str(e),
            ))
            return {"ok": False, "error": str(e)}

    async def publish_batch(
        self,
        candidate_ids: List[str],
        kb_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        results = []
        for cid in candidate_ids:
            r = await self.publish(cid, kb_id=kb_id)
            r["candidate_id"] = cid
            results.append(r)
        return results
