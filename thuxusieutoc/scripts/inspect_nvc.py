
import asyncio
import json

from playwright.async_api import async_playwright
from app.config import settings


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto(
            settings.nvc_login_url,
            wait_until="domcontentloaded",
            timeout=settings.browser_timeout,
        )

        await page.wait_for_timeout(8000)

        result = await page.evaluate("""() => {
            const labels = Array.from(
                document.querySelectorAll("label")
            );

            const candidates = Array.from(
                document.querySelectorAll(
                    "input, textarea, button, [role], [contenteditable], " +
                    "div, span"
                )
            ).filter(el => {
                const text = (el.innerText || el.textContent || "")
                    .trim().replace(/\\\\s+/g, " ");

                const placeholder = el.getAttribute("placeholder") || "";
                const aria = el.getAttribute("aria-label") || "";
                const name = el.getAttribute("name") || "";

                return (
                    /Tên Đăng Nhập|Mật Khẩu|Đăng Nhập/i.test(text) ||
                    /Tên Đăng Nhập|Mật Khẩu/i.test(
                        placeholder + " " + aria + " " + name
                    )
                );
            }).slice(0, 40);

            return {
                labels: labels.map(el => ({
                    text: (el.innerText || "").trim(),
                    html: el.outerHTML.slice(0, 1000)
                })),
                candidates: candidates.map(el => ({
                    tag: el.tagName,
                    type: el.getAttribute("type"),
                    name: el.getAttribute("name"),
                    id: el.id,
                    placeholder: el.getAttribute("placeholder"),
                    role: el.getAttribute("role"),
                    ariaLabel: el.getAttribute("aria-label"),
                    className: String(el.className || "").slice(0, 300),
                    html: el.outerHTML.slice(0, 1200)
                }))
            };
        }""")

        print("\\n========== LOGIN ELEMENTS ==========")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        print("\\nNhan Enter de dong trinh duyet...")
        input()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
