"""
AstrBot 知识库 HTTP 客户端
通过 AstrBot Dashboard API 操作知识库
"""
from __future__ import annotations
import re
from typing import Optional, List, Dict, Any

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class AstrKBClient:
    def __init__(
        self,
        base_url: str = "http://localhost:6185",
        username: str = "",
        password: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None

    async def _ensure_auth(self) -> None:
        if self._token:
            return
        await self._login()

    async def _login(self) -> None:
        if not HAS_AIOHTTP:
            raise RuntimeError("aiohttp 未安装，无法调用 AstrBot API")
        if not self.username:
            raise RuntimeError("AstrBot API 用户名未配置，请在插件设置中填写 astr_token 或确保 AstrBot 已配置认证")
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{self.base_url}/api/auth/login",
                json={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                if data.get("status") == "ok":
                    self._token = data["data"]["token"]
                else:
                    raise RuntimeError(f"AstrBot 登录失败: {data.get('message', data)}")

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def list_kbs(self) -> List[Dict[str, Any]]:
        """列出所有知识库"""
        await self._ensure_auth()
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                f"{self.base_url}/api/kb/list",
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                return data.get("data", {}).get("items", [])

    async def import_chunks(
        self,
        kb_id: str,
        file_name: str,
        chunks: List[str],
        file_type: str = "txt",
    ) -> Dict[str, Any]:
        """向知识库导入预切片文本"""
        await self._ensure_auth()
        body = {
            "kb_id": kb_id,
            "documents": [{"file_name": file_name, "chunks": chunks, "file_type": file_type}],
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{self.base_url}/api/kb/document/import",
                json=body,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                return await resp.json()

    async def get_upload_progress(self, task_id: str) -> Dict[str, Any]:
        """查询导入任务进度"""
        await self._ensure_auth()
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                f"{self.base_url}/api/kb/document/upload/progress",
                params={"task_id": task_id},
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return await resp.json()
