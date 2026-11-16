
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
                timeout=60000
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
                timeout=60000
            )

            print("Dang mo wallet...")
            await page.goto(
                settings.nvc_wallet_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.locator("table").wait_for(
                state="visible",
                timeout=30000
            )
            await page.wait_for_timeout(2000)

            print("\nDang mo bo loc danh muc...")

            # Bộ lọc là combobox, không phải button thông thường.
            category = page.get_by_role("combobox").nth(0)
            await category.click()
            await page.wait_for_timeout(1000)

            print("\n========== CAC LUA CHON DANH MUC ==========")

            options = await page.locator(
                '[role="option"], [role="listbox"] *, [data-value]'
            ).evaluate_all("""
                els => els.map(el => ({
                    tag: el.tagName,
                    role: el.getAttribute("role"),
                    text: el.innerText?.trim(),
                    value: el.getAttribute("data-value"),
                    aria: el.getAttribute("aria-label"),
                    selected: el.getAttribute("aria-selected"),
                    state: el.getAttribute("data-state")
                })).filter(x =>
                    x.text || x.value || x.aria || x.role === "option"
                )
            """)

            print(json.dumps(
                options,
                ensure_ascii=False,
                indent=2
            ))

            print("\n========== NOI DUNG MENU ==========")
            print((await page.locator("body").inner_text())[-3000:])

            print("\nKhong thuc hien lenh chuyen Coin.")
            input("Nhan Enter de dong trinh duyet...")

        except Exception as e:
            print("\nLOI:", repr(e))
            input("Nhan Enter de thoat...")

        finally:
            if browser:
                await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
