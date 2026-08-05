"""
plugins/status.py
------------------
دستورات:
  .status    -> نمایش وضعیت کلی سلف‌بات: مدت آپ‌تایم، پلاگین‌ها، تعداد لیست‌ها،
                و «انقضا»ی سشن (اطلاعات مصرف/تاریخ آخرین بررسی، چون تلگرام
                تاریخ انقضای دقیق نمی‌دهد مگر session را invalid کرده باشد).
  .plugins   -> نمایش نام پلاگین‌های بارگذاری‌شده.

توضیح درباره‌ی «انقضا»:
تلگرام یک «تاریخ انقضا» ثابت برای Session String اعلام نمی‌کند؛ یک سشن تا
زمانی معتبر است که کاربر آن را از "Active Sessions" حذف نکرده یا تلگرام
آن را به دلیل بی‌فعالیتی طولانی (معمولاً چند ماه) یا رفتار مشکوک باطل نکرده
باشد. بنابراین در بخش وضعیت، ربات:
  - از چه زمانی روشن است (uptime) را نشان می‌دهد،
  - آخرین باری که با موفقیت به تلگرام متصل شده را ثبت و نمایش می‌دهد،
  - و یادآوری می‌کند که وضعیت را از طریق تلگرام (Settings > Devices) هم چک کند.
"""

import time
import platform
from telethon import events, __version__ as telethon_version

import database as db
from config import COMMAND_PREFIX, DEVICE_MODEL
from security import is_authorized
from plugin_loader import load_all_plugins

PREFIX = COMMAND_PREFIX

START_TIME = time.time()


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days} روز")
    if hours:
        parts.append(f"{hours} ساعت")
    if minutes:
        parts.append(f"{minutes} دقیقه")
    if not parts:
        parts.append(f"{seconds} ثانیه")
    return " و ".join(parts)


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}status$"))
    async def status_handler(event):
        if not await is_authorized(event):
            return

        uptime = _format_duration(time.time() - START_TIME)
        last_seen_alive = db.setting_get("last_alive_ts", None)
        if last_seen_alive:
            last_check = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(int(last_seen_alive))
            )
        else:
            last_check = "نامشخص"

        total_lists = len(db.list_names())
        total_scheduled = len(list(db.schedule_list_pending()))
        autoreply_state = "فعال ✅" if db.setting_get_bool("autoreply_enabled") else "غیرفعال ❌"

        me = await client.get_me()

        text = (
            "📊 **وضعیت سلف‌بات**\n\n"
            f"👤 اکانت: {me.first_name or ''} (`{me.id}`)\n"
            f"⏱ مدت روشن بودن (uptime): {uptime}\n"
            f"📡 آخرین بررسی سلامت اتصال: {last_check}\n"
            f"🖥 دستگاه: {DEVICE_MODEL}\n"
            f"🧩 پلاگین‌های بارگذاری‌شده: {len(getattr(client, '_loaded_plugins', []))}\n"
            f"📋 تعداد لیست‌های تعریف‌شده: {total_lists}\n"
            f"⏳ پیام‌های زمان‌بندی‌شده در انتظار: {total_scheduled}\n"
            f"🔁 پاسخ خودکار: {autoreply_state}\n\n"
            "ℹ️ تلگرام تاریخ انقضای ثابتی برای سشن اعلام نمی‌کند؛ سشن تا زمانی "
            "معتبر است که آن را از Settings → Devices حذف نکرده باشی یا تلگرام "
            "به‌دلیل بی‌فعالیتی طولانی (معمولاً چندین ماه) آن را باطل نکرده باشد. "
            "این ربات هر چند دقیقه یک‌بار یک پینگ سبک به تلگرام می‌زند تا هم "
            "آنلاین/فعال بماند و هم زمان آخرین اتصال موفق ثبت شود (بالا)."
        )
        await event.edit(text, parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}plugins$"))
    async def plugins_handler(event):
        if not await is_authorized(event):
            return
        names = getattr(client, "_loaded_plugins", [])
        if not names:
            await event.edit("هیچ پلاگینی بارگذاری نشده.")
            return
        lines = ["🧩 **پلاگین‌های بارگذاری‌شده:**\n"]
        for n in names:
            lines.append(f"• `{n}`")
        await event.edit("\n".join(lines), parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}reload$"))
    async def reload_handler(event):
        if not await is_authorized(event):
            return
        await event.edit("♻️ در حال بارگذاری مجدد پلاگین‌ها...")
        loaded = await load_all_plugins(client)
        client._loaded_plugins = loaded
        await event.edit(f"✅ {len(loaded)} پلاگین بارگذاری شد:\n" + ", ".join(f"`{n}`" for n in loaded))
