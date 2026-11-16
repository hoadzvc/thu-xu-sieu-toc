
import asyncio

from playwright.async_api import async_playwright

from app.config import settings


# "buy": tai khoan chuyen Coin cho nguoi mua
# "sell": tai khoan nhan Coin tu nguoi ban
ACCOUNT_ROLE = "buy"


def get_password(secret):
    if not secret:
        return ""
    return secret.get_secret_value()


async def main():
    if ACCOUNT_ROLE == "buy":
        username = settings.nvc_buy_username
        password = get_password(settings.nvc_buy_password)

    elif ACCOUNT_ROLE == "sell":
        username = settings.nvc_sell_username
        password = get_password(settings.nvc_sell_password)

    else:
        raise ValueError("ACCOUNT_ROLE khong hop le")

    if not username or not password:
        print("THIEU TAI KHOAN HOAC MAT KHAU TRONG FILE .env")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(20000)

        try:
            print("Dang mo trang dang nhap NVC...")

            await page.goto(
                settings.nvc_login_url,
                wait_until="commit",
                timeout=60000,
            )

            await page.locator("#login-username").wait_for(
                state="visible",
                timeout=30000,
            )

            await page.locator("#login-password").wait_for(
                state="visible",
                timeout=30000,
            )

            print("Da tim thay o dang nhap.")

            await page.locator("#login-username").fill(username)
            await page.locator("#login-password").fill(password)

            print("Da dien thong tin dang nhap.")
            print("Dang gui yeu cau dang nhap...")

            await page.locator('button[type="submit"]').click()

            await page.wait_for_timeout(5000)

            print("\n========== KET QUA ==========")
            print("URL:", page.url)
            print("TITLE:", await page.title())

            username_visible = await page.locator(
                "#login-username"
            ).is_visible()

            password_visible = await page.locator(
                "#login-password"
            ).is_visible()

            if (
                not username_visible
                and not password_visible
                and "/login" not in page.url
            ):
                print("CO DAU HIEU DANG NHAP THANH CONG.")
            else:
                print("CHUA XAC NHAN DUOC DANG NHAP.")
                print("Hay kiem tra thong bao loi tren trinh duyet.")

                error_text = await page.locator("body").inner_text()
                print("\nNOI DUNG TRANG:")
                print(error_text[:1500])

            print("\nKHONG THUC HIEN LENH CHUYEN COIN.")

        except Exception as error:
            print("\nLOI KIEM TRA:", str(error)[:500])

        finally:
            input("\nNhan Enter de dong trinh duyet...")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
