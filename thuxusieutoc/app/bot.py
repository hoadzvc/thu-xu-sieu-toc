
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

from app.config import settings
from app.db import init_db, close_db


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


# ==========================================
# BOT AND DISPATCHER
# ==========================================

bot = Bot(
    token=settings.bot_token.get_secret_value(),
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()


# ==========================================
# REGISTER ROUTERS
# ==========================================

def register_routers():
    """
    Đăng ký các router của bot.

    Những router sẽ được tạo ở các file tiếp theo.
    """

    from app.handlers.user import router as user_router
    from app.handlers.orders import router as orders_router
    from app.handlers.admin import router as admin_router

    # Router cụ thể trước, router tổng quát sau.
    dp.include_router(admin_router)
    dp.include_router(orders_router)
    dp.include_router(user_router)


# ==========================================
# STARTUP
# ==========================================

async def on_startup():
    logger.info("Đang khởi tạo database...")

    await init_db()

    logger.info("Database đã sẵn sàng.")

    bot_info = await bot.get_me()

    logger.info(
        "Telegram bot đã khởi động: @%s",
        bot_info.username,
    )


# ==========================================
# SHUTDOWN
# ==========================================

async def on_shutdown():
    logger.info("Đang dừng Telegram bot...")

    try:
        await bot.session.close()
    except TelegramAPIError:
        logger.exception("Lỗi khi đóng Telegram session.")

    await close_db()

    logger.info("Đã dừng bot an toàn.")


# ==========================================
# MAIN
# ==========================================

async def main():
    token = settings.bot_token.get_secret_value()

    if not token:
        raise RuntimeError(
            "Bạn chưa cấu hình BOT_TOKEN trong file .env"
        )

    register_routers()

    try:
        await on_startup()

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    except KeyboardInterrupt:
        logger.info("Nhận lệnh dừng từ bàn phím.")

    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (RuntimeError, TelegramAPIError):
        logger.exception("Không thể khởi động Telegram bot.")
        sys.exit(1)
