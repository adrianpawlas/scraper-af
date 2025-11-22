"""
Test script to debug API calls
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # Track all API calls
        api_calls = []
        
        async def handle_response(response):
            url = response.url
            if '/api/bff/catalog' in url:
                try:
                    status = response.status
                    data = await response.json() if status == 200 else None
                    api_calls.append({
                        'url': url,
                        'status': status,
                        'data': data
                    })
                    print(f"\n=== API CALL FOUND ===")
                    print(f"Status: {status}")
                    print(f"URL: {url[:200]}")
                    if data:
                        print(f"Data keys: {list(data.keys())}")
                        if 'data' in data:
                            print(f"Data.data keys: {list(data['data'].keys())}")
                            if 'category' in data['data']:
                                cat = data['data']['category']
                                print(f"Category keys: {list(cat.keys())}")
                                if 'products' in cat:
                                    print(f"Products count: {len(cat['products'])}")
                except Exception as e:
                    print(f"Error processing response: {e}")
        
        page.on("response", handle_response)
        
        url = "https://www.abercrombie.com/shop/eu/mens"
        print(f"Loading: {url}")
        await page.goto(url, wait_until="load", timeout=60000)
        await asyncio.sleep(5)
        
        # Scroll to trigger product loading
        print("Scrolling to load products...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(5)
        
        # Wait for network to be idle
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except:
            pass
        
        await asyncio.sleep(5)
        
        print(f"\n=== SUMMARY ===")
        print(f"Found {len(api_calls)} API calls")
        
        if api_calls:
            # Save first successful call
            for call in api_calls:
                if call['status'] == 200 and call['data']:
                    print(f"\n=== SUCCESSFUL API RESPONSE ===")
                    print(json.dumps(call['data'], indent=2)[:2000])
                    break
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test())

