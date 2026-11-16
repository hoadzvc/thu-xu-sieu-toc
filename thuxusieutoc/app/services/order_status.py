
from decimal import Decimal

from sqlalchemy import select, func

from app.db import AsyncSessionLocal
from app.models import Order, ExchangeTransaction
from app.services.wallet import release_reserved_wallet_in_session
from app.services.wallet import capture_reserved_wallet_in_session


class OrderStatusError(Exception):
    """Lỗi chuyển trạng thái đơn hàng."""


STATUSES = {
    "pending",
    "pending_payment",
    "pending_processing",
    "paid",
    "processing",
    "waiting_transfer",
    "waiting_admin",
    "completed",
    "cancelled",
    "rejected",
    "failed",
}

FINAL_STATUSES = {
    "completed",
    "cancelled",
    "rejected",
    "failed",
}

# Chỉ cho phép chuyển trạng thái trung gian ở hàm chung.
# Các trạng thái kết thúc phải đi qua hàm nghiệp vụ riêng.
TRANSITIONS = {
    "pending": {
        "waiting_transfer",
        "waiting_admin",
    },
    "pending_payment": {
        "paid",
    },
    "pending_processing": {
        "processing",
    },
    "paid": {
        "processing",
    },
    "processing": {
        "waiting_transfer",
        "waiting_admin",
    },
    "waiting_transfer": {
        "waiting_admin",
        "processing",
    },
    "waiting_admin": set(),
}


async def _get_order_for_update(session, order_id: int):
    result = await session.execute(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
    )

    order = result.scalar_one_or_none()

    if order is None:
        raise OrderStatusError("Không tìm thấy đơn hàng.")

    return order


async def _get_verified_coin_amount(session, order_id: int) -> int:
    """
    Tổng số xu của các giao dịch website đã xác minh
    và được gắn với đơn hàng này.
    """

    result = await session.execute(
        select(
            func.coalesce(
                func.sum(ExchangeTransaction.amount_coin),
                0,
            )
        ).where(
            ExchangeTransaction.order_id == order_id,
            ExchangeTransaction.verified.is_(True),
        )
    )

    return int(result.scalar_one() or 0)


async def get_order(order_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Order).where(Order.id == order_id)
        )
        return result.scalar_one_or_none()


async def change_order_status(
    order_id: int,
    new_status: str,
    *,
    expected_status: str | None = None,
    admin_note: str | None = None,
):
    """
    Chỉ cập nhật trạng thái trung gian.

    Không dùng hàm này để hoàn tất, hủy hoặc từ chối đơn.
    Những thao tác đó phải đi qua các hàm nghiệp vụ riêng.
    """

    if new_status not in STATUSES:
        raise OrderStatusError("Trạng thái mới không hợp lệ.")

    if new_status in FINAL_STATUSES:
        raise OrderStatusError(
            "Hãy sử dụng hàm hoàn tất, hủy hoặc từ chối đơn tương ứng."
        )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            order = await _get_order_for_update(session, order_id)

            current_status = order.status

            if expected_status and current_status != expected_status:
                raise OrderStatusError(
                    f"Trạng thái đơn đã thay đổi: {current_status}"
                )

            if current_status in FINAL_STATUSES:
                raise OrderStatusError(
                    "Đơn hàng đã kết thúc, không thể thay đổi."
                )

            allowed = TRANSITIONS.get(current_status, set())

            if new_status not in allowed:
                raise OrderStatusError(
                    f"Không thể chuyển từ {current_status} "
                    f"sang {new_status}."
                )

            order.status = new_status

            if admin_note is not None:
                order.admin_note = admin_note[:2000]

            await session.flush()

            return {
                "order_id": order.id,
                "order_code": order.order_code,
                "old_status": current_status,
                "new_status": new_status,
            }


async def mark_order_completed(
    order_id: int,
    *,
    admin_note: str | None = None,
):
    """
    Hoàn tất ĐƠN MUA.

    Điều kiện:
    - Đơn đang chờ Admin duyệt.
    - Đã xác minh giao đủ số xu.
    - Nếu thanh toán QR: payment_status phải là paid.
    - Nếu thanh toán ví: phải có tiền đang khóa.
    - Capture tiền ví và cập nhật đơn trong cùng transaction.
    """

    async with AsyncSessionLocal() as session:
        async with session.begin():
            order = await _get_order_for_update(session, order_id)

            if order.status != "waiting_admin":
                raise OrderStatusError(
                    "Đơn mua chưa ở trạng thái chờ Admin duyệt."
                )

            if order.order_type != "buy":
                raise OrderStatusError(
                    "Đây không phải đơn mua. "
                    "Đơn bán phải dùng mark_sell_order_paid()."
                )

            verified_amount = await _get_verified_coin_amount(
                session,
                order.id,
            )

            if verified_amount < int(order.amount_coin):
                raise OrderStatusError(
                    "Chưa xác minh giao đủ số xu cho khách."
                )

            if order.payment_method == "qr":
                if order.payment_status != "paid":
                    raise OrderStatusError(
                        "Đơn QR chưa được xác minh thanh toán."
                    )

            elif order.payment_method == "wallet":
                if not order.wallet_reserved:
                    raise OrderStatusError(
                        "Đơn không có khoản tiền ví đang khóa."
                    )

                await capture_reserved_wallet_in_session(
                    session,
                    order.user_id,
                    Decimal(str(order.total_amount)),
                    idempotency_key=f"order:{order.id}:capture",
                    description=f"Thanh toán đơn {order.order_code}",
                )

                order.wallet_reserved = False
                order.payment_status = "paid"

            else:
                raise OrderStatusError(
                    "Phương thức thanh toán của đơn không hợp lệ."
                )

            old_status = order.status
            order.status = "completed"

            if admin_note is not None:
                order.admin_note = admin_note[:2000]

            order.completed_at = func.now()

            await session.flush()

            return {
                "order_id": order.id,
                "order_code": order.order_code,
                "old_status": old_status,
                "new_status": "completed",
            }


