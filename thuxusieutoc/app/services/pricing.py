
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class PriceResult:
    website: str
    order_type: str
    amount_coin: int
    total_amount: Decimal
    unit_price_description: str


def money(value: Decimal) -> Decimal:
    """Làm tròn tiền đến đơn vị đồng."""
    return value.quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )


def calculate_nvc_buy(amount_coin: int) -> PriceResult:
    """
    Giá mua Nhiemvucheo:
    - 0 đến 10 triệu: 10.000đ / 1 triệu.
    - Trên 10 đến 100 triệu: 9.000đ / 1 triệu.
    - Phần vượt 100 triệu: 8.000đ / 1 triệu.

    Tính lũy tiến theo từng bậc.
    """

    if amount_coin < 1_000_000:
        raise ValueError("Mua Nhiemvucheo tối thiểu 1 triệu xu.")

    if amount_coin % 1_000_000 != 0:
        raise ValueError("Số xu Nhiemvucheo phải là bội số 1 triệu.")

    units = amount_coin // 1_000_000

    first = min(units, 10)
    second = min(max(units - 10, 0), 90)
    third = max(units - 100, 0)

    total = (
        Decimal(first * 10_000)
        + Decimal(second * 9_000)
        + Decimal(third * 8_000)
    )

    return PriceResult(
        website="nvc",
        order_type="buy",
        amount_coin=amount_coin,
        total_amount=money(total),
        unit_price_description="10.000đ / 9.000đ / 8.000đ theo bậc",
    )


def calculate_nvc_sell(amount_coin: int) -> PriceResult:
    """
    Giá bán Nhiemvucheo:
    - 0 đến 50 triệu: 8.000đ / 1 triệu.
    - Phần vượt 50 triệu: 9.000đ / 1 triệu.

    Tính lũy tiến theo từng bậc.
    """

    if amount_coin < 1_000_000:
        raise ValueError("Bán Nhiemvucheo tối thiểu 1 triệu xu.")

    if amount_coin % 1_000_000 != 0:
        raise ValueError("Số xu Nhiemvucheo phải là bội số 1 triệu.")

    units = amount_coin // 1_000_000

    first = min(units, 50)
    second = max(units - 50, 0)

    total = (
        Decimal(first * 8_000)
        + Decimal(second * 9_000)
    )

    return PriceResult(
        website="nvc",
        order_type="sell",
        amount_coin=amount_coin,
        total_amount=money(total),
        unit_price_description="8.000đ / 9.000đ theo bậc",
    )


def calculate_xsmm_buy(amount_coin: int) -> PriceResult:
    """
    XSMM mua:
    9.000đ / 10.000 xu.
    Tối thiểu 50.000 xu.
    """

    if amount_coin < 50_000:
        raise ValueError("Mua XSMM tối thiểu 50.000 xu.")

    if amount_coin % 10_000 != 0:
        raise ValueError("Số xu XSMM phải là bội số 10.000.")

    total = (
        Decimal(amount_coin)
        / Decimal(10_000)
        * Decimal(9_000)
    )

    return PriceResult(
        website="xsmm",
        order_type="buy",
        amount_coin=amount_coin,
        total_amount=money(total),
        unit_price_description="9.000đ / 10.000 xu",
    )


def calculate_xsmm_sell(amount_coin: int) -> PriceResult:
    """
    XSMM bán:
    7.500đ / 10.000 xu.
    Tối thiểu 100.000 xu.
    """

    if amount_coin < 100_000:
        raise ValueError("Bán XSMM tối thiểu 100.000 xu.")

    if amount_coin % 10_000 != 0:
        raise ValueError("Số xu XSMM phải là bội số 10.000.")

    total = (
        Decimal(amount_coin)
        / Decimal(10_000)
        * Decimal(7_500)
    )

    return PriceResult(
        website="xsmm",
        order_type="sell",
        amount_coin=amount_coin,
        total_amount=money(total),
        unit_price_description="7.500đ / 10.000 xu",
    )


def calculate_price(
    website: str,
    order_type: str,
    amount_coin: int,
) -> PriceResult:
    """
    Hàm tính giá tổng hợp.

    website: nvc hoặc xsmm
    order_type: buy hoặc sell
    """

    if website == "nvc" and order_type == "buy":
        return calculate_nvc_buy(amount_coin)

    if website == "nvc" and order_type == "sell":
        return calculate_nvc_sell(amount_coin)

    if website == "xsmm" and order_type == "buy":
        return calculate_xsmm_buy(amount_coin)

    if website == "xsmm" and order_type == "sell":
        return calculate_xsmm_sell(amount_coin)

    raise ValueError("Website hoặc loại đơn không hợp lệ.")
