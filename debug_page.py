"""
Debug script to see what's actually on the page
"""
import asyncio
from playwright.async_api import async_playwright

async def debug_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Show browser
        page = await browser.new_page()
        
        url = "https://www.abercrombie.com/shop/eu/mens?categoryId=84605&filtered=true&rows=90&start=0"
        
        print(f"Loading: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Wait a bit
        await asyncio.sleep(5)
        
        # Get page info
        title = await page.title()
        current_url = page.url
        print(f"\nPage title: {title}")
        print(f"Current URL: {current_url}")
        
        # Check if redirected
        if current_url != url:
            print(f"⚠️ Redirected from {url} to {current_url}")
        
        # Get page text content
        body_text = await page.evaluate("() => document.body.innerText")
        print(f"\nBody text length: {len(body_text)}")
        print(f"First 500 chars: {body_text[:500]}")
        
        # Check for common bot detection messages
        if any(word in body_text.lower() for word in ['captcha', 'verify', 'robot', 'blocked', 'access denied']):
            print("\n⚠️ Possible bot detection!")
        
        # Take screenshot
        await page.screenshot(path="debug_screenshot.png")
        print("\nScreenshot saved to debug_screenshot.png")
        
        # Check for links
        links_count = await page.evaluate("() => document.querySelectorAll('a').length")
        print(f"\nTotal <a> tags: {links_count}")
        
        # Check for product links specifically
        product_links = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return {
                    total: links.length,
                    with_p: links.filter(l => l.href.includes('/p/')).length,
                    sample: links.slice(0, 10).map(l => l.href)
                };
            }
        """)
        print(f"Links with '/p/': {product_links['with_p']}")
        if product_links['sample']:
            print("Sample links:")
            for link in product_links['sample']:
                print(f"  - {link}")
        
        # Wait for user to see
        print("\nBrowser will stay open for 30 seconds...")
        await asyncio.sleep(30)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_page())

