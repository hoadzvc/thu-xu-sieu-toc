
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import AsyncSessionLocal
from app.models import ExchangeTransaction


class ExchangeTransactionError(Exception):
    """Lỗi lưu giao dịch website."""


async def save_verified_exchange(
    *,
    order_id: int,
    website: str,
    website_transaction_id: str,
    transaction_type: str,
    coin_amount: int,
    sender_username: str,
    receiver_username: str,
    raw_reference: str | None = None,
):
    """
    Lưu giao dịch website đã được adapter xác minh.

    Không gọi hàm này chỉ vì website trả về thông báo thành công.
    Phải xác minh giao dịch trong lịch sử website trước.
    """

    if order_id <= 0:
        raise ExchangeTransactionError("Mã đơn hàng không hợp lệ.")

    if website not in {"nvc", "xsmm"}:
        raise ExchangeTransactionError("Website không hợp lệ.")

    if transaction_type not in {"buy", "sell"}:
        raise ExchangeTransactionError("Loại giao dịch không hợp lệ.")

    if (
        isinstance(coin_amount, bool)
        or not isinstance(coin_amount, int)
        or coin_amount <= 0
    ):
        raise ExchangeTransactionError("Số xu không hợp lệ.")

    website_transaction_id = str(website_transaction_id).strip()

    if not website_transaction_id:
        raise ExchangeTransactionError("Thiếu mã giao dịch website.")

    sender_username = str(sender_username).strip().lstrip("@")
    receiver_username = str(receiver_username).strip().lstrip("@")

    if not sender_username or not receiver_username:
        raise ExchangeTransactionError(
            "Thiếu username người gửi hoặc người nhận."
        )

    async with AsyncSessionLocal() as session:
        async with session.begin():

            # Kiểm tra mã giao dịch đã được sử dụng chưa.
            existing_result = await session.execute(
                select(ExchangeTransaction).where(
                    ExchangeTransaction.website == website,
                    ExchangeTransaction.website_transaction_id
                    == website_transaction_id,
                )
            )

            existing = existing_result.scalar_one_or_none()

            if existing is not None:
                # Chỉ coi là giao dịch trùng hợp lệ khi khớp
                # toàn bộ thông tin quan trọng.
                same_transaction = (
                    existing.order_id == order_id
                    and existing.amount_coin == coin_amount
                    and existing.sender_username.lower()
                    == sender_username.lower()
                    and existing.receiver_username.lower()
                    == receiver_username.lower()
                    and existing.verified is True
                )

                if not same_transaction:
                    raise ExchangeTransactionError(
                        "Mã giao dịch website đã được sử dụng "
                        "cho một giao dịch khác."
                    )

                return existing

            transaction = ExchangeTransaction(
                order_id=order_id,
                website=website,
                website_transaction_id=website_transaction_id,
                sender_username=sender_username,
                receiver_username=receiver_username,
                amount_coin=coin_amount,
                status="verified",
                verified=True,
                raw_reference=raw_reference,
            )

            session.add(transaction)

            try:
                await session.flush()
            except IntegrityError as exc:
                raise ExchangeTransactionError(
                    "Giao dịch website bị trùng mã."
                ) from exc

            return transaction


async def get_exchange_transaction(
    website: str,
    website_transaction_id: str,
):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExchangeTransaction).where(
                ExchangeTransaction.website == website,
                ExchangeTransaction.website_transaction_id
                == str(website_transaction_id).strip(),
            )
        )

        return result.scalar_one_or_none()


async def get_order_exchange_transactions(order_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExchangeTransaction)
            .where(ExchangeTransaction.order_id == order_id)
            .order_by(ExchangeTransaction.created_at.asc())
        )

        return list(result.scalars().all())


async def verify_order_exchange(
    order_id: int,
    expected_coin_amount: int,
) -> bool:
    """
    Kiểm tra tổng số xu đã xác minh của đơn.

    Chỉ trả về True khi tổng số xu đã xác minh
    lớn hơn hoặc bằng số xu đơn hàng.
    """

    if expected_coin_amount <= 0:
        return False

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ExchangeTransaction).where(
                ExchangeTransaction.order_id == order_id,
                ExchangeTransaction.verified.is_(True),
            )
        )

        transactions = result.scalars().all()

        total_coin = sum(
            int(transaction.amount_coin)
            for transaction in transactions
        )

        return total_coin >= expected_coin_amount
