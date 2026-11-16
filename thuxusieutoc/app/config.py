
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )

    # TELEGRAM
    bot_token: SecretStr = SecretStr("")
    admin_ids: str = ""

    # DATABASE
    database_url: str = "sqlite+aiosqlite:///./data/bot.db"

    # SECURITY
    secret_key: SecretStr = SecretStr("")

    # NHIEMVUCHEO
    nvc_login_url: str = "https://nhiemvucheo.com/login"
    nvc_gift_url: str = "https://nhiemvucheo.com/gift"
    nvc_wallet_url: str = "https://nhiemvucheo.com/wallet"

    # Tài khoản NVC gửi Coin cho khách mua
    nvc_buy_username: str = ""
    nvc_buy_password: SecretStr = SecretStr("")

    # Tài khoản NVC nhận Coin từ khách bán
    nvc_sell_username: str = ""
    nvc_sell_password: SecretStr = SecretStr("")

    # XSMM
    xsmm_login_url: str = "https://xsmm.net/login"
    xsmm_transfer_url: str = "https://xsmm.net/transfer"
    xsmm_transactions_url: str = "https://xsmm.net/transactions"

    xsmm_username: str = ""
    xsmm_password: SecretStr = SecretStr("")
    xsmm_transfer_password: SecretStr = SecretStr("")

    # SEPAY
    sepay_api_key: SecretStr = SecretStr("")
    sepay_webhook_secret: SecretStr = SecretStr("")

    sepay_bank_account: str = ""
    sepay_bank_name: str = ""
    sepay_account_name: str = ""
    sepay_webhook_url: str = ""

    # SUPPORT
    support_username: str = ""
    support_group_url: str = ""

    # LANGUAGE
    default_language: str = "vi"

    # PLAYWRIGHT
    headless: bool = False
    browser_timeout: int = 30000

    # APPLICATION
    app_env: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @field_validator("admin_ids")
    @classmethod
    def validate_admin_ids(cls, value: str) -> str:
        value = value.strip()

        if not value:
            return value

        for item in value.split(","):
            if not item.strip().isdigit():
                raise ValueError(
                    "ADMIN_IDS phải là các Telegram ID dạng số, "
                    "phân cách bằng dấu phẩy."
                )

        return value

    @field_validator("browser_timeout")
    @classmethod
    def validate_browser_timeout(cls, value: int) -> int:
        if value < 1000:
            raise ValueError(
                "BROWSER_TIMEOUT phải từ 1000ms trở lên."
            )
        return value

    @field_validator("api_port")
    @classmethod
    def validate_api_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("API_PORT không hợp lệ.")
        return value

    @property
    def admin_id_list(self) -> set[int]:
        if not self.admin_ids:
            return set()

        return {
            int(item.strip())
            for item in self.admin_ids.split(",")
            if item.strip()
        }

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def reload_settings() -> Settings:
    """
    Đọc lại file .env mà không thay thế đối tượng settings.

    Các module đã import:
        from app.config import settings

    vẫn sử dụng được cấu hình mới sau khi gọi hàm này.

    Nếu cấu hình mới không hợp lệ, settings hiện tại
    sẽ được giữ nguyên.
    """

    new_settings = Settings()

    # Chỉ cập nhật sau khi Settings() đã xác thực thành công.
    for field_name in type(settings).model_fields:
        setattr(
            settings,
            field_name,
            getattr(new_settings, field_name),
        )

    get_settings.cache_clear()

    return settings
