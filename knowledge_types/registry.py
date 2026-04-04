"""
Schema 注册表 - 管理所有业务知识类型的元数据
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .schemas import BusinessKnowledgeType, ChangeMode


@dataclass
class TypeRegistration:
    btype: BusinessKnowledgeType
    display_name: str
    base_type: str
    schema_template: dict
    required_fields: List[str]
    classifier_hint: str
    conflict_strategy: ChangeMode


class SchemaRegistry:
    def __init__(self):
        self._registry: Dict[str, TypeRegistration] = {}

    def register(self, reg: TypeRegistration) -> None:
        self._registry[reg.btype.value] = reg

    def get(self, btype: BusinessKnowledgeType) -> Optional[TypeRegistration]:
        return self._registry.get(btype.value)

    def get_by_string(self, s: str) -> Optional[TypeRegistration]:
        return self._registry.get(s)

    def all_types(self) -> List[BusinessKnowledgeType]:
        return [r.btype for r in self._registry.values()]

    def all_registrations(self) -> List[TypeRegistration]:
        return list(self._registry.values())

    def is_registered(self, btype: BusinessKnowledgeType) -> bool:
        return btype.value in self._registry

    def get_classifier_hints(self) -> Dict[str, str]:
        return {k: v.classifier_hint for k, v in self._registry.items()}


_registry: Optional[SchemaRegistry] = None


def get_registry() -> SchemaRegistry:
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
        _init_registry(_registry)
    return _registry


def _init_registry(r: SchemaRegistry) -> None:
    r.register(TypeRegistration(
        btype=BusinessKnowledgeType.FAQ_CARD,
        display_name="问答卡片",
        base_type="structured",
        schema_template={"question": "", "answer": "", "aliases": [], "tags": []},
        required_fields=["question", "answer"],
        classifier_hint='包含明确问题和解答，常以"为什么""怎么""如何"开头',
        conflict_strategy=ChangeMode.REPLACE,
    ))
    r.register(TypeRegistration(
        btype=BusinessKnowledgeType.RULE_ENTRY,
        display_name="规则条目",
        base_type="factual",
        schema_template={"rule_title": "", "conditions": [], "effect": "", "exceptions": [], "tags": []},
        required_fields=["rule_title", "effect"],
        classifier_hint='描述约束、规定、禁止事项，常含"不允许""必须""禁止"等',
        conflict_strategy=ChangeMode.REPLACE,
    ))
    r.register(TypeRegistration(
        btype=BusinessKnowledgeType.PROCEDURE,
        display_name="操作流程",
        base_type="structured",
        schema_template={"title": "", "steps": [], "prerequisites": [], "notes": [], "tags": []},
        required_fields=["title", "steps"],
        classifier_hint='描述操作步骤序列，常含数字序号、"首先""然后""最后"等',
        conflict_strategy=ChangeMode.REPLACE,
    ))
    r.register(TypeRegistration(
        btype=BusinessKnowledgeType.VERSIONED_FACT,
        display_name="版本化事实",
        base_type="factual",
        schema_template={"subject": "", "fact": "", "valid_from": "", "valid_until": "", "version": "", "tags": []},
        required_fields=["subject", "fact"],
        classifier_hint='包含版本号、时间戳、"从X版本起"等，事实会随版本变化',
        conflict_strategy=ChangeMode.COEXIST,
    ))
    r.register(TypeRegistration(
        btype=BusinessKnowledgeType.ENTITY_PROFILE,
        display_name="实体档案",
        base_type="mixed",
        schema_template={"entity_name": "", "entity_type": "", "attributes": {}, "description": "", "tags": []},
        required_fields=["entity_name", "entity_type"],
        classifier_hint='描述特定对象（人、物、地点、概念）的属性和特征',
        conflict_strategy=ChangeMode.MERGE,
    ))
    r.register(TypeRegistration(
        btype=BusinessKnowledgeType.CONFIG_ITEM,
        display_name="配置项",
        base_type="factual",
        schema_template={"key": "", "value": None, "value_type": "string", "description": "", "default": None, "tags": []},
        required_fields=["key", "value"],
        classifier_hint='配置参数、系统设置，常含"默认值""参数""设置"等',
        conflict_strategy=ChangeMode.REPLACE,
    ))
