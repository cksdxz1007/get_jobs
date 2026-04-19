# main.py - JobFlow 入口
"""
JobFlow - Python 轻量化自动求职投递工具

用法:
    python src/main.py --keyword "Python 工程师"
    python src/main.py --keyword "后端开发" --platform liepin
    python src/main.py --config config.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from models.config import AppConfig
from db.database import Database
from automation.browser import BrowserManager, PlaywrightUtil, DeviceType
from automation.cookies import CookieManager
from platforms.liepin import LiepinHandler
from utils.notify import TelegramNotifier
from utils.ai import AIMatcher


def parse_args():
    parser = argparse.ArgumentParser(description="JobFlow - 自动求职投递工具")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--keyword", "-k", help="搜索关键词")
    parser.add_argument("--platform", "-p", default="liepin", help="平台: liepin, boss, job51, zhilian")
    parser.add_argument("--city", help="城市代码")
    parser.add_argument("--limit", type=int, help="每日投递上限")
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    parser.add_argument("--search-only", action="store_true", help="仅搜索，不投递")
    parser.add_argument("--login-only", action="store_true", help="仅登录，保存 Cookie")
    return parser.parse_args()


async def run_liepin(cfg: AppConfig, args):
    """执行猎聘自动化"""
    db = Database(os.path.expanduser(cfg.db.path))
    cookie_path = os.path.expanduser(cfg.liepin.cookie_path)

    cookie_mgr = CookieManager(cookie_path)
    browser_mgr = BrowserManager(
        headless=args.headless or cfg.browser.headless,
        slowmo=cfg.browser.slowmo,
    )
    util = PlaywrightUtil(browser_mgr)

    liepin = LiepinHandler(
        cookie_manager=cookie_mgr,
        db=db,
        delay_min=cfg.liepin.delay_min,
        delay_max=cfg.liepin.delay_max,
        daily_limit=args.limit or cfg.liepin.daily_limit,
    )
    liepin.util = util

    notifier = None
    if cfg.telegram.bot_token:
        notifier = TelegramNotifier(
            bot_token=cfg.telegram.bot_token,
            chat_id=cfg.telegram.chat_id,
            notify_on_success=cfg.telegram.notify_on_success,
            notify_on_failure=cfg.telegram.notify_on_failure,
        )

    # 启动浏览器
    await browser_mgr.start()
    context = await browser_mgr.new_context(DeviceType.DESKTOP)
    page = await browser_mgr.new_page(context)

    try:
        # 登录
        print("[JobFlow] 开始登录猎聘...")
        login_ok = await liepin.login(page)
        if not login_ok:
            print("[JobFlow] ❌ 登录失败，退出")
            return

        if args.login_only:
            print("[JobFlow] ✅ Cookie 已保存，登录任务完成")
            return

        # 搜索
        keywords = [args.keyword] if args.keyword else cfg.keywords

        for kw in keywords:
            print(f"\n[JobFlow] 🔍 开始搜索: {kw}")
            jobs = await liepin.search(kw, page, city_code=args.city or "")
            print(f"[JobFlow] 发现 {len(jobs)} 个职位")

            if args.search_only:
                print("[JobFlow] 仅搜索模式，跳过投递")
                continue

            if not jobs:
                continue

            # 过滤已投递
            unapplied = [j for j in jobs if not db.is_applied(j.platform, j.job_id)]
            print(f"[JobFlow] 待投递: {len(unapplied)} 个")

            # 批量投递
            async def progress(current, total, title, success):
                print(f"  [{current}/{total}] {'✅' if success else '❌'} {title}")
                if success and notifier:
                    await notifier.notify_success(title, "")

            results = await liepin.apply_batch(unapplied, page, progress_callback=progress)

            # 统计
            success_count = sum(1 for r in results if r.success)
            print(f"[JobFlow] ✅ 投递完成: {success_count}/{len(results)}")

            if notifier:
                await notifier.send_summary("猎聘", kw, {
                    "total": len(results),
                    "success": success_count,
                    "failed": len(results) - success_count,
                    "skipped": len(jobs) - len(unapplied),
                })

    finally:
        await browser_mgr.close()


async def main_async(args):
    # 加载配置
    config_path = Path(args.config)
    if not config_path.exists():
        # 尝试相对于工作目录
        config_path = Path(__file__).parent.parent / args.config

    if config_path.exists():
        cfg = AppConfig.from_yaml(config_path)
        print(f"[JobFlow] 加载配置: {config_path}")
    else:
        print(f"[JobFlow] 配置文件不存在，使用默认配置")
        cfg = AppConfig()

    # 根据平台选择执行器
    if args.platform == "liepin":
        await run_liepin(cfg, args)
    else:
        print(f"[JobFlow] 平台 {args.platform} 暂未实现 (P1)")
        print("目前仅支持: liepin")


def main():
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[JobFlow] 用户中断，退出")
    except Exception as e:
        print(f"[JobFlow] 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()