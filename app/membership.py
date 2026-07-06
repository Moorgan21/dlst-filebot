import logging

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant

from .config import FORCE_JOIN_CHANNEL
from .redis_client import client as redis_client

logger = logging.getLogger(__name__)

_NOT_JOINED_STATUSES = {ChatMemberStatus.LEFT, ChatMemberStatus.BANNED}

# مدت زمانی که نتیجه‌ی مثبت چک عضویت کش می‌شه؛ چون قبلاً این چک روی هر پیام
# (حتی متن‌های ساده) یه رفت‌وبرگشت شبکه‌ای جدا به تلگرام می‌زد و باعث کند شدن پاسخ‌دهی می‌شد
_MEMBERSHIP_CACHE_TTL_SECONDS = 300


def _cache_key(user_id: int) -> str:
    return f"filebot:membership:{user_id}"


async def is_channel_member(client, user_id: int) -> bool:
    if not FORCE_JOIN_CHANNEL:
        return True

    if await redis_client.get(_cache_key(user_id)):
        return True

    try:
        member = await client.get_chat_member(FORCE_JOIN_CHANNEL, user_id)
        is_member = member.status not in _NOT_JOINED_STATUSES
    except UserNotParticipant:
        is_member = False
    except Exception:
        # اگه چک عضویت به هر دلیلی (مثلاً بات ادمین کانال نیست) خطا بده، به‌جای
        # بلاک کردن همهٔ کاربرها، اجازه می‌دیم رد بشن و فقط لاگ می‌کنیم
        logger.exception("failed to check channel membership for user_id=%s", user_id)
        return True

    if is_member:
        await redis_client.set(_cache_key(user_id), "1", ex=_MEMBERSHIP_CACHE_TTL_SECONDS)

    return is_member
