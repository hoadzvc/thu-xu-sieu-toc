
import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol


class ExchangeError(Exception):
    """Lỗi giao dịch xu."""


class ExchangeConfigurationError(ExchangeError):
    """Adapter website chưa được cấu hình."""


class ExchangeExecutionError(ExchangeError):
    """Giao dịch thất bại."""


class ExchangeUncertain(ExchangeError):
    """
    Không xác định được giao dịch đã thành công hay chưa.

    Không được tự động gửi lại giao dịch trong trường hợp này.
    """


class ExchangeVerificationError(ExchangeError):
    """Không xác minh được giao dịch trong lịch sử."""


@dataclass(frozen=True)
class ExchangeRequest:
    order_id: int
    website: str
    order_type: str
    coin_amount: int
    username: str


@dataclass(frozen=True)
class ExchangeResult:
    success: bool
    website: str
    transaction_id: str | None
    sender_username: str | None
    receiver_username: str | None
    coin_amount: int
    message: str = ""
    raw_reference: str | None = None


class ExchangeAdapter(Protocol):
    async def execute(
        self,
        request: ExchangeRequest,
    ) -> ExchangeResult:
        ...

    async def verify(
        self,
        request: ExchangeRequest,
        result: ExchangeResult,
    ) -> ExchangeResult:
        ...


# =========================================================
# ĐĂNG KÝ ADAPTER
# =========================================================

_adapters: dict[tuple[str, str], ExchangeAdapter] = {}

# Khóa riêng cho từng tài khoản website.
# NVC mua và bán sử dụng hai khóa khác nhau.
# XSMM mua và bán dùng chung một khóa.
_account_locks: dict[str, asyncio.Lock] = {}

# Ngăn hai tác vụ cùng xử lý một order trong cùng tiến trình.
_order_locks: dict[int, asyncio.Lock] = {}


def _account_key(website: str, order_type: str) -> str:
    if website == "nvc":
        if order_type == "buy":
            return "nvc_buy_account"

        return "nvc_sell_account"

    if website == "xsmm":
        return "xsmm_shared_account"

    raise ExchangeConfigurationError(
        f"Website không được hỗ trợ: {website}"
    )


def register_adapter(
    website: str,
    order_type: str,
    adapter: ExchangeAdapter,
) -> None:
    if website not in {"nvc", "xsmm"}:
        raise ExchangeConfigurationError("Website không hợp lệ.")

    if order_type not in {"buy", "sell"}:
        raise ExchangeConfigurationError("Loại đơn không hợp lệ.")

    key = (website, order_type)

    if key in _adapters:
        raise ExchangeConfigurationError(
            f"Adapter {website}/{order_type} đã được đăng ký."
        )

    _adapters[key] = adapter


def get_adapter(
    website: str,
    order_type: str,
) -> ExchangeAdapter:
    adapter = _adapters.get((website, order_type))

    if adapter is None:
        raise ExchangeConfigurationError(
            f"Chưa cấu hình adapter cho {website}/{order_type}."
        )

    return adapter


def _validate_request(request: ExchangeRequest) -> None:
    if request.order_id <= 0:
        raise ExchangeError("Mã đơn hàng không hợp lệ.")

    if request.website not in {"nvc", "xsmm"}:
        raise ExchangeError("Website không hợp lệ.")

    if request.order_type not in {"buy", "sell"}:
        raise ExchangeError("Loại đơn hàng không hợp lệ.")

    if (
        isinstance(request.coin_amount, bool)
        or not isinstance(request.coin_amount, int)
        or request.coin_amount <= 0
    ):
        raise ExchangeError("Số xu không hợp lệ.")

    username = request.username.strip().lstrip("@")

    if not username or len(username) > 100:
        raise ExchangeError("Username không hợp lệ.")


def _validate_result(
    request: ExchangeRequest,
    result: ExchangeResult,
) -> None:
    if not isinstance(result, ExchangeResult):
        raise ExchangeExecutionError(
            "Adapter trả về dữ liệu không hợp lệ."
        )

    if not result.success:
        raise ExchangeExecutionError(
            result.message or "Website báo giao dịch thất bại."
        )

    if result.website != request.website:
        raise ExchangeVerificationError(
            "Website trả về không khớp đơn hàng."
        )

    if not result.transaction_id:
        raise ExchangeVerificationError(
            "Thiếu mã giao dịch trên website."
        )

    if result.coin_amount != request.coin_amount:
        raise ExchangeVerificationError(
            "Số xu giao dịch không khớp số xu đơn hàng."
        )

    if not result.sender_username or not result.receiver_username:
        raise ExchangeVerificationError(
            "Thiếu username người gửi hoặc người nhận."
        )

    if result.sender_username.strip().lstrip("@").lower() == "":
        raise ExchangeVerificationError("Username người gửi không hợp lệ.")

    if result.receiver_username.strip().lstrip("@").lower() == "":
        raise ExchangeVerificationError("Username người nhận không hợp lệ.")


