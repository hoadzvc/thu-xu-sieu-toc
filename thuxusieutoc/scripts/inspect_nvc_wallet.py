
import asyncio
import json

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from app.config import settings


# Chọn tài khoản NVC cần kiểm tra:
# "buy" = tài khoản dùng để gửi Coin cho người mua
# "sell" = tài khoản dùng để nhận Coin từ người bán
ACCOUNT_ROLE = "buy"


async def main():
    if ACCOUNT_ROLE == "buy":
        username = settings.nvc_buy_username
        password = settings.nvc_buy_password.get_secret_value()
    else:
        username = settings.nvc_sell_username
        password = settings.nvc_sell_password.get_secret_value()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False
        )
        page = await browser.new_page()
        page.set_default_timeout(30000)

        try:
            print("Dang mo trang dang nhap NVC...")
            await page.goto(
                settings.nvc_login_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.locator("#login-username").wait_for(state="visible")
            await page.locator("#login-password").wait_for(state="visible")

            print("Dang dien thong tin dang nhap...")
            await page.locator("#login-username").fill(username)
            await page.locator("#login-password").fill(password)

            print("Dang gui yeu cau dang nhap...")
            await page.locator('button[type="submit"]').click()

            # Chờ tối đa 60 giây để website xử lý đăng nhập.
            try:
                await page.wait_for_url(
                    lambda url: "/login" not in url,
                    timeout=60000
                )
            except PlaywrightTimeoutError:
                pass

            await page.wait_for_timeout(3000)

            print("\n========== KIEM TRA DANG NHAP ==========")
            print("URL:", page.url)
            print("TITLE:", await page.title())

            if "/login" in page.url:
                print("CHUA XAC NHAN DUOC DANG NHAP.")
                print("Noi dung trang:")
                print((await page.locator("body").inner_text())[:3000])
                return

            print("Da chuyen khoi trang dang nhap.")

            print("\nDang mo trang lich su vi...")
            await page.goto(
                settings.nvc_wallet_url,
                wait_until="domcontentloaded",
                timeout=60000
            )
            await page.wait_for_timeout(5000)

            result = await page.evaluate("""() => {
                const clean = s => (s || '').trim();

                return {
                    url: location.href,
                    title: document.title,
                    headings: [...document.querySelectorAll('h1,h2,h3')]
                        .map(x => clean(x.innerText)),
                    buttons: [...document.querySelectorAll('button')]
                        .map(x => clean(x.innerText))
                        .filter(Boolean),
                    inputs: [...document.querySelectorAll('input,select')]
                        .map(x => ({
                            tag: x.tagName,
                            type: x.type || '',
                            name: x.name || '',
                            id: x.id || '',
                            placeholder: x.placeholder || '',
                            value: x.value || ''
                        })),
                    tables: [...document.querySelectorAll('table')]
                        .slice(0, 5)
                        .map(table => ({
                            headers: [...table.querySelectorAll('th')]
                                .map(x => clean(x.innerText)),
                            rows: [...table.querySelectorAll('tbody tr')]
                                .slice(0, 5)
                                .map(row => [...row.querySelectorAll('td')]
                                    .map(x => clean(x.innerText)))
                        })),
                    bodyText: document.body.innerText.slice(0, 5000)
                };
            }""")

            print("\n========== KET QUA TRANG WALLET ==========")
            print(json.dumps(result, ensure_ascii=False, indent=2))

        except Exception as e:
            print("\nLOI KIEM TRA:", repr(e))

        finally:
            input("\nNhan Enter de dong trinh duyet...")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
