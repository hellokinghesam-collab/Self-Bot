"""
config.py
---------
تمام مقادیر حساس (API_ID, API_HASH, SESSION_STRING, ...) فقط و فقط
از متغیرهای محیطی (Environment Variables) خوانده می‌شوند.

هرگز مقدار واقعی این متغیرها را داخل کد ننویس و کامیت نکن.
در ریلوی (Railway) این مقادیر را در بخش Variables پروژه تنظیم کن.
"""

import os
import sys
import logging

logger = logging.getLogger("selfbot.config")


def _get_env(name: str, required: bool = True, default=None, cast=str):
    """
    خواندن امن یک متغیر محیطی.
    اگر required باشد و مقدار موجود نباشد، برنامه با پیام واضح متوقف می‌شود
    (به جای کرش با traceback نامفهوم یا -بدتر- اجرا با مقدار خالی/ناامن).
    """
    raw = os.environ.get(name, default)
    if required and (raw is None or str(raw).strip() == ""):
        logger.critical(
            "متغیر محیطی الزامی '%s' تنظیم نشده است. "
            "برنامه متوقف می‌شود. لطفاً آن را در تنظیمات محیط (Railway Variables) اضافه کن.",
            name,
        )
        sys.exit(1)
    if raw is None:
        return default
    try:
        return cast(raw)
    except (ValueError, TypeError):
        logger.critical("مقدار متغیر '%s' نامعتبر است.", name)
        sys.exit(1)


# ---------------------------------------------------------------------------
# مقادیر حساس - همه از Environment Variables
# ---------------------------------------------------------------------------

API_ID: int = _get_env("API_ID", required=True, cast=int)
API_HASH: str = _get_env("API_HASH", required=True, cast=str)

# رشته سشن (StringSession تلگرام). این معادل رمز عبور کامل اکانت است.
SESSION_STRING: str = _get_env("SESSION_STRING", required=True, cast=str)

# شماره تلفن فقط برای مرحله اولیه ساخت سشن لازم است (اسکریپت جدا generate_session.py)
# در ران‌تایم اصلی ربات استفاده نمی‌شود، اما اگر تعریف شده باشد می‌خوانیمش.
PHONE_NUMBER: str = _get_env("PHONE_NUMBER", required=False, default="", cast=str)

# ---------------------------------------------------------------------------
# تنظیمات غیرحساس (قابل تغییر با مقدار پیش‌فرض)
# ---------------------------------------------------------------------------

# آیدی عددی خودت (owner). اگر ست نشود، ربات در اولین اجرا خودش آن را
# از get_me() تشخیص می‌دهد؛ اما تعریف صریح آن امن‌تر است.
OWNER_ID: int = _get_env("OWNER_ID", required=False, default=0, cast=int)

# پیشوند دستورات (مثلاً . یا ! یا /)
COMMAND_PREFIX: str = _get_env("COMMAND_PREFIX", required=False, default=".", cast=str)

# مسیر دیتابیس SQLite (روی ریلوی از یک Volume برای پایداری دیتا استفاده کن)
DB_PATH: str = _get_env("DB_PATH", required=False, default="data/selfbot.db", cast=str)

# فاصله (ثانیه) بین هر تلاش برای زنده نگه‌داشتن اتصال / آنلاین ماندن
KEEPALIVE_INTERVAL: int = _get_env("KEEPALIVE_INTERVAL", required=False, default=60, cast=int)

# سطح لاگ
LOG_LEVEL: str = _get_env("LOG_LEVEL", required=False, default="INFO", cast=str)

# نام دستگاه/برنامه که در تنظیمات دستگاه‌های تلگرام شما نمایش داده می‌شود
DEVICE_MODEL: str = _get_env("DEVICE_MODEL", required=False, default="SelfBot", cast=str)
