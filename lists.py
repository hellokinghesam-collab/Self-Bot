"""
plugins/lists.py
----------------
مدیریت لیست‌های کاربران: دوست (friend)، دشمن (enemy) و هر لیست دلخواه دیگر.

دستورات:
  .addfriend  (با ریپلای روی پیام کاربر موردنظر)
  .addenemy   (با ریپلای)
  .add <نام لیست>       (با ریپلای)  -> لیست دلخواه/سلیقه‌ای خودت
  .remove <نام لیست>    (با ریپلای)
  .list <نام لیست>      -> نمایش اعضای آن لیست
  .lists                -> نمایش همه‌ی لیست‌های موجود با تعداد اعضا
  .clearlist <نام لیست> -> پاکسازی کامل یک لیست

نکته امنیتی: نام لیست همیشه sanitize می‌شود (فقط حروف/عدد/زیرخط مجاز است)
تا در query های دیتابیس یا نمایش خروجی مشکلی پیش نیاید.
"""

import re
from telethon import events

import database as db
from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX


def _clean_list_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_\u0600-\u06FF]", "", name)
    return name or "default"


async def _resolve_target_user(event):
    """کاربر هدف را از پیام ریپلای‌شده استخراج می‌کند."""
    if not event.is_reply:
        return None
    replied = await event.get_reply_message()
    sender = await replied.get_sender()
    return sender


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}addfriend$"))
    async def add_friend(event):
        if not await is_authorized(event):
            return
        user = await _resolve_target_user(event)
        if not user:
            await event.edit("⚠️ برای افزودن دوست، روی پیام او ریپلای کن.")
            return
        name = getattr(user, "first_name", None) or str(user.id)
        added = db.list_add("friend", user.id, note=name)
        if added:
            await event.edit(f"✅ {name} به لیست دوستان اضافه شد.")
        else:
            await event.edit(f"ℹ️ {name} از قبل در لیست دوستان بود.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}addenemy$"))
    async def add_enemy(event):
        if not await is_authorized(event):
            return
        user = await _resolve_target_user(event)
        if not user:
            await event.edit("⚠️ برای افزودن دشمن، روی پیام او ریپلای کن.")
            return
        name = getattr(user, "first_name", None) or str(user.id)
        added = db.list_add("enemy", user.id, note=name)
        if added:
            await event.edit(f"✅ {name} به لیست دشمنان اضافه شد.")
        else:
            await event.edit(f"ℹ️ {name} از قبل در لیست دشمنان بود.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}add (\S+)$"))
    async def add_custom(event):
        if not await is_authorized(event):
            return
        list_name = _clean_list_name(event.pattern_match.group(1))
        user = await _resolve_target_user(event)
        if not user:
            await event.edit("⚠️ برای افزودن، روی پیام کاربر موردنظر ریپلای کن.")
            return
        name = getattr(user, "first_name", None) or str(user.id)
        added = db.list_add(list_name, user.id, note=name)
        if added:
            await event.edit(f"✅ {name} به لیست «{list_name}» اضافه شد.")
        else:
            await event.edit(f"ℹ️ {name} از قبل در لیست «{list_name}» بود.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}remove (\S+)$"))
    async def remove_from_list(event):
        if not await is_authorized(event):
            return
        list_name = _clean_list_name(event.pattern_match.group(1))
        user = await _resolve_target_user(event)
        if not user:
            await event.edit("⚠️ برای حذف، روی پیام کاربر موردنظر ریپلای کن.")
            return
        removed = db.list_remove(list_name, user.id)
        if removed:
            await event.edit(f"🗑 از لیست «{list_name}» حذف شد.")
        else:
            await event.edit(f"ℹ️ این کاربر در لیست «{list_name}» نبود.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}list (\S+)$"))
    async def show_list(event):
        if not await is_authorized(event):
            return
        list_name = _clean_list_name(event.pattern_match.group(1))
        rows = db.list_get_all(list_name)
        if not rows:
            await event.edit(f"لیست «{list_name}» خالی است.")
            return
        lines = [f"📋 **لیست «{list_name}»** ({len(rows)} عضو):\n"]
        for r in rows:
            note = r["note"] or "بدون نام"
            lines.append(f"• {note} — `{r['user_id']}`")
        await event.edit("\n".join(lines), parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}lists$"))
    async def show_all_lists(event):
        if not await is_authorized(event):
            return
        names = db.list_names()
        if not names:
            await event.edit("هیچ لیستی هنوز ساخته نشده است.")
            return
        lines = ["📚 **لیست‌های موجود:**\n"]
        for n in names:
            count = len(db.list_get_all(n))
            lines.append(f"• `{n}` — {count} عضو")
        await event.edit("\n".join(lines), parse_mode="md")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}clearlist (\S+)$"))
    async def clear_list(event):
        if not await is_authorized(event):
            return
        list_name = _clean_list_name(event.pattern_match.group(1))
        count = db.list_clear(list_name)
        await event.edit(f"🧹 لیست «{list_name}» پاکسازی شد. ({count} مورد حذف شد)")
