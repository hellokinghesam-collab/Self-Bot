"""
plugins/extras.py
-------------------
مجموعه‌ای از قابلیت‌های اضافه‌ی رایج در سلف‌بات‌ها:

  .purge <تعداد>       -> حذف N پیام آخر خودت در همین چت (فقط پیام‌های خودت)
  .edit <متن جدید>      (با ریپلای روی پیام خودت) -> ویرایش پیام قبلی خودت
  .calc <عبارت>         -> محاسبه‌ی یک عبارت ریاضی ساده
  .afk [دلیل]           -> فعال کردن حالت AFK؛ به هرکسی که در PV پیام بدهد
                            یک‌بار پاسخ خودکار «فعلاً نیستم» داده می‌شود
  .unafk                -> خاموش کردن حالت AFK
  .pin (با ریپلای)      -> پین کردن پیام ریپلای‌شده در همان چت (اگر دسترسی داری)
  .unpin (با ریپلای)    -> برداشتن پین

⚠️ نکات امنیتی:
  - `.calc` از `eval` مستقیم استفاده نمی‌کند؛ یک ارزیاب امنِ محدود به عملگرهای
    ریاضی پایه دارد (AST-based) تا اجرای کد دلخواه (Code Injection) ممکن نباشد.
  - `.purge` فقط پیام‌های خودِ کاربر (out=True) را حذف می‌کند، هرگز پیام دیگران را.
"""

import ast
import operator
import logging
import time
from telethon import events

import database as db
from config import COMMAND_PREFIX
from security import is_authorized

PREFIX = COMMAND_PREFIX
logger = logging.getLogger("selfbot.extras")

# --- ارزیاب امن عبارات ریاضی (بدون eval) ---
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("مقدار غیرمجاز")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
        return _ALLOWED_OPERATORS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("عبارت غیرمجاز")


def safe_calculate(expr: str):
    parsed = ast.parse(expr, mode="eval")
    return _safe_eval(parsed.body)


async def register(client):

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}purge (\d+)$"))
    async def purge_handler(event):
        if not await is_authorized(event):
            return
        count = min(int(event.pattern_match.group(1)), 200)  # سقف امن برای جلوگیری از فلود
        chat_id = event.chat_id
        deleted = 0
        async for msg in client.iter_messages(chat_id, limit=count + 1):
            if msg.out:
                try:
                    await msg.delete()
                    deleted += 1
                except Exception as e:
                    logger.warning("حذف پیام %s ناموفق بود: %s", msg.id, e)
        # پیام تاییدیه موقت (چون خودِ پیام دستور هم حذف شده)
        confirm = await client.send_message(chat_id, f"🧹 {deleted} پیام حذف شد.")
        await confirm.delete(delay=3)

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}edit (.+)$"))
    async def edit_handler(event):
        if not await is_authorized(event):
            return
        new_text = event.pattern_match.group(1)
        if not event.is_reply:
            await event.edit("⚠️ روی پیام خودت که می‌خواهی ویرایش کنی ریپلای کن.")
            return
        replied = await event.get_reply_message()
        if not replied.out:
            await event.edit("🚫 فقط می‌توانی پیام‌های خودت را ویرایش کنی.")
            return
        try:
            await replied.edit(new_text)
            await event.delete()
        except Exception as e:
            await event.edit(f"❌ ویرایش ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}calc (.+)$"))
    async def calc_handler(event):
        if not await is_authorized(event):
            return
        expr = event.pattern_match.group(1).strip()
        try:
            result = safe_calculate(expr)
            await event.edit(f"🧮 `{expr}` = **{result}**", parse_mode="md")
        except Exception:
            await event.edit("⚠️ عبارت ریاضی نامعتبر است.")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}afk( (.*))?$"))
    async def afk_on_handler(event):
        if not await is_authorized(event):
            return
        reason = (event.pattern_match.group(2) or "").strip()
        db.setting_set_bool("afk_enabled", True)
        db.setting_set("afk_reason", reason or "فعلاً در دسترس نیستم.")
        db.setting_set("afk_since", str(int(time.time())))
        await event.edit(f"😴 حالت AFK فعال شد. دلیل: {reason or '(بدون توضیح)'}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}unafk$"))
    async def afk_off_handler(event):
        if not await is_authorized(event):
            return
        db.setting_set_bool("afk_enabled", False)
        await event.edit("🙋 حالت AFK غیرفعال شد. خوش برگشتی!")

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def afk_autoreply(event):
        if event.out:
            return
        if not db.setting_get_bool("afk_enabled", default=False):
            return
        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return
        # حداکثر یک پاسخ AFK در هر ۱۰ دقیقه به یک نفر، برای جلوگیری از اسپم
        key = f"afk_last_reply::{sender.id}"
        last = db.setting_get(key, "0")
        now = int(time.time())
        if now - int(last) < 600:
            return
        reason = db.setting_get("afk_reason", "فعلاً در دسترس نیستم.")
        await event.respond(f"🤖 (پاسخ خودکار) {reason}")
        db.setting_set(key, str(now))

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}pin$"))
    async def pin_handler(event):
        if not await is_authorized(event):
            return
        if not event.is_reply:
            await event.edit("⚠️ روی پیامی که می‌خواهی پین کنی ریپلای کن.")
            return
        replied = await event.get_reply_message()
        try:
            await client.pin_message(event.chat_id, replied.id, notify=False)
            await event.edit("📌 پیام پین شد.")
        except Exception as e:
            await event.edit(f"❌ پین کردن ناموفق بود: {e}")

    @client.on(events.NewMessage(pattern=rf"^\{PREFIX}unpin$"))
    async def unpin_handler(event):
        if not await is_authorized(event):
            return
        if not event.is_reply:
            await event.edit("⚠️ روی پیام پین‌شده ریپلای کن.")
            return
        replied = await event.get_reply_message()
        try:
            await client.unpin_message(event.chat_id, replied.id)
            await event.edit("📌 پین برداشته شد.")
        except Exception as e:
            await event.edit(f"❌ برداشتن پین ناموفق بود: {e}")
