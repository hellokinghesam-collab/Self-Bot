"""
plugins/scheduler.py
---------------------
زمان‌بندی ارسال پیام.

دستورات:
  .schedule <دقیقه> <متن>   -> پیام را بعد از N دقیقه در همین چت ارسال می‌کند
  .scheduled                 -> نمایش پیام‌های زمان‌بندی‌شده در انتظار ارسال
  .unschedule <id>           -> لغو یک پیام زمان‌بندی‌شده با آیدی آن

یک لوپ پس‌زمینه (background task) هر چند ثانیه یک‌بار دیتابیس را چک می‌کند
و پیام‌های سررسیدشده را ارسال می‌کند. این لوپ در main.py هنگام استارت
اجرا می‌شود (schedule_loop).
"""

import time
import asyncio
import logging
from telethon import events

import database as db
from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX
logger = logging.getLogger("selfbot.scheduler")


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}schedule (\d+) (.+)$"))
    async def schedule_message(event):
        if not await is_authorized(event):
            return
        minutes = int(event.pattern_match.group(1))
        text = event.pattern_match.group(2)
        send_at = int(time.time()) + minutes * 60
        msg_id = db.schedule_add(event.chat_id, text, send_at)
        await event.edit(
            f"⏰ پیام زمان‌بندی شد (شناسه #{msg_id})، ارسال در {minutes} دقیقه دیگر."
        )

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}scheduled$"))
    async def list_scheduled(event):
        if not await is_authorized(event):
            return
        rows = db.schedule_list_pending()
        if not rows:
            await event.edit("هیچ پیام زمان‌بندی‌شده‌ای در انتظار نیست.")
            return
        lines = ["⏳ **پیام‌های زمان‌بندی‌شده:**\n"]
        now = int(time.time())
        for r in rows:
            remaining_min = max(0, (r["send_at"] - now) // 60)
            preview = r["text"][:40] + ("..." if len(r["text"]) > 40 else "")
            lines.append(f"#{r['id']} — «{preview}» — {remaining_min} دقیقه دیگر")
        await event.edit("\n".join(lines), parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}unschedule (\d+)$"))
    async def cancel_scheduled(event):
        if not await is_authorized(event):
            return
        msg_id = int(event.pattern_match.group(1))
        ok = db.schedule_cancel(msg_id)
        if ok:
            await event.edit(f"🗑 پیام زمان‌بندی‌شده #{msg_id} لغو شد.")
        else:
            await event.edit(f"⚠️ پیامی با شناسه #{msg_id} پیدا نشد.")


async def schedule_loop(client, interval_seconds: int = 15):
    """
    این تابع یک لوپ بی‌نهایت است که باید به صورت background task اجرا شود.
    هر `interval_seconds` ثانیه، پیام‌های سررسیدشده را از دیتابیس می‌خواند و ارسال می‌کند.
    """
    while True:
        try:
            now = int(time.time())
            due = db.schedule_due(now)
            for row in due:
                try:
                    await client.send_message(row["chat_id"], row["text"])
                except Exception as e:
                    logger.warning("ارسال پیام زمان‌بندی‌شده #%s ناموفق بود: %s", row["id"], e)
                finally:
                    db.schedule_mark_sent(row["id"])
        except Exception as e:
            logger.exception("خطا در حلقه‌ی زمان‌بند: %s", e)
        await asyncio.sleep(interval_seconds)
