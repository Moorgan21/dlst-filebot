# dlst-filebot

ربات تلگرامی که فایل‌های ارسالی (سند، ویدیو، صدا، ویس، ویدیو نوت، گیف، عکس) رو می‌گیره و در ازاش یه **لینک استریم مستقیم HTTP** برمی‌گردونه؛ بدون این‌که فایل روی سرور ذخیره بشه.

## ویژگی‌ها

- استریم لحظه‌ای فایل از تلگرام به کاربر (بدون ذخیره‌سازی روی دیسک)
- پشتیبانی کامل از HTTP Range requests → قابلیت Seek در پلیر و Resume در دانلودرها
- تشخیص خودکار Content-Type و نام فایل
- ثبت آمار کل ترافیک استریم‌شده (`/traffic`، مخصوص ادمین)
- ثبت گزارش متنی هر فایل جدید (نام، حجم، فرستنده) در یک کانال خصوصی (`LOG_CHANNEL`)
- لینک‌های خروجی با یک توکن امضاشده (HMAC، کلید = `BOT_TOKEN`) محافظت می‌شن؛ بدون توکن معتبر درخواست رد می‌شه و امکان حدس‌زدن/برداشتن فایل سایر کاربران وجود نداره
- سقف پهنای‌باند کل سرور که به‌صورت پویا بین لینک‌های فعال تقسیم می‌شه، سقف تعداد لینک فعال هم‌زمان با صف FIFO، و محدودیت نرخ فایل/لینک به ازای هر کاربر (همه روی Redis، پایدار در برابر ری‌استارت)
- عضویت اجباری در یک کانال قبل از استفاده از بات (`FORCE_JOIN_CHANNEL`، اختیاری)
- قابل اجرا روی چند سرور با یک سقف پهنای‌باند/لینک فعال مشترک و سراسری (بخش «مقیاس‌پذیری روی چند سرور» رو ببین)

## ساختار پروژه

```
app/
├── main.py            # نقطه ورود سرور اصلی: بالا آوردن بات (هندلر پیام‌ها) و وب‌سرور aiohttp
├── stream_node.py      # نقطه ورود سرورهای استریمِ اضافی (بدون هندلر پیام، فقط استریم فایل)
├── bot.py              # هندلرهای پیام تلگرام (/start, /traffic, دریافت فایل، عضویت اجباری)
├── stream.py           # روت‌های HTTP استریم (GET/HEAD /dl/{chat_id}/{message_id})
├── link_manager.py     # مدیریت لینک‌های فعال، سقف MAX_ACTIVE_LINKS و صف (روی Redis)
├── throttle.py         # تقسیم پویای پهنای‌باند بین لینک‌های فعال (روی Redis، سراسری بین سرورها)
├── rate_limit.py       # محدودیت نرخ فایل/لینک به ازای هر کاربر (روی Redis)
├── membership.py       # چک عضویت اجباری در کانال (با کش کوتاه‌مدت روی Redis)
├── media.py            # تشخیص نوع فایل/نام/mime برای انواع مدیای تلگرام
├── redis_client.py     # کلاینت مشترک Redis
├── keyed_lock.py       # قفل‌های asyncio تفکیک‌شده بر اساس کلید (برای rate_limit)
├── pyrogram_patch.py   # پچ یک باگ شناخته‌شده‌ی Pyrogram (بازه‌ی ID کانال‌های جدید تلگرام)
├── range_utils.py      # پارس هدر Range و محاسبه chunk ها
├── security.py         # ساخت/تأیید توکن امضاشده‌ی هر لینک (HMAC)
├── stats.py            # ذخیره و بازیابی آمار ترافیک (stats.json)
└── config.py           # خواندن تنظیمات از .env
```

## نصب و راه‌اندازی

