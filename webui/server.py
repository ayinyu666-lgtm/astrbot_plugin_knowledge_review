"""
知识审核 WebUI 服务
FastAPI-in-thread 架构，独立于 AstrBot 主进程
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List, Optional

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from astrbot.api import logger

from ..storage.review_store import ReviewStore
from ..storage.models import CandidateStatus
from ..services.candidate_ingest_service import CandidateIngestService
from ..services.classifier_service import ClassifierService
from ..services.review_service import ReviewService
from ..services.publish_service import PublishService
from ..integrations.astr_kb_client import AstrKBClient


class KRWebUIServer:
    def __init__(self, store: ReviewStore, config: Dict[str, Any], context: Any = None):
        self.store = store
        self.config = config
        self.context = context
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._app: Optional[Any] = None
        self._server: Optional[Any] = None

        # 初始化服务
        self.ingest_service = CandidateIngestService(store)
        self.classifier_service = ClassifierService(config)
        self.review_service = ReviewService(store)

        # AstrBot KB 客户端
        astr_base = config.get("astr_base_url", "http://localhost:6185")
        if not astr_base.startswith("http"):
            astr_base = f"http://{astr_base}"
        self._astr_client = AstrKBClient(
            base_url=astr_base,
            username=self._get_astr_username(),
            password=self._get_astr_password(),
        )
        self.publish_service = PublishService(store, self._astr_client)

    def _get_astr_username(self) -> str:
        try:
            with open("/AstrBot/data/cmd_config.json") as f:
                cfg = json.load(f)
            return cfg.get("dashboard", {}).get("username", "astrbot")
        except Exception:
            return "astrbot"

    def _get_astr_password(self) -> str:
        try:
            with open("/AstrBot/data/cmd_config.json") as f:
                cfg = json.load(f)
            return cfg.get("dashboard", {}).get("password", "")
        except Exception:
            return ""

    def _build_app(self) -> Any:
        if not HAS_FASTAPI:
            raise RuntimeError("fastapi/uvicorn 未安装")

        app = FastAPI(title="Knowledge Review WebUI", version="0.1.0")

        # ── 静态文件 ──
        web_dir = os.path.join(os.path.dirname(__file__), "web")
        if os.path.exists(web_dir):
            @app.get("/", response_class=HTMLResponse)
            async def index():
                with open(os.path.join(web_dir, "index.html"), encoding="utf-8") as f:
                    return f.read()
        else:
            @app.get("/", response_class=HTMLResponse)
            async def index():
                return "<h1>Knowledge Review Plugin</h1><p>web/ 目录不存在</p>"

        # ── 候选知识 API ──
        @app.get("/api/candidates")
        async def list_candidates(
            status: Optional[str] = None,
            page: int = 1,
            page_size: int = 20,
        ):
            st = CandidateStatus(status) if status else None
            items = self.store.list_candidates(status=st, offset=(page - 1) * page_size, limit=page_size)
            total = self.store.count_candidates(status=st)
            return {"ok": True, "data": {"items": [_rec_to_dict(r) for r in items], "total": total, "page": page, "page_size": page_size}}

        @app.get("/api/candidates/{candidate_id}")
        async def get_candidate(candidate_id: str):
            r = self.store.get_candidate(candidate_id)
            if not r:
                raise HTTPException(404, "候选记录不存在")
            return {"ok": True, "data": _rec_to_dict(r)}

        @app.post("/api/candidates/ingest")
        async def ingest_candidate(request: Request):
            body = await request.json()
            text = body.get("text", "").strip()
            if not text:
                raise HTTPException(400, "text 不能为空")
            record = self.ingest_service.ingest(
                raw_text=text,
                source_plugin=body.get("source", "manual"),
                source_session=body.get("session"),
                source_user=body.get("user"),
                metadata=body.get("metadata", {}),
            )
            # 如果配置了 auto_classify，异步触发分类
            if self.config.get("auto_classify", True):
                asyncio.create_task(_auto_classify(self, record.id, text))
            return {"ok": True, "data": _rec_to_dict(record)}

        @app.post("/api/candidates/{candidate_id}/classify")
        async def classify_candidate(candidate_id: str):
            r = self.store.get_candidate(candidate_id)
            if not r:
                raise HTTPException(404, "候选记录不存在")
            result = await self.classifier_service.classify(r.raw_text)
            self.store.update_candidate(
                candidate_id,
                {
                    "status": CandidateStatus.CLASSIFIED,
                    "type": result.get("business_type", ""),        # DB 列名是 type
                    "confidence": result.get("confidence", 0.0),
                },
            )
            return {"ok": True, "data": result}

        @app.post("/api/candidates/{candidate_id}/approve")
        async def approve_candidate(candidate_id: str, request: Request):
            body = await request.json()
            r = self.review_service.approve(
                candidate_id,
                reviewer=body.get("reviewer", "webui"),
                notes=body.get("notes", ""),
                target_kb_id=body.get("kb_id"),
                target_kb_name=body.get("kb_name"),
            )
            if not r:
                raise HTTPException(404, "候选记录不存在")
            return {"ok": True, "data": _rec_to_dict(r)}

        @app.post("/api/candidates/{candidate_id}/reject")
        async def reject_candidate(candidate_id: str, request: Request):
            body = await request.json()
            r = self.review_service.reject(candidate_id, reason=body.get("reason", ""))
            if not r:
                raise HTTPException(404, "候选记录不存在")
            return {"ok": True, "data": _rec_to_dict(r)}

        @app.post("/api/candidates/{candidate_id}/modify")
        async def modify_candidate(candidate_id: str, request: Request):
            body = await request.json()
            new_text = body.get("rag_text", "").strip()
            if not new_text:
                raise HTTPException(400, "rag_text 不能为空")
            r = self.review_service.modify_and_approve(
                candidate_id,
                new_rag_text=new_text,
                reviewer=body.get("reviewer", "webui"),
                notes=body.get("notes", ""),
                target_kb_id=body.get("kb_id"),
                target_kb_name=body.get("kb_name"),
            )
            if not r:
                raise HTTPException(404, "候选记录不存在")
            return {"ok": True, "data": _rec_to_dict(r)}

        @app.post("/api/candidates/{candidate_id}/publish")
        async def publish_candidate(candidate_id: str, request: Request):
            body = await request.json()
            result = await self.publish_service.publish(
                candidate_id,
                kb_id=body.get("kb_id"),
                kb_name=body.get("kb_name"),
            )
            return {"ok": result.get("ok", False), "data": result}

        @app.post("/api/candidates/publish-batch")
        async def publish_batch(request: Request):
            body = await request.json()
            ids = body.get("ids", [])
            kb_id = body.get("kb_id")
            results = await self.publish_service.publish_batch(ids, kb_id=kb_id)
            return {"ok": True, "data": results}

        @app.delete("/api/candidates/{candidate_id}")
        async def delete_candidate(candidate_id: str):
            ok = self.store.delete_candidate(candidate_id)
            if not ok:
                raise HTTPException(404, "候选记录不存在")
            return {"ok": True}

        # ── 知识库列表 ──
        @app.get("/api/kbs")
        async def list_kbs():
            try:
                kbs = await self._astr_client.list_kbs()
                return {"ok": True, "data": kbs}
            except Exception as e:
                return {"ok": False, "error": str(e), "data": []}

        # ── 发布记录 ──
        @app.get("/api/publish-log")
        async def publish_log(page: int = 1, page_size: int = 20):
            logs = self.store.list_publish_logs(offset=(page - 1) * page_size, limit=page_size)
            return {"ok": True, "data": [_plog_to_dict(l) for l in logs]}

        return app

    async def start(self) -> str:
        host = self.config.get("webui_host", "0.0.0.0")
        port = int(self.config.get("webui_port", 8095))
        self._app = self._build_app()

        config = uvicorn.Config(self._app, host=host, port=port, log_level="warning")
        self._server = uvicorn.Server(config)

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._server.serve())

        self._thread = threading.Thread(target=_run, daemon=True, name="kr-webui")
        self._thread.start()
        url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}"
        logger.info(f"[knowledge_review] WebUI started at {url}")
        return url

    async def stop(self):
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5)


async def _auto_classify(server: KRWebUIServer, candidate_id: str, text: str) -> None:
    try:
        result = await server.classifier_service.classify(text)
        server.store.update_candidate(
            candidate_id,
            {
                "status": CandidateStatus.CLASSIFIED,
                "type": result.get("business_type", ""),
                "confidence": result.get("confidence", 0.0),
            },
        )
    except Exception as e:
        logger.warning(f"[knowledge_review] 自动分类失败 {candidate_id}: {e}")


def _rec_to_dict(r: Any) -> Dict[str, Any]:
    import dataclasses
    d = dataclasses.asdict(r)
    # status 可能是枚举或普通字符串，统一转为字符串
    st = r.status
    d["status"] = st.value if hasattr(st, "value") else str(st)
    return d


def _plog_to_dict(l: Any) -> Dict[str, Any]:
    import dataclasses
    return dataclasses.asdict(l)
