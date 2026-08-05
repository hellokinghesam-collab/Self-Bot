"""
generate_session.py
--------------------
⚠️ این اسکریپت را فقط یک‌بار، روی کامپیوتر شخصی خودت اجرا کن (نه روی Railway/سرور).

هدف: ساخت SESSION_STRING که سپس آن را به‌عنوان یک Environment Variable
در Railway وارد می‌کنی. خودِ فایل این اسکریپت هرگز نباید روی سرور public
اجرا شود یا کلید نهایی در جایی لاگ/ذخیره شود.

مراحل استفاده:
  1. از https://my.telegram.org مقادیر API_ID و API_HASH را بگیر.
  2. این اسکریپت را اجرا کن:  python generate_session.py
  3. API_ID، API_HASH و شماره تلفن را وارد کن.
  4. کد تاییدی که تلگرام برایت پیامک/ارسال می‌کند را وارد کن (و رمز دومرحله‌ای در صورت فعال بودن).
  5. رشته‌ی نهایی چاپ می‌شود. آن را کپی کن و در Railway، به عنوان مقدار
     متغیر محیطی SESSION_STRING قرار بده.

🔒 نکات امنیتی حیاتی:
  - این رشته معادل رمز عبور کامل اکانت تلگرام توست. هرکسی آن را داشته باشد
    می‌تواند بدون نیاز به رمز عبور یا کد تایید وارد اکانتت شود.
  - هرگز این رشته را در گیت‌هاب، در چت با دیگران، یا در هیچ فایل عمومی قرار نده.
  - این فایل (generate_session.py) خودش هیچ سکرتی داخلش هاردکد ندارد،
    پس آپلود همین فایل به گیت‌هاب مشکلی ندارد؛ آنچه باید محرمانه بماند
    خروجیِ چاپ‌شده (رشته‌ی سشن) است، نه خودِ این اسکریپت.
  - اگر فکر می‌کنی رشته لو رفته، فوراً از تلگرام Settings > Devices
    آن سشن را Terminate کن و یک سشن جدید بساز.
"""

import asyncio
import getpass

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    print("=== ساخت Session String برای سلف‌بات تلگرام ===\n")
    api_id = int(input("API_ID را وارد کن: ").strip())
    api_hash = input("API_HASH را وارد کن: ").strip()

    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        # Telethon در صورت نیاز خودش شماره تلفن، کد تایید و رمز دومرحله‌ای
        # (در صورت فعال بودن) را به صورت تعاملی از شما می‌پرسد.
        me = await client.get_me()
        session_string = client.session.save()

        print("\n✅ ورود موفق بود. اکانت:", me.first_name, me.id)
        print("\n" + "=" * 60)
        print("SESSION_STRING شما (این را در Railway به عنوان متغیر محیطی قرار بده):\n")
        print(session_string)
        print("=" * 60)
        print(
            "\n⚠️ این رشته را با هیچ‌کس به اشتراک نگذار و در هیچ فایل عمومی/گیت‌هاب قرار نده."
        )


if __name__ == "__main__":
    asyncio.run(main())
