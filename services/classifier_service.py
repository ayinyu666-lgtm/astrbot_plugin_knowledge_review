"""
AI Classification Service / AI 分类服务
Classifies candidate knowledge into business types.
Supports provider fallback chain: gate_provider_id → fallback_provider_ids → heuristic.

Uses AstrBot Context API (provider.text_chat) instead of raw HTTP calls.
"""
from __future__ import annotations
import json
import asyncio
from typing import Optional, Dict, Any, List

from astrbot.api import logger

from ..knowledge_types.schemas import BusinessKnowledgeType
from ..knowledge_types.registry import get_registry


CLASSIFY_PROMPT = """你是一个知识分类专家。请将以下文本分类为6种业务知识类型之一。

类型说明：
{hints}

待分类文本：
{text}

请返回 JSON，格式如下（不要添加 markdown 代码块）：
{{"business_type": "<类型标识>", "confidence": 0.0到1.0, "auto_tags": ["标签1", "标签2"], "reason": "分类理由"}}

可选类型标识：faq_card, rule_entry, procedure, versioned_fact, entity_profile, config_item"""


class ClassifierService:
    def __init__(self, plugin_config: Dict[str, Any], context: Any = None):
        self.config = plugin_config
        self._context = context

    def _resolve_providers(self) -> list:
        """
        Resolve provider instances via AstrBot Context API.
        Priority: gate_provider_id → fallback_provider_ids → None.
        """
        if self._context is None:
            return []

        candidate_ids: List[str] = []
        gate_id = str(self.config.get("gate_provider_id", "") or "").strip()
        if gate_id:
            candidate_ids.append(gate_id)

        fallback_ids = self.config.get("fallback_provider_ids", [])
        if isinstance(fallback_ids, str):
            fallback_ids = [s.strip() for s in fallback_ids.split(",") if s.strip()]
        if isinstance(fallback_ids, list):
            candidate_ids.extend(str(f).strip() for f in fallback_ids if str(f).strip())

        providers = []
        seen = set()
        for pid in candidate_ids:
            if pid in seen:
                continue
            seen.add(pid)
            prov = self._context.get_provider_by_id(pid)
            if prov is not None:
                providers.append(prov)
            else:
                logger.debug(f"[KR-Classifier] Provider '{pid}' 不可用 / not available")

        return providers

    async def classify(self, text: str) -> Dict[str, Any]:
        """
        Classify text via LLM with fallback chain.
        Falls back to heuristic if all providers fail.
        """
        providers = self._resolve_providers()
        if not providers:
            logger.debug("[KR-Classifier] 无可用 Provider，使用启发式 / No providers, using heuristic")
            return self._heuristic_classify(text)

        last_error = None
        for prov in providers:
            try:
                return await self._llm_classify(text, prov)
            except Exception as e:
                last_error = e
                try:
                    pid = prov.meta().id
                except Exception:
                    pid = "?"
                logger.debug(f"[KR-Classifier] Provider {pid} 失败 / failed: {e}")
                continue

        return {
            "business_type": "faq_card",
            "confidence": 0.3,
            "auto_tags": [],
            "reason": f"所有 Provider 均失败 / All providers failed ({last_error!s})，退回启发式",
            "error": str(last_error),
        }

    async def _llm_classify(self, text: str, provider: Any) -> Dict[str, Any]:
        reg = get_registry()
        hints = "\n".join(f"- {k}: {v}" for k, v in reg.get_classifier_hints().items())
        prompt = CLASSIFY_PROMPT.format(hints=hints, text=text[:1500])

        resp = await asyncio.wait_for(
            provider.text_chat(
                prompt=prompt,
                contexts=[],
                system_prompt="你是一个知识分类专家。只返回 JSON，不要包含其他文字或 markdown 代码块。",
                func_tool=None,
            ),
            timeout=30,
        )
        content = str(getattr(resp, "completion_text", "") or "").strip()
        # Remove possible markdown code block
        if content.startswith("```"):
            content = content.split("```")[1].lstrip("json").strip()
        result = json.loads(content)
        return {
            "business_type": result.get("business_type", "faq_card"),
            "confidence": float(result.get("confidence", 0.7)),
            "auto_tags": result.get("auto_tags", []),
            "reason": result.get("reason", ""),
        }

    def _heuristic_classify(self, text: str) -> Dict[str, Any]:
        """Heuristic classification fallback / 简单启发式分类"""
        lowered = text.lower()
        if any(k in lowered for k in ["如何", "怎么", "为什么", "？", "?", "what", "how", "why"]):
            return {"business_type": "faq_card", "confidence": 0.6, "auto_tags": [], "reason": "含疑问词 / question words"}
        if any(k in lowered for k in ["步骤", "step", "1.", "2.", "首先", "然后", "最后"]):
            return {"business_type": "procedure", "confidence": 0.6, "auto_tags": [], "reason": "含步骤词 / step words"}
        if any(k in lowered for k in ["禁止", "不允许", "必须", "规定", "规则", "policy"]):
            return {"business_type": "rule_entry", "confidence": 0.6, "auto_tags": [], "reason": "含规则词 / rule words"}
        if any(k in lowered for k in ["v1", "v2", "版本", "version", "update", "更新"]):
            return {"business_type": "versioned_fact", "confidence": 0.5, "auto_tags": [], "reason": "含版本词 / version words"}
        if any(k in lowered for k in ["配置", "参数", "config", "setting", "默认值"]):
            return {"business_type": "config_item", "confidence": 0.5, "auto_tags": [], "reason": "含配置词 / config words"}
        return {"business_type": "entity_profile", "confidence": 0.4, "auto_tags": [], "reason": "默认分类 / default"}
