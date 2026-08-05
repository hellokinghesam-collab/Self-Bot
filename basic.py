"""
plugins/basic.py
----------------
دستورات پایه‌ی سلف‌بات:
  .ping              - تست سرعت پاسخ‌گویی
  .help              - نمایش راهنمای کامل دستورات
  .bold <متن>        - ارسال متن به صورت بولد (**پررنگ**)
  .italic <متن>       - ارسال متن به صورت ایتالیک
  .code <متن>         - ارسال متن به صورت کد (monospace)
  .del                - حذف پیام دستور (ریپلای‌شده یا خودش)
  .id                 - نمایش آیدی کاربر/چت/پیام ریپلای‌شده
"""

import time
from telethon import events

from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}ping$"))
    async def ping_handler(event):
        if not await is_authorized(event):
            return
        start = time.monotonic()
        msg = await event.edit("🏓 در حال سنجش...")
        elapsed_ms = (time.monotonic() - start) * 1000
        await msg.edit(f"🏓 Pong!\n⏱ {elapsed_ms:.1f}ms")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}bold(?: |$)(.*)", ))
    async def bold_handler(event):
        if not await is_authorized(event):
            return
        text = event.pattern_match.group(1).strip()
        if not text and event.is_reply:
            replied = await event.get_reply_message()
            text = replied.raw_text or ""
        if not text:
            await event.edit(f"⚠️ استفاده: `{PREFIX}bold متن شما`")
            return
        await event.edit(f"**{text}**", parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}italic(?: |$)(.*)"))
    async def italic_handler(event):
        if not await is_authorized(event):
            return
        text = event.pattern_match.group(1).strip()
        if not text and event.is_reply:
            replied = await event.get_reply_message()
            text = replied.raw_text or ""
        if not text:
            await event.edit(f"⚠️ استفاده: `{PREFIX}italic متن شما`")
            return
        await event.edit(f"__{text}__", parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}code(?: |$)(.*)"))
    async def code_handler(event):
        if not await is_authorized(event):
            return
        text = event.pattern_match.group(1).strip()
        if not text and event.is_reply:
            replied = await event.get_reply_message()
            text = replied.raw_text or ""
        if not text:
            await event.edit(f"⚠️ استفاده: `{PREFIX}code متن شما`")
            return
        # از backtick سه‌گانه استفاده می‌کنیم تا کاراکترهای خاص داخل متن مشکل ایجاد نکنند
        safe_text = text.replace("`", "'")
        await event.edit(f"```{safe_text}```", parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}del$"))
    async def del_handler(event):
        if not await is_authorized(event):
            return
        if event.is_reply:
            replied = await event.get_reply_message()
            await replied.delete()
        await event.delete()

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}id$"))
    async def id_handler(event):
        if not await is_authorized(event):
            return
        lines = [f"💬 آیدی چت: `{event.chat_id}`"]
        if event.is_reply:
            replied = await event.get_reply_message()
            sender = await replied.get_sender()
            if sender:
                lines.append(f"👤 آیدی فرستنده پیام ریپلای‌شده: `{sender.id}`")
            lines.append(f"✉️ آیدی پیام ریپلای‌شده: `{replied.id}`")
        await event.edit("\n".join(lines), parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}help$"))
    async def help_handler(event):
        if not await is_authorized(event):
            return
        text = (
            "🤖 **راهنمای سلف‌بات**\n\n"
            "**پایه:**\n"
            f"`{PREFIX}ping` — تست سرعت\n"
            f"`{PREFIX}bold متن` — بولد کردن\n"
            f"`{PREFIX}italic متن` — ایتالیک کردن\n"
            f"`{PREFIX}code متن` — فرمت کد\n"
            f"`{PREFIX}del` — حذف پیام (و ریپلای‌شده)\n"
            f"`{PREFIX}id` — نمایش آیدی‌ها\n\n"
            "**لیست‌ها (دوست/دشمن/دلخواه):**\n"
            f"`{PREFIX}addfriend` (ریپلای) — افزودن به لیست دوستان\n"
            f"`{PREFIX}addenemy` (ریپلای) — افزودن به لیست دشمنان\n"
            f"`{PREFIX}add <لیست>` (ریپلای) — افزودن به لیست دلخواه\n"
            f"`{PREFIX}remove <لیست>` (ریپلای) — حذف از لیست\n"
            f"`{PREFIX}list <لیست>` — نمایش اعضای لیست\n"
            f"`{PREFIX}lists` — نمایش همه لیست‌های موجود\n"
            f"`{PREFIX}clearlist <لیست>` — پاکسازی کامل یک لیست\n\n"
            "**پاسخ خودکار:**\n"
            f"`{PREFIX}autoreply on/off` — فعال/غیرفعال کردن پاسخ خودکار\n"
            f"`{PREFIX}setreply <لیست> <متن>` — تنظیم متن پاسخ برای یک لیست\n\n"
            "**زمان‌بندی:**\n"
            f"`{PREFIX}schedule <دقیقه> <متن>` — زمان‌بندی ارسال پیام در همین چت\n"
            f"`{PREFIX}scheduled` — نمایش پیام‌های زمان‌بندی‌شده\n"
            f"`{PREFIX}unschedule <id>` — لغو یک پیام زمان‌بندی‌شده\n\n"
            "**فوروارد خودکار:**\n"
            f"`{PREFIX}fwdadd <source_id> <dest_id>` — ثبت قانون فوروارد\n"
            f"`{PREFIX}fwdremove <source_id> <dest_id>` — حذف قانون فوروارد\n"
            f"`{PREFIX}fwdlist` — نمایش قوانین فوروارد فعال\n\n"
            "**فایل:**\n"
            f"`{PREFIX}save` (ریپلای) — دانلود فایل روی سرور\n"
            f"`{PREFIX}upload <نام فایل>` — آپلود از downloads/\n"
            f"`{PREFIX}storage` — حجم اشغال‌شده روی سرور\n"
            f"`{PREFIX}clearstorage` — پاک کردن فایل‌های دانلودشده\n\n"
            "**مدیریت گروه (نیاز به دسترسی ادمین):**\n"
            f"`{PREFIX}gkick <group_id> <user_id>` — اخراج عضو\n"
            f"`{PREFIX}gban / gunban <group_id> <user_id>` — بن/رفع بن\n"
            f"`{PREFIX}gmute <group_id> <user_id> <دقیقه>` — سکوت موقت\n"
            f"`{PREFIX}gunmute <group_id> <user_id>` — رفع سکوت\n"
            f"`{PREFIX}ginfo / gadmins <group_id>` — اطلاعات/ادمین‌های گروه\n\n"
            "**متفرقه:**\n"
            f"`{PREFIX}purge <تعداد>` — حذف پیام‌های اخیر خودت\n"
            f"`{PREFIX}edit <متن>` (ریپلای) — ویرایش پیام قبلی خودت\n"
            f"`{PREFIX}calc <عبارت>` — محاسبه‌گر امن\n"
            f"`{PREFIX}afk [دلیل]` / `{PREFIX}unafk` — حالت عدم حضور\n"
            f"`{PREFIX}pin` / `{PREFIX}unpin` (ریپلای) — پین کردن پیام\n\n"
            "**ترجمه:**\n"
            f"`{PREFIX}tr <زبان> <متن>` — ترجمه‌ی متن یا پیام ریپلای‌شده\n"
            f"`{PREFIX}autotr on <زبان>` / `{PREFIX}autotr off` — ترجمه خودکار PV\n\n"
            "**آمار:**\n"
            f"`{PREFIX}stats` — آمار امروز\n"
            f"`{PREFIX}statsweek` — خلاصه‌ی ۷ روز اخیر\n\n"
            "**سیستم:**\n"
            f"`{PREFIX}status` — وضعیت کلی و انقضای سشن\n"
            f"`{PREFIX}plugins` — لیست پلاگین‌های بارگذاری‌شده\n"
            f"`{PREFIX}reload` — بارگذاری مجدد پلاگین‌ها\n"
        )
        await event.edit(text, parse_mode="md")
