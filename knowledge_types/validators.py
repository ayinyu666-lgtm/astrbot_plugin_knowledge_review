"""
Schema 校验器
"""
from __future__ import annotations
from typing import List, Tuple

from .schemas import BusinessKnowledgeType
from .registry import get_registry


def validate_schema(btype: BusinessKnowledgeType, schema_data: dict) -> Tuple[bool, List[str]]:
    """校验 schema_data 是否满足必填字段要求"""
    reg = get_registry().get(btype)
    if not reg:
        return False, [f"未注册的业务类型: {btype.value}"]
    errors = []
    for field in reg.required_fields:
        val = schema_data.get(field)
        if val is None or (isinstance(val, (str, list)) and not val):
            errors.append(f"必填字段为空: {field}")
    return len(errors) == 0, errors


def fill_defaults(btype: BusinessKnowledgeType, schema_data: dict) -> dict:
    """用模板默认值填充缺失字段（不覆盖已有值）"""
    reg = get_registry().get(btype)
    if not reg:
        return schema_data
    result = dict(reg.schema_template)
    result.update(schema_data)
    return result


def sanitize_schema(btype: BusinessKnowledgeType, schema_data: dict) -> dict:
    """移除模板之外的未知字段"""
    reg = get_registry().get(btype)
    if not reg:
        return schema_data
    allowed = set(reg.schema_template.keys())
    return {k: v for k, v in schema_data.items() if k in allowed}
