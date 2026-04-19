# automation/browser.py
from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import (
    AsyncPlaywright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    DeviceType,
)

from .stealth import STEALTH_JS

DEFAULT_TIMEOUT = 30_000  # 30s
DEFAULT_WAIT = 10_000     # 10s

HEADERS_DESKTOP = {
    "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    "sec-ch-ua-platform": '"macOS"',
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://www.liepin.com/",
}

HEADERS_MOBILE = {
    "sec-ch-ua": '"Chromium";v="135", "Not A(Brand";v="99"',
    "sec-ch-ua-platform": '"iOS"',
}


def _load_stealth_js() -> str:
    """加载 stealth.js，可以是本地文件或内置版本"""
    return STEALTH_JS


class BrowserManager:
    """Playwright 浏览器生命周期管理"""

    def __init__(
        self,
        headless: bool = False,
        slowmo: int = 50,
        user_data_dir: Optional[str] = None,
    ):
        self.headless = headless
        self.slowmo = slowmo
        self.user_data_dir = user_data_dir
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context_desktop: Optional[BrowserContext] = None
        self._context_mobile: Optional[BrowserContext] = None

    async def start(self):
        """启动 Playwright 和浏览器"""
        if self._browser:
            return
        self._playwright = p = await AsyncPlaywright().start()
        self._browser = await p.chromium.launch(
            headless=self.headless,
            slow_mo=self.slowmo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

    async def new_context(
        self,
        device_type: DeviceType = DeviceType.DESKTOP,
    ) -> BrowserContext:
        """创建新的浏览器上下文"""
        await self.start()
        if device_type == DeviceType.DESKTOP:
            context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                permissions=["geolocation"],
            )
        else:
            context = await self._browser.new_context(
                viewport={"width": 375, "height": 812, "device_scale_factor": 3},
                user_agent=(
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/13.0 Mobile/15E148 Safari/604.1"
                ),
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                is_mobile=True,
                has_touch=True,
            )

        # 设置 extra HTTP 头
        headers = HEADERS_DESKTOP if device_type == DeviceType.DESKTOP else HEADERS_MOBILE
        await context.set_extra_http_headers(headers)

        # 注入反检测脚本
        await context.add_init_script(_load_stealth_js())

        return context

    async def new_page(self, context: BrowserContext) -> Page:
        """创建新页面"""
        return await context.new_page()

    async def close(self):
        """关闭所有资源"""
        if self._context_mobile:
            await self._context_mobile.close()
        if self._context_desktop:
            await self._context_desktop.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._context_desktop = None
        self._context_mobile = None

    async def screenshot(self, page: Page, path: str):
        await page.screenshot(path=path)


class PlaywrightUtil:
    """浏览器操作工具类，参考 Java 版 PlaywrightUtil"""

    def __init__(self, manager: BrowserManager):
        self.manager = manager

    async def navigate(self, url: str, page: Page, device: DeviceType = DeviceType.DESKTOP):
        await page.goto(url, wait_until="networkidle", timeout=DEFAULT_TIMEOUT)

    async def sleep(self, seconds: float):
        await asyncio.sleep(seconds)

    async def sleep_millis(self, millis: int):
        await asyncio.sleep(millis / 1000)

    async def wait_for_element(
        self,
        page: Page,
        selector: str,
        timeout: int = DEFAULT_WAIT,
        device: DeviceType = DeviceType.DESKTOP,
    ):
        return page.locator(selector).wait_for(timeout=timeout)

    async def click(
        self,
        page: Page,
        selector: str,
        device: DeviceType = DeviceType.DESKTOP,
    ):
        await page.locator(selector).click(timeout=DEFAULT_TIMEOUT)

    async def fill(
        self,
        page: Page,
        selector: str,
        text: str,
        device: DeviceType = DeviceType.DESKTOP,
    ):
        await page.locator(selector).fill(text, timeout=DEFAULT_TIMEOUT)

    async def type_human_like(
        self,
        page: Page,
        selector: str,
        text: str,
        min_delay: int = 50,
        max_delay: int = 150,
        device: DeviceType = DeviceType.DESKTOP,
    ):
        """模拟人类打字，有随机延迟"""
        el = page.locator(selector)
        await el.click(timeout=DEFAULT_TIMEOUT)
        await asyncio.sleep(0.3)
        for char in text:
            await el.type(char, delay=random.randint(min_delay, max_delay))

    async def get_text(
        self,
        page: Page,
        selector: str,
        device: DeviceType = DeviceType.DESKTOP,
    ) -> str:
        el = page.locator(selector).first
        return await el.inner_text(timeout=DEFAULT_TIMEOUT) if await el.count() > 0 else ""

    async def get_attribute(
        self,
        page: Page,
        selector: str,
        attr: str,
        device: DeviceType = DeviceType.DESKTOP,
    ) -> str:
        el = page.locator(selector).first
        return await el.get_attribute(attr) if await el.count() > 0 else ""

    async def screenshot(page: Page, path: str):
        await page.screenshot(path=path, full_page=False)

    async def screenshot_element(page: Page, selector: str, path: str):
        el = page.locator(selector).first
        if await el.count() > 0:
            await el.screenshot(path=path)

    # --- 鼠标微调（模拟真人） ---
    async def mouse_move_center_then_click(self, page: Page, selector: str):
        """移动到元素中心，微调后再点击，模拟真人的鼠标轨迹"""
        el = page.locator(selector)
        box = await el.bounding_box()
        if not box:
            return
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        await page.mouse.move(cx, cy)
        await asyncio.sleep(0.1)
        await page.mouse.move(cx + random.randint(-3, 3), cy + random.randint(-3, 3))
        await asyncio.sleep(0.05)
        await page.mouse.move(cx, cy)
        await asyncio.sleep(0.05)
        await el.click()