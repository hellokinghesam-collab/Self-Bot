"""
plugin_loader.py
----------------
بارگذاری خودکار تمام پلاگین‌های داخل پوشه plugins/.
هر پلاگین یک فایل .py با یک تابع async به نام register(client) است
که هندلرهای خودش را با client.add_event_handler ثبت می‌کند.

برای ساخت افزونه (Plugin) جدید:
1. یک فایل جدید در plugins/my_plugin.py بساز.
2. تابع async def register(client): ... تعریف کن.
3. داخلش با @client.on(events.NewMessage(...)) هندلر تعریف کن.
4. کافیست! لودر خودش آن را در استارت بعدی پیدا و بارگذاری می‌کند.
"""

import importlib
import logging
import pkgutil

import plugins

logger = logging.getLogger("selfbot.plugin_loader")


async def load_all_plugins(client):
    loaded = []
    for _, module_name, _ in pkgutil.iter_modules(plugins.__path__):
        full_name = f"plugins.{module_name}"
        try:
            module = importlib.import_module(full_name)
            if hasattr(module, "register"):
                await module.register(client)
                loaded.append(module_name)
                logger.info("پلاگین بارگذاری شد: %s", module_name)
            else:
                logger.warning("پلاگین %s فاقد تابع register است و رد شد.", module_name)
        except Exception as e:
            logger.exception("خطا در بارگذاری پلاگین %s: %s", module_name, e)
    return loaded
