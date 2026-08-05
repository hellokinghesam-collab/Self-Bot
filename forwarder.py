"""
plugins/forwarder.py
---------------------
فوروارد خودکار پیام‌های یک چت به چت (یا چت‌های) دیگر.

دستورات (فقط از Saved Messages):
  .fwdadd <dest_id>       (با ریپلای روی یک پیام از چت مبدأ، یا در خودِ چت مبدأ اجرا شود)
                          -> از این چت به چت با آیدی dest_id فوروارد کن
  .fwdadd here <dest_id>  -> همین که در آن هستی (چت فعلی) را به‌عنوان مبدأ ثبت کن
  .fwdremove <dest_id>    -> لغو فوروارد از چت فعلی به مقصد مشخص
  .fwdlist                -> نمایش تمام قوانین فوروارد فعال

نحوه کارکرد:
  وقتی پیام جدیدی (که خودِ کاربر نفرستاده) در یک چت منبع می‌رسد که برایش
  قانون فوروارد ثبت شده، پیام به مقصد(ها) فوروارد می‌شود.

⚠️ نکات امنیتی و رعایت محدودیت‌های تلگرام:
  - یک RateLimiter (حداکثر ۱۰ فوروارد در هر ۳۰ ثانیه) وجود دارد تا از رفتار
    شبیه اسپم که می‌تواند باعث محدودیت اکانت شود جلوگیری شود. اگر از سقف رد شود،
    فوروارد آن پیام نادیده گرفته می‌شود (silently skipped) نه اینکه صف شود،
    چون صف‌کردن نامحدود خودش می‌تواند به فلود ناخواسته در آینده منجر شود.
  - فوروارد از/به گروه‌هایی که کاربر عضو نیست انجام نمی‌شود (Telethon خودش
    خطای دسترسی می‌دهد و این پلاگین آن خطا را می‌گیرد و لاگ می‌کند، متوقف نمی‌شود).
"""

import logging
from telethon import events

import database as db
from config import COMMAND_PREFIX
from security import is_authorized, RateLimiter

PREFIX = COMMAND_PREFIX
logger = logging.getLogger("selfbot.forwarder")

# حداکثر ۱۰ فوروارد در هر ۳۰ ثانیه - محافظت در برابر رفتار مشکوک/فلود
_forward_limiter = RateLimiter(max_calls=10, period_seconds=30)


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}fwdadd (-?\d+)$"))
    async def fwd_add_current(event):
        if not await is_authorized(event):
            return
        dest_id = int(event.pattern_match.group(1))
        source_id = event.chat_id
        # چون این دستور فقط در Saved Messages اجرا می‌شود، source باید توسط
        # کاربر با ریپلای یا آرگومان جدا مشخص شود؛ برای سادگی از فرمت زیر استفاده می‌کنیم:
        # .fwdadd <source_id> <dest_id>  را در تابع دیگر پایین پوشش می‌دهیم.
        await event.edit(
            "⚠️ برای افزودن قانون فوروارد از فرمت زیر استفاده کن:\n"
            f"`{PREFIX}fwdadd <source_id> <dest_id>`\n\n"
            "برای پیدا کردن آیدی یک چت، در همان چت دستور `.id` را بزن."
        )

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}fwdadd (-?\d+) (-?\d+)$"))
    async def fwd_add(event):
        if not await is_authorized(event):
            return
        source_id = int(event.pattern_match.group(1))
        dest_id = int(event.pattern_match.group(2))
        added = db.forward_rule_add(source_id, dest_id)
        if added:
            await event.edit(f"✅ فوروارد خودکار ثبت شد: `{source_id}` → `{dest_id}`")
        else:
            await event.edit("ℹ️ این قانون فوروارد از قبل وجود دارد.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}fwdremove (-?\d+) (-?\d+)$"))
    async def fwd_remove(event):
        if not await is_authorized(event):
            return
        source_id = int(event.pattern_match.group(1))
        dest_id = int(event.pattern_match.group(2))
        removed = db.forward_rule_remove(source_id, dest_id)
        if removed:
            await event.edit(f"🗑 قانون فوروارد `{source_id}` → `{dest_id}` حذف شد.")
        else:
            await event.edit("⚠️ چنین قانونی پیدا نشد.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}fwdlist$"))
    async def fwd_list(event):
        if not await is_authorized(event):
            return
        rules = db.forward_rules_all()
        if not rules:
            await event.edit("هیچ قانون فوروارد فعالی وجود ندارد.")
            return
        lines = ["📤 **قوانین فوروارد فعال:**\n"]
        for r in rules:
            lines.append(f"#{r['id']}: `{r['source_chat_id']}` → `{r['dest_chat_id']}`")
        await event.edit("\n".join(lines), parse_mode="md")

    @client.on(events.NewMessage(incoming=True))
    async def auto_forward(event):
        # این هندلر خودکار است؛ باید کاملاً از پیام‌های شخصی/دستوری جدا بماند.
        if event.out:
            return
        rules = db.forward_rules_for_source(event.chat_id)
        if not rules:
            return
        if not _forward_limiter.allow("forward"):
            logger.warning("محدودیت نرخ فوروارد فعال شد؛ این پیام فوروارد نشد.")
            return
        for rule in rules:
            dest_id = rule["dest_chat_id"]
            try:
                await client.forward_messages(dest_id, event.message)
            except Exception as e:
                logger.warning("فوروارد به %s ناموفق بود: %s", dest_id, e)
