"""
知识渲染器 - 将 schema_data 渲染为人读文本和RAG文本
"""
from __future__ import annotations
from typing import List

from .schemas import BusinessKnowledgeType


def render_for_review(btype: BusinessKnowledgeType, schema_data: dict) -> str:
    """渲染为供人工审核阅读的文本"""
    fn = _REVIEW_RENDERERS.get(btype.value)
    if fn:
        return fn(schema_data)
    return str(schema_data)


def render_for_rag(btype: BusinessKnowledgeType, schema_data: dict) -> str:
    """渲染为 RAG 检索全文"""
    fn = _RAG_RENDERERS.get(btype.value)
    if fn:
        return fn(schema_data)
    return str(schema_data)


def extract_keywords(btype: BusinessKnowledgeType, schema_data: dict) -> List[str]:
    """提取关键词列表"""
    tags = schema_data.get("tags", [])
    if isinstance(tags, list):
        return [str(t) for t in tags if t]
    return []


# —— FAQ_CARD ——
def _review_faq(d: dict) -> str:
    lines = [f"【问答卡片】"]
    if d.get("question"):
        lines.append(f"Q: {d['question']}")
    if d.get("answer"):
        lines.append(f"A: {d['answer']}")
    if d.get("aliases"):
        lines.append(f"别名: {', '.join(d['aliases'])}")
    if d.get("tags"):
        lines.append(f"标签: {', '.join(d['tags'])}")
    return "\n".join(lines)

def _rag_faq(d: dict) -> str:
    parts = []
    if d.get("aliases"):
        parts.append(" / ".join(d["aliases"]))
    if d.get("question"):
        parts.append(d["question"])
    if d.get("answer"):
        parts.append(d["answer"])
    return " ".join(parts)

# —— RULE_ENTRY ——
def _review_rule(d: dict) -> str:
    lines = [f"【规则条目】{d.get('rule_title', '')}"]
    if d.get("conditions"):
        lines.append(f"触发条件: {'; '.join(d['conditions'])}")
    if d.get("effect"):
        lines.append(f"效果/规定: {d['effect']}")
    if d.get("exceptions"):
        lines.append(f"例外: {'; '.join(d['exceptions'])}")
    return "\n".join(lines)

def _rag_rule(d: dict) -> str:
    parts = [d.get("rule_title", ""), d.get("effect", "")]
    if d.get("conditions"):
        parts.extend(d["conditions"])
    return " | ".join(p for p in parts if p)

# —— PROCEDURE ——
def _review_procedure(d: dict) -> str:
    lines = [f"【操作流程】{d.get('title', '')}"]
    if d.get("prerequisites"):
        lines.append(f"前提: {'; '.join(d['prerequisites'])}")
    for i, step in enumerate(d.get("steps", []), 1):
        lines.append(f"步骤{i}: {step}")
    if d.get("notes"):
        lines.append(f"注意: {'; '.join(d['notes'])}")
    return "\n".join(lines)

def _rag_procedure(d: dict) -> str:
    parts = [d.get("title", "")]
    parts.extend(d.get("steps", []))
    return "\n".join(p for p in parts if p)

# —— VERSIONED_FACT ——
def _review_versioned(d: dict) -> str:
    lines = [f"【版本化事实】{d.get('subject', '')}"]
    if d.get("version"):
        lines.append(f"版本: {d['version']}")
    if d.get("valid_from"):
        lines.append(f"生效起: {d['valid_from']}")
    if d.get("valid_until"):
        lines.append(f"截止: {d['valid_until']}")
    if d.get("fact"):
        lines.append(f"内容: {d['fact']}")
    return "\n".join(lines)

def _rag_versioned(d: dict) -> str:
    parts = []
    if d.get("version"):
        parts.append(f"[v{d['version']}]")
    parts.append(d.get("subject", ""))
    parts.append(d.get("fact", ""))
    return " ".join(p for p in parts if p)

# —— ENTITY_PROFILE ——
def _review_entity(d: dict) -> str:
    lines = [f"【实体档案】{d.get('entity_name', '')} ({d.get('entity_type', '')})"]
    if d.get("description"):
        lines.append(d["description"])
    attrs = d.get("attributes", {})
    if isinstance(attrs, dict) and attrs:
        for k, v in attrs.items():
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)

def _rag_entity(d: dict) -> str:
    parts = [d.get("entity_name", ""), d.get("entity_type", ""), d.get("description", "")]
    attrs = d.get("attributes", {})
    if isinstance(attrs, dict):
        for k, v in attrs.items():
            parts.append(f"{k}: {v}")
    return " | ".join(p for p in parts if p)

# —— CONFIG_ITEM ——
def _review_config(d: dict) -> str:
    lines = [f"【配置项】{d.get('key', '')}"]
    if d.get("value") is not None:
        lines.append(f"值: {d['value']}")
    if d.get("default") is not None:
        lines.append(f"默认: {d['default']}")
    if d.get("description"):
        lines.append(f"说明: {d['description']}")
    return "\n".join(lines)

def _rag_config(d: dict) -> str:
    parts = [d.get("key", ""), str(d.get("value", "")), d.get("description", "")]
    return " | ".join(p for p in parts if p)


_REVIEW_RENDERERS = {
    "faq_card": _review_faq,
    "rule_entry": _review_rule,
    "procedure": _review_procedure,
    "versioned_fact": _review_versioned,
    "entity_profile": _review_entity,
    "config_item": _review_config,
}
_RAG_RENDERERS = {
    "faq_card": _rag_faq,
    "rule_entry": _rag_rule,
    "procedure": _rag_procedure,
    "versioned_fact": _rag_versioned,
    "entity_profile": _rag_entity,
    "config_item": _rag_config,
}