```bash
git clone https://github.com/Moorgan21/dlst-filebot.git
cd dlst-filebot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

سپس مقادیر `.env` رو پر کن:

| متغیر | توضیح |
|---|---|
| `API_ID`, `API_HASH` | از [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | توکن بات از [@BotFather](https://t.me/BotFather) |
| `PORT`, `BIND_ADDRESS` | آدرس و پورت وب‌سرور استریم |
| `BASE_URL` | آدرس عمومی سرور، برای ساخت لینک‌های خروجی |
| `LOG_CHANNEL` | (اختیاری) آیدی کانال خصوصی برای گزارش متنی فایل‌های جدید |
| `ADMIN_ID` | آیدی عددی ادمین، برای دسترسی به `/traffic` |
| `REDIS_URL` | آدرس Redis؛ برای لینک‌های فعال، صف، محدودیت نرخ و pacing پهنای‌باند |
| `MAX_ACTIVE_LINKS` | سقف تعداد لینک فعال هم‌زمان (پیش‌فرض ۲۵) |
| `LINK_TTL_MINUTES` | مدت اعتبار هر لینک به دقیقه (پیش‌فرض ۱۲۰) |
| `TOTAL_SERVER_MBPS` | کل پهنای‌باند سرور (مگابیت بر ثانیه) که پویا بین لینک‌های فعال تقسیم می‌شه (پیش‌فرض ۲۰۰) |
| `MAX_FILES_PER_WINDOW`, `FILE_RATE_WINDOW_HOURS` | محدودیت نرخ ارسال فایل هر کاربر (پیش‌فرض: ۵ فایل هر ۲ ساعت) |
| `FORCE_JOIN_CHANNEL` | (اختیاری) یوزرنیم کانالی که عضویت توش اجباریه |

اجرا:

```bash
python3 -m app.main
```

## اجرا به‌صورت سرویس systemd

```ini
[Unit]
Description=Telegram File-to-Stream-Link Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/dlst-filebot
ExecStart=/usr/bin/python3 -m app.main
Restart=always
RestartSec=5
StandardOutput=append:/var/log/dlst-filebot.log
StandardError=append:/var/log/dlst-filebot.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now dlst-filebot.service
```

## مقیاس‌پذیری روی چند سرور

پهنای‌باند کل (`TOTAL_SERVER_MBPS`) و سقف لینک‌های فعال (`MAX_ACTIVE_LINKS`) به‌صورت سراسری روی Redis حساب می‌شن (نه توی حافظه‌ی پروسه؛ حتی pacing پهنای‌باند هر توکن با یه اسکریپت Lua اتمیک روی Redis انجام می‌شه)، پس می‌شه هر تعداد سرور استریم اضافه کرد بدون این‌که سهم هر لینک به‌هم بریزه یا سقف لینک فعال رد بشه — حتی اگه اتصالات یه لینک واحد بین چند سرور تقسیم بشن.

معماری: **سرور اصلی** همون `app/main.py` رو اجرا می‌کنه (هندلر پیام‌ها + صف + وب‌سرور استریم). **سرورهای اضافی** فقط `app/stream_node.py` رو اجرا می‌کنن — یه کلاینت پایگرام سبک (`no_updates=True`) که هیچ پیامی رو پردازش نمی‌کنه (پس آپدیت‌های تلگرام رو دوبار پردازش نمی‌کنن) و فقط فایل استریم می‌کنه. چون توکن لینک HMAC-شده و مستقل از سرورِ سرو‌کننده است و وضعیت لینک‌ها روی Redis مشترکه، **هر سروری می‌تونه هر لینکی رو جواب بده** — نیازی به sticky routing نیست.

### ۱. اتصال امن Redis بین سرورها

اگه سرورها روی شبکه‌ی خصوصی مشترک نیستن (مثلاً پروایدرهای متفاوت)، یه تونل WireGuard بینشون بزن:

روی سرور اصلی:
```bash
apt-get install -y wireguard
umask 077 && mkdir -p /etc/wireguard
wg genkey | tee /etc/wireguard/server1_private.key | wg pubkey > /etc/wireguard/server1_public.key
```
`/etc/wireguard/wg0.conf`:
```ini
[Interface]
PrivateKey = <کلید خصوصی سرور اصلی>
Address = 10.10.0.1/24
ListenPort = 51820

