import asyncio
import logging

from aiohttp import web
from pyrogram import Client

from . import pyrogram_patch  # noqa: F401  # باید قبل از هر resolve_peer اعمال بشه

from .config import API_ID, API_HASH, BOT_TOKEN, BIND_ADDRESS, PORT, PYROGRAM_WORKERS
from .redis_client import client as redis_client
from .stream import routes
from .throttle import shared_throttle

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# entrypoint سبک برای سرورهای استریمِ اضافی (غیر از سرور اصلی): هیچ هندلر پیامی
# نداره (no_updates=True یعنی اصلاً آپدیت تلگرام دریافت/پردازش نمی‌کنه)، فقط
# برای get_messages/stream_media استفاده می‌شه؛ چون توکن بات یکیه، چند سشن
# هم‌زمان (این + سشن اصلی روی سرور کنترل) بدون تداخل کار می‌کنن. صف/اطلاع‌رسانی
# (run_drain_loop) فقط روی سرور اصلی اجرا می‌مونه، اینجا لازم نیست.
fetch_client = Client(
    "file_to_link_bot_stream_node",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="sessions",
    workers=PYROGRAM_WORKERS,
    no_updates=True,
)


async def main():
    await fetch_client.start()
    logger.info("Stream-only node started (no_updates client)")

    app = web.Application()
    app["bot"] = fetch_client
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, BIND_ADDRESS, PORT)
    await site.start()
    logger.info("Streaming server running on %s:%s", BIND_ADDRESS, PORT)

    throttle_refresh_task = asyncio.ensure_future(shared_throttle.run_active_count_refresh_loop())

    try:
        await asyncio.Event().wait()
    finally:
        throttle_refresh_task.cancel()
        await runner.cleanup()
        await fetch_client.stop()
        await redis_client.aclose()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
