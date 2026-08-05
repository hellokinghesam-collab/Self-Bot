"""
plugins/groupadmin.py
-----------------------
مدیریت گروه‌هایی که خودت در آن‌ها ادمین/مالک هستی.

دستورات (فقط از Saved Messages، و همیشه با ذکر آیدی گروه چون Saved Messages
یک چت جداست و نمی‌تواند به‌جای گروه عمل کند):

  .gpin <group_id>              (با ریپلای در Saved Messages روی متنِ پیامِ موردنظر
                                  کار نمی‌کند چون پیام در گروه نیست؛ به‌جایش:)
  در عمل، برای عملیات روی «یک پیام مشخص» باید مستقیماً داخل خودِ گروه دستور
  بدهی، نه در Saved Messages. اما طبق سیاست امنیتی این پروژه، ما اجازه‌ی
  اجرای دستور از هیچ چتی جز Saved Messages را نمی‌دهیم؛ بنابراین دستورات این
  پلاگین محدود به عملیاتی هستند که با «آیدی گروه + آیدی/username کاربر»
  قابل انجامند، بدون نیاز به حضور/ریپلای داخل خودِ گروه:

  .gkick <group_id> <user_id>     -> اخراج کاربر از گروه (نیاز به دسترسی ادمین)
  .gban <group_id> <user_id>      -> بن کامل کاربر در گروه
  .gunban <group_id> <user_id>    -> رفع بن کاربر
  .gmute <group_id> <user_id> <دقیقه>  -> سکوت موقت کاربر
  .gunmute <group_id> <user_id>   -> رفع سکوت
  .ginfo <group_id>               -> نمایش اطلاعات پایه‌ی گروه (تعداد اعضا و ...)
  .gadmins <group_id>             -> نمایش لیست ادمین‌های گروه

⚠️ محدودیت‌های امنیتی حیاتی:
  1. پیش از هر عملیات، ربات بررسی می‌کند که خودِ کاربر (owner اکانت) در آن
     گروه واقعاً دسترسی ادمین با مجوز لازم (ban_users) را دارد. اگر نداشته
     باشد، عملیات اجرا نمی‌شود و پیام خطای واضح داده می‌شود.
  2. یک RateLimiter محدودکننده (حداکثر ۵ عملیات مدیریتی در هر ۶۰ ثانیه) فعال
     است تا از رفتار ناگهانی/انبوه (که می‌تواند به چشم تلگرام مشکوک باشد)
     جلوگیری شود.
  3. این پلاگین هرگز کاربران را در گروه‌هایی که عضو آن نیستی مدیریت نمی‌کند
     (Telethon خودش برای این حالت خطا برمی‌گرداند و همان خطا نمایش داده می‌شود).
  4. هیچ قابلیتی برای عضویت خودکار در گروه‌های ناشناس، اسپم به گروه‌ها، یا
     افزودن اعضا به‌صورت انبوه در این پلاگین وجود ندارد.
"""

import logging
from telethon import events, functions
from telethon.tl.types import ChatBannedRights

from config import COMMAND_PREFIX
from security import is_authorized, RateLimiter

PREFIX = COMMAND_PREFIX
logger = logging.getLogger("selfbot.groupadmin")

# حداکثر ۵ عملیات مدیریتی (kick/ban/mute) در هر ۶۰ ثانیه
_admin_limiter = RateLimiter(max_calls=5, period_seconds=60)


