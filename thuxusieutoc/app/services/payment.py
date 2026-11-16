
import hashlib
import json
import logging
import re

from decimal import Decimal, InvalidOperation

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import (
    Order,
    PaymentTransaction,
    ProcessedWebhook,
)

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


class PaymentMismatch(PaymentError):
    pass


class DuplicatePayment(PaymentError):
    pass


def normalize_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(
            Decimal("0.01")
        )
    except (InvalidOperation, TypeError, ValueError):
        raise PaymentError("Số tiền thanh toán không hợp lệ.")

    if not amount.is_finite() or amount <= 0:
        raise PaymentError("Số tiền phải lớn hơn 0.")

    return amount


def normalize_reference(value: str | None) -> str | None:
    if not value:
        return None

    normalized = re.sub(
        r"[^A-Z0-9]",
        "",
        str(value).upper(),
    )

    # Mã đơn nội bộ có thể bắt đầu bằng XU.
    # Mã chuyển khoản được tạo bằng cách thêm XU phía trước.
    match = re.search(
        r"XU[A-Z0-9]{6,40}",
        normalized,
    )

    return match.group(0) if match else None


def create_payment_reference(order_code: str) -> str:
    clean_code = re.sub(
        r"[^A-Z0-9]",
        "",
        str(order_code).upper(),
    )

    if not clean_code:
        raise PaymentError("Mã đơn không hợp lệ.")

    return f"XU{clean_code}"


def extract_order_reference(
    content: str | None,
    code: str | None = None,
) -> str | None:
    """
    Ưu tiên mã đơn trong trường code.
    Nếu không có thì tìm trong content.
    """

    reference = normalize_reference(code)

    if reference:
        return reference

    return normalize_reference(content)


def _payload_hash(payload: dict | None) -> str:
    """
    Tạo SHA256 từ payload để lưu ProcessedWebhook.
    """

    serialized = json.dumps(
        payload or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


async def create_qr_payment(
    *,
    order_id: int,
    sepay_qr_base_url: str,
    bank_account: str,
    bank_name: str,
):
    """
    Chuẩn bị thông tin tạo QR.

    Hàm này chưa tự tạo QR động.
    URL QR cần được tích hợp theo cấu hình chính thức.
    """

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Order).where(Order.id == order_id)
        )

        order = result.scalar_one_or_none()

        if order is None:
            raise PaymentError("Không tìm thấy đơn hàng.")

        if (
            order.order_type != "buy"
            or order.payment_method != "qr"
            or order.status != "pending_payment"
            or order.payment_status != "unpaid"
        ):
            raise PaymentError(
                "Đơn hàng không đủ điều kiện thanh toán QR."
            )

        reference = create_payment_reference(
            order.order_code
        )

        amount = normalize_amount(order.total_amount)

        return {
            "order_id": order.id,
            "order_code": order.order_code,
            "reference": reference,
            "amount": str(amount),
            "bank_account": bank_account,
            "bank_name": bank_name,
            "qr_base_url": sepay_qr_base_url,
        }


async def _find_order_by_reference(
    session,
    reference: str,
):
    """
    Tìm đơn theo mã nội bộ chính xác.

    Ví dụ:
    order_code = XUABC123456
    payment_reference = XUXUABC123456

    Sau khi bỏ tiền tố XU của mã thanh toán,
    ta tìm đúng order_code.
    """

    if not reference.startswith("XU"):
        return None

    order_code = reference[2:]

    result = await session.execute(
        select(Order).where(
            Order.order_code == order_code
        )
    )

    return result.scalar_one_or_none()


async def _record_reconciliation(
    session,
    *,
    event_id: str,
    transaction_id: str,
    amount: Decimal,
    content: str,
    reason: str,
    raw_payload: dict | None,
):
    """
    Ghi nhận giao dịch cần Admin đối soát.

    Không xác nhận đơn.
    Không giao xu.
    """

    payload = raw_payload or {}

    session.add(
        PaymentTransaction(
            order_id=None,
            provider="sepay",
            provider_transaction_id=transaction_id,
            bank_account=str(
                payload.get("accountNumber") or ""
            ),
            transfer_code=str(
                payload.get("code") or ""
            ),
            content=content,
            amount=amount,
            transfer_type="in",
            status="reconciliation",
            raw_payload={
                "event_id": event_id,
                "content": content,
                "reason": reason,
                "payload": payload,
            },
        )
    )

    session.add(
        ProcessedWebhook(
            provider="sepay",
            event_id=event_id,
            payload_hash=_payload_hash(payload),
        )
    )


