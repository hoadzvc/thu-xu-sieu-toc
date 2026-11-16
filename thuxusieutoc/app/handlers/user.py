
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from sqlalchemy import select

from app.config import settings
from app.db import AsyncSessionLocal
from app.models import User, Wallet
from app.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)

router = Router(name="user")


# ==========================================
# TEXTS
# ==========================================

WELCOME_TEXT = """
<b>🌟 XU EXCHANGE BOT</b>

Chào mừng bạn đến với hệ thống mua bán xu tự động.

Bạn có thể sử dụng các chức năng:

🛒 Mua xu
💰 Bán xu
👛 Quản lý ví
📜 Lịch sử đơn hàng
📱 Thanh toán QR qua SePay
💵 Xem bảng giá

Vui lòng chọn chức năng bên dưới.
"""

GUIDE_TEXT = """
<b>📖 HƯỚNG DẪN SỬ DỤNG</b>

<b>1. Mua xu</b>
- Chọn website.
- Nhập số xu cần mua.
- Nhập username nhận xu.
- Chọn thanh toán bằng ví hoặc QR.
- Xác nhận đơn hàng.

<b>2. Bán xu</b>
- Chọn website.
- Nhập số xu muốn bán.
- Nhập username gửi xu.
- Nhập thông tin ngân hàng nhận tiền.
- Chuyển xu vào tài khoản hệ thống.
- Bot tự kiểm tra giao dịch.
- Admin duyệt và thực hiện thanh toán.

<b>3. Thanh toán QR</b>
- Quét QR riêng của đơn hàng.
- Chuyển đúng số tiền.
- Chờ hệ thống xác nhận thanh toán.

<b>Lưu ý:</b>
Không cung cấp mật khẩu website cho người lạ.
Không gửi xu khi chưa kiểm tra đúng tài khoản nhận.
"""

PRICE_TEXT = """
<b>💵 BẢNG GIÁ THAM KHẢO</b>

<b>NHIEMVUCHEO</b>

Khách bán:
- Dưới 50 triệu: 8.000đ / 1 triệu xu
- Phần vượt 50 triệu: 9.000đ / 1 triệu xu

Khách mua:
- 0–10 triệu: 10.000đ / 1 triệu xu
- Trên 10–100 triệu: 9.000đ / 1 triệu xu
- Phần vượt 100 triệu: 8.000đ / 1 triệu xu

<b>XSMM</b>

Khách bán:
- 7.500đ / 10.000 xu
- Tối thiểu 100.000 xu

Khách mua:
- 9.000đ / 10.000 xu
- Tối thiểu 50.000 xu

Giá cuối cùng được tính theo số lượng và bảng giá hiện hành.
"""

SUPPORT_TEXT = """
<b>🆘 HỖ TRỢ KHÁCH HÀNG</b>

Nếu bạn gặp vấn đề về đơn hàng hoặc thanh toán:

- Không tự chuyển khoản thêm khi chưa được xác nhận.
- Không gửi mật khẩu hoặc mã bảo mật.
- Cung cấp mã đơn hàng khi liên hệ Admin.

Liên hệ hỗ trợ:
"""


# ==========================================
# USER REGISTRATION
# ==========================================

async def register_user(message: Message) -> User:
    """
    Tạo khách hàng và ví nếu chưa tồn tại.
    """

    telegram_user = message.from_user

    if telegram_user is None:
        raise ValueError("Không xác định được Telegram user.")

    async with AsyncSessionLocal() as session:
        async with session.begin():

            result = await session.execute(
                select(User).where(
                    User.telegram_id == telegram_user.id
                )
            )

            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    full_name=telegram_user.full_name,
                    language="vi",
                )

                session.add(user)
                await session.flush()

                session.add(
                    Wallet(
                        user_id=user.id,
                    )
                )

            else:
                user.username = telegram_user.username
                user.full_name = telegram_user.full_name

            return user


# ==========================================
# START COMMAND
# ==========================================

@router.message(CommandStart())
async def start_handler(message: Message):
    try:
        user = await register_user(message)

        is_admin = user.telegram_id in settings.admin_id_list

        if user.is_blocked:
            await message.answer(
                "⛔ Tài khoản của bạn hiện đang bị khóa. "
                "Vui lòng liên hệ Admin."
            )
            return

        await message.answer(
            WELCOME_TEXT,
            reply_markup=main_menu_keyboard(is_admin),
        )

    except Exception:
        logger.exception("Không thể đăng ký người dùng.")
        await message.answer(
            "Có lỗi xảy ra khi khởi tạo tài khoản. "
            "Vui lòng thử lại sau."
        )


