# bili_api.py
"""B站 API 轻量客户端——调旧版接口拿动态列表，不需 WBI 签名"""
import json
import asyncio
from pathlib import Path
from logger_config import logger

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# 旧版 API，不需要 WBI 签名，带 Cookie 即可
SPACE_HISTORY_URL = (
    "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history"
    "?host_uid={uid}&offset_dynamic_id=0&need_top=1&platform=web"
)


class BiliAPI:
    """B站动态列表 API 客户端"""

    def __init__(self, cookie_file: Path):
        self.cookie_file = cookie_file

    def _load_cookie_str(self) -> str:
        """加载Cookie文件，返回Cookie字符串"""
        try:
            if not self.cookie_file.exists():
                return ""
            cookies = json.loads(self.cookie_file.read_text(encoding="utf-8"))
            return "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        except Exception as e:
            logger.error(f"Cookie加载失败: {e}")
            return ""

    async def close(self):
        pass  # 无状态，不需要清理

    async def get_dynamics(self, uid: str) -> list[dict]:
        """
        获取用户空间动态列表（用 urllib 同步请求，asyncio.to_thread 包装）。
        返回: [{"dynamic_id": "...", "type": 2, "content": "...", ...}, ...]
        """
        import urllib.request

        cookie_str = self._load_cookie_str()
        url = SPACE_HISTORY_URL.format(uid=uid)

        def _sync_request():
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": f"https://space.bilibili.com/{uid}/dynamic",
                    "Cookie": cookie_str,
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())

        try:
            data = await asyncio.to_thread(_sync_request)
        except Exception as e:
            logger.error(f"API请求失败: {e}")
            return []

        if data.get("code") != 0:
            logger.error(f"API返回异常 code={data.get('code')} msg={data.get('message')}")
            return []

        api_data = data.get("data") or {}
        cards = api_data.get("cards", [])
        result = []
        for card in cards:
            desc = card.get("desc", {})
            card_str = card.get("card", "{}")
            try:
                card_data = json.loads(card_str)
                item = card_data.get("item", {})
                content = item.get("description") or item.get("content") or ""
                images = []
                for pic in (item.get("pictures") or []):
                    src = pic.get("img_src", "")
                    if src:
                        if src.startswith("//"):
                            src = "https:" + src
                        elif src.startswith("http://"):
                            src = src.replace("http://", "https://")
                        images.append(src)
            except json.JSONDecodeError:
                content = ""
                images = []

            result.append({
                "dynamic_id": desc.get("dynamic_id_str") or str(desc.get("dynamic_id", "")),
                "type": desc.get("type", 0),
                "content": content.strip(),
                "images": images,
                "timestamp": desc.get("timestamp", 0),
            })

        return result
