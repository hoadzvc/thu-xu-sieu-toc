
import asyncio
import json

from playwright.async_api import async_playwright
from app.config import settings


async def main():
    browser = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_timeout(30000)

            role = "buy"

            if role == "buy":
                username = settings.nvc_buy_username
                password = settings.nvc_buy_password.get_secret_value()
            else:
                username = settings.nvc_sell_username
                password = settings.nvc_sell_password.get_secret_value()

            print("Dang mo trang dang nhap NVC...")

            await page.goto(
                settings.nvc_login_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.locator("#login-username").fill(username)
            await page.locator("#login-password").fill(password)

            print("Dang gui yeu cau dang nhap...")
            await page.locator('button[type="submit"]').click()

            # Cho website xu ly dang nhap
            login_ok = False

            for i in range(60):
                await asyncio.sleep(1)

                if page.is_closed():
                    print("Trang da bi dong.")
                    return

                try:
                    login_form_visible = await page.locator(
                        "#login-username"
                    ).is_visible()

                    body_text = await page.locator("body").inner_text(
                        timeout=5000
                    )

                    if (
                        "/login" not in page.url
                        and not login_form_visible
                        and "Đang Xác Thực" not in body_text
                    ):
                        login_ok = True
                        break

                except Exception:
                    pass

                print(f"Dang cho dang nhap: {i + 1}/60 giay")

            if not login_ok:
                print("\nCHUA XAC NHAN DUOC DANG NHAP.")
                print("URL:", page.url)

                try:
                    print((await page.locator("body").inner_text())[:3000])
                except Exception:
                    pass

                input("\nNhan Enter de dong...")
                return

            print("\nDANG NHAP CO DAU HIEU THANH CONG.")
            print("Dang mo trang lich su vi...")

            await page.goto(
                settings.nvc_wallet_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.wait_for_timeout(5000)

            print("\n========== THONG TIN TRANG WALLET ==========")
            print("URL:", page.url)
            print("TITLE:", await page.title())

            # Lay noi dung trang
            body_text = await page.locator("body").inner_text()
            print("\n========== NOI DUNG TRANG ==========")
            print(body_text[:12000])

            # Lay cac nut
            buttons = await page.locator("button").evaluate_all(
                """els => els.map(e => ({
                    text: (e.innerText || e.textContent || '').trim(),
                    type: e.type || '',
                    aria: e.getAttribute('aria-label')
                }))"""
            )

            # Lay cac o nhap va bo loc
            inputs = await page.locator(
                "input, select, textarea"
            ).evaluate_all(
                """els => els.map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    name: e.name || '',
                    id: e.id || '',
                    placeholder: e.placeholder || '',
                    value: e.value || ''
                }))"""
            )

            # Lay tieu de cot va du lieu bang
            tables = await page.locator("table").evaluate_all(
                """els => els.map(table => ({
                    headers: Array.from(
                        table.querySelectorAll('thead th')
                    ).map(e => e.innerText.trim()),
                    rows: Array.from(
                        table.querySelectorAll('tbody tr')
                    ).slice(0, 10).map(row =>
                        Array.from(row.querySelectorAll('th, td'))
                            .map(cell => cell.innerText.trim())
                    )
                }))"""
            )

            print("\n========== BUTTONS ==========")
            print(json.dumps(buttons, ensure_ascii=False, indent=2))

            print("\n========== INPUTS / FILTERS ==========")
            print(json.dumps(inputs, ensure_ascii=False, indent=2))

            print("\n========== TABLES ==========")
            print(json.dumps(tables, ensure_ascii=False, indent=2))

            print("\nGIU TRINH DUYET MO DE KIEM TRA.")
            input("Nhan Enter de dong...")

        except Exception as e:
            print("\nLOI:", repr(e))
            input("Nhan Enter de thoat...")

        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
