#!/usr/bin/env python3
"""Debug script to test product extraction"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from playwright.async_api import async_playwright


async def test_product_extraction():
    """Test product extraction from Abercrombie & Fitch"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "https://www.abercrombie.com/shop/eu/mens"
        print(f"Navigating to: {url}")
        
        await page.goto(url, wait_until='networkidle')
        await asyncio.sleep(5)
        
        # Scroll to load content
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(3)
        
        # Find all links
        all_links = await page.query_selector_all('a')
        print(f"\nTotal links found: {len(all_links)}")
        
        # Find product links
        product_links = []
        for link in all_links:
            href = await link.get_attribute('href')
            if href and ('/p/' in href or '/shop/' in href):
                product_links.append(href)
        
        print(f"\nProduct-related links found: {len(product_links)}")
        for i, link in enumerate(product_links[:10]):
            print(f"  {i+1}. {link}")
        
        # Check page content
        title = await page.title()
        print(f"\nPage title: {title}")
        
        # Check for specific selectors
        selectors_to_try = [
            'a[href*="/p/"]',
            'a[href*="/shop/eu/p/"]',
            '[data-testid*="product"]',
            '.product-card',
            'article',
            'main'
        ]
        
        print("\nSelector results:")
        for selector in selectors_to_try:
            try:
                elements = await page.query_selector_all(selector)
                print(f"  {selector}: {len(elements)} elements")
            except Exception as e:
                print(f"  {selector}: Error - {e}")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_product_extraction())
