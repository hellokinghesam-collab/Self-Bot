"""
plugins/daily_stats.py
------------------------
ثبت و نمایش آمار روزانه‌ی فعالیت سلف‌بات.

این پلاگین دو نقش دارد:
  1. یک هندلر «ناظر» با اولویت پایین که هر پیام ورودی/خروجی را (بدون دخالت در
     پردازش سایر پلاگین‌ها) می‌شمارد و در دیتابیس ثبت می‌کند.
  2. دستور `.stats` برای نمایش آمار امروز و `.statsweek` برای نمایش خلاصه‌ی
     ۷ روز اخیر.

آمارهایی که ثبت می‌شود:
  - تعداد پیام‌های ارسالی توسط خودت (messages_sent)
  - تعداد پیام‌های دریافتی از دیگران (messages_received)
  - تعداد دستوراتی که اجرا کرده‌ای (commands_run)
  - تعداد چت‌های خصوصی/گروهیِ فعال امروز (شمارش یکتا)

⚠️ نکات حریم خصوصی:
  - هیچ متن پیامی ذخیره نمی‌شود؛ فقط شمارنده‌های عددی و آیدی چت‌ها (برای شمارش
    چت‌های یکتا) در دیتابیس محلی خودِ سرور نگه‌داری می‌شوند.
  - این آمار فقط برای خودت (owner) قابل مشاهده است، چون فقط دستورات ارسالی
    از Saved Messages پردازش می‌شوند.
"""

from telethon import events

import database as db
from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX


def _bar(value: int, max_value: int, width: int = 12) -> str:
    """یک نوار پیشرفت متنی ساده برای نمایش نسبت در پیام تلگرام."""
    if max_value <= 0:
        filled = 0
    else:
        filled = min(width, round((value / max_value) * width))
    return "▓" * filled + "░" * (width - filled)


async def register(client):

    # --- ناظر شمارش پیام‌ها (باید بعد از سایر پلاگین‌ها ثبت شود ولی چون فقط
    # شمارش می‌کند و پیام را edit/consume نمی‌کند، ترتیب ثبت اهمیتی ندارد) ---

    @client.on(events.NewMessage())
    async def stats_counter(event):
        try:
            is_group = event.is_group or event.is_channel
            if event.out:
                db.stats_bump("messages_sent", chat_id=event.chat_id, is_group=is_group)
                # اگر پیام با پیشوند دستور شروع شود، آن را هم به‌عنوان دستور بشمار
                if event.raw_text and event.raw_text.startswith(PREFIX):
                    db.stats_bump("commands_run")
            else:
                db.stats_bump("messages_received", chat_id=event.chat_id, is_group=is_group)
        except Exception:
            # شمارش آمار هرگز نباید باعث خطا در پردازش پیام اصلی شود
            pass

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}stats$"))
    async def stats_handler(event):
        if not await is_authorized(event):
            return
        import json

        row = db.stats_get()
        if row is None:
            await event.edit("📊 هنوز آماری برای امروز ثبت نشده.")
            return

        sent = row["messages_sent"]
        received = row["messages_received"]
        commands = row["commands_run"]
        try:
            private_count = len(json.loads(row["private_chats"]))
        except Exception:
            private_count = 0
        try:
            group_count = len(json.loads(row["group_chats"]))
        except Exception:
            group_count = 0

        max_val = max(sent, received, 1)
        text = (
            f"📊 **آمار امروز ({row['day']})**\n\n"
            f"📤 پیام ارسالی: {sent}\n{_bar(sent, max_val)}\n\n"
            f"📥 پیام دریافتی: {received}\n{_bar(received, max_val)}\n\n"
            f"⚙️ دستورات اجراشده: {commands}\n"
            f"👤 چت‌های خصوصی فعال: {private_count}\n"
            f"👥 گروه‌های فعال: {group_count}\n"
        )
        await event.edit(text, parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}statsweek$"))
    async def stats_week_handler(event):
        if not await is_authorized(event):
            return
        rows = db.stats_get_range(days=7)
        if not rows:
            await event.edit("📊 هنوز آماری ثبت نشده.")
            return

        lines = ["📊 **آمار ۷ روز اخیر:**\n"]
        total_sent = 0
        total_received = 0
        for r in reversed(rows):  # قدیمی‌ترین به جدیدترین
            total_sent += r["messages_sent"]
            total_received += r["messages_received"]
            lines.append(
                f"`{r['day']}` — ارسالی: {r['messages_sent']} | دریافتی: {r['messages_received']} | دستورات: {r['commands_run']}"
            )
        lines.append(f"\n**جمع کل:** ارسالی {total_sent} | دریافتی {total_received}")
        await event.edit("\n".join(lines), parse_mode="md")
