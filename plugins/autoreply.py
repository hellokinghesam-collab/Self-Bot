"""
plugins/autoreply.py
---------------------
پاسخ خودکار به پیام‌های خصوصی، مبتنی بر لیست‌های ساخته‌شده (دوست/دشمن/دلخواه).

منطق:
- کاربر با `.setreply <لیست> <متن>` یک پیام پاسخ برای یک لیست تعریف می‌کند.
  مثال: .setreply enemy برو با یکی دیگه صحبت کن
        .setreply friend سلام رفیق! الان نیستم زود جواب میدم
- با `.autoreply on` / `.autoreply off` کل قابلیت پاسخ خودکار فعال/غیرفعال می‌شود.
- وقتی پیام خصوصی جدیدی (که خودِ کاربر نفرستاده) می‌رسد:
    اگر فرستنده در یکی از لیست‌هایی باشد که برایش پاسخ تعریف شده،
    و autoreply فعال باشد،
    و به آن کاربر در بازه‌ی اخیر (پیش‌فرض ۶ ساعت) پاسخ خودکار داده نشده باشد
    (برای جلوگیری از اسپم پاسخ به یک نفر)،
    آنگاه پاسخ مربوطه ارسال می‌شود.

نکته امنیتی: این پلاگین هرگز به گروه‌ها پیام نمی‌فرستد و هرگز پیام‌های
دیگران را در گروه‌ها پردازش نمی‌کند؛ فقط پیام‌های خصوصی ورودی (is_private و not out).
دستورات تنظیم (`.setreply`, `.autoreply`) طبق قانون کلی امنیتی فقط از
Saved Messages قابل اجرا هستند (چون از is_authorized استفاده می‌کنند).
"""

import time
from telethon import events

import database as db
from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX

# جلوگیری از اسپم پاسخ خودکار: هر چند ثانیه یک بار حداکثر یک پاسخ خودکار
# به یک کاربر مشخص داده شود.
_COOLDOWN_SECONDS = 6 * 60 * 60  # ۶ ساعت
_last_autoreply_ts: dict[int, float] = {}


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}autoreply (on|off)$"))
    async def toggle_autoreply(event):
        if not await is_authorized(event):
            return
        state = event.pattern_match.group(1) == "on"
        db.setting_set_bool("autoreply_enabled", state)
        await event.edit(f"🔁 پاسخ خودکار {'فعال' if state else 'غیرفعال'} شد.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}setreply (\S+) (.+)$", ))
    async def set_reply_text(event):
        if not await is_authorized(event):
            return
        list_name = event.pattern_match.group(1).strip().lower()
        text = event.pattern_match.group(2).strip()
        db.setting_set(f"autoreply_text::{list_name}", text)
        await event.edit(f"✅ متن پاسخ خودکار برای لیست «{list_name}» تنظیم شد.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}unsetreply (\S+)$"))
    async def unset_reply_text(event):
        if not await is_authorized(event):
            return
        list_name = event.pattern_match.group(1).strip().lower()
        db.setting_set(f"autoreply_text::{list_name}", "")
        await event.edit(f"🗑 پاسخ خودکار لیست «{list_name}» حذف شد.")

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def handle_incoming_private(event):
        # این هندلر خودکار است و نباید هرگز روی پیام‌های خودِ کاربر (out) اجرا شود.
        if event.out:
            return
        if not db.setting_get_bool("autoreply_enabled", default=False):
            return

        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        # بررسی cooldown برای جلوگیری از اسپم پاسخ
        now = time.time()
        last = _last_autoreply_ts.get(sender.id, 0)
        if now - last < _COOLDOWN_SECONDS:
            return

        # بررسی هر لیستی که کاربر عضوش است و برایش متن پاسخ تعریف شده
        for list_name in db.list_names():
            if db.list_contains(list_name, sender.id):
                reply_text = db.setting_get(f"autoreply_text::{list_name}", "")
                if reply_text:
                    await event.respond(reply_text)
                    _last_autoreply_ts[sender.id] = now
                    return  # فقط یک پاسخ در هر بار کافی است
