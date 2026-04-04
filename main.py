"""
astrbot_plugin_knowledge_review - 候选知识审核与自动入 RAG 插件
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
    "候选知识审核中心：收集-分类-审核-入 RAG 全流程管理",
    "0.2.0",
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
        logger.info("[knowledge_review] 初始化...")
        try:
            self._webui_url = await self.webui.start()
            logger.info(f"[knowledge_review] WebUI 已启动: {self._webui_url}")
        except Exception as e:
            logger.error(f"[knowledge_review] WebUI 启动失败: {e}", exc_info=True)
        logger.info("[knowledge_review] 初始化完成")

    async def terminate(self) -> None:
        logger.info("[knowledge_review] 正在停止...")
        try:
            await self.webui.stop()
        except Exception:
            pass
        logger.info("[knowledge_review] 已停止")

    @filter.command("kr_status")
    async def cmd_status(self, event: AstrMessageEvent):
        """显示审核插件状态"""
        from .storage.models import CandidateStatus
        new_count = self.store.count_candidates(CandidateStatus.NEW)
        pending = self.store.count_candidates(CandidateStatus.NEEDS_REVIEW)
        approved = self.store.count_candidates(CandidateStatus.APPROVED)
        published = self.store.count_candidates(CandidateStatus.PUBLISHED)
        webui_url = self._webui_url or "（WebUI 未启动）"
        yield event.plain_result(
            f"📦 知识审核中心\n"
            f"  新增待处理: {new_count}\n"
            f"  待人工审核: {pending}\n"
            f"  已批准待发布: {approved}\n"
            f"  已发布: {published}\n"
            f"  WebUI: {webui_url}"
        )
