
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models import Wallet, WalletTransaction


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class WalletError(Exception):
    """Lỗi nghiệp vụ liên quan đến ví."""


class InsufficientBalance(WalletError):
    """Số dư khả dụng không đủ."""


class WalletNotFound(WalletError):
    """Không tìm thấy ví."""


class DuplicateTransaction(WalletError):
    """Giao dịch đã được xử lý hoặc mã giao dịch bị sử dụng sai."""


def money(value: Any) -> Decimal:
    """Chuẩn hóa số tiền về Decimal có 2 chữ số thập phân."""
    try:
        amount = Decimal(str(value)).quantize(CENT)
    except (InvalidOperation, ValueError, TypeError):
        raise WalletError("Số tiền không hợp lệ.")

    if not amount.is_finite() or amount <= ZERO:
        raise WalletError("Số tiền phải lớn hơn 0.")

    return amount


def _validate_key(idempotency_key: str) -> str:
    if not isinstance(idempotency_key, str):
        raise WalletError("Mã chống giao dịch trùng không hợp lệ.")

    key = idempotency_key.strip()

    if not key or len(key) > 255:
        raise WalletError("Mã chống giao dịch trùng không hợp lệ.")

    return key


async def _get_wallet(
    session: AsyncSession,
    user_id: int,
) -> Wallet:
    result = await session.execute(
        select(Wallet)
        .where(Wallet.user_id == user_id)
        .with_for_update()
    )

    wallet = result.scalar_one_or_none()

    if wallet is None:
        raise WalletNotFound("Khách hàng chưa có ví.")

    return wallet


async def _get_existing_transaction(
    session: AsyncSession,
    *,
    user_id: int,
    transaction_type: str,
    amount: Decimal,
    idempotency_key: str,
) -> WalletTransaction | None:
    result = await session.execute(
        select(WalletTransaction).where(
            WalletTransaction.idempotency_key == idempotency_key
        )
    )

    transaction = result.scalar_one_or_none()

    if transaction is None:
        return None

    # Không cho phép dùng lại một key cho giao dịch khác.
    existing_amount = Decimal(str(transaction.amount))

    if (
        transaction.user_id != user_id
        or transaction.transaction_type != transaction_type
        or existing_amount != amount
    ):
        raise DuplicateTransaction(
            "Mã giao dịch đã được sử dụng cho một giao dịch khác."
        )

    return transaction


async def _record_transaction(
    session: AsyncSession,
    *,
    user_id: int,
    transaction_type: str,
    amount: Decimal,
    balance_after: Decimal,
    idempotency_key: str,
    description: str,
) -> None:
    session.add(
        WalletTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_after=balance_after,
            idempotency_key=idempotency_key,
            description=description,
        )
    )

    # Phát hiện lỗi unique ngay trong transaction hiện tại.
    await session.flush()


# =========================================================
# CÁC HÀM DÙNG TRONG TRANSACTION CÓ SẴN
# FILE 16 sẽ sử dụng các hàm này để cập nhật ví và đơn
# trong cùng một database transaction.
# =========================================================

async def reserve_wallet_in_session(
    session: AsyncSession,
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Khóa tiền chờ xử lý đơn hàng",
) -> Decimal:
    value = money(amount)
    key = _validate_key(idempotency_key)

    existing = await _get_existing_transaction(
        session,
        user_id=user_id,
        transaction_type="reserve",
        amount=value,
        idempotency_key=key,
    )

    wallet = await _get_wallet(session, user_id)

    balance = Decimal(str(wallet.balance))
    locked = Decimal(str(wallet.locked_balance))

    if existing:
        return balance - locked

    available = balance - locked

    if available < value:
        raise InsufficientBalance(
            f"Số dư khả dụng không đủ. Hiện có: {available}"
        )

    wallet.locked_balance = locked + value

    await _record_transaction(
        session,
        user_id=user_id,
        transaction_type="reserve",
        amount=value,
        balance_after=balance,
        idempotency_key=key,
        description=description,
    )

    return available - value


