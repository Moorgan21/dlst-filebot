import asyncio
import logging

from aiohttp import web

from . import stats
from .bot import bot
from .config import BIND_ADDRESS, PORT
from .link_manager import link_manager
from .redis_client import client as redis_client
from .stream import routes
from .throttle import shared_throttle

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def _periodic_stats_save():
    while True:
        await asyncio.sleep(30)
        stats.save()


async def main():
    await bot.start()
    me = await bot.get_me()
    logger.info("Bot started as @%s", me.username)

    app = web.Application()
    app["bot"] = bot
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, BIND_ADDRESS, PORT)
    await site.start()
    logger.info("Streaming server running on %s:%s", BIND_ADDRESS, PORT)

    stats_task = asyncio.ensure_future(_periodic_stats_save())
    queue_task = asyncio.ensure_future(link_manager.run_drain_loop(bot))
    throttle_refresh_task = asyncio.ensure_future(shared_throttle.run_active_count_refresh_loop())

    try:
        await asyncio.Event().wait()
    finally:
        stats_task.cancel()
        queue_task.cancel()
        throttle_refresh_task.cancel()
        stats.save()
        await runner.cleanup()
        await bot.stop()
        await redis_client.aclose()


if __name__ == "__main__":
    # عمداً از asyncio.run استفاده نمی‌شود: asyncio.run یک event loop کاملاً جدید
    # می‌سازد، درحالی‌که آبجکت Client در bot.py در زمان import ساخته شده و
    # صف/تسک‌های داخلی Dispatcher را به همان event loop فعلی (get_event_loop)
    # گره زده. اگر اینجا از asyncio.run استفاده شود، آپدیت‌های تلگرام در صفی
    # می‌مانند که هیچ‌کس (روی event loop درست) آن را پردازش نمی‌کند.
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
