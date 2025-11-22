"""
Simple test - just try to get product URLs
"""
import asyncio
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Test with visible browser
        page = await browser.new_page()
        
        url = "https://www.abercrombie.com/shop/eu/mens?categoryId=84605&filtered=true&rows=90&start=0"
        
        print(f"Loading: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)  # Wait for content
        
        # Scroll
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)
        
        # Get product URLs
        urls = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href*="/p/"]'));
                return [...new Set(links.map(l => {
                    const url = new URL(l.href);
                    return url.origin + url.pathname;
                }).filter(href => href.includes('/p/') && !href.includes('category')))];
            }
        """)
        
        print(f"\nFound {len(urls)} product URLs")
        if urls:
            print("\nFirst 5:")
            for i, u in enumerate(urls[:5], 1):
                print(f"{i}. {u}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test())

