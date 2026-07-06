import os

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

PORT = int(os.environ.get("PORT", 8080))
BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")
BASE_URL = os.environ.get("BASE_URL", f"http://127.0.0.1:{PORT}").rstrip("/")

_log_channel = os.environ.get("LOG_CHANNEL", "").strip()
LOG_CHANNEL = int(_log_channel) if _log_channel else None

_admin_id = os.environ.get("ADMIN_ID", "").strip()
ADMIN_ID = int(_admin_id) if _admin_id else None

# اندازه هر بخش (chunk) که تلگرام برای دانلود فایل استفاده می‌کند
CHUNK_SIZE = 1024 * 1024

# حداکثر تعداد لینک‌های فعال هم‌زمان در کل ربات؛ مازاد روی این تعداد صف می‌شه
MAX_ACTIVE_LINKS = int(os.environ.get("MAX_ACTIVE_LINKS", 25))

# مدت اعتبار هر لینک پس از فعال شدن (به دقیقه)
LINK_TTL_MINUTES = int(os.environ.get("LINK_TTL_MINUTES", 120))
LINK_TTL_SECONDS = LINK_TTL_MINUTES * 60

# کل پهنای‌باند سرور (مگابیت بر ثانیه) که به‌طور پویا بین لینک‌های فعال تقسیم می‌شه؛
# مثلاً با ۲ لینک فعال هرکدوم ۱۰۰ می‌گیرن، با ۲۵ تا (سقف MAX_ACTIVE_LINKS) هرکدوم ۸ می‌گیرن
TOTAL_SERVER_MBPS = float(os.environ.get("TOTAL_SERVER_MBPS", 200))
if TOTAL_SERVER_MBPS <= 0:
    raise ValueError("TOTAL_SERVER_MBPS باید عددی بزرگ‌تر از صفر باشه")
TOTAL_SERVER_BYTES_PER_SECOND = int(TOTAL_SERVER_MBPS * 1_000_000 / 8)

# حداکثر تعداد فایلی که هر کاربر در بازه‌ی FILE_RATE_WINDOW_HOURS می‌تونه بفرسته و لینک بگیره
MAX_FILES_PER_WINDOW = int(os.environ.get("MAX_FILES_PER_WINDOW", 5))
FILE_RATE_WINDOW_HOURS = int(os.environ.get("FILE_RATE_WINDOW_HOURS", 2))
FILE_RATE_WINDOW_SECONDS = FILE_RATE_WINDOW_HOURS * 60 * 60

# آدرس اتصال به ردیس؛ برای نگهداری لینک‌های فعال، صف و محدودیت‌های نرخ (پایدار در برابر ری‌استارت)
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

# تعداد HandlerTask های همزمان پایگرام برای پردازش آپدیت‌ها (پیش‌فرض خودِ کتابخونه ۸ است)
PYROGRAM_WORKERS = int(os.environ.get("PYROGRAM_WORKERS", 32))

# اختیاری: یوزرنیم کانالی که عضویت توش برای استفاده از بات اجباریه (بدون @ یا لینک کامل)
_force_join_channel = os.environ.get("FORCE_JOIN_CHANNEL", "").strip().lstrip("@")
if _force_join_channel.startswith("https://t.me/"):
    _force_join_channel = _force_join_channel.rsplit("/", 1)[-1]
FORCE_JOIN_CHANNEL = f"@{_force_join_channel}" if _force_join_channel else None
FORCE_JOIN_CHANNEL_LINK = f"https://t.me/{_force_join_channel}" if _force_join_channel else None
