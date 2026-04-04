"""
业务知识类型层

在基础知识类型（factual/structured/narrative/mixed）之上，
定义面向治理和发布的业务知识类型层。
"""

import copy
from enum import Enum
from typing import Any, Dict, List, Optional

# standalone - no KnowledgeType dependency needed
KnowledgeType = None  # not used here


class BusinessKnowledgeType(str, Enum):
    """业务知识类型枚举 - 面向候选治理与正式 RAG 发布"""
    FAQ_CARD = "faq_card"              # 高频问答
    RULE_ENTRY = "rule_entry"          # 规则/限制/约束
    PROCEDURE = "procedure"            # 步骤型操作
    VERSIONED_FACT = "versioned_fact"  # 带版本条件的事实
    ENTITY_PROFILE = "entity_profile"  # 对象资料卡
    CONFIG_ITEM = "config_item"        # 配置项说明


class ChangeMode(str, Enum):
    """新旧知识冲突时的处理模式"""
    APPEND = "append"       # 追加补充到已有知识
    REPLACE = "replace"     # 覆写旧知识
    COEXIST = "coexist"     # 并存（通常是版本差异）
    MERGE = "merge"         # 字段合并
    REJECT = "reject"       # 拒绝（噪音/错误候选）


# 业务类型到基础类型的映射
BUSINESS_TO_BASE_TYPE: Dict[BusinessKnowledgeType, str] = {
    BusinessKnowledgeType.FAQ_CARD: "factual",
    BusinessKnowledgeType.RULE_ENTRY: "structured",
    BusinessKnowledgeType.PROCEDURE: "mixed",
    BusinessKnowledgeType.VERSIONED_FACT: "factual",
    BusinessKnowledgeType.ENTITY_PROFILE: "mixed",
    BusinessKnowledgeType.CONFIG_ITEM: "structured",
}

# 业务类型的中文名
BUSINESS_TYPE_DISPLAY_NAMES: Dict[BusinessKnowledgeType, str] = {
    BusinessKnowledgeType.FAQ_CARD: "问答卡片",
    BusinessKnowledgeType.RULE_ENTRY: "规则条目",
    BusinessKnowledgeType.PROCEDURE: "操作步骤",
    BusinessKnowledgeType.VERSIONED_FACT: "版本化事实",
    BusinessKnowledgeType.ENTITY_PROFILE: "实体资料卡",
    BusinessKnowledgeType.CONFIG_ITEM: "配置项",
}

# 各业务类型的空 schema 模板
BUSINESS_TYPE_SCHEMAS: Dict[BusinessKnowledgeType, Dict[str, Any]] = {
    BusinessKnowledgeType.FAQ_CARD: {
        "question": "",
        "answer": "",
        "aliases": [],
        "keywords": [],
        "conditions": [],
        "scope": "",
        "source_refs": [],
        "confidence": 0.0,
    },
    BusinessKnowledgeType.RULE_ENTRY: {
        "subject": "",
        "rule": "",
        "conditions": [],
        "exceptions": [],
        "impact": "",
        "keywords": [],
        "source_refs": [],
        "confidence": 0.0,
    },
    BusinessKnowledgeType.PROCEDURE: {
        "title": "",
        "goal": "",
        "steps": [],
        "prerequisites": [],
        "expected_result": "",
        "failure_signals": [],
        "keywords": [],
        "source_refs": [],
        "confidence": 0.0,
    },
    BusinessKnowledgeType.VERSIONED_FACT: {
        "fact": "",
        "subject": "",
        "version_scope": "",
        "conditions": [],
        "conflicts_with": [],
        "keywords": [],
        "source_refs": [],
        "confidence": 0.0,
    },
    BusinessKnowledgeType.ENTITY_PROFILE: {
        "name": "",
        "category": "",
        "summary": "",
        "attributes": {},
        "related_entities": [],
        "keywords": [],
        "source_refs": [],
        "confidence": 0.0,
    },
    BusinessKnowledgeType.CONFIG_ITEM: {
        "key": "",
        "title": "",
        "description": "",
        "default_value": "",
        "allowed_values": [],
        "recommended_value": "",
        "risk_notes": [],
        "keywords": [],
        "source_refs": [],
        "confidence": 0.0,
    },
}


def get_business_type_from_string(type_str: str) -> Optional[BusinessKnowledgeType]:
    """从字符串获取业务知识类型"""
    if not type_str:
        return None
    try:
        return BusinessKnowledgeType(type_str.lower().strip())
    except ValueError:
        return None


def get_base_type(btype: BusinessKnowledgeType) -> str:
    """获取业务类型对应的基础类型"""
    return BUSINESS_TO_BASE_TYPE.get(btype, KnowledgeType.MIXED)


def get_empty_schema(btype: BusinessKnowledgeType) -> Dict[str, Any]:
    """获取业务类型的空 schema（深拷贝，防止共享引用）"""
    return copy.deepcopy(BUSINESS_TYPE_SCHEMAS.get(btype, {}))


def get_display_name(btype: BusinessKnowledgeType) -> str:
    """获取业务类型中文名"""
    return BUSINESS_TYPE_DISPLAY_NAMES.get(btype, str(btype.value))


def get_change_mode_from_string(mode_str: str) -> Optional[ChangeMode]:
    """从字符串获取 change_mode"""
    if not mode_str:
        return None
    try:
        return ChangeMode(mode_str.lower().strip())
    except ValueError:
        return None


def list_all_business_types() -> List[Dict[str, str]]:
    """列出所有业务类型（供 UI 选择）"""
    return [
        {"value": t.value, "label": BUSINESS_TYPE_DISPLAY_NAMES.get(t, t.value)}
        for t in BusinessKnowledgeType
    ]