# ==========================================
# COMMON USER CHECK
# ==========================================

async def get_user_by_telegram_id(telegram_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == telegram_id
            )
        )

        return result.scalar_one_or_none()


# ==========================================
# BUY / SELL MENU
# ==========================================

@router.message(F.text == "🛒 Mua xu")
async def buy_menu(message: Message):
    user = await get_user_by_telegram_id(
        message.from_user.id
    )

    if not user or user.is_blocked:
        await message.answer(
            "⛔ Bạn không thể sử dụng chức năng này."
        )
        return

    await message.answer(
        "<b>🛒 MUA XU</b>\n\n"
        "Bạn sẽ chọn website và số lượng xu "
        "ở bước tiếp theo."
    )

    await message.answer(
        "Chọn website:",
        reply_markup=__import__(
            "app.keyboards.main",
            fromlist=["website_keyboard"],
        ).website_keyboard("buy"),
    )


@router.message(F.text == "💰 Bán xu")
async def sell_menu(message: Message):
    user = await get_user_by_telegram_id(
        message.from_user.id
    )

    if not user or user.is_blocked:
        await message.answer(
            "⛔ Bạn không thể sử dụng chức năng này."
        )
        return

    from app.keyboards.main import website_keyboard

    await message.answer(
        "<b>💰 BÁN XU</b>\n\n"
        "Chọn website bạn muốn bán xu:",
        reply_markup=website_keyboard("sell"),
    )


# ==========================================
# WALLET
# ==========================================

@router.message(F.text == "👛 Ví của tôi")
async def wallet_handler(message: Message):
    telegram_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == telegram_id
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            await message.answer(
                "Vui lòng bấm /start để đăng ký."
            )
            return

        result = await session.execute(
            select(Wallet).where(
                Wallet.user_id == user.id
            )
        )

        wallet = result.scalar_one_or_none()

        if wallet is None:
            wallet = Wallet(user_id=user.id)
            session.add(wallet)
            await session.commit()

        balance = wallet.balance
        locked = wallet.locked_balance
        available = balance - locked

        await message.answer(
            "<b>👛 VÍ CỦA BẠN</b>\n\n"
            f"💰 Số dư: <b>{balance:,.0f}đ</b>\n"
            f"🔒 Đang khóa: <b>{locked:,.0f}đ</b>\n"
            f"✅ Khả dụng: <b>{available:,.0f}đ</b>"
        )


# ==========================================
# PRICE LIST
# ==========================================

@router.message(F.text == "💵 Bảng giá")
async def price_handler(message: Message):
    await message.answer(PRICE_TEXT)


# ==========================================
# GUIDE
# ==========================================

@router.message(F.text == "📖 Hướng dẫn")
async def guide_handler(message: Message):
    await message.answer(GUIDE_TEXT)


# ==========================================
# SUPPORT
# ==========================================

@router.message(F.text == "🆘 Hỗ trợ")
async def support_handler(message: Message):
    text = SUPPORT_TEXT

    if settings.support_username:
        text += (
            f"\n👤 Admin: @{settings.support_username}"
        )

    if settings.support_group_url:
        text += (
            "\n👥 Nhóm hỗ trợ: "
            f"{settings.support_group_url}"
        )

    await message.answer(text)


# ==========================================
# HOME CALLBACK
# ==========================================

@router.callback_query(F.data == "nav:home")
async def home_callback(callback: CallbackQuery):
    if callback.from_user is None:
        await callback.answer()
        return

    user = await get_user_by_telegram_id(
        callback.from_user.id
    )

    if user is None:
        await callback.answer(
            "Vui lòng bấm /start trước.",
            show_alert=True,
        )
        return

    if user.is_blocked:
        await callback.answer(
            "Tài khoản của bạn đang bị khóa.",
            show_alert=True,
        )
        return

    is_admin = user.telegram_id in settings.admin_id_list

    await callback.message.answer(
        WELCOME_TEXT,
        reply_markup=main_menu_keyboard(is_admin),
    )

    await callback.answer()


# ==========================================
# CANCEL CALLBACK
# ==========================================

@router.callback_query(F.data == "nav:cancel")
async def cancel_callback(callback: CallbackQuery):
    await callback.answer(
        "Đã gửi yêu cầu hủy. Nếu đã tạo đơn, "
        "hãy kiểm tra trạng thái đơn trước khi đặt lại.",
        show_alert=True,
    )
