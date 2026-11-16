
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """
    Menu chính dành cho khách hàng.
    Admin có thêm nút quản trị.
    """

    keyboard = [
        [
            KeyboardButton(text="🛒 Mua xu"),
            KeyboardButton(text="💰 Bán xu"),
        ],
        [
            KeyboardButton(text="👛 Ví của tôi"),
            KeyboardButton(text="📜 Lịch sử đơn"),
        ],
        [
            KeyboardButton(text="📱 Thanh toán QR"),
            KeyboardButton(text="💵 Bảng giá"),
        ],
        [
            KeyboardButton(text="📖 Hướng dẫn"),
            KeyboardButton(text="🆘 Hỗ trợ"),
        ],
    ]

    if is_admin:
        keyboard.append([
            KeyboardButton(text="⚙️ Quản trị"),
        ])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Chọn chức năng bạn muốn sử dụng...",
    )


def back_home_keyboard() -> InlineKeyboardMarkup:
    """
    Nút quay lại và về trang chủ dùng trong các bước đặt đơn.
    """

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Quay lại",
            callback_data="nav:back",
        ),
        InlineKeyboardButton(
            text="🏠 Trang chủ",
            callback_data="nav:home",
        ),
    )

    builder.row(
        InlineKeyboardButton(
            text="❌ Hủy đơn",
            callback_data="nav:cancel",
        )
    )

    return builder.as_markup()


def website_keyboard(action: str) -> InlineKeyboardMarkup:
    """
    Chọn website cho quy trình mua hoặc bán.
    action: buy hoặc sell.
    """

    if action not in {"buy", "sell"}:
        raise ValueError("action phải là buy hoặc sell")

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🌐 Nhiemvucheo",
            callback_data=f"{action}:website:nvc",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🌐 XSMM",
            callback_data=f"{action}:website:xsmm",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Quay lại",
            callback_data="nav:back",
        ),
        InlineKeyboardButton(
            text="🏠 Trang chủ",
            callback_data="nav:home",
        ),
    )

    return builder.as_markup()


def payment_method_keyboard() -> InlineKeyboardMarkup:
    """
    Hai phương thức thanh toán dành cho khách mua xu.
    """

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="👛 Thanh toán bằng ví",
            callback_data="payment:wallet",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📱 Thanh toán qua QR",
            callback_data="payment:qr",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Quay lại",
            callback_data="nav:back",
        ),
        InlineKeyboardButton(
            text="❌ Hủy đơn",
            callback_data="nav:cancel",
        ),
    )

    return builder.as_markup()


def confirm_order_keyboard() -> InlineKeyboardMarkup:
    """
    Xác nhận hoặc hủy đơn hàng.
    """

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Xác nhận đặt đơn",
            callback_data="order:confirm",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Quay lại",
            callback_data="nav:back",
        ),
        InlineKeyboardButton(
            text="❌ Hủy đơn",
            callback_data="nav:cancel",
        ),
    )

    return builder.as_markup()


def qr_payment_keyboard() -> InlineKeyboardMarkup:
    """
    Nút kiểm tra trạng thái thanh toán QR.
    """

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔄 Kiểm tra thanh toán",
            callback_data="payment:check",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🆘 Liên hệ hỗ trợ",
            callback_data="support:open",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Trang chủ",
            callback_data="nav:home",
        )
    )

    return builder.as_markup()


def sell_transfer_keyboard() -> InlineKeyboardMarkup:
    """
    Nút khách thông báo đã chuyển xu.
    Đây chỉ là yêu cầu kiểm tra, không phải bằng chứng nhận xu.
    """

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📤 Tôi đã chuyển xu",
            callback_data="sell:check_transfer",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📋 Sao chép thông tin",
            callback_data="sell:copy_info",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="❌ Hủy đơn",
            callback_data="nav:cancel",
        )
    )

    return builder.as_markup()


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Menu quản trị.
    Việc xác thực quyền admin phải được thực hiện
    trong handler, không chỉ dựa vào việc ẩn nút.
    """

    builder = InlineKeyboardBuilder()

    buttons = [
        ("📊 Thống kê", "admin:stats"),
        ("🛒 Đơn mua xu", "admin:buy_orders"),
        ("💰 Đơn bán xu", "admin:sell_orders"),
        ("💳 Duyệt thanh toán", "admin:payments"),
        ("👛 Quản lý ví", "admin:wallets"),
        ("💵 Cài đặt bảng giá", "admin:prices"),
        ("🌐 Quản lý website", "admin:websites"),
        ("👥 Quản lý khách hàng", "admin:users"),
        ("📢 Gửi thông báo", "admin:broadcast"),
        ("📋 Nhật ký hệ thống", "admin:logs"),
    ]

    for label, callback in buttons:
        builder.row(
            InlineKeyboardButton(
                text=label,
                callback_data=callback,
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🏠 Trang chủ",
            callback_data="nav:home",
        )
    )

    return builder.as_markup()
