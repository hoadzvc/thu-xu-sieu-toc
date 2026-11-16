
import hashlib
import hmac
import json
import logging
import time

from fastapi import HTTPException, Request

from app.config import settings
from app.services.payment import (
    process_sepay_webhook,
    PaymentError,
    PaymentMismatch,
    DuplicatePayment,
)

logger = logging.getLogger(__name__)

MAX_TIMESTAMP_DRIFT = 300


def _secret_value(name: str) -> str:
    value = getattr(settings, name, None)

    if value is None:
        return ""

    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()

    return str(value).strip()


def verify_api_key(request: Request) -> bool:
    expected = _secret_value("sepay_api_key")

    if not expected:
        return False

    authorization = request.headers.get("Authorization", "")
    prefix = "Apikey "

    if not authorization.startswith(prefix):
        return False

    received = authorization[len(prefix):].strip()

    return hmac.compare_digest(received, expected)


def verify_hmac_signature(
    *,
    raw_body: bytes,
    timestamp_header: str,
    signature_header: str,
) -> bool:
    secret = _secret_value("sepay_webhook_secret")

    if not secret or not timestamp_header or not signature_header:
        return False

    try:
        timestamp = int(timestamp_header)
    except (TypeError, ValueError):
        return False

    if abs(int(time.time()) - timestamp) > MAX_TIMESTAMP_DRIFT:
        return False

    signed_content = timestamp_header.encode("utf-8") + b"." + raw_body

    digest = hmac.new(
        secret.encode("utf-8"),
        signed_content,
        hashlib.sha256,
    ).hexdigest()

    expected_signature = f"sha256={digest}"

    return hmac.compare_digest(
        signature_header.strip().lower(),
        expected_signature,
    )


def authenticate_webhook(
    request: Request,
    raw_body: bytes,
) -> None:
    """
    Nếu có HMAC secret: bắt buộc xác thực HMAC.
    Nếu không có HMAC secret: sử dụng API Key.

    Không tự động chuyển sang API Key khi HMAC sai.
    """

    hmac_secret = _secret_value("sepay_webhook_secret")

    if hmac_secret:
        signature = request.headers.get("X-SePay-Signature", "")
        timestamp = request.headers.get("X-SePay-Timestamp", "")

        if not verify_hmac_signature(
            raw_body=raw_body,
            timestamp_header=timestamp,
            signature_header=signature,
        ):
            raise HTTPException(
                status_code=401,
                detail="Chữ ký HMAC không hợp lệ hoặc đã hết hạn.",
            )

        return

    if verify_api_key(request):
        return

    raise HTTPException(
        status_code=401,
        detail="Webhook không được xác thực.",
    )


def validate_bank_account(payload: dict) -> None:
    expected_account = _secret_value("sepay_bank_account")

    if not expected_account:
        raise HTTPException(
            status_code=503,
            detail="Chưa cấu hình tài khoản ngân hàng SePay.",
        )

    received_account = str(
        payload.get("accountNumber") or ""
    ).strip()

    if not received_account:
        raise HTTPException(
            status_code=400,
            detail="Webhook thiếu accountNumber.",
        )

    if not hmac.compare_digest(
        received_account,
        expected_account,
    ):
        raise HTTPException(
            status_code=400,
            detail="Giao dịch không thuộc tài khoản ngân hàng của hệ thống.",
        )


def normalize_sepay_payload(payload: dict) -> dict:
    """
    Chuẩn hóa payload SePay cho payment.py.

    Giữ riêng code và content để FILE 19 có thể đối chiếu
    mã đơn trong cả hai trường.
    """

    required_fields = (
        "id",
        "transferType",
        "transferAmount",
    )

    for field in required_fields:
        if payload.get(field) is None:
            raise HTTPException(
                status_code=400,
                detail=f"Webhook thiếu trường {field}.",
            )

    transaction_id = str(payload["id"]).strip()

    if not transaction_id:
        raise HTTPException(
            status_code=400,
            detail="Mã giao dịch SePay không hợp lệ.",
        )

    try:
        amount = int(payload["transferAmount"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Số tiền giao dịch không hợp lệ.",
        )

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Số tiền giao dịch phải lớn hơn 0.",
        )

    direction = str(payload["transferType"]).strip().lower()

    return {
        "event_id": transaction_id,
        "transaction_id": transaction_id,
        "content": str(payload.get("content") or ""),
        "code": str(payload.get("code") or ""),
        "amount": amount,
        "direction": direction,
        "raw_payload": payload,
    }


async def handle_sepay_request(request: Request) -> dict:
    """
    Xử lý webhook SePay.

    - Xác thực request.
    - Kiểm tra tài khoản nhận.
    - Chỉ xử lý giao dịch tiền vào.
    - Chuyển payload đã chuẩn hóa cho FILE 19.
    - Không trực tiếp giao xu tại đây.
    """

    raw_body = await request.body()

    if not raw_body:
        raise HTTPException(
            status_code=400,
            detail="Webhook không có dữ liệu.",
        )

    authenticate_webhook(request, raw_body)

    content_type = request.headers.get(
        "content-type", ""
    ).lower()

    if "application/json" not in content_type:
        raise HTTPException(
            status_code=415,
            detail="Webhook phải sử dụng application/json.",
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Dữ liệu JSON không hợp lệ.",
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Payload phải là JSON object.",
        )

    validate_bank_account(payload)

    normalized = normalize_sepay_payload(payload)

    # Nếu webhook nhận cả tiền vào và tiền ra,
    # bỏ qua tiền ra và trả thành công để tránh retry vô ích.
    if normalized["direction"] != "in":
        return {
            "success": True,
            "ignored": True,
            "message": "Đã bỏ qua giao dịch không phải tiền vào.",
        }

    try:
        result = await process_sepay_webhook(**normalized)

        return {
            "success": True,
            "message": result.get(
                "message",
                "Webhook đã được tiếp nhận.",
            ),
            "data": result,
        }

    except DuplicatePayment:
        logger.info(
            "SePay duplicate transaction: %s",
            normalized["transaction_id"],
        )

        return {
            "success": True,
            "duplicate": True,
            "message": "Giao dịch đã được ghi nhận trước đó.",
        }

    except PaymentMismatch as exc:
        logger.warning(
            "SePay payment mismatch: %s",
            str(exc),
        )

        # Lỗi đối soát cần được xử lý trong FILE 19.
        # Nếu FILE 19 chưa ghi nhận giao dịch vào reconciliation,
        # cần sửa FILE 19 trước khi dùng production.
        return {
            "success": True,
            "reconciliation_required": True,
            "message": "Giao dịch cần được đối soát thủ công.",
        }

    except PaymentError:
        logger.exception(
            "SePay payment processing error. Transaction ID: %s",
            normalized["transaction_id"],
        )

        raise HTTPException(
            status_code=500,
            detail="Lỗi xử lý thanh toán. Giao dịch chưa được xác nhận.",
        )

    except Exception:
        logger.exception(
            "Unexpected SePay webhook error. Transaction ID: %s",
            normalized["transaction_id"],
        )

        raise HTTPException(
            status_code=500,
            detail="Lỗi hệ thống khi xử lý webhook.",
        )