async def process_sepay_webhook(
    *,
    event_id: str,
    transaction_id: str,
    content: str,
    amount,
    direction: str,
    raw_payload: dict | None = None,
    code: str | None = None,
):
    """
    Xử lý giao dịch SePay đã được xác thực ở FILE 20.

    Quy tắc:
    - Chỉ xử lý giao dịch tiền vào.
    - Mã đơn phải khớp chính xác.
    - Số tiền phải khớp tuyệt đối.
    - Giao dịch không khớp được đưa vào đối soát.
    - Không ghi nhận một giao dịch ngân hàng hai lần.
    - Không tự giao xu tại bước này.
    """

    event_id = str(event_id).strip()
    transaction_id = str(transaction_id).strip()
    direction = str(direction).strip().lower()

    if not event_id or not transaction_id:
        raise PaymentError(
            "Thiếu mã sự kiện hoặc mã giao dịch."
        )

    if direction not in {"in", "credit"}:
        raise PaymentError(
            "Giao dịch không phải tiền vào."
        )

    received_amount = normalize_amount(amount)

    content = str(content or "")
    code = str(code or "")
    payload = raw_payload or {}

    if not isinstance(payload, dict):
        raise PaymentError(
            "Payload giao dịch không hợp lệ."
        )

    reference = extract_order_reference(
        content=content,
        code=code,
    )

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():

                # 1. Kiểm tra webhook đã xử lý.
                existing_event = await session.execute(
                    select(ProcessedWebhook).where(
                        ProcessedWebhook.provider == "sepay",
                        ProcessedWebhook.event_id == event_id,
                    )
                )

                if existing_event.scalar_one_or_none():
                    return {
                        "success": True,
                        "duplicate": True,
                        "message": "Webhook đã được xử lý.",
                    }

                # 2. Kiểm tra giao dịch ngân hàng đã tồn tại.
                existing_payment = await session.execute(
                    select(PaymentTransaction).where(
                        PaymentTransaction.provider == "sepay",
                        PaymentTransaction.provider_transaction_id
                        == transaction_id,
                    )
                )

                if existing_payment.scalar_one_or_none():
                    return {
                        "success": True,
                        "duplicate": True,
                        "message": "Giao dịch ngân hàng đã được ghi nhận.",
                    }

                # 3. Không tìm được mã đơn: lưu đối soát.
                if not reference:
                    await _record_reconciliation(
                        session,
                        event_id=event_id,
                        transaction_id=transaction_id,
                        amount=received_amount,
                        content=content,
                        reason="missing_order_reference",
                        raw_payload=payload,
                    )

                    return {
                        "success": False,
                        "reconciliation": True,
                        "message": "Không tìm thấy mã đơn.",
                    }

                # 4. Tìm đơn hàng.
                order = await _find_order_by_reference(
                    session,
                    reference,
                )

                if order is None:
                    await _record_reconciliation(
                        session,
                        event_id=event_id,
                        transaction_id=transaction_id,
                        amount=received_amount,
                        content=content,
                        reason="order_not_found",
                        raw_payload=payload,
                    )

                    return {
                        "success": False,
                        "reconciliation": True,
                        "message": "Không tìm thấy đơn tương ứng.",
                    }

                # 5. Kiểm tra đơn có đủ điều kiện nhận thanh toán.
                if (
                    order.order_type != "buy"
                    or order.payment_method != "qr"
                    or order.status != "pending_payment"
                    or order.payment_status != "unpaid"
                ):
                    await _record_reconciliation(
                        session,
                        event_id=event_id,
                        transaction_id=transaction_id,
                        amount=received_amount,
                        content=content,
                        reason="order_not_eligible",
                        raw_payload=payload,
                    )

                    return {
                        "success": False,
                        "reconciliation": True,
                        "message": "Đơn không đủ điều kiện nhận tiền.",
                    }

                # 6. So sánh số tiền chính xác.
                expected_amount = normalize_amount(
                    order.total_amount
                )

                if received_amount != expected_amount:
                    await _record_reconciliation(
                        session,
                        event_id=event_id,
                        transaction_id=transaction_id,
                        amount=received_amount,
                        content=content,
                        reason="amount_mismatch",
                        raw_payload={
                            **payload,
                            "expected_amount": str(expected_amount),
                            "received_amount": str(received_amount),
                        },
                    )

                    return {
                        "success": False,
                        "reconciliation": True,
                        "message": "Số tiền không khớp đơn hàng.",
                        "expected_amount": str(expected_amount),
                        "received_amount": str(received_amount),
                    }

                # 7. Ghi nhận thanh toán hợp lệ.
                session.add(
                    PaymentTransaction(
                        order_id=order.id,
                        provider="sepay",
                        provider_transaction_id=transaction_id,
                        bank_account=str(
                            payload.get("accountNumber") or ""
                        ),
                        transfer_code=code,
                        content=content,
                        amount=received_amount,
                        transfer_type="in",
                        status="success",
                        raw_payload=payload,
                    )
                )

                session.add(
                    ProcessedWebhook(
                        provider="sepay",
                        event_id=event_id,
                        payload_hash=_payload_hash(payload),
                    )
                )

                # 8. Cập nhật trạng thái thanh toán.
                # Chưa giao xu tại bước này.
                order.status = "paid"
                order.payment_status = "paid"

                await session.flush()

                logger.info(
                    "QR payment verified: order=%s transaction=%s",
                    order.order_code,
                    transaction_id,
                )

                return {
                    "success": True,
                    "duplicate": False,
                    "order_id": order.id,
                    "order_code": order.order_code,
                    "amount": str(received_amount),
                    "message": "Đã xác minh thanh toán.",
                }

    except PaymentError:
        raise

    except Exception:
        logger.exception(
            "Lỗi xử lý SePay transaction=%s",
            transaction_id,
        )
        raise
