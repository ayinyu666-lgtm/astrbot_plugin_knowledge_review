"""
数据模型定义（面向 SQLite 存储）
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class CandidateStatus(str, Enum):
    NEW = "new"
    CLASSIFIED = "classified"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    PUBLISH_FAILED = "publish_failed"
    NEEDS_REGRESSION_FIX = "needs_regression_fix"


@dataclass
class CandidateRecord:
    id: str = ""
    title: str = ""
    type: str = "faq_card"
    base_type: str = "factual"
    schema_data: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    normalized_text: str = ""
    keywords: List[str] = field(default_factory=list)
    confidence: float = 0.0
    status: str = CandidateStatus.NEW
    scope_key: str = ""
    source_plugin: str = "manual"
    change_mode: str = ""
    target_kb: str = ""
    published_doc_id: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    # 额外字段（不存 DB 主表，从 JSON 解析）
    source_refs: List[Dict] = field(default_factory=list)
    conflict_ids: List[str] = field(default_factory=list)


@dataclass
class ReviewLogEntry:
    id: str = ""
    candidate_id: str = ""
    action: str = ""
    operator: str = "user"
    before_data: Dict[str, Any] = field(default_factory=dict)
    after_data: Dict[str, Any] = field(default_factory=dict)
    note: str = ""
    created_at: float = 0.0


@dataclass
class PublishLogEntry:
    id: str = ""
    candidate_id: str = ""
    kb_id: str = ""
    doc_id: str = ""
    rendered_content: str = ""
    result: str = "pending"
    error_message: str = ""
    created_at: float = 0.0
