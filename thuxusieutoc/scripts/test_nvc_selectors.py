import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from app.config import settings


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=settings.headless
        )

        page = await browser.new_page()

        # Không chờ toàn bộ tài nguyên của trang tải xong
        page.set_default_timeout(20000)

        try:
            await page.goto(
                settings.nvc_login_url,
                wait_until="commit",
                timeout=60000,
            )

            # Chờ trang bắt đầu hiển thị
            await page.locator("#login-username").wait_for(
                state="visible",
                timeout=30000,
            )

            await page.locator("#login-password").wait_for(
                state="visible",
                timeout=30000,
            )

            print("\n========== KIEM TRA SELECTOR NVC ==========")
            print("URL:", page.url)
            print(
                "Username:",
                await page.locator("#login-username").count()
            )
            print(
                "Password:",
                await page.locator("#login-password").count()
            )
            print(
                "Submit:",
                await page.locator('button[type="submit"]').count()
            )

            print(
                "Username visible:",
                await page.locator("#login-username").is_visible()
            )

            print(
                "Password visible:",
                await page.locator("#login-password").is_visible()
            )

            print("\nKIEM TRA HOAN TAT.")

        except PlaywrightTimeoutError as error:
            print("\nKHONG TIM THAY DU CAC THANH PHAN.")
            print("URL hien tai:", page.url)
            print("Chi tiet:", str(error).splitlines()[0])

        finally:
            input("\nNhan Enter de dong trinh duyet...")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())