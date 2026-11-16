
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)

from app.config import settings
from app.services.exchange import (
    ExchangeRequest,
    ExchangeResult,
)


class NVCAdapterError(Exception):
    """Lỗi chung của NhiemVuCheo adapter."""


class NVCAdapterNotConfigured(NVCAdapterError):
    """Chưa xác nhận đủ selector để thao tác an toàn."""


class NVCVerificationError(NVCAdapterError):
    """Không thể xác minh giao dịch."""


@dataclass(frozen=True)
class NVCSelectors:
    """
    Selector phải được xác nhận từ giao diện thực tế.

    Không tự điền selector phỏng đoán.
    """

    username_input: str | None = None
    password_input: str | None = None
    login_button: str | None = None

    receiver_input: str | None = None
    amount_input: str | None = None
    transfer_button: str | None = None

    transaction_rows: str | None = None
    transaction_id: str | None = None
    transaction_content: str | None = None
    transaction_amount: str | None = None
    transaction_time: str | None = None


class NVCAdapter:
    """
    Adapter NhiemVuCheo.

    Giai đoạn này chỉ dựng khung kết nối.
    Chưa cho phép chuyển Coin khi selector chưa được xác nhận.
    """

    website = "nvc"

    def __init__(
        self,
        selectors: NVCSelectors | None = None,
    ) -> None:
        self.selectors = selectors or NVCSelectors()

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def _require_selectors(self, *names: str) -> None:
        missing = [
            name
            for name in names
            if not getattr(self.selectors, name, None)
        ]

        if missing:
            raise NVCAdapterNotConfigured(
                "NVC chưa cấu hình selector: "
                + ", ".join(missing)
            )

    async def start(self) -> None:
        """Khởi động trình duyệt Playwright."""

        if self._playwright is not None:
            return

        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=settings.HEADLESS,
        )

        self._context = await self._browser.new_context(
            locale="vi-VN",
        )

        self._page = await self._context.new_page()

        self._page.set_default_timeout(
            settings.BROWSER_TIMEOUT
        )

    async def close(self) -> None:
        """Đóng trình duyệt và giải phóng tài nguyên."""

        if self._context is not None:
            await self._context.close()

        if self._browser is not None:
            await self._browser.close()

        if self._playwright is not None:
            await self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    def _require_page(self) -> Page:
        if self._page is None:
            raise NVCAdapterError(
                "Trình duyệt chưa được khởi động."
            )

        return self._page

    async def login(self) -> None:
        """
        Đăng nhập NVC.

        Chưa triển khai thao tác nhập thông tin cho đến khi
        selector được xác nhận.
        """

        self._require_selectors(
            "username_input",
            "password_input",
            "login_button",
        )

        raise NVCAdapterNotConfigured(
            "Chưa bật đăng nhập tự động. "
            "Cần kiểm tra selector và trạng thái đăng nhập."
        )

    async def execute(
        self,
        request: ExchangeRequest,
    ) -> ExchangeResult:
        """
        Chuyển Coin.

        Cố ý chưa thực hiện giao dịch khi chưa xác minh
        selector, tài khoản và quy tắc phí.
        """

        if request.website != self.website:
            raise NVCAdapterError(
                "Yêu cầu không thuộc NhiemVuCheo."
            )

        self._require_selectors(
            "receiver_input",
            "amount_input",
            "transfer_button",
        )

        raise NVCAdapterNotConfigured(
            "Chưa cho phép chuyển Coin. "
            "Cần xác minh selector, username tài khoản "
            "hệ thống và số Coin thực tế phải chuyển."
        )

    async def verify(
        self,
        request: ExchangeRequest,
        result: ExchangeResult,
    ) -> ExchangeResult:
        """
        Xác minh giao dịch sau khi chuyển.

        Chưa trả về thành công nếu chưa đọc được lịch sử.
        """

        self._require_selectors(
            "transaction_rows",
            "transaction_id",
            "transaction_content",
            "transaction_amount",
            "transaction_time",
        )

        raise NVCVerificationError(
            "Chưa triển khai bộ đọc lịch sử NVC."
        )

    async def find_matching_transaction(
        self,
        request: ExchangeRequest,
    ) -> ExchangeResult | None:
        """
        Tìm giao dịch đã tồn tại trước khi thực hiện.

        Chưa được phép trả về giao dịch khớp khi chưa có
        bộ đọc lịch sử và quy tắc đối chiếu đầy đủ.
        """

        self._require_selectors(
            "transaction_rows",
            "transaction_id",
            "transaction_content",
            "transaction_amount",
            "transaction_time",
        )

        raise NVCVerificationError(
            "Chưa thể kiểm tra lịch sử giao dịch NVC."
        )

    async def inspect_current_page(self) -> dict[str, Any]:
        """
        Lấy thông tin cơ bản để kiểm tra trang hiện tại.
        Không lấy cookie, mật khẩu hoặc token.
        """

        page = self._require_page()

        return {
            "url": page.url,
            "title": await page.title(),
        }