[Peer]
PublicKey = <کلید عمومی سرور دوم>
AllowedIPs = 10.10.0.2/32
```

روی هر سرور اضافی (به همون روش کلید بساز، بعد):
```ini
[Interface]
PrivateKey = <کلید خصوصی این سرور>
Address = 10.10.0.2/24   # برای سرور بعدی: 10.10.0.3 و ...

[Peer]
PublicKey = <کلید عمومی سرور اصلی>
Endpoint = <IP عمومی سرور اصلی>:51820
AllowedIPs = 10.10.0.1/32
PersistentKeepalive = 25
```
هر دو طرف: `systemctl enable --now wg-quick@wg0` و تست با `ping 10.10.0.x`.

### ۲. محافظت از Redis

روی سرور اصلی، `/etc/redis/redis.conf` رو ویرایش کن تا هم روی لوکال هم روی IP تونل گوش بده، و پسورد بذار:
```
bind 127.0.0.1 -::1 10.10.0.1
requirepass <یک پسورد رندوم قوی>
```
بعد `systemctl restart redis-server` و `REDIS_URL` رو تو `.env` سرور اصلی هم آپدیت کن:
```
REDIS_URL=redis://:<پسورد>@127.0.0.1:6379/0
```

### ۳. دیپلوی سرور اضافی

کد رو (بدون `venv`, `sessions`, `.env`, `.git`) با `rsync`/`git clone` به سرور اضافی منتقل کن، `venv` بساز و `pip install -r requirements.txt`، و `.env` بساز با همون `API_ID`/`API_HASH`/`BOT_TOKEN`/`TOTAL_SERVER_MBPS` سرور اصلی، ولی `REDIS_URL` رو به آدرس تونل بده:
```
REDIS_URL=redis://:<پسورد>@10.10.0.1:6379/0
```
پوشه‌ی `sessions/` رو دستی بساز (چون Pyrogram برای سشن جدید بهش نیاز داره):
```bash
mkdir -p sessions
```

### ۴. اجرا به‌صورت systemd

```ini
[Unit]
Description=dlst-filebot stream-only node
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/dlst-filebot
ExecStart=/path/to/dlst-filebot/venv/bin/python3 -m app.stream_node
Restart=always
RestartSec=5
StandardOutput=append:/path/to/dlst-filebot/stream_node.log
StandardError=append:/path/to/dlst-filebot/stream_node.log

[Install]
WantedBy=multi-user.target
```
```bash
systemctl daemon-reload && systemctl enable --now stream-node.service
```

### ۵. لود بالانس روی nginx سرور اصلی

```nginx
upstream filebot_backends {
    server 127.0.0.1:8085;
    server 10.10.0.2:8085;   # به ازای هر سرور اضافی یه خط دیگه
}

server {
    location / {
        proxy_pass http://filebot_backends;
        # ... بقیه‌ی تنظیمات proxy مثل قبل
    }
}
```
```bash
nginx -t && systemctl reload nginx
```

## دستورات بات

- `/start` — راهنمای استفاده
- ارسال هر فایلی → دریافت لینک مستقیم `BASE_URL/dl/{chat_id}/{message_id}?t={token}` (توکن به‌صورت خودکار و امضاشده با `BOT_TOKEN` ساخته می‌شه؛ بدون توکن معتبر درخواست با خطای ۴۰۳ رد می‌شه)
- `/traffic` — نمایش کل حجم استریم‌شده از راه‌اندازی سرویس (فقط `ADMIN_ID`)

## نیازمندی‌ها

- Python 3.10+
- [pyrogram](https://docs.pyrogram.org/) 2.x

## لایسنس

این پروژه تحت لایسنس [MIT](LICENSE) منتشر شده است.
