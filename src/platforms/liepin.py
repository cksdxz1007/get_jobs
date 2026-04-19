# platforms/liepin.py
"""
猎聘 (Liepin) 平台自动化投递

参考 Java 版: src/main/java/com/getjobs/worker/liepin/Liepin.java
核心逻辑：
1. 登录（微信扫码）→ 保存 Cookie
2. 拦截 searchfront4c API 解析职位列表
3. 自动点击"聊一聊"按钮投递
4. 翻页遍历（最多50页）
"""
from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import datetime
from typing import Optional

from playwright.async_api import Page, BrowserContext

from ..automation.browser import PlaywrightUtil, DeviceType
from ..automation.cookies import CookieManager
from ..db.database import Database
from ..models.job import Job, ApplyResult
from ..utils.ai import AIMatcher
from .base import PlatformHandler


# 页面选择器（参考 Java 版 Locators.java）
SELECTORS = {
    # QR 扫码登录
    "qr_modal": ".login-scan-modal, [class*='qrcode'], .scan-code",
    "qr_img": "img[src*='qrcode'], canvas.qrcode-img, .login-scan-content img",

    # 登录状态
    "logged_in_nav": ".header-nav, .lp-header, [class*='nav']",
    "user_avatar": "[class*='avatar'], [class*='user']",

    # 搜索
    "search_input": "input[name*='keyword'], input[placeholder*='搜索'], #keywordInput",
    "search_btn": "button.search-btn, .search-button, input[type='submit']",

    # 职位卡片
    "job_card": ".job-card-box, .job-list-box [class*='job-card'], .job-item",
    "job_card_inner": ".job-card-box, [class*='job-card']",

    # HR 区域
    "hr_info_box": ".recruiter-info-box, .recruiter-info, .hr-info",
    "hr_contact": ".contact-info, [class*='hr-'], [class*='recruiter']",
    "card_footer": ".job-card-footer, .card-footer, .job-bottom",

    # "聊一聊" 按钮
    "chat_btn": "button.ant-btn.ant-btn-primary.ant-btn-round, button[class*='ant-btn'][class*='primary'], button:has-text('聊一聊')",

    # 聊天窗口
    "chat_panel": ".chat-panel, [class*='chat-window'], .im-window",
    "chat_header": ".chat-header, [class*='chat-title']",
    "chat_close": "[class*='close-chat'], [class*='chat-close'], .icon-close",
    "chat_input": "textarea.chat-input, [class*='chat-input'] textarea, input.chat-msg-input",

    # 分页
    "next_page_btn": ".next-page, [class*='next'], [class*='pager'] button:has-text('下一页')",
    "page_loading": ".loading, [class*='loading']",
    "no_more_jobs": ".empty-tip, .no-data",

    # 职位详情
    "salary": "[class*='salary'], .job-salary",
    "company_name": "[class*='company-name'], .comp-name",
    "job_title": "[class*='job-title'], .position-name, h1.title",
}