async def _check_can_manage(client, group_id: int) -> tuple[bool, str]:
    """
    بررسی می‌کند خودِ کاربر در گروه موردنظر دسترسی لازم برای مدیریت اعضا را دارد.
    خروجی: (مجاز است؟, پیام توضیحی در صورت عدم مجوز)
    """
    try:
        me = await client.get_me()
        permissions = await client.get_permissions(group_id, me.id)
    except Exception as e:
        return False, f"دسترسی به اطلاعات گروه ممکن نشد: {e}"

    if not (permissions.is_admin or permissions.is_creator):
        return False, "تو در این گروه ادمین نیستی."
    if not (permissions.ban_users or permissions.is_creator):
        return False, "دسترسی 'مدیریت اعضا' (ban_users) در این گروه به تو داده نشده."
    return True, ""


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}gkick (-?\d+) (-?\d+)$"))
    async def gkick_handler(event):
        if not await is_authorized(event):
            return
        group_id = int(event.pattern_match.group(1))
        user_id = int(event.pattern_match.group(2))

        if not _admin_limiter.allow("group_admin"):
            await event.edit("⏳ محدودیت نرخ عملیات مدیریتی فعال شد؛ کمی صبر کن.")
            return

        ok, reason = await _check_can_manage(client, group_id)
        if not ok:
            await event.edit(f"🚫 عملیات انجام نشد: {reason}")
            return

        try:
            await client.kick_participant(group_id, user_id)
            await event.edit(f"✅ کاربر `{user_id}` از گروه اخراج شد.")
        except Exception as e:
            await event.edit(f"❌ اخراج ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}gban (-?\d+) (-?\d+)$"))
    async def gban_handler(event):
        if not await is_authorized(event):
            return
        group_id = int(event.pattern_match.group(1))
        user_id = int(event.pattern_match.group(2))

        if not _admin_limiter.allow("group_admin"):
            await event.edit("⏳ محدودیت نرخ عملیات مدیریتی فعال شد؛ کمی صبر کن.")
            return

        ok, reason = await _check_can_manage(client, group_id)
        if not ok:
            await event.edit(f"🚫 عملیات انجام نشد: {reason}")
            return

        try:
            rights = ChatBannedRights(until_date=None, view_messages=True)
            await client(functions.channels.EditBannedRequest(
                channel=group_id, participant=user_id, banned_rights=rights
            ))
            await event.edit(f"✅ کاربر `{user_id}` بن شد.")
        except Exception as e:
            await event.edit(f"❌ بن کردن ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}gunban (-?\d+) (-?\d+)$"))
    async def gunban_handler(event):
        if not await is_authorized(event):
            return
        group_id = int(event.pattern_match.group(1))
        user_id = int(event.pattern_match.group(2))

        ok, reason = await _check_can_manage(client, group_id)
        if not ok:
            await event.edit(f"🚫 عملیات انجام نشد: {reason}")
            return

        try:
            rights = ChatBannedRights(until_date=None, view_messages=False)
            await client(functions.channels.EditBannedRequest(
                channel=group_id, participant=user_id, banned_rights=rights
            ))
            await event.edit(f"✅ بن کاربر `{user_id}` برداشته شد.")
        except Exception as e:
            await event.edit(f"❌ رفع بن ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}gmute (-?\d+) (-?\d+) (\d+)$"))
    async def gmute_handler(event):
        if not await is_authorized(event):
            return
        group_id = int(event.pattern_match.group(1))
        user_id = int(event.pattern_match.group(2))
        minutes = int(event.pattern_match.group(3))

        if not _admin_limiter.allow("group_admin"):
            await event.edit("⏳ محدودیت نرخ عملیات مدیریتی فعال شد؛ کمی صبر کن.")
            return

        ok, reason = await _check_can_manage(client, group_id)
        if not ok:
            await event.edit(f"🚫 عملیات انجام نشد: {reason}")
            return

        import time
        until = int(time.time()) + minutes * 60
        try:
            rights = ChatBannedRights(until_date=until, send_messages=True)
            await client(functions.channels.EditBannedRequest(
                channel=group_id, participant=user_id, banned_rights=rights
            ))
            await event.edit(f"🔇 کاربر `{user_id}` به مدت {minutes} دقیقه سکوت شد.")
        except Exception as e:
            await event.edit(f"❌ سکوت کردن ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}gunmute (-?\d+) (-?\d+)$"))
    async def gunmute_handler(event):
        if not await is_authorized(event):
            return
        group_id = int(event.pattern_match.group(1))
        user_id = int(event.pattern_match.group(2))

        ok, reason = await _check_can_manage(client, group_id)
        if not ok:
            await event.edit(f"🚫 عملیات انجام نشد: {reason}")
            return

        try:
            rights = ChatBannedRights(until_date=None, send_messages=False)
            await client(functions.channels.EditBannedRequest(
                channel=group_id, participant=user_id, banned_rights=rights
            ))
            await event.edit(f"🔊 سکوت کاربر `{user_id}` برداشته شد.")
        except Exception as e:
            await event.edit(f"❌ رفع سکوت ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}ginfo (-?\d+)$"))
    async def ginfo_handler(event):
        if not await is_authorized(event):
            return
        group_id = int(event.pattern_match.group(1))
        try:
            entity = await client.get_entity(group_id)
            participants_count = getattr(entity, "participants_count", None)
            title = getattr(entity, "title", "نامشخص")
            lines = [
                f"ℹ️ **اطلاعات گروه**",
                f"عنوان: {title}",
                f"آیدی: `{group_id}`",
            ]
            if participants_count is not None:
                lines.append(f"تعداد اعضا: {participants_count}")
            await event.edit("\n".join(lines), parse_mode="md")
        except Exception as e:
            await event.edit(f"❌ دریافت اطلاعات گروه ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}gadmins (-?\d+)$"))
    async def gadmins_handler(event):
        if not await is_authorized(event):
            return
        group_id = int(event.pattern_match.group(1))
        try:
            admins = []
            async for user in client.iter_participants(group_id, filter=None):
                perms = await client.get_permissions(group_id, user.id)
                if perms.is_admin or perms.is_creator:
                    admins.append(user)
            if not admins:
                await event.edit("هیچ ادمینی پیدا نشد یا دسترسی کافی نیست.")
                return
            lines = ["👑 **ادمین‌های گروه:**\n"]
            for a in admins:
                name = a.first_name or a.username or str(a.id)
                lines.append(f"• {name} — `{a.id}`")
            await event.edit("\n".join(lines), parse_mode="md")
        except Exception as e:
            await event.edit(f"❌ دریافت لیست ادمین‌ها ناموفق بود: {e}")
