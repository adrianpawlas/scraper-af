import asyncio
import json
from playwright.async_api import async_playwright

async def test_mens_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print("Going to men's category page...")
            await page.goto("https://www.abercrombie.com/shop/eu/mens", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(10)  # Wait longer for dynamic content

            print("Page title:", await page.title())

            # Check for various elements
            print("\n=== Checking for different elements ===")

            # Look for any links
            all_links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links.slice(0, 50).map(link => ({
                        href: link.href,
                        text: (link.textContent || '').trim().substring(0, 100),
                        className: link.className
                    }));
                }
            """)

            print(f"\nFirst 50 links found: {len(all_links)}")
            for i, link in enumerate(all_links[:20]):
                print(f"{i+1}. {link['text'][:50]} -> {link['href']}")

            # Look for category-related elements - focus on men's section
            categories = await page.evaluate("""
                () => {
                    const cats = [];
                    const selectors = [
                        '[data-category-id]',
                        '[data-testid*="category"]',
                        '.category',
                        '.subcategory',
                        'nav a',
                        '[role="navigation"] a'
                    ];

                    for (const selector of selectors) {
                        const elements = Array.from(document.querySelectorAll(selector));
                        for (const el of elements) {
                            if (el.tagName === 'A') {
                                cats.push({
                                    selector: selector,
                                    href: el.href,
                                    text: (el.textContent || '').trim(),
                                    categoryId: el.getAttribute('data-category-id') || ''
                                });
                            } else {
                                cats.push({
                                    selector: selector,
                                    text: (el.textContent || '').trim(),
                                    categoryId: el.getAttribute('data-category-id') || '',
                                    href: el.querySelector('a')?.href || ''
                                });
                            }
                        }
                    }

                    // Get all links that contain '/mens' anywhere
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    const mensLinks = allLinks.filter(link =>
                        link.href && (link.href.includes('/mens') || link.href.includes('mens-'))
                    ).map(link => ({
                        href: link.href,
                        text: (link.textContent || '').trim(),
                        categoryId: link.getAttribute('data-category-id') || ''
                    }));

                    return {
                        all: cats.slice(0, 10),
                        mens: mensLinks.slice(0, 30)
                    };
                }
            """)

            print(f"\nAll category-related elements: {len(categories['all'])}")
            for cat in categories['all']:
                print(f"- {cat['selector']}: {cat['text']} -> {cat['href']} (ID: {cat['categoryId']})")

            print(f"\nMen's categories: {len(categories['mens'])}")
            for cat in categories['mens']:
                print(f"- {cat['text']} -> {cat['href']} (ID: {cat['categoryId']})")

            # Check for script data or JSON
            scripts = await page.evaluate("""
                () => {
                    const scripts = Array.from(document.querySelectorAll('script[type="application/json"], script:not([src])'));
                    const data = [];
                    for (const script of scripts) {
                        const content = script.textContent || '';
                        if (content.includes('category') || content.includes('subcategory') || content.length > 500) {
                            data.push(content.substring(0, 200) + '...');
                        }
                    }
                    return data.slice(0, 5);
                }
            """)

            print(f"\nJSON scripts with category data: {len(scripts)}")
            for i, script in enumerate(scripts):
                print(f"Script {i+1}: {script}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_mens_page())
