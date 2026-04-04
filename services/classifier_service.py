"""
AI 分类服务 - 对候选知识进行业务类型分类
支持 provider 回退链：gate_provider_id → fallback_provider_ids → 启发式分类
"""
from __future__ import annotations
import json
import asyncio
from typing import Optional, Dict, Any, List

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

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
    def __init__(self, plugin_config: Dict[str, Any]):
        self.config = plugin_config
        self._astrbot_config = self._load_astrbot_config()

    def _load_astrbot_config(self) -> Dict[str, Any]:
        try:
            import json, os
            cfg_path = "/AstrBot/data/cmd_config.json"
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding="utf-8-sig") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _get_llm_endpoints(self) -> List[Dict[str, str]]:
        """
        获取 LLM 端点列表（含回退链）。
        优先级：gate_provider_id → fallback_provider_ids
        """
        endpoints = []
        providers = self._astrbot_config.get("provider", [])
        if not isinstance(providers, list):
            return endpoints

        # 收集要尝试的 provider id 列表
        candidate_ids = []
        gate_id = self.config.get("gate_provider_id", "")
        if gate_id:
            candidate_ids.append(gate_id)

        fallback_ids = self.config.get("fallback_provider_ids", [])
        if isinstance(fallback_ids, str):
            fallback_ids = [s.strip() for s in fallback_ids.split(",") if s.strip()]
        if isinstance(fallback_ids, list):
            candidate_ids.extend(str(f).strip() for f in fallback_ids if str(f).strip())

        seen = set()
        for pid in candidate_ids:
            if pid in seen:
                continue
            seen.add(pid)
            for p in providers:
                if isinstance(p, dict) and p.get("id") == pid:
                    endpoints.append({
                        "id": pid,
                        "api_key": p.get("key", ""),
                        "base_url": p.get("api_base", "https://api.openai.com/v1"),
                        "model": p.get("model_config", {}).get("model", "gpt-3.5-turbo"),
                    })
                    break

        return endpoints

    async def classify(self, text: str) -> Dict[str, Any]:
        """
        调用 LLM 对文本进行分类。
        按回退链依次尝试，全部失败时退回启发式分类。
        返回: {business_type, confidence, auto_tags, reason}
        """
        if not HAS_AIOHTTP:
            return self._heuristic_classify(text)

        endpoints = self._get_llm_endpoints()
        if not endpoints:
            return self._heuristic_classify(text)

        last_error = None
        for ep in endpoints:
            try:
                return await self._llm_classify(text, ep)
            except Exception as e:
                last_error = e
                continue  # 尝试下一个 provider

        return {
            "business_type": "faq_card",
            "confidence": 0.3,
            "auto_tags": [],
            "reason": f"所有 LLM provider 均失败({last_error!s})，退回启发式分类",
            "error": str(last_error),
        }

    async def _llm_classify(self, text: str, endpoint: Dict[str, str]) -> Dict[str, Any]:
        reg = get_registry()
        hints = "\n".join(f"- {k}: {v}" for k, v in reg.get_classifier_hints().items())
        prompt = CLASSIFY_PROMPT.format(hints=hints, text=text[:1500])

        payload = {
            "model": endpoint["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 256,
        }
        headers = {
            "Authorization": f"Bearer {endpoint['api_key']}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{endpoint['base_url']}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                data = await resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # 移除可能的 markdown 代码块
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
        """简单启发式分类（无 LLM 时回退）"""
        lowered = text.lower()
        if any(k in lowered for k in ["如何", "怎么", "为什么", "？", "?", "what", "how", "why"]):
            return {"business_type": "faq_card", "confidence": 0.6, "auto_tags": [], "reason": "含疑问词"}
        if any(k in lowered for k in ["步骤", "step", "1.", "2.", "首先", "然后", "最后"]):
            return {"business_type": "procedure", "confidence": 0.6, "auto_tags": [], "reason": "含步骤词"}
        if any(k in lowered for k in ["禁止", "不允许", "必须", "规定", "规则", "policy"]):
            return {"business_type": "rule_entry", "confidence": 0.6, "auto_tags": [], "reason": "含规则词"}
        if any(k in lowered for k in ["v1", "v2", "版本", "version", "update", "更新"]):
            return {"business_type": "versioned_fact", "confidence": 0.5, "auto_tags": [], "reason": "含版本词"}
        if any(k in lowered for k in ["配置", "参数", "config", "setting", "默认值"]):
            return {"business_type": "config_item", "confidence": 0.5, "auto_tags": [], "reason": "含配置词"}
        return {"business_type": "entity_profile", "confidence": 0.4, "auto_tags": [], "reason": "默认分类"}
