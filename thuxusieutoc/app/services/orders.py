
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Order
from app.services.pricing import (
    calculate_nvc_price,
    calculate_xsmm_price,
)
from app.services.wallet import (
    reserve_wallet,
    InsufficientBalance,
    WalletError,
)


class OrderError(Exception):
    """Lỗi nghiệp vụ đơn hàng."""


WEBSITES = {"nvc", "xsmm"}
ORDER_TYPES = {"buy", "sell"}
PAYMENT_METHODS = {"wallet", "qr"}


def validate_order_input(
    order_type: str,
    website: str,
    coin_amount: int,
    payment_method: str | None = None,
    bank_info: str | None = None,
):
    if order_type not in ORDER_TYPES:
        raise OrderError("Loại đơn hàng không hợp lệ.")

    if website not in WEBSITES:
        raise OrderError("Website không hợp lệ.")

    if (
        isinstance(coin_amount, bool)
        or not isinstance(coin_amount, int)
        or coin_amount <= 0
    ):
        raise OrderError("Số xu phải là số nguyên dương.")

    if order_type == "buy":
        if payment_method not in PAYMENT_METHODS:
            raise OrderError("Phương thức thanh toán không hợp lệ.")

    if order_type == "sell":
        if payment_method is not None:
            raise OrderError(
                "Đơn bán không sử dụng phương thức thanh toán mua."
            )

        if not bank_info or not bank_info.strip():
            raise OrderError(
                "Đơn bán cần thông tin ngân hàng nhận tiền."
            )


def calculate_order_price(
    order_type: str,
    website: str,
    coin_amount: int,
) -> Decimal:
    """
    Tính giá đơn hàng bằng VND.
    """

    if website == "nvc":
        result = calculate_nvc_price(
            order_type,
            coin_amount,
        )
    else:
        result = calculate_xsmm_price(
            order_type,
            coin_amount,
        )

    try:
        total = Decimal(str(result.total_price)).quantize(
            Decimal("0.01")
        )
    except Exception as exc:
        raise OrderError(
            "Không thể tính giá đơn hàng."
        ) from exc

    if not total.is_finite() or total <= 0:
        raise OrderError("Giá đơn hàng không hợp lệ.")

    return total


async def create_order(
    *,
    user_id: int,
    order_type: str,
    website: str,
    coin_amount: int,
    username: str,
    payment_method: str | None = None,
    bank_info: str | None = None,
) -> Order:
    """
    Tạo đơn mua hoặc bán.

    Mua bằng ví:
        Khóa tiền, chưa trừ tiền thực tế.

    Mua bằng QR:
        Chờ SePay xác minh thanh toán.

    Bán:
        Chờ xác minh xu nhận được, sau đó Admin duyệt
        và thực hiện thanh toán cho khách.
    """

    validate_order_input(
        order_type=order_type,
        website=website,
        coin_amount=coin_amount,
        payment_method=payment_method,
        bank_info=bank_info,
    )

    username = str(username).strip().lstrip("@")

    if not username:
        raise OrderError("Username không được để trống.")

    if len(username) > 100:
        raise OrderError("Username quá dài.")

    if bank_info is not None:
        bank_info = bank_info.strip()

        if len(bank_info) > 2000:
            raise OrderError(
                "Thông tin ngân hàng quá dài."
            )

    total_price = calculate_order_price(
        order_type,
        website,
        coin_amount,
    )

    order_code = f"XU{uuid4().hex[:12].upper()}"

    # Xác định trạng thái ban đầu.
    if order_type == "buy" and payment_method == "qr":
        initial_status = "pending_payment"
        initial_payment_status = "unpaid"
        initial_payout_status = "not_required"

    elif order_type == "buy" and payment_method == "wallet":
        initial_status = "pending"
        initial_payment_status = "pending"
        initial_payout_status = "not_required"

    else:
        initial_status = "pending"
        initial_payment_status = "unpaid"
        initial_payout_status = "pending"

    # Phân biệt username người nhận và người gửi.
    username_target = (
        username if order_type == "buy" else None
    )

    username_source = (
        username if order_type == "sell" else None
    )

    # Tạo đơn hàng.
    async with AsyncSessionLocal() as session:
        async with session.begin():
            order = Order(
                order_code=order_code,
                user_id=user_id,
                order_type=order_type,
                website=website,
                amount_coin=coin_amount,
                unit_price=(
                    total_price / Decimal(coin_amount)
                ).quantize(Decimal("0.0001")),
                total_amount=total_price,
                fee_amount=Decimal("0"),
                username_target=username_target,
                username_source=username_source,
                bank_info=bank_info,
                payment_method=payment_method,
                status=initial_status,
                payment_status=initial_payment_status,
                payout_status=initial_payout_status,
                transfer_attempted=False,
                wallet_reserved=False,
            )

            session.add(order)
            await session.flush()

            order_id = order.id

    # Khóa tiền ví cho đơn mua.
    if order_type == "buy" and payment_method == "wallet":
        try:
            await reserve_wallet(
                user_id,
                total_price,
                idempotency_key=f"order:{order_id}:reserve",
                description=f"Khóa tiền cho đơn {order_code}",
            )

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Order).where(
                            Order.id == order_id
                        )
                    )

                    saved_order = result.scalar_one()

                    saved_order.wallet_reserved = True
                    saved_order.status = "pending_processing"

        except (InsufficientBalance, WalletError):
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    result = await session.execute(
                        select(Order).where(
                            Order.id == order_id
                        )
                    )

                    saved_order = result.scalar_one_or_none()

                    if saved_order:
                        saved_order.status = "cancelled"
                        saved_order.payment_status = "unpaid"

            raise

    # Trả về đơn đã lưu.
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Order).where(
                Order.id == order_id
            )
        )

        saved_order = result.scalar_one_or_none()

        if saved_order is None:
            raise OrderError(
                "Không tìm thấy đơn vừa tạo."
            )

        return saved_order


async def get_order_by_code(order_code: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Order).where(
                Order.order_code == order_code
            )
        )

        return result.scalar_one_or_none()


async def get_user_orders(
    user_id: int,
    limit: int = 10,
):
    limit = max(1, min(limit, 50))

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.id.desc())
            .limit(limit)
        )

        return list(result.scalars().all())