def _validate_direction(
    request: ExchangeRequest,
    result: ExchangeResult,
) -> None:
    """
    Kiểm tra chiều giao dịch.

    Mua: tài khoản hệ thống gửi xu cho khách.
    Bán: khách gửi xu vào tài khoản hệ thống.
    """

    sender = result.sender_username.strip().lstrip("@").lower()
    receiver = result.receiver_username.strip().lstrip("@").lower()
    customer = request.username.strip().lstrip("@").lower()

    if request.order_type == "buy":
        if receiver != customer:
            raise ExchangeVerificationError(
                "Người nhận xu không trùng username khách đặt mua."
            )

    elif request.order_type == "sell":
        if sender != customer:
            raise ExchangeVerificationError(
                "Người gửi xu không trùng username khách bán."
            )


# =========================================================
# KIỂM TRA LỊCH SỬ
# =========================================================

async def check_exchange_history(
    request: ExchangeRequest,
) -> ExchangeResult | None:
    """
    Kiểm tra lịch sử trước khi gửi giao dịch.

    Adapter cần hỗ trợ phương thức:
        find_matching_transaction(request)

    Nếu chưa hỗ trợ, không được tự ý gửi giao dịch
    khi trạng thái đơn đang không rõ ràng.
    """

    adapter = get_adapter(request.website, request.order_type)

    finder = getattr(adapter, "find_matching_transaction", None)

    if finder is None:
        raise ExchangeConfigurationError(
            "Adapter chưa hỗ trợ kiểm tra giao dịch trong lịch sử."
        )

    try:
        result = await finder(request)
    except asyncio.TimeoutError as exc:
        raise ExchangeUncertain(
            "Timeout khi kiểm tra lịch sử giao dịch."
        ) from exc

    if result is None:
        return None

    _validate_result(request, result)
    _validate_direction(request, result)

    verified = await adapter.verify(request, result)

    _validate_result(request, verified)
    _validate_direction(request, verified)

    return verified


# =========================================================
# THỰC HIỆN GIAO DỊCH
# =========================================================

async def execute_exchange(
    request: ExchangeRequest,
) -> ExchangeResult:
    """
    Thực hiện chuyển xu và xác minh kết quả.

    Quy tắc:
    - Mỗi order chỉ được xử lý một lần tại một thời điểm.
    - Mỗi tài khoản website chỉ có một thao tác đồng thời.
    - Kiểm tra lịch sử trước khi chuyển.
    - Timeout không tự động gửi lại.
    """

    _validate_request(request)

    adapter = get_adapter(request.website, request.order_type)

    account_key = _account_key(
        request.website,
        request.order_type,
    )

    if account_key not in _account_locks:
        _account_locks[account_key] = asyncio.Lock()

    if request.order_id not in _order_locks:
        _order_locks[request.order_id] = asyncio.Lock()

    order_lock = _order_locks[request.order_id]
    account_lock = _account_locks[account_key]

    async with order_lock:
        async with account_lock:

            # Kiểm tra giao dịch đã tồn tại chưa.
            existing = await check_exchange_history(request)

            if existing is not None:
                return existing

            # Chỉ gửi khi chắc chắn lịch sử không có giao dịch phù hợp.
            try:
                result = await adapter.execute(request)

            except asyncio.TimeoutError as exc:
                raise ExchangeUncertain(
                    "Website timeout khi chuyển xu. "
                    "Cần kiểm tra lịch sử trước khi xử lý tiếp."
                ) from exc

            except ExchangeUncertain:
                raise

            except ExchangeError:
                raise

            except Exception as exc:
                # Lỗi không rõ xảy ra trước hay sau khi website nhận lệnh.
                raise ExchangeUncertain(
                    "Không xác định được kết quả chuyển xu. "
                    "Không được gửi lại tự động."
                ) from exc

            _validate_result(request, result)
            _validate_direction(request, result)

            # Xác minh lại trong lịch sử website.
            try:
                verified = await adapter.verify(request, result)

            except asyncio.TimeoutError as exc:
                raise ExchangeUncertain(
                    "Đã gửi lệnh nhưng chưa xác minh được lịch sử. "
                    "Cần đối soát thủ công hoặc kiểm tra lại."
                ) from exc

            except Exception as exc:
                raise ExchangeUncertain(
                    "Không thể xác minh giao dịch sau khi gửi lệnh."
                ) from exc

            _validate_result(request, verified)
            _validate_direction(request, verified)

            return verified


# =========================================================
# TIỆN ÍCH
# =========================================================

def get_registered_adapters() -> list[str]:
    return [
        f"{website}/{order_type}"
        for website, order_type in _adapters
    ]


def clear_adapters() -> None:
    """
    Chỉ dùng trong kiểm thử.
    Không gọi trong khi bot đang xử lý đơn hàng.
    """
    _adapters.clear()
    _account_locks.clear()
    _order_locks.clear()
