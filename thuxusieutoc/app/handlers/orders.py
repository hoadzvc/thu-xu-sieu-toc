
import logging
import re

from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from app.keyboards.main import (
    website_keyboard,
    payment_method_keyboard,
    confirm_order_keyboard,
    back_home_keyboard,
)

logger = logging.getLogger(__name__)

router = Router(name="orders")


# ==========================================
# ORDER STATES
# ==========================================

class BuyOrderStates(StatesGroup):
    waiting_amount = State()
    waiting_username = State()
    waiting_payment_method = State()
    confirming = State()


class SellOrderStates(StatesGroup):
    waiting_amount = State()
    waiting_username = State()
    waiting_bank_info = State()
    confirming = State()


# ==========================================
# CONSTANTS
# ==========================================

WEBSITE_NAMES = {
    "nvc": "Nhiemvucheo",
    "xsmm": "XSMM",
}

COIN_UNIT = 1_000_000


# ==========================================
# VALIDATION
# ==========================================

def parse_coin_amount(value: str, website: str, order_type: str):
    """
    Kiểm tra số xu theo quy định từng website.
    Trả về số xu hợp lệ hoặc None.
    """

    cleaned = value.strip().replace(",", "").replace(".", "")

    if not cleaned.isdigit():
        return None

    amount = int(cleaned)

    if amount <= 0:
        return None

    if website == "nvc":
        if amount < 1_000_000:
            return None

        if amount % 1_000_000 != 0:
            return None

    elif website == "xsmm":
        minimum = 100_000 if order_type == "sell" else 50_000

        if amount < minimum:
            return None

        if amount % 10_000 != 0:
            return None

    else:
        return None

    return amount


def valid_username(value: str) -> bool:
    """
    Kiểm tra username cơ bản.
    Không thay thế việc kiểm tra username trên website.
    """

    value = value.strip().lstrip("@")

    if not 2 <= len(value) <= 100:
        return False

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        return False

    return True


def format_coin(amount: int) -> str:
    return f"{amount:,}"


# ==========================================
# BUY ORDER - SELECT WEBSITE
# ==========================================

