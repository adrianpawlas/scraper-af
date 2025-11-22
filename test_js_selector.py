import asyncio
from playwright.async_api import async_playwright

async def test_js_selector():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print("Going to men's category page...")
            await page.goto("https://www.abercrombie.com/shop/eu/mens", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(10)

            # Test the same JavaScript that's used in the scraper
            result = await page.evaluate("""
                () => {
                    const subcats = [];
                    const seen = new Set();

                    // Try multiple selectors
                    const selectors = [
                        'a[href*="categoryId"]',
                        'a[href*="/mens-"]',
                        'a[href*="/womens-"]',
                        '[data-category-id]',
                        '.category-link',
                        'nav a',
                        'a[class*="category"]'
                    ];

                    let links = [];
                    for (const selector of selectors) {
                        try {
                            const found = Array.from(document.querySelectorAll(selector));
                            console.log(`Selector "${selector}" found ${found.length} elements`);
                            links.push(...found);
                        } catch (e) {
                            console.log(`Selector "${selector}" failed: ${e.message}`);
                        }
                    }

                    // Also try to find links in navigation menus
                    const navLinks = Array.from(document.querySelectorAll('nav a, [role="navigation"] a'));
                    console.log(`Navigation links found: ${navLinks.length}`);
                    links.push(...navLinks);

                    console.log(`Total links collected: ${links.length}`);

                    for (const link of links) {
                        const href = link.href || link.getAttribute('href') || '';
                        if (!href) continue;

                        // Skip product links (they contain /p/ and product IDs)
                        if (href.includes('/p/') || /\\d{8,}/.test(href)) continue;

                        // Check if it has categoryId in URL or is a category link
                        if (href.includes('categoryId=') || href.match(/\\/(mens|womens)-[^\\/]+/)) {
                            if (!seen.has(href)) {
                                seen.add(href);
                                try {
                                    const url = new URL(href, window.location.origin);
                                    const categoryId = url.searchParams.get('categoryId');

                                    // If no categoryId in URL, try to extract from path or data attributes
                                    let catId = categoryId;
                                    if (!catId) {
                                        // Try data attributes first
                                        const dataId = link.getAttribute('data-category-id') ||
                                                     link.getAttribute('data-id') ||
                                                     link.closest('[data-category-id]')?.getAttribute('data-category-id');
                                        if (dataId) catId = dataId;
                                    }

                                    // For men's categories, try to map known category IDs
                                    if (!catId && href.includes('/mens-')) {
                                        const path = href.split('/').pop();
                                        const knownMappings = {
                                            'mens-new-arrivals': '84591',
                                            'mens-tops-new-arrivals': '84587',
                                            'mens-bottoms-new-arrivals': '84588',
                                            'mens-bottoms': '6570775'
                                        };
                                        catId = knownMappings[path] || '';
                                    }

                                    if (catId || href.match(/\\/(mens|womens)-[^\\/]+/)) {
                                        subcats.push({
                                            url: href,
                                            categoryId: catId || '',
                                            name: (link.textContent || link.innerText || '').trim() || href.split('/').pop()
                                        });
                                    }
                                } catch (e) {
                                    // If URL parsing fails, still try to add if it looks like a category link
                                    if (href.match(/\\/(mens|womens)-[^\\/]+/)) {
                                        subcats.push({
                                            url: href,
                                            categoryId: '',
                                            name: (link.textContent || link.innerText || '').trim() || href.split('/').pop()
                                        });
                                    }
                                }
                            }
                        }
                    }

                    console.log(`Final subcategories found: ${subcats.length}`);
                    return subcats;
                }
            """)

            print(f"JavaScript returned {len(result)} subcategories:")
            for cat in result[:10]:  # Show first 10
                print(f"- {cat['name']} -> {cat['url']} (ID: {cat['categoryId']})")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_js_selector())
