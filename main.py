"""
main.py
-------
نقطه‌ی ورود اصلی سلف‌بات.

مسئولیت‌ها:
  1. اتصال به تلگرام با StringSession (بدون نیاز به ورود تعاملی).
  2. راه‌اندازی دیتابیس.
  3. بارگذاری تمام پلاگین‌ها از پوشه plugins/.
  4. اجرای حلقه‌ی keep-alive برای آنلاین/فعال نگه‌داشتن اکانت.
  5. اجرای حلقه‌ی زمان‌بند پیام‌ها.
  6. مدیریت خطا و اتصال‌مجدد خودکار در صورت قطعی شبکه.

هرگز هیچ مقدار حساسی (API_ID/API_HASH/SESSION_STRING) در این فایل هاردکد
نشده؛ همه از config.py که خودش از Environment Variables می‌خواند تأمین می‌شود.
"""

import asyncio
import logging
import time
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    AuthKeyDuplicatedError,
    AuthKeyUnregisteredError,
    UserDeactivatedBanError,
    SessionPasswordNeededError,
)

import config
import database as db
from plugin_loader import load_all_plugins
from plugins.scheduler import schedule_loop

# ---------------------------------------------------------------------------
# تنظیمات لاگ
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("selfbot.main")

# جلوگیری از لو رفتن اطلاعات حساس در لاگ‌های خودِ کتابخانه‌ی telethon
logging.getLogger("telethon").setLevel(logging.WARNING)


async def keepalive_loop(client: TelegramClient, interval: int):
    """
    هر `interval` ثانیه یک درخواست سبک (get_me) به تلگرام می‌زند تا:
      - اتصال زنده و برقرار بماند (به‌خصوص پشت پلتفرم‌هایی مثل Railway که
        ممکن است idle connection را می‌بندند)
      - وضعیت "آنلاین" اکانت به‌روز بماند
      - زمان آخرین اتصال موفق برای دستور .status ثبت شود
    """
    while True:
        try:
            if client.is_connected():
                await client.get_me()
                db.setting_set("last_alive_ts", str(int(time.time())))
            else:
                logger.warning("اتصال قطع بود؛ در حال تلاش برای اتصال مجدد...")
                await client.connect()
        except Exception as e:
            logger.warning("خطا در حلقه‌ی keep-alive: %s", e)
        await asyncio.sleep(interval)


async def main():
    logger.info("در حال راه‌اندازی سلف‌بات...")

    db.init_db()
    logger.info("دیتابیس آماده شد.")

    client = TelegramClient(
        StringSession(config.SESSION_STRING),
        config.API_ID,
        config.API_HASH,
        device_model=config.DEVICE_MODEL,
        system_version="1.0",
        app_version="1.0",
    )

    try:
        await client.connect()
    except Exception as e:
        logger.critical("اتصال اولیه به تلگرام ناموفق بود: %s", e)
        sys.exit(1)

    if not await client.is_user_authorized():
        logger.critical(
            "SESSION_STRING نامعتبر است یا منقضی شده. "
            "لطفاً با اسکریپت generate_session.py یک سشن جدید بساز و "
            "متغیر محیطی SESSION_STRING را در Railway به‌روزرسانی کن."
        )
        sys.exit(1)

    me = await client.get_me()
    logger.info("با موفقیت با اکانت %s (%s) متصل شد.", me.first_name, me.id)
    db.setting_set("last_alive_ts", str(int(time.time())))

    # بارگذاری پلاگین‌ها
    loaded = await load_all_plugins(client)
    client._loaded_plugins = loaded
    logger.info("مجموعاً %d پلاگین بارگذاری شد: %s", len(loaded), ", ".join(loaded))

    # اجرای حلقه‌های پس‌زمینه
    asyncio.create_task(keepalive_loop(client, config.KEEPALIVE_INTERVAL))
    asyncio.create_task(schedule_loop(client))

    logger.info("سلف‌بات آماده و در حال اجراست. منتظر دستورات در Saved Messages...")

    try:
        await client.run_until_disconnected()
    except (AuthKeyUnregisteredError, UserDeactivatedBanError, AuthKeyDuplicatedError) as e:
        logger.critical(
            "سشن دیگر معتبر نیست (%s). این معمولاً یعنی از دستگاه‌ها حذف شده یا "
            "اکانت محدود شده است. لازم است سشن جدید بسازی.",
            type(e).__name__,
        )
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("سلف‌بات متوقف شد (KeyboardInterrupt).")
