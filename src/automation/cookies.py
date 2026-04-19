# automation/cookies.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from playwright.async_api import BrowserContext


COOKIE_TEMPLATE = {
    "name": "",
    "value": "",
    "domain": "",
    "path": "/",
    "expires": -1,
    "httpOnly": False,
    "secure": False,
    "sameSite": "Lax",
}


def cookie_dict_to_json_style(cookies: list[dict]) -> list[dict]:
    """确保 cookie 格式兼容 Playwright"""
    result = []
    for c in cookies:
        item = dict(COOKIE_TEMPLATE)
        item.update(c)
        # Playwright 需要的字段
        if "sameSite" not in item:
            item["sameSite"] = "Lax"
        result.append(item)
    return result


class CookieManager:
    """Cookie 存储与加载"""

    def __init__(self, cookie_path: str = "~/.jobflow/cookies/liepin.json"):
        self.cookie_path = Path(cookie_path).expanduser()
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, cookies: list[dict]):
        """保存 cookies 到文件"""
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

    def load(self) -> list[dict]:
        """从文件加载 cookies"""
        if not self.cookie_path.exists():
            return []
        with open(self.cookie_path, encoding="utf-8") as f:
            return json.load(f)

    def is_valid(self) -> bool:
        """检查 cookie 是否包含猎聘关键 cookie（acw_tc 或 TMS_UID）"""
        if not self.cookie_path.exists():
            return False
        cookies = self.load()
        if not cookies:
            return False
        names = {c.get("name", "") for c in cookies}
        # 猎聘关键 cookie：acw_tc (反爬验证) 或 TMS_UID (用户ID)
        return bool(names & {"acw_tc", "TMS_UID"})

    async def apply_to_context(self, context: BrowserContext):
        """将保存的 cookie 应用到浏览器上下文"""
        cookies = self.load()
        if not cookies:
            return
        formatted = cookie_dict_to_json_style(cookies)
        await context.add_cookies(formatted)

    async def save_from_context(self, context: BrowserContext):
        """从浏览器上下文保存 cookie"""
        cookies = await context.cookies()
        self.save(cookies)