async def capture_reserved_wallet_in_session(
    session: AsyncSession,
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Thanh toán đơn hàng thành công",
) -> Decimal:
    value = money(amount)
    key = _validate_key(idempotency_key)

    existing = await _get_existing_transaction(
        session,
        user_id=user_id,
        transaction_type="capture",
        amount=-value,
        idempotency_key=key,
    )

    wallet = await _get_wallet(session, user_id)

    balance = Decimal(str(wallet.balance))
    locked = Decimal(str(wallet.locked_balance))

    if existing:
        return balance

    if locked < value:
        raise WalletError("Tiền đang khóa không đủ để thanh toán.")

    if balance < value:
        raise WalletError("Số dư ví không hợp lệ.")

    wallet.balance = balance - value
    wallet.locked_balance = locked - value

    await _record_transaction(
        session,
        user_id=user_id,
        transaction_type="capture",
        amount=-value,
        balance_after=wallet.balance,
        idempotency_key=key,
        description=description,
    )

    return Decimal(str(wallet.balance))


async def release_reserved_wallet_in_session(
    session: AsyncSession,
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Mở khóa tiền do đơn hàng thất bại",
) -> Decimal:
    value = money(amount)
    key = _validate_key(idempotency_key)

    existing = await _get_existing_transaction(
        session,
        user_id=user_id,
        transaction_type="release",
        amount=value,
        idempotency_key=key,
    )

    wallet = await _get_wallet(session, user_id)

    balance = Decimal(str(wallet.balance))
    locked = Decimal(str(wallet.locked_balance))

    if existing:
        return balance - locked

    if locked < value:
        raise WalletError("Số tiền đang khóa không đủ để mở khóa.")

    wallet.locked_balance = locked - value

    await _record_transaction(
        session,
        user_id=user_id,
        transaction_type="release",
        amount=value,
        balance_after=balance,
        idempotency_key=key,
        description=description,
    )

    return balance - (locked - value)


async def deposit_wallet_in_session(
    session: AsyncSession,
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Nạp tiền vào ví",
) -> Decimal:
    value = money(amount)
    key = _validate_key(idempotency_key)

    existing = await _get_existing_transaction(
        session,
        user_id=user_id,
        transaction_type="deposit",
        amount=value,
        idempotency_key=key,
    )

    wallet = await _get_wallet(session, user_id)

    if existing:
        return Decimal(str(wallet.balance))

    wallet.balance = Decimal(str(wallet.balance)) + value

    await _record_transaction(
        session,
        user_id=user_id,
        transaction_type="deposit",
        amount=value,
        balance_after=wallet.balance,
        idempotency_key=key,
        description=description,
    )

    return Decimal(str(wallet.balance))


# =========================================================
# CÁC HÀM GỌI ĐỘC LẬP
# Tự tạo session và transaction.
# =========================================================

async def get_wallet_summary(user_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Wallet).where(Wallet.user_id == user_id)
        )

        wallet = result.scalar_one_or_none()

        if wallet is None:
            return {
                "balance": ZERO,
                "locked_balance": ZERO,
                "available_balance": ZERO,
            }

        balance = Decimal(str(wallet.balance))
        locked = Decimal(str(wallet.locked_balance))

        return {
            "balance": balance,
            "locked_balance": locked,
            "available_balance": balance - locked,
        }


async def reserve_wallet(
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Khóa tiền chờ xử lý đơn hàng",
) -> Decimal:
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                return await reserve_wallet_in_session(
                    session,
                    user_id,
                    amount,
                    idempotency_key=idempotency_key,
                    description=description,
                )
    except IntegrityError as exc:
        raise DuplicateTransaction(
            "Yêu cầu khóa tiền đã bị trùng."
        ) from exc


async def capture_reserved_wallet(
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Thanh toán đơn hàng thành công",
) -> Decimal:
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                return await capture_reserved_wallet_in_session(
                    session,
                    user_id,
                    amount,
                    idempotency_key=idempotency_key,
                    description=description,
                )
    except IntegrityError as exc:
        raise DuplicateTransaction(
            "Thanh toán ví đã bị trùng."
        ) from exc


async def release_reserved_wallet(
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Mở khóa tiền do đơn hàng thất bại",
) -> Decimal:
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                return await release_reserved_wallet_in_session(
                    session,
                    user_id,
                    amount,
                    idempotency_key=idempotency_key,
                    description=description,
                )
    except IntegrityError as exc:
        raise DuplicateTransaction(
            "Yêu cầu mở khóa tiền đã bị trùng."
        ) from exc


async def deposit_wallet(
    user_id: int,
    amount,
    *,
    idempotency_key: str,
    description: str = "Nạp tiền vào ví",
) -> Decimal:
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                return await deposit_wallet_in_session(
                    session,
                    user_id,
                    amount,
                    idempotency_key=idempotency_key,
                    description=description,
                )
    except IntegrityError as exc:
        raise DuplicateTransaction(
            "Giao dịch nạp tiền đã bị trùng."
        ) from exc
