"""
plugins/files.py
------------------
دانلود و آپلود فایل‌ها.

دستورات (فقط از Saved Messages):
  .save        (با ریپلای روی پیام حاوی فایل/عکس/ویدیو) -> دانلود فایل روی سرور
               و ارسال دوباره به Saved Messages به همراه اطلاعات فایل (اسم/حجم)
  .upload <مسیر>   -> آپلود یک فایل مشخص از روی دیسک سرور به همان چت
  .storage         -> نمایش حجم اشغال‌شده‌ی پوشه‌ی دانلودها روی سرور
  .clearstorage    -> پاک‌کردن تمام فایل‌های دانلودشده روی سرور (آزاد کردن فضا)

⚠️ نکات امنیتی:
  - تمام فایل‌ها فقط داخل پوشه‌ی محلی `downloads/` ذخیره می‌شوند (هرگز مسیر
    دلخواه از کاربر گرفته نمی‌شود برای *دانلود*؛ نام فایل توسط خودِ Telethon/
    این پلاگین تعیین می‌شود، نه از متن پیام).
  - برای `.upload <مسیر>`، مسیر ورودی همیشه Sanitization و به‌صورت "resolve"شده
    بررسی می‌شود تا خارج از پوشه‌ی مجاز پروژه (`downloads/`) چیزی خوانده نشود؛
    این از Path Traversal (مثل `../../etc/passwd`) جلوگیری می‌کند.
  - حداکثر حجم فایل قابل دانلود محدود شده (پیش‌فرض ۵۰۰ مگابایت، محدودیت
    خودِ تلگرام برای اکانت‌های عادی) تا از پر شدن دیسک سرور جلوگیری شود.
"""

import os
import logging
from pathlib import Path
from telethon import events

from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX
logger = logging.getLogger("selfbot.files")

# پوشه‌ی مجاز و ایزوله برای ذخیره‌ی فایل‌های دانلودشده
DOWNLOAD_DIR = Path("downloads").resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_MB = 500


def _safe_resolve_in_downloads(user_supplied_name: str) -> Path | None:
    """
    مسیر وارد‌شده توسط کاربر را resolve می‌کند و تضمین می‌دهد که نتیجه‌ی نهایی
    همچنان داخل DOWNLOAD_DIR باقی می‌ماند (جلوگیری از Path Traversal).
    اگر خارج از پوشه‌ی مجاز باشد، None برمی‌گرداند.
    """
    candidate = (DOWNLOAD_DIR / user_supplied_name).resolve()
    if DOWNLOAD_DIR not in candidate.parents and candidate != DOWNLOAD_DIR:
        return None
    if not str(candidate).startswith(str(DOWNLOAD_DIR)):
        return None
    return candidate


def _human_size(num_bytes: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}save$"))
    async def save_handler(event):
        if not await is_authorized(event):
            return
        if not event.is_reply:
            await event.edit("⚠️ برای دانلود، روی پیام حاوی فایل/عکس/ویدیو ریپلای کن.")
            return

        replied = await event.get_reply_message()
        if not replied.media:
            await event.edit("⚠️ پیام ریپلای‌شده فایلی ندارد.")
            return

        # بررسی حجم فایل قبل از دانلود، در صورت وجود اطلاعات حجم
        file_size = getattr(replied.file, "size", None)
        if file_size and file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            await event.edit(
                f"⚠️ حجم فایل بیش از حد مجاز ({MAX_FILE_SIZE_MB}MB) است و دانلود نمی‌شود."
            )
            return

        await event.edit("⬇️ در حال دانلود فایل...")
        try:
            path = await client.download_media(replied, file=str(DOWNLOAD_DIR) + os.sep)
        except Exception as e:
            logger.exception("خطا در دانلود فایل")
            await event.edit(f"❌ دانلود ناموفق بود: {e}")
            return

        if not path:
            await event.edit("❌ دانلود ناموفق بود (نوع فایل پشتیبانی نمی‌شود).")
            return

        size = os.path.getsize(path)
        fname = os.path.basename(path)
        await event.edit(
            f"✅ فایل ذخیره شد:\n📄 `{fname}`\n📦 حجم: {_human_size(size)}\n"
            f"می‌توانی با `{PREFIX}upload {fname}` دوباره ارسالش کنی."
        )

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}upload (.+)$"))
    async def upload_handler(event):
        if not await is_authorized(event):
            return
        raw_name = event.pattern_match.group(1).strip()
        target = _safe_resolve_in_downloads(raw_name)
        if target is None:
            await event.edit("🚫 مسیر نامعتبر است (خارج از پوشه‌ی مجاز downloads/).")
            return
        if not target.exists() or not target.is_file():
            await event.edit(f"⚠️ فایلی با نام `{raw_name}` در downloads/ پیدا نشد.")
            return

        size = target.stat().st_size
        if size > MAX_FILE_SIZE_MB * 1024 * 1024:
            await event.edit(f"⚠️ حجم فایل بیش از حد مجاز ({MAX_FILE_SIZE_MB}MB) است.")
            return

        await event.edit("⬆️ در حال آپلود فایل...")
        try:
            await client.send_file(event.chat_id, str(target))
            await event.delete()
        except Exception as e:
            logger.exception("خطا در آپلود فایل")
            await event.edit(f"❌ آپلود ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}storage$"))
    async def storage_handler(event):
        if not await is_authorized(event):
            return
        total = 0
        count = 0
        for f in DOWNLOAD_DIR.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
                count += 1
        await event.edit(
            f"💾 پوشه‌ی downloads/: {count} فایل، مجموع حجم {_human_size(total)}"
        )

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}clearstorage$"))
    async def clear_storage_handler(event):
        if not await is_authorized(event):
            return
        count = 0
        for f in DOWNLOAD_DIR.rglob("*"):
            if f.is_file():
                try:
                    f.unlink()
                    count += 1
                except Exception as e:
                    logger.warning("حذف فایل %s ناموفق بود: %s", f, e)
        await event.edit(f"🧹 {count} فایل از downloads/ پاک شد.")