async def mark_sell_order_paid(
    order_id: int,
    *,
    admin_note: str | None = None,
):
    """
    Hoàn tất ĐƠN BÁN sau khi Admin thực sự chuyển khoản cho khách.

    Hàm này chỉ được gọi sau thao tác chuyển khoản thủ công
    và khi Admin bấm nút 'Đã thanh toán'.
    """

    async with AsyncSessionLocal() as session:
        async with session.begin():
            order = await _get_order_for_update(session, order_id)

            if order.order_type != "sell":
                raise OrderStatusError(
                    "Đây không phải đơn bán."
                )

            if order.status != "waiting_admin":
                raise OrderStatusError(
                    "Đơn bán chưa ở trạng thái chờ Admin duyệt."
                )

            verified_amount = await _get_verified_coin_amount(
                session,
                order.id,
            )

            if verified_amount < int(order.amount_coin):
                raise OrderStatusError(
                    "Chưa xác minh nhận đủ xu từ khách."
                )

            if order.payout_status == "paid":
                raise OrderStatusError(
                    "Đơn này đã được đánh dấu thanh toán."
                )

            old_status = order.status

            order.payout_status = "paid"
            order.status = "completed"
            order.completed_at = func.now()

            if admin_note is not None:
                order.admin_note = admin_note[:2000]

            await session.flush()

            return {
                "order_id": order.id,
                "order_code": order.order_code,
                "old_status": old_status,
                "new_status": "completed",
                "payout_status": "paid",
            }


async def _finish_unsuccessful_order(
    order_id: int,
    *,
    final_status: str,
    reason: str,
):
    """
    Hủy, từ chối hoặc đánh dấu thất bại.

    Nếu là đơn mua bằng ví:
    - Chỉ mở khóa khi chưa thử giao xu.
    - Không có giao dịch xu đã xác minh.
    - Tiền và trạng thái đơn được cập nhật cùng transaction.
    """

    if final_status not in {"cancelled", "rejected", "failed"}:
        raise OrderStatusError("Trạng thái kết thúc không hợp lệ.")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            order = await _get_order_for_update(session, order_id)

            if order.status in FINAL_STATUSES:
                raise OrderStatusError(
                    "Đơn hàng đã kết thúc."
                )

            verified_amount = await _get_verified_coin_amount(
                session,
                order.id,
            )

            if order.transfer_attempted:
                raise OrderStatusError(
                    "Đơn đã thử giao dịch trên website. "
                    "Cần đối soát trước khi hủy hoặc hoàn tiền."
                )

            if verified_amount > 0:
                raise OrderStatusError(
                    "Đơn đã có giao dịch xu được xác minh. "
                    "Không thể tự động hủy hoặc mở khóa tiền."
                )

            if order.wallet_reserved:
                if order.order_type != "buy":
                    raise OrderStatusError(
                        "Đơn không phải đơn mua nhưng lại có tiền ví đang khóa."
                    )

                await release_reserved_wallet_in_session(
                    session,
                    order.user_id,
                    Decimal(str(order.total_amount)),
                    idempotency_key=f"order:{order.id}:release",
                    description=f"Mở khóa tiền đơn {order.order_code}",
                )

                order.wallet_reserved = False

            old_status = order.status
            order.status = final_status
            order.admin_note = reason[:2000]

            await session.flush()

            return {
                "order_id": order.id,
                "order_code": order.order_code,
                "old_status": old_status,
                "new_status": final_status,
            }


async def cancel_order(
    order_id: int,
    reason: str = "Đơn hàng bị hủy",
):
    return await _finish_unsuccessful_order(
        order_id,
        final_status="cancelled",
        reason=reason,
    )


async def reject_order(
    order_id: int,
    reason: str,
):
    return await _finish_unsuccessful_order(
        order_id,
        final_status="rejected",
        reason=reason,
    )


async def fail_order(
    order_id: int,
    reason: str,
):
    return await _finish_unsuccessful_order(
        order_id,
        final_status="failed",
        reason=reason,
    )
