"""
astrbot_plugin_knowledge_review - Knowledge Candidate Review & Auto-RAG Plugin
候选知识审核与自动入 RAG 插件
"""
from __future__ import annotations

import os
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register

from .storage.review_store import ReviewStore
from .webui.server import KRWebUIServer


@register(
    "astrbot_plugin_knowledge_review",
    "yulong",
    "候选知识审核中心：收集-分类-审核-入 RAG 全流程管理 / Knowledge Review Center: collect-classify-review-publish to RAG",
    "0.3.0",
)
class KnowledgeReviewPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = dict(config or {})

        # 持久化数据目录
        self._data_dir = StarTools.get_data_dir("astrbot_plugin_knowledge_review")
        os.makedirs(self._data_dir, exist_ok=True)

        db_path = os.path.join(self._data_dir, "review.db")
        self.store = ReviewStore(db_path)

        self.webui: KRWebUIServer = KRWebUIServer(self.store, self.config, context)
        self._webui_url: str = ""

    async def initialize(self) -> None:
        """Plugin initialization / 插件初始化"""
        logger.info("[knowledge_review] 初始化 / Initializing...")

        try:
            self._webui_url = await self.webui.start()
            logger.info(f"[knowledge_review] WebUI 已启动 / started: {self._webui_url}")
        except Exception as e:
            logger.error(f"[knowledge_review] WebUI 启动失败 / start failed: {e}", exc_info=True)
        logger.info("[knowledge_review] 初始化完成 / Initialization complete")

    async def terminate(self) -> None:
        logger.info("[knowledge_review] 正在停止 / Stopping...")
        try:
            await self.webui.stop()
        except Exception:
            pass
        logger.info("[knowledge_review] 已停止 / Stopped")

    @filter.command("kr_providers")
    async def list_providers(self, event: AstrMessageEvent):
        """列出所有可用的 AI Provider / List all available AI Providers"""
        providers = self.context.get_all_providers()
        if not providers:
            yield event.plain_result(
                "⚠️ 当前无可用 Provider / No providers available."
            )
            return

        lines = ["🤖 可用 Provider / Available Providers:\n"]
        for p in providers:
            try:
                meta = p.meta()
                lines.append(f"  • {meta.id}  (model: {meta.model})")
            except Exception:
                lines.append(f"  • {getattr(p, 'model_name', '?')}")

        gate_id = str(self.config.get("gate_provider_id", "") or "").strip()
        fallbacks = self.config.get("fallback_provider_ids", [])
        lines.append(f"\n📌 当前分类 Provider / Current Classifier: {gate_id or '(默认/default)'}")
        if fallbacks:
            lines.append(f"📌 回退链 / Fallback: {', '.join(str(f) for f in fallbacks)}")
        lines.append("\n💡 将上方 ID 填入插件设置即可 / Copy an ID above into plugin config")

        yield event.plain_result("\n".join(lines))

    @filter.command("kr_status")
    async def cmd_status(self, event: AstrMessageEvent):
        """显示审核插件状态 / Show review plugin status"""
        from .storage.models import CandidateStatus
        new_count = self.store.count_candidates(CandidateStatus.NEW)
        pending = self.store.count_candidates(CandidateStatus.NEEDS_REVIEW)
        approved = self.store.count_candidates(CandidateStatus.APPROVED)
        published = self.store.count_candidates(CandidateStatus.PUBLISHED)
        webui_url = self._webui_url or "（WebUI 未启动 / not running）"
        yield event.plain_result(
            f"📦 知识审核中心 / Knowledge Review Center\n"
            f"  新增待处理 / New: {new_count}\n"
            f"  待人工审核 / Pending Review: {pending}\n"
            f"  已批准待发布 / Approved: {approved}\n"
            f"  已发布 / Published: {published}\n"
            f"  WebUI: {webui_url}"
        )
