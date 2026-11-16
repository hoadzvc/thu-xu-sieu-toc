
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )

    username: Mapped[str | None] = mapped_column(String(100))
    full_name: Mapped[str | None] = mapped_column(String(200))

    language: Mapped[str] = mapped_column(
        String(10), default="vi", nullable=False
    )

    is_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    wallet: Mapped["Wallet | None"] = relationship(
        back_populates="user", uselist=False
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="user"
    )


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )

    locked_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="wallet")

    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="ck_wallet_balance_nonnegative",
        ),
        CheckConstraint(
            "locked_balance >= 0",
            name="ck_wallet_locked_nonnegative",
        ),
        CheckConstraint(
            "locked_balance <= balance",
            name="ck_wallet_locked_not_above_balance",
        ),
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True, index=True
    )

    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )

    description: Mapped[str] = mapped_column(
        String(500), default="", nullable=False
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(150), unique=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    order_code: Mapped[str] = mapped_column(
        String(40), unique=True, index=True, nullable=False
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )

    order_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    website: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    amount_coin: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )

    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )

    username_target: Mapped[str | None] = mapped_column(
        String(100)
    )

    username_source: Mapped[str | None] = mapped_column(
        String(100)
    )

    payment_method: Mapped[str | None] = mapped_column(
        String(20)
    )

    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False, index=True
    )

    payment_status: Mapped[str] = mapped_column(
        String(30), default="unpaid", nullable=False, index=True
    )

    payout_status: Mapped[str] = mapped_column(
        String(30), default="not_required", nullable=False
    )

    wallet_reserved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    transfer_attempted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    admin_note: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    user: Mapped["User"] = relationship(back_populates="orders")

    __table_args__ = (
        CheckConstraint(
            "amount_coin > 0",
            name="ck_order_coin_positive",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_order_total_nonnegative",
        ),
        CheckConstraint(
            "fee_amount >= 0",
            name="ck_order_fee_nonnegative",
        ),
        Index(
            "ix_orders_user_created",
            "user_id",
            "created_at",
        ),
    )


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(
        String(30), default="sepay", nullable=False
    )

    provider_transaction_id: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True, index=True
    )

    bank_account: Mapped[str | None] = mapped_column(
        String(100)
    )

    transfer_code: Mapped[str | None] = mapped_column(
        String(100), index=True
    )

    content: Mapped[str | None] = mapped_column(Text)

    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )

    transfer_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="received", nullable=False
    )

    # Lưu payload webhook dạng JSON để phục vụ đối soát.
    # Không lưu API key, mật khẩu hoặc thông tin xác thực vào đây.
    raw_payload: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_transaction_id",
            name="uq_payment_provider_transaction",
        ),
    )


class ExchangeTransaction(Base):
    __tablename__ = "exchange_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )

    website: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    website_transaction_id: Mapped[str | None] = mapped_column(
        String(150)
    )

    sender_username: Mapped[str | None] = mapped_column(
        String(100)
    )

    receiver_username: Mapped[str | None] = mapped_column(
        String(100)
    )

    amount_coin: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False
    )

    verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    raw_reference: Mapped[str | None] = mapped_column(Text)

    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "website",
            "website_transaction_id",
            name="uq_exchange_website_transaction",
        ),
    )


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    event_id: Mapped[str] = mapped_column(
        String(150), nullable=False
    )

    payload_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_id",
            name="uq_processed_webhook_event",
        ),
    )