@router.callback_query(F.data.startswith("buy:website:"))
async def buy_select_website(
    callback: CallbackQuery,
    state: FSMContext,
):
    website = callback.data.split(":")[-1]

    if website not in WEBSITE_NAMES:
        await callback.answer(
            "Website không hợp lệ.",
            show_alert=True,
        )
        return

    await state.clear()

    await state.update_data(
        order_type="buy",
        website=website,
    )

    await state.set_state(
        BuyOrderStates.waiting_amount
    )

    if website == "nvc":
        instruction = (
            "Nhập số xu muốn mua.\n\n"
            "Ví dụ: <code>1000000</code>\n"
            "Số lượng phải là bội số của 1 triệu xu."
        )
    else:
        instruction = (
            "Nhập số xu muốn mua.\n\n"
            "Ví dụ: <code>50000</code>\n"
            "Tối thiểu 50.000 xu, bước 10.000 xu."
        )

    await callback.message.answer(
        f"<b>🛒 MUA XU - {WEBSITE_NAMES[website]}</b>\n\n"
        f"{instruction}",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


# ==========================================
# BUY ORDER - AMOUNT
# ==========================================

@router.message(BuyOrderStates.waiting_amount)
async def buy_enter_amount(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()

    amount = parse_coin_amount(
        message.text or "",
        data["website"],
        "buy",
    )

    if amount is None:
        await message.answer(
            "❌ Số xu không hợp lệ.\n"
            "Vui lòng nhập lại theo đúng mức tối thiểu "
            "và bước số lượng của website."
        )
        return

    await state.update_data(amount_coin=amount)

    await state.set_state(
        BuyOrderStates.waiting_username
    )

    await message.answer(
        "👤 Nhập username người nhận xu.\n\n"
        "Ví dụ: <code>nguyenvana</code>\n"
        "Không cần nhập mật khẩu website.",
        reply_markup=back_home_keyboard(),
    )


# ==========================================
# BUY ORDER - TARGET USERNAME
# ==========================================

@router.message(BuyOrderStates.waiting_username)
async def buy_enter_username(
    message: Message,
    state: FSMContext,
):
    username = (message.text or "").strip().lstrip("@")

    if not valid_username(username):
        await message.answer(
            "❌ Username không hợp lệ. Vui lòng nhập lại."
        )
        return

    await state.update_data(
        username_target=username
    )

    await state.set_state(
        BuyOrderStates.waiting_payment_method
    )

    await message.answer(
        "💳 Chọn phương thức thanh toán:",
        reply_markup=payment_method_keyboard(),
    )


# ==========================================
# BUY ORDER - PAYMENT METHOD
# ==========================================

@router.callback_query(F.data == "payment:wallet")
async def buy_payment_wallet(
    callback: CallbackQuery,
    state: FSMContext,
):
    current = await state.get_state()

    if current != BuyOrderStates.waiting_payment_method.state:
        await callback.answer(
            "Phiên đặt đơn không hợp lệ.",
            show_alert=True,
        )
        return

    await state.update_data(
        payment_method="wallet"
    )

    await show_buy_confirmation(callback, state)


@router.callback_query(F.data == "payment:qr")
async def buy_payment_qr(
    callback: CallbackQuery,
    state: FSMContext,
):
    current = await state.get_state()

    if current != BuyOrderStates.waiting_payment_method.state:
        await callback.answer(
            "Phiên đặt đơn không hợp lệ.",
            show_alert=True,
        )
        return

    await state.update_data(
        payment_method="qr"
    )

    await show_buy_confirmation(callback, state)


# ==========================================
# BUY ORDER - CONFIRMATION
# ==========================================

async def show_buy_confirmation(
    callback: CallbackQuery,
    state: FSMContext,
):
    data = await state.get_data()

    website = WEBSITE_NAMES[data["website"]]
    amount = format_coin(data["amount_coin"])

    payment = (
        "Ví nội bộ"
        if data["payment_method"] == "wallet"
        else "QR SePay"
    )

    await state.set_state(
        BuyOrderStates.confirming
    )

    await callback.message.answer(
        "<b>📋 XÁC NHẬN ĐƠN MUA XU</b>\n\n"
        f"🌐 Website: <b>{website}</b>\n"
        f"🪙 Số xu: <b>{amount}</b>\n"
        f"👤 Người nhận: <b>{data['username_target']}</b>\n"
        f"💳 Thanh toán: <b>{payment}</b>\n\n"
        "Vui lòng kiểm tra kỹ thông tin trước khi tiếp tục.",
        reply_markup=confirm_order_keyboard(),
    )

    await callback.answer()


# ==========================================
# SELL ORDER - SELECT WEBSITE
# ==========================================

@router.callback_query(F.data.startswith("sell:website:"))
async def sell_select_website(
    callback: CallbackQuery,
    state: FSMContext,
):
    website = callback.data.split(":")[-1]

    if website not in WEBSITE_NAMES:
        await callback.answer(
            "Website không hợp lệ.",
            show_alert=True,
        )
        return

    await state.clear()

    await state.update_data(
        order_type="sell",
        website=website,
    )

    await state.set_state(
        SellOrderStates.waiting_amount
    )

    if website == "nvc":
        instruction = (
            "Nhập số xu muốn bán.\n\n"
            "Ví dụ: <code>1000000</code>\n"
            "Số lượng phải là bội số của 1 triệu xu."
        )
    else:
        instruction = (
            "Nhập số xu muốn bán.\n\n"
            "Ví dụ: <code>100000</code>\n"
            "Tối thiểu 100.000 xu, bước 10.000 xu."
        )

    await callback.message.answer(
        f"<b>💰 BÁN XU - {WEBSITE_NAMES[website]}</b>\n\n"
        f"{instruction}",
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


# ==========================================
# SELL ORDER - AMOUNT
# ==========================================

@router.message(SellOrderStates.waiting_amount)
async def sell_enter_amount(
    message: Message,
    state: FSMContext,
):
    data = await state.get_data()

    amount = parse_coin_amount(
        message.text or "",
        data["website"],
        "sell",
    )

    if amount is None:
        await message.answer(
            "❌ Số xu không hợp lệ.\n"
            "Vui lòng nhập lại đúng mức tối thiểu "
            "và bước số lượng."
        )
        return

    await state.update_data(
        amount_coin=amount
    )

    await state.set_state(
        SellOrderStates.waiting_username
    )

    await message.answer(
        "👤 Nhập username tài khoản sẽ gửi xu.\n\n"
        "Ví dụ: <code>nguyenvana</code>",
        reply_markup=back_home_keyboard(),
    )


# ==========================================
# SELL ORDER - SOURCE USERNAME
# ==========================================

@router.message(SellOrderStates.waiting_username)
async def sell_enter_username(
    message: Message,
    state: FSMContext,
):
    username = (message.text or "").strip().lstrip("@")

    if not valid_username(username):
        await message.answer(
            "❌ Username không hợp lệ. Vui lòng nhập lại."
        )
        return

    await state.update_data(
        username_source=username
    )

    await state.set_state(
        SellOrderStates.waiting_bank_info
    )

    await message.answer(
        "<b>🏦 THÔNG TIN NHẬN THANH TOÁN</b>\n\n"
        "Nhập theo mẫu:\n\n"
        "<code>Ngân hàng: Vietcombank\n"
        "Số tài khoản: 0123456789\n"
        "Chủ tài khoản: NGUYEN VAN A</code>\n\n"
        "Chỉ nhập thông tin nhận tiền, "
        "không nhập mật khẩu hoặc mã OTP.",
        reply_markup=back_home_keyboard(),
    )


# ==========================================
# SELL ORDER - BANK INFO
# ==========================================

@router.message(SellOrderStates.waiting_bank_info)
async def sell_enter_bank_info(
    message: Message,
    state: FSMContext,
):
    bank_info = (message.text or "").strip()

    if len(bank_info) < 10 or len(bank_info) > 500:
        await message.answer(
            "❌ Thông tin chưa hợp lệ. "
            "Vui lòng nhập lại đầy đủ."
        )
        return

    if len(bank_info.splitlines()) < 2:
        await message.answer(
            "Vui lòng nhập ít nhất tên ngân hàng "
            "và số tài khoản."
        )
        return

    await state.update_data(
        bank_info=bank_info
    )

    await state.set_state(
        SellOrderStates.confirming
    )

    data = await state.get_data()

    await message.answer(
        "<b>📋 XÁC NHẬN ĐƠN BÁN XU</b>\n\n"
        f"🌐 Website: <b>{WEBSITE_NAMES[data['website']]}</b>\n"
        f"🪙 Số xu: <b>{format_coin(data['amount_coin'])}</b>\n"
        f"👤 Username gửi: <b>{data['username_source']}</b>\n\n"
        "<b>🏦 Thông tin nhận tiền:</b>\n"
        f"<code>{data['bank_info']}</code>\n\n"
        "Kiểm tra kỹ thông tin trước khi xác nhận.",
        reply_markup=confirm_order_keyboard(),
    )


# ==========================================
# CONFIRM ORDER - TEMPORARY GUARD
# ==========================================

@router.callback_query(F.data == "order:confirm")
async def confirm_order(
    callback: CallbackQuery,
    state: FSMContext,
):
    current = await state.get_state()

    if current not in {
        BuyOrderStates.confirming.state,
        SellOrderStates.confirming.state,
    }:
        await callback.answer(
            "Không có đơn hàng nào cần xác nhận.",
            show_alert=True,
        )
        return

    data = await state.get_data()

    # Chưa tạo đơn ở đây.
    # Việc tạo đơn sẽ được kết nối với service,
    # bảng giá và kiểm tra ví trong các file tiếp theo.

    logger.info(
        "User %s đã xác nhận thông tin đơn %s",
        callback.from_user.id,
        data.get("order_type"),
    )

    await callback.message.answer(
        "✅ Đã nhận yêu cầu xác nhận.\n\n"
        "Hệ thống đang hoàn thiện phần tính giá "
        "và tạo đơn an toàn. Đơn chưa được tạo "
        "và chưa có giao dịch tiền hoặc xu nào phát sinh."
    )

    await state.clear()
    await callback.answer()


# ==========================================
# NAVIGATION
# ==========================================

@router.callback_query(F.data == "nav:back")
async def order_back(
    callback: CallbackQuery,
    state: FSMContext,
):
    current = await state.get_state()

    if current is None:
        await callback.answer(
            "Không có bước nào để quay lại.",
            show_alert=True,
        )
        return

    data = await state.get_data()

    if data.get("order_type") == "buy":
        if current == BuyOrderStates.waiting_username.state:
            await state.set_state(
                BuyOrderStates.waiting_amount
            )
            text = "Vui lòng nhập lại số xu muốn mua."

        elif current == BuyOrderStates.waiting_payment_method.state:
            await state.set_state(
                BuyOrderStates.waiting_username
            )
            text = "Vui lòng nhập username người nhận xu."

        elif current == BuyOrderStates.confirming.state:
            await state.set_state(
                BuyOrderStates.waiting_payment_method
            )
            await callback.message.answer(
                "Chọn lại phương thức thanh toán:",
                reply_markup=payment_method_keyboard(),
            )
            await callback.answer()
            return

        else:
            await state.clear()
            await callback.message.answer(
                "Bạn đã quay lại menu chính. "
                "Hãy chọn Mua xu hoặc Bán xu."
            )
            await callback.answer()
            return

    else:
        if current == SellOrderStates.waiting_username.state:
            await state.set_state(
                SellOrderStates.waiting_amount
            )
            text = "Vui lòng nhập lại số xu muốn bán."

        elif current == SellOrderStates.waiting_bank_info.state:
            await state.set_state(
                SellOrderStates.waiting_username
            )
            text = "Vui lòng nhập username gửi xu."

        elif current == SellOrderStates.confirming.state:
            await state.set_state(
                SellOrderStates.waiting_bank_info
            )
            text = "Vui lòng nhập lại thông tin ngân hàng."

        else:
            await state.clear()
            await callback.message.answer(
                "Bạn đã quay lại menu chính."
            )
            await callback.answer()
            return

    await callback.message.answer(
        text,
        reply_markup=back_home_keyboard(),
    )

    await callback.answer()


@router.callback_query(F.data == "nav:cancel")
async def cancel_order(
    callback: CallbackQuery,
    state: FSMContext,
):
    await state.clear()

    await callback.message.answer(
        "❌ Đã hủy quá trình nhập đơn.\n"
        "Chưa có giao dịch tiền hoặc xu nào được thực hiện."
    )

    await callback.answer()
