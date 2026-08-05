"""
plugins/translator.py
------------------------
ترجمه‌ی متن‌ها با استفاده از کتابخانه‌ی deep-translator (بدون نیاز به API Key
پولی؛ به‌صورت پیش‌فرض از موتور رایگان Google Translate استفاده می‌کند).

دستورات (فقط از Saved Messages):
  .tr <زبان مقصد> <متن>       -> ترجمه‌ی متن داده‌شده
  .tr <زبان مقصد>              (با ریپلای روی یک پیام) -> ترجمه‌ی همان پیام
  .autotr on <زبان مقصد>       -> فعال کردن ترجمه‌ی خودکار پیام‌های خصوصی دریافتی
  .autotr off                  -> غیرفعال کردن ترجمه‌ی خودکار

  کدهای زبان رایج: fa (فارسی), en (انگلیسی), ar (عربی), tr (ترکی), de (آلمانی),
  fr (فرانسوی), es (اسپانیایی), ru (روسی), zh-CN (چینی)

نحوه‌ی کارکرد ترجمه‌ی خودکار:
  وقتی فعال باشد، هر پیام خصوصی دریافتی (که خودِ کاربر نفرستاده) به زبان
  مقصدِ تنظیم‌شده ترجمه و به‌صورت یک پیام جدا در همان چت برایت (خودت) نمایش
  داده می‌شود (با ارسال پاسخ حاوی ترجمه، نه جایگزینی پیام اصلی).

⚠️ نکات:
  - این کتابخانه از سرویس غیررسمی/رایگان گوگل استفاده می‌کند و در موارد نادر
    ممکن است به دلیل تغییرات سمت گوگل یا محدودیت نرخ موقتاً خطا بدهد؛ پلاگین
    این خطا را می‌گیرد و پیام مناسب نمایش می‌دهد، کرش نمی‌کند.
  - هیچ محتوایی به سرور ثالث دیگری جز سرویس ترجمه ارسال نمی‌شود.
"""

import logging
from telethon import events

import database as db
from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX
logger = logging.getLogger("selfbot.translator")

_VALID_LANG_HINT = (
    "کدهای رایج: fa (فارسی), en (انگلیسی), ar (عربی), tr (ترکی), "
    "de (آلمانی), fr (فرانسوی), es (اسپانیایی), ru (روسی)"
)


def _translate_sync(text: str, target_lang: str) -> str:
    """
    ترجمه‌ی همزمان (sync) متن. این تابع در یک thread جدا از event loop اصلی
    اجرا می‌شود (با asyncio.to_thread) تا حلقه‌ی رویداد Telethon مسدود نشود.
    """
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source="auto", target=target_lang).translate(text)


async def _do_translate(text: str, target_lang: str) -> str:
    import asyncio
    return await asyncio.to_thread(_translate_sync, text, target_lang)


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}tr (\S+)(?: (.*))?$"))
    async def translate_handler(event):
        if not await is_authorized(event):
            return
        target_lang = event.pattern_match.group(1).strip()
        text = (event.pattern_match.group(2) or "").strip()

        if not text and event.is_reply:
            replied = await event.get_reply_message()
            text = replied.raw_text or ""

        if not text:
            await event.edit(
                f"⚠️ استفاده: `{PREFIX}tr <زبان مقصد> <متن>` یا با ریپلای روی پیام.\n{_VALID_LANG_HINT}"
            )
            return

        await event.edit("🌐 در حال ترجمه...")
        try:
            translated = await _do_translate(text, target_lang)
        except Exception as e:
            logger.warning("خطا در ترجمه: %s", e)
            await event.edit(f"❌ ترجمه ناموفق بود. زبان مقصد معتبر است؟\n{_VALID_LANG_HINT}")
            return

        await event.edit(f"🌐 **ترجمه ({target_lang}):**\n\n{translated}", parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}autotr off$"))
    async def autotr_off(event):
        if not await is_authorized(event):
            return
        db.setting_set_bool("autotr_enabled", False)
        await event.edit("🌐 ترجمه‌ی خودکار غیرفعال شد.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}autotr on (\S+)$"))
    async def autotr_on(event):
        if not await is_authorized(event):
            return
        target_lang = event.pattern_match.group(1).strip()
        db.setting_set_bool("autotr_enabled", True)
        db.setting_set("autotr_target_lang", target_lang)
        await event.edit(
            f"🌐 ترجمه‌ی خودکار پیام‌های خصوصی به زبان «{target_lang}» فعال شد."
        )

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def auto_translate_incoming(event):
        if event.out:
            return
        if not db.setting_get_bool("autotr_enabled", default=False):
            return
        text = event.raw_text
        if not text or not text.strip():
            return

        target_lang = db.setting_get("autotr_target_lang", "en")
        try:
            translated = await _do_translate(text, target_lang)
        except Exception as e:
            logger.warning("ترجمه‌ی خودکار ناموفق بود: %s", e)
            return

        # اگر ترجمه تفاوت معناداری با متن اصلی نداشت (مثلاً همان زبان بود)، رد شود
        if translated.strip().lower() == text.strip().lower():
            return

        await event.reply(f"🌐 ({target_lang}): {translated}")
