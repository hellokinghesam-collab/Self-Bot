"""
healthcheck.py
---------------
یک اسکریپت مستقل و سریع برای بررسی اینکه آیا تمام پیش‌نیازهای اجرا (متغیرهای
محیطی، اتصال به تلگرام، اعتبار سشن) درست تنظیم شده‌اند — بدون نیاز به اجرای
کامل main.py و بارگذاری پلاگین‌ها.

استفاده (هم لوکال، هم به‌عنوان اولین قدم عیب‌یابی روی Railway):
    python healthcheck.py

اگر همه‌چیز درست باشد خروجی با کد 0 و پیام ✅ تمام می‌شود.
اگر مشکلی باشد (متغیر محیطی گم‌شده، سشن نامعتبر، عدم دسترسی شبکه)، خروجی
با کد غیر صفر و توضیح دقیق مشکل تمام می‌شود — این خیلی سریع‌تر از خواندن
لاگ کامل main.py است.
"""

import asyncio
import sys


async def run_healthcheck():
    print("🔍 در حال بررسی پیکربندی سلف‌بات...\n")

    # مرحله ۱: بررسی وجود متغیرهای محیطی الزامی (بدون چاپ مقدار واقعی آن‌ها)
    import os
    required_vars = ["API_ID", "API_HASH", "SESSION_STRING"]
    missing = [v for v in required_vars if not os.environ.get(v, "").strip()]
    if missing:
        print(f"❌ متغیر(های) محیطی الزامی تنظیم نشده‌اند: {', '.join(missing)}")
        print("   این‌ها را در Railway → Variables اضافه کن.")
        return False
    print("✅ همه‌ی متغیرهای محیطی الزامی موجودند.")

    # مرحله ۲: بررسی معتبر بودن API_ID (باید عدد باشد)
    try:
        api_id = int(os.environ["API_ID"])
    except ValueError:
        print("❌ مقدار API_ID باید یک عدد باشد.")
        return False
    api_hash = os.environ["API_HASH"]
    session_string = os.environ["SESSION_STRING"]
    print("✅ فرمت API_ID و API_HASH معتبر است.")

    # مرحله ۳: تلاش برای اتصال واقعی به تلگرام با همین اطلاعات
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("❌ کتابخانه‌ی telethon نصب نیست. `pip install -r requirements.txt` را اجرا کن.")
        return False

    print("🔌 در حال تلاش برای اتصال به تلگرام...")
    client = TelegramClient(StringSession(session_string), api_id, api_hash)
    try:
        await client.connect()
    except Exception as e:
        print(f"❌ اتصال به سرورهای تلگرام ناموفق بود: {e}")
        print("   این می‌تواند به دلیل مشکل شبکه یا API_ID/API_HASH اشتباه باشد.")
        return False

    if not await client.is_user_authorized():
        print("❌ SESSION_STRING نامعتبر یا منقضی است.")
        print("   یک سشن جدید با `python generate_session.py` بساز و SESSION_STRING را در Railway به‌روزرسانی کن.")
        await client.disconnect()
        return False

    me = await client.get_me()
    print(f"✅ اتصال موفق! اکانت متصل: {me.first_name or ''} (id: {me.id})")
    await client.disconnect()

    print("\n🎉 همه‌چیز آماده است. حالا می‌توانی `python main.py` را اجرا کنی.")
    return True


if __name__ == "__main__":
    ok = asyncio.run(run_healthcheck())
    sys.exit(0 if ok else 1)
