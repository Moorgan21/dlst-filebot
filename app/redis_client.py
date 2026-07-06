import redis.asyncio as redis

from .config import REDIS_URL

client = redis.from_url(REDIS_URL, decode_responses=True)
