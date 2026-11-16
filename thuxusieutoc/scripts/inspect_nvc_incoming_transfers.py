
import asyncio
import json

from playwright.async_api import async_playwright
from app.config import settings


async def main():
    browser = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            page.set_default_timeout(20000)

            print("Dang dang nhap NVC...")

            await page.goto(
                settings.nvc_login_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            await page.locator("#login-username").fill(
                settings.nvc_buy_username
            )
            await page.locator("#login-password").fill(
                settings.nvc_buy_password.get_secret_value()
            )
            await page.locator('button[type="submit"]').click()

            await page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=60000,
            )

            print("Dang mo wallet...")

            await page.goto(
                settings.nvc_wallet_url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            await page.locator("table").wait_for(
                state="visible",
                timeout=30000,
            )

            await page.wait_for_timeout(1500)

            print("Loc giao dich Cong Coin...")

            await page.get_by_role(
                "button",
                name="Cộng Coin (+)",
            ).click()

            await page.wait_for_timeout(1500)

            print("Loc danh muc Chuyen Coin...")

            await page.get_by_role("combobox").nth(0).click()

            await page.get_by_role(
                "option",
                name="Chuyển Coin",
                exact=True,
            ).click()

            await page.wait_for_timeout(2000)

            rows = await page.locator(
                "table tbody tr"
            ).evaluate_all("""
                rows => rows.map((row, index) => ({
                    index,
                    text: row.innerText?.trim(),
                    cells: Array.from(
                        row.querySelectorAll("td")
                    ).map((td, cellIndex) => ({
                        cellIndex,
                        text: td.innerText?.trim(),
                        html: td.innerHTML
                    }))
                }))
            """)

            print("\\n========== GIAO DICH CONG COIN / CHUYEN COIN ==========")
            print(json.dumps(rows, ensure_ascii=False, indent=2))

            print("\\n========== NOI DUNG WALLET ==========")
            print((await page.locator("body").inner_text())[-5000:])

            print("\\nChi doc lich su. KHONG chuyen Coin.")

            input("Nhan Enter de dong trinh duyet...")

        except Exception as e:
            print("\\nLOI:", repr(e))
            input("Nhan Enter de thoat...")

        finally:
            if browser:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
