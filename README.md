# dlst-filebot

ربات تلگرامی که فایل‌های ارسالی (سند، ویدیو، صدا، ویس، ویدیو نوت، گیف، عکس) رو می‌گیره و در ازاش یه **لینک استریم مستقیم HTTP** برمی‌گردونه؛ بدون این‌که فایل روی سرور ذخیره بشه.

## ویژگی‌ها

- استریم لحظه‌ای فایل از تلگرام به کاربر (بدون ذخیره‌سازی روی دیسک)
- پشتیبانی کامل از HTTP Range requests → قابلیت Seek در پلیر و Resume در دانلودرها
- تشخیص خودکار Content-Type و نام فایل
- ثبت آمار کل ترافیک استریم‌شده (`/traffic`، مخصوص ادمین)
- امکان نگهداری پایدار فایل‌ها در یک کانال خصوصی (`LOG_CHANNEL`) به‌جای تکیه به چت کاربر

## ساختار پروژه

```
app/
├── main.py         # نقطه ورود: بالا آوردن بات و وب‌سرور aiohttp
├── bot.py          # هندلرهای پیام تلگرام (/start, /traffic, دریافت فایل)
├── stream.py       # روت‌های HTTP استریم (GET/HEAD /dl/{chat_id}/{message_id})
├── range_utils.py  # پارس هدر Range و محاسبه chunk ها
├── stats.py        # ذخیره و بازیابی آمار ترافیک (stats.json)
└── config.py       # خواندن تنظیمات از .env
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
| `LOG_CHANNEL` | (اختیاری) آیدی کانال خصوصی برای نگهداری پایدار فایل‌ها |
| `ADMIN_ID` | آیدی عددی ادمین، برای دسترسی به `/traffic` |

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

## دستورات بات

- `/start` — راهنمای استفاده
- ارسال هر فایلی → دریافت لینک مستقیم `BASE_URL/dl/{chat_id}/{message_id}`
- `/traffic` — نمایش کل حجم استریم‌شده از راه‌اندازی سرویس (فقط `ADMIN_ID`)

## نیازمندی‌ها

- Python 3.10+
- [pyrogram](https://docs.pyrogram.org/) 2.x
