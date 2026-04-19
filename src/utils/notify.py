# utils/notify.py
"""
Telegram 通知模块
"""
from __future__ import annotations

import os
from datetime import datetime

try:
    import telegram
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


class TelegramNotifier:
    def __init__(
        self,
        bot_token: str = None,
        chat_id: str = None,
        notify_on_success: bool = True,
        notify_on_failure: bool = False,
    ):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.notify_on_success = notify_on_success
        self.notify_on_failure = notify_on_failure
        self.bot = None
        if self.bot_token and self.chat_id and HAS_TELEGRAM:
            self.bot = telegram.Bot(token=self.bot_token)

    async def send(self, message: str):
        if not self.bot:
            print(f"[Telegram] (未配置，跳过发送): {message[:80]}")
            return
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"[Telegram] 发送失败: {e}")

    async def notify_success(self, job_title: str, company: str):
        if not self.notify_on_success:
            return
        msg = f"✅ *投递成功*\n\n📌 {job_title}\n🏢 {company}\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        await self.send(msg)

    async def notify_failure(self, job_title: str, company: str, error: str = ""):
        if not self.notify_on_failure:
            return
        msg = f"❌ *投递失败*\n\n📌 {job_title}\n🏢 {company}\n💬 {error or '未知错误'}\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        await self.send(msg)

    async def send_summary(self, platform: str, keyword: str, stats: dict):
        """发送每日统计报告"""
        total = stats.get("total", 0)
        success = stats.get("success", 0)
        failed = stats.get("failed", 0)
        skipped = stats.get("skipped", 0)

        msg = (
            f"📊 *{platform} 投递报告*\n\n"
            f"🔍 关键词: `{keyword}`\n"
            f"📋 总计: {total} 个职位\n"
            f"✅ 成功: {success}\n"
            f"❌ 失败: {failed}\n"
            f"⏭️ 跳过: {skipped}\n"
            f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await self.send(msg)

    async def send_daily_report(self, stats: dict):
        """发送早报/晚报"""
        msg = (
            f"🌅 *每日求职早报*\n\n"
            f"今日投递: {stats.get('today_success', 0)} 个\n"
            f"本周投递: {stats.get('week_success', 0)} 个\n"
            f"成功率: {stats.get('success_rate', '0%')}\n"
            f"待投递: {stats.get('pending', 0)} 个\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        await self.send(msg)