class LiepinHandler(PlatformHandler):
    """猎聘平台处理器"""

    platform_name = "liepin"
    api_url_pattern = "com.liepin.searchfront4c.pc-search-job"
    api_exclude_pattern = "com.liepin.searchfront4c.pc-search-job-cond-init"

    def __init__(
        self,
        cookie_manager: CookieManager,
        db: Database,
        delay_min: float = 3.0,
        delay_max: float = 8.0,
        daily_limit: int = 100,
        ai_matcher: AIMatcher = None,
    ):
        self.cookie_manager = cookie_manager
        self.db = db
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.daily_limit = daily_limit
        self.ai_matcher = ai_matcher
        self.util = None  # injected by caller

        # 运行时状态
        self._applied_today = 0
        self._stop_requested = False

    def _rand_delay(self):
        return random.uniform(self.delay_min, self.delay_max)

    async def is_logged_in(self, page: Page) -> bool:
        """通过检查页面是否有用户头像或登录弹窗来判断登录状态"""
        try:
            await page.wait_for_selector(
                "[class*='avatar'], [class*='user-name'], .header-user",
                timeout=3000,
            )
            return True
        except Exception:
            pass

        # 检查是否有登录弹窗（未登录时会弹二维码）
        try:
            await page.wait_for_selector(
                "[class*='qrcode'], [class*='login'], [class*='scan']",
                timeout=2000,
            )
            return False
        except Exception:
            return False

    async def login(self, page: Page) -> bool:
        """
        微信扫码登录，保存 cookie 到文件
        流程：
        1. 访问猎聘官网
        2. 检查是否已登录（Cookie 有效）
        3. 若未登录，等待扫码，保存新 Cookie
        """
        # 先尝试加载已有 cookie
        await self.cookie_manager.apply_to_context(page.context)
        await page.goto("https://www.liepin.com/", wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(2)

        if await self.is_logged_in(page):
            print("[Liepin] Cookie 有效，已登录")
            await self.cookie_manager.save_from_context(page.context)
            return True

        print("[Liepin] Cookie 无效，开始扫码登录...")
        # 点击登录按钮触发扫码弹窗
        try:
            login_btn = page.locator("[class*='login'], a:has-text('登录')").first
            await login_btn.click(timeout=5000)
            await asyncio.sleep(1)
        except Exception:
            pass

        # 等待二维码出现
        try:
            await page.wait_for_selector(
                "img[src*='qrcode'], canvas, [class*='scan-code']",
                timeout=10_000,
            )
        except Exception:
            print("[Liepin] 未找到二维码，可能已自动登录")
            return await self.is_logged_in(page)

        print("[Liepin] 请在 120 秒内使用微信扫码...")
        # 等待扫码完成（页面变化说明登录成功）
        try:
            await page.wait_for_selector(
                "[class*='avatar'], [class*='user-name']",
                timeout=120_000,
            )
            print("[Liepin] 扫码成功！")
            await self.cookie_manager.save_from_context(page.context)
            return True
        except Exception:
            print("[Liepin] 扫码超时")
            return False

    async def search(self, keyword: str, page: Page, **kwargs) -> list[Job]:
        """
        搜索职位：
        1. 拦截 XHR API 响应
        2. 构建搜索 URL 并导航
        3. 解析每页的 jobCardList
        4. 翻页直到无新职位或达到上限
        """
        city_code = kwargs.get("city_code", "")
        salary = kwargs.get("salary", "")

        # 构建搜索 URL
        params = {"keyword": keyword}
        if city_code:
            params["city"] = city_code
        if salary:
            params["salary"] = salary

        query = "&".join(f"{k}={v}" for k, v in params.items())
        search_url = f"https://www.liepin.com/zhaopin/?{query}"

        # API 响应缓存（用于投递时获取详情）
        api_entities_cache: list[dict] = []
        jobs: list[Job] = []

        # 使用 context.route() 一次性拦截，避免 page.on() 监听器泄漏
        async def handle_route(route):
            response = await route.fetch()
            if self.api_url_pattern in response.url and self.api_exclude_pattern not in response.url:
                try:
                    body = response.json()
                    card_list = (
                        body.get("data", {}).get("data", {}).get("jobCardList")
                        or body.get("data", {}).get("jobCardList", [])
                        or body
                    )
                    if isinstance(card_list, list) and card_list:
                        api_entities_cache.extend(card_list)
                except Exception:
                    pass
            await route.continue_()

        route_handle = page.context.on("route", handle_route)

        # 分页计数
        page_num = 0
        max_pages = 50

        try:
            for page_num in range(1, max_pages + 1):
                if self._stop_requested:
                    break

                current_count = self.db.get_applied_count_today(self.platform_name)
                if current_count >= self.daily_limit:
                    print(f"[Liepin] 今日已投 {current_count} 次，达到上限 {self.daily_limit}")
                    break

                # 访问搜索页
                url = f"{search_url}&curPage={page_num - 1}"
                print(f"[Liepin] 访问第 {page_num} 页: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_load_state('networkidle', timeout=10_000)

                # 等待职位卡片加载
                try:
                    await page.wait_for_selector(
                        "[class*='job-card'], .job-list-box, [class*='job-item']",
                        timeout=10_000,
                    )
                except Exception:
                    print(f"[Liepin] 第 {page_num} 页无职位，可能已到底")
                    break

                # 收集所有职位卡片 - 修复 selector 逻辑（去掉初始赋值，直接 for/else）
                card_selectors = [
                    "[class*='job-card-box']",
                    ".job-list-box > div",
                    "[class*='job-item']",
                ]
                cards = None
                for sel in card_selectors:
                    candidates = page.locator(sel)
                    if await candidates.count() > 0:
                        cards = candidates
                        break
                if cards is None:
                    print(f"[Liepin] 第 {page_num} 页无职位卡片，停止翻页")
                    break

                card_count = await cards.count()
                print(f"[Liepin] 第 {page_num} 页发现 {card_count} 个职位")

                if card_count == 0:
                    break

                # 遍历每张卡片
                for i in range(min(card_count, 20)):  # 每页最多取20个
                    if self._stop_requested:
                        break
                    if self.db.get_applied_count_today(self.platform_name) >= self.daily_limit:
                        break

                    try:
                        card = cards.nth(i)
                        job = await self._parse_card(card, api_entities_cache, i)
                        if job and not self.db.is_applied(job.platform, job.job_id):
                            self.db.save_job(job)
                            jobs.append(job)
                            print(f"  [新职位] {job.title} @ {job.company}")
                    except Exception as e:
                        print(f"  解析第 {i} 张卡片失败: {e}")

                # 翻页
                try:
                    next_btn = page.locator("[class*='next']:not([class*='disabled']), [class*='pager'] button:has-text('下一页')").first
                    if await next_btn.is_disabled() or not await next_btn.is_visible():
                        print("[Liepin] 已到最后一页")
                        break
                    await next_btn.click()
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except Exception:
                    print("[Liepin] 未找到下一页按钮")
                    break
        finally:
            # 清理 route 监听器，避免泄漏
            if route_handle:
                await route_handle.dispose()

        return jobs

    async def _parse_card(self, card, api_entities_cache: list, index: int) -> Optional[Job]:
        """从一张职位卡片中解析出 Job 对象"""
        try:
            # 尝试从 API 缓存获取详细信息
            api_data = api_entities_cache[index] if index < len(api_entities_cache) else {}

            # 标题
            title_el = card.locator("[class*='job-title'], [class*='title'], h3, .name")
            title = await title_el.first.inner_text() if await title_el.count() > 0 else ""

            # 公司名
            company_el = card.locator("[class*='company'], .comp-name, [class*='name']")
            company = await company_el.first.inner_text() if await company_el.count() > 0 else ""

            # 薪资
            salary_el = card.locator("[class*='salary'], .salary")
            salary = await salary_el.first.inner_text() if await salary_el.count() > 0 else ""

            # 地区
            area_el = card.locator("[class*='area'], [class*='zone'], [class*='dq']")
            area = await area_el.first.inner_text() if await area_el.count() > 0 else ""

            # 经验/学历
            tags_els = card.locator("[class*='tag'], [class*='label'], span")
            tags = []
            for el in tags_els.all():
                text = (await el.inner_text()).strip()
                if text and len(text) < 20:
                    tags.append(text)

            # 职位链接
            link_el = card.locator("a[href*='liepin.com']").first
            link = await link_el.get_attribute("href") if await link_el.count() > 0 else ""
            if link and not link.startswith("http"):
                link = "https://www.liepin.com" + link

            # jobId 从链接或 data-id 中提取
            job_id = api_data.get("jobId") or re.search(r'/job/(\d+)/', link or "").group(1) if link else ""

            # 从 API 补充信息
            recruiter_name = api_data.get("recruiterName") or ""
            recruiter_title = api_data.get("recruiterTitle") or ""
            experience = api_data.get("requireWorkYears") or ""
            education = api_data.get("requireEduLevel") or ""
            company_industry = api_data.get("compIndustry") or ""
            company_scale = api_data.get("compScale") or ""
            refresh_time = api_data.get("refreshTime") or ""

            return Job(
                platform=self.platform_name,
                job_id=job_id,
                title=title.strip() if title else "",
                company=company.strip() if company else "",
                salary=salary.strip() if salary else "",
                area=area.strip() if area else "",
                experience=experience,
                education=education,
                tags=tags,
                company_industry=company_industry,
                company_scale=company_scale,
                recruiter_name=recruiter_name,
                recruiter_title=recruiter_title,
                link=link,
                refresh_time=refresh_time,
                raw_data=api_data,
            )
        except Exception as e:
            return None

    async def apply(self, job: Job, page: Page) -> ApplyResult:
        """
        对单个职位执行"聊一聊"投递：
        1. 滚动卡片到可视区
        2. Hover HR 区域，显示"聊一聊"按钮
        3. 鼠标微调后点击
        4. 等待聊天窗口打开后关闭
        """
        try:
            if self.db.is_applied(job.platform, job.job_id):
                return ApplyResult(job, True, "已投递，跳过")

            # 打开职位页
            if job.link:
                await page.goto(job.link, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(2)

            # 滚动到"聊一聊"按钮区域
            chat_btn_selectors = [
                "button.ant-btn.ant-btn-primary",
                "button[class*='primary']:has-text('聊一聊')",
                "[class*='聊一聊']",
                "button:has-text('聊一聊')",
            ]

            chat_btn = None
            for sel in chat_btn_selectors:
                locator = page.locator(sel).first
                if await locator.count() > 0 and await locator.is_visible():
                    chat_btn = locator
                    break

            if not chat_btn:
                # 尝试滚动到底部找按钮
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)
                for sel in chat_btn_selectors:
                    locator = page.locator(sel).first
                    if await locator.count() > 0:
                        chat_btn = locator
                        break

            if not chat_btn:
                return ApplyResult(job, False, "未找到'聊一聊'按钮", "button_not_found")

            # 鼠标微调后点击（模拟真人）
            box = await chat_btn.bounding_box()
            if box:
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                await page.mouse.move(cx, cy)
                await asyncio.sleep(0.1)
                # 微调
                await page.mouse.move(cx + random.randint(-3, 3), cy + random.randint(-3, 3))
                await asyncio.sleep(0.05)
                await page.mouse.move(cx, cy)
                await asyncio.sleep(0.05)

            await chat_btn.click()
            print(f"[Liepin] 已点击聊一聊: {job.title} @ {job.company}")

            # 等待聊天窗口出现
            await asyncio.sleep(2)

            # 检查聊天窗口是否出现
            chat_opened = False
            try:
                chat_panel = page.locator("[class*='chat'], [class*='im'], .chat-panel").first
                if await chat_panel.is_visible(timeout=3000):
                    chat_opened = True
                    print(f"[Liepin] 聊天窗口已打开: {job.title}")
                    # 关闭聊天窗口
                    close_btn = page.locator("[class*='close'], [class*='icon-close'], [class*='chat-close']").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
                        await asyncio.sleep(0.5)
            except Exception:
                pass

            # 更新数据库
            now = datetime.now()
            self.db.update_job_status(job.id, "success", now)
            self._applied_today += 1

            if chat_opened:
                return ApplyResult(job, True, "聊一聊成功")
            else:
                return ApplyResult(job, False, "聊天窗口未出现，投递可能被拦截", "chat_not_opened")

        except Exception as e:
            self.db.update_job_status(job.id, "failed")
            return ApplyResult(job, False, f"投递失败: {e}", str(e))

    def stop(self):
        self._stop_requested = True

    async def apply_batch(self, jobs: list[Job], page: Page, progress_callback=None):
        """批量投递多个职位"""
        results = []
        for i, job in enumerate(jobs):
            if self._stop_requested:
                break
            if self.db.get_applied_count_today(self.platform_name) >= self.daily_limit:
                print("[Liepin] 达到每日上限，停止")
                break

            # AI 匹配过滤（score >= 0.6 才投递）
            if self.ai_matcher:
                try:
                    profile = {"skills": [], "desired_roles": [], "summary": ""}
                    match_result = await self.ai_matcher.match_score(
                        job.title,
                        job.description or "",
                        profile,
                    )
                    score = match_result.get("score", 0.5)
                    if score < 0.6:
                        print(f"  [AI过滤] {job.title} @ {job.company} (匹配分 {score:.2f} < 0.6)")
                        continue
                except Exception as e:
                    print(f"  [AI匹配异常] {e}，跳过AI过滤")

            result = await self.apply(job, page)
            results.append(result)

            if progress_callback:
                progress_callback(i + 1, len(jobs), job.title, result.success)

            # 随机延时
            await asyncio.sleep(self._rand_delay())

        return results