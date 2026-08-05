"""
security.py
-----------
این ماژول تنها مسئولیتش این است که مطمئن شود *هیچ* دستوری، از *هیچ* منبعی
جز خود صاحب اکانت در چت Saved Messages اجرا نمی‌شود.

نکات امنیتی رعایت‌شده:
1. is_authorized فقط زمانی True برمی‌گرداند که:
   - فرستنده پیام دقیقاً همان اکانتی باشد که سلف‌بات با آن لاگین کرده (out_going / me).
   - چت مقصد "Saved Messages" (چت با خود کاربر) باشد.
2. حتی اگر یک اکانت دیگر عضو مکالمه شود یا پیام‌فوروارد شده حاوی متن دستور باشد،
   چون sender آن پیام «من» نیست، دستور اجرا نمی‌شود.
3. این تابع مرکزی است و هر پلاگین جدید باید از همین تابع استفاده کند؛
   به این ترتیب یک نقطه‌ی واحد برای ممیزی امنیتی وجود دارد.
"""

from telethon.tl.custom import Message


async def is_authorized(event: Message) -> bool:
    """
    بررسی می‌کند که آیا این پیام مجاز به اجرای دستور سلف‌بات هست یا نه.
    فقط پیام‌هایی که:
      - خودِ کاربر صاحب اکانت فرستاده (event.out == True)
      - در چت Saved Messages (پیام به خود) ارسال شده
    مجاز شمرده می‌شوند.
    """
    try:
        if not event.out:
            # پیام از طرف کس دیگری است -> هرگز اجازه اجرای دستور نده.
            return False
        if not event.is_private:
            return False
        # چت خصوصی با خودِ کاربر = Saved Messages
        me = await event.client.get_me()
        if event.chat_id != me.id:
            return False
        return True
    except Exception:
        # در هر حالت نامشخص یا خطا، محافظه‌کارانه رفتار کن: اجازه نده.
        return False


def sanitize_for_log(text: str, max_len: int = 200) -> str:
    """
    برای جلوگیری از لو رفتن اطلاعات حساس در لاگ‌ها (مثل session string در صورت
    اشتباهی چاپ شدن)، طول متن لاگ‌شده را محدود می‌کند.
    """
    if text is None:
        return ""
    text = text.replace("\n", " ")
    if len(text) > max_len:
        return text[:max_len] + "...(truncated)"
    return text


class RateLimiter:
    """
    محدودکننده‌ی نرخ ساده و در-حافظه (in-memory).

    هدف: جلوگیری از رفتارهایی که می‌توانند شبیه اسپم/ربات به نظر برسند و باعث
    محدود یا مسدود شدن اکانت توسط تلگرام شوند (مثلاً فوروارد بیش‌ازحد سریع،
    یا اجرای پی‌درپی دستورات مدیریت گروه مثل kick/ban).

    استفاده:
        limiter = RateLimiter(max_calls=5, period_seconds=10)
        if not limiter.allow("forward"):
            # به جای اجرا، صبر کن یا رد کن
    """

    def __init__(self, max_calls: int, period_seconds: float):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self._events: dict[str, list] = {}

    def allow(self, key: str) -> bool:
        import time as _time
        now = _time.monotonic()
        bucket = self._events.setdefault(key, [])
        cutoff = now - self.period_seconds
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= self.max_calls:
            return False
        bucket.append(now)
        return True
