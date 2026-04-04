"""
变更解析 - 新知识与既有知识冲突时的处理模式建议
"""
from __future__ import annotations
from typing import Optional, Tuple

from .schemas import BusinessKnowledgeType, ChangeMode

_DEPRECATION_SIGNALS = ["已废弃", "过时", "deprecated", "obsolete", "不再适用"]
_COEXIST_SIGNALS = ["v1", "v2", "版本", "version", "旧版", "新版"]


def suggest_change_mode(
    new_data: dict,
    existing_data: Optional[dict],
    new_text: str = "",
) -> Tuple[ChangeMode, str]:
    """推断最合适的变更模式"""
    if existing_data is None:
        return ChangeMode.APPEND, "首次添加，直接写入"

    lowered = new_text.lower()
    for sig in _DEPRECATION_SIGNALS:
        if sig in lowered:
            return ChangeMode.REPLACE, f"检测到废弃信号「{sig}」，建议替换旧记录"

    for sig in _COEXIST_SIGNALS:
        if sig in lowered:
            return ChangeMode.COEXIST, f"检测到多版本信号「{sig}」，建议共存"

    new_q = new_data.get("question") or new_data.get("rule_title") or new_data.get("subject") or new_data.get("key")
    old_q = existing_data.get("question") or existing_data.get("rule_title") or existing_data.get("subject") or existing_data.get("key")
    if new_q and old_q and str(new_q).strip() == str(old_q).strip():
        return ChangeMode.REPLACE, "主键相同，建议直接替换"

    return ChangeMode.MERGE, "无明确信号，建议合并"


def apply_change_mode(
    mode: ChangeMode,
    new_data: dict,
    existing_data: Optional[dict],
) -> dict:
    """根据模式合并新旧数据，返回最终 schema_data"""
    if mode == ChangeMode.APPEND:
        return dict(new_data)
    if mode == ChangeMode.REPLACE:
        return dict(new_data)
    if mode == ChangeMode.COEXIST:
        return dict(new_data)  # 调用方负责保留两条记录
    if mode == ChangeMode.REJECT:
        return dict(existing_data or {})
    # MERGE: 以 new_data 为主，旧数据补全缺失字段
    merged = dict(existing_data or {})
    merged.update({k: v for k, v in new_data.items() if v is not None and v != "" and v != []})
    return merged
