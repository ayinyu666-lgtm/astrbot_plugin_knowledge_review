"""
Memorix 桥接 - 提供从 Memorix 抓取候选知识的工具函数
（当前为占位实现，实际推送由 Memorix 插件调用本插件 REST 端点完成）
"""
from __future__ import annotations
from typing import Optional, Dict, Any


class MemorixBridge:
    """
    未来可通过 AstrBot context.get_registered_star("astrbot_plugin_memorix")
    获取 Memorix 实例并读取记忆数据。
    当前阶段：Memorix 直接通过 HTTP POST 到本插件 WebUI 的 /api/candidates/ingest
    提交候选知识。
    """

    @staticmethod
    def memorix_record_to_candidate(record: Dict[str, Any]) -> Dict[str, Any]:
        """将 Memorix 记忆记录转换为候选知识格式"""
        return {
            "text": record.get("content") or record.get("text") or "",
            "session": record.get("session_id") or record.get("scope"),
            "user": record.get("user") or record.get("user_id"),
            "metadata": {
                "memorix_id": record.get("id"),
                "created_at": record.get("created_at"),
            },
        }
