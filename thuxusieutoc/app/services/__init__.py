
"""
Business services for the coin exchange bot.

Các module trong package này xử lý:
- Pricing: tính giá mua và bán xu.
- Wallet: quản lý số dư và giao dịch ví.
- Orders: tạo và xử lý đơn hàng.
- Payments: xử lý thanh toán QR và đối soát.
- Exchange: giao dịch xu trên các website.
"""

from app.services.pricing import (
    PriceResult,
    calculate_nvc_price,
    calculate_xsmm_price,
)

from app.services.wallet import (
    WalletError,
    InsufficientBalance,
    WalletNotFound,
    DuplicateTransaction,
    get_wallet_summary,
    deposit_wallet,
    reserve_wallet,
    capture_reserved_wallet,
    release_reserved_wallet,
)

__all__ = [
    "PriceResult",
    "calculate_nvc_price",
    "calculate_xsmm_price",
    "WalletError",
    "InsufficientBalance",
    "WalletNotFound",
    "DuplicateTransaction",
    "get_wallet_summary",
    "deposit_wallet",
    "reserve_wallet",
    "capture_reserved_wallet",
    "release_reserved_wallet",
]
