
import asyncio
import json
from playwright.async_api import async_playwright
from app.config import settings


async def wait_and_read(page, label):
    # Chờ website cập nhật dữ liệu sau khi đổi bộ lọc
    await page.wait_for_timeout(2500)

    rows = await page.locator("table tbody tr").evaluate_all(
        """rows => rows.map(row =>
            Array.from(row.querySelectorAll('td'))
                .map(cell => cell.innerText.trim())
        )"""
    )

    print(f"\n========== {label} ==========")
    print(json.dumps(rows, ensure_ascii=False, indent=2))

    return rows


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        page.set_default_timeout(30000)

        username = settings.nvc_buy_username
        password = settings.nvc_buy_password.get_secret_value()

        try:
            print("Dang dang nhap NVC...")

            await page.goto(
                settings.nvc_login_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.locator("#login-username").fill(username)
            await page.locator("#login-password").fill(password)
            await page.locator('button[type="submit"]').click()

            await page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=60000
            )

            await page.goto(
                settings.nvc_wallet_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.locator("table tbody tr").first.wait_for(
                state="visible",
                timeout=30000
            )

            await wait_and_read(page, "DU LIEU BAN DAU")

            print("\nDANG BAM TRU COIN...")
            await page.get_by_role(
                "button",
                name="Trừ Coin (−)"
            ).click()

            await wait_and_read(page, "SAU KHI BAM TRU COIN")

            print("\nGIU TRINH DUYET MO DE KIEM TRA.")
            input("Nhan Enter de dong...")

        except Exception as e:
            print("\nLOI:", repr(e))
            input("Nhan Enter de thoat...")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
