"""
Local test script for the scraper (without embeddings and database)
"""
import asyncio
import logging
import sys
from product_scraper import ProductScraper
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def test_scraper():
    """Test the scraper locally"""
    scraper = ProductScraper()
    
    # Test category URL
    category_url = "https://www.abercrombie.com/shop/eu/mens"
    
    logger.info("="*60)
    logger.info("Testing product URL discovery...")
    logger.info("="*60)
    
    # Test getting product URLs (limit to 1 page for testing)
    product_urls = await scraper.get_all_product_urls(category_url, max_pages=1)
    
    logger.info(f"\nFound {len(product_urls)} product URLs")
    
    if product_urls:
        logger.info("\nFirst 5 product URLs:")
        for i, url in enumerate(product_urls[:5], 1):
            logger.info(f"{i}. {url}")
        
        # Test scraping details from first product
        logger.info("\n" + "="*60)
        logger.info("Testing product detail scraping...")
        logger.info("="*60)
        
        browser = await scraper.init_browser()
        page = await browser.new_page()
        
        try:
            test_url = product_urls[0]
            logger.info(f"\nScraping: {test_url}")
            
            product = await scraper.scrape_product_details(page, test_url)
            
            if product:
                logger.info("\n✅ Product scraped successfully!")
                logger.info("\nProduct Data:")
                logger.info(json.dumps(product, indent=2, ensure_ascii=False))
            else:
                logger.error("❌ Failed to scrape product")
        finally:
            await browser.close()
    else:
        logger.error("❌ No product URLs found!")
        logger.info("\nTrying to debug...")
        
        # Try to see what's on the page
        browser = await scraper.init_browser()
        page = await browser.new_page()
        
        try:
            test_url = f"{category_url}?categoryId=84605&filtered=true&rows=90&start=0"
            logger.info(f"Loading: {test_url}")
            await page.goto(test_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)  # Wait longer
            
            # Get page content and check for product links
            content = await page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            
            # Count links with /p/
            links_with_p = soup.find_all('a', href=lambda x: x and '/p/' in x)
            logger.info(f"Found {len(links_with_p)} links containing '/p/'")
            
            if links_with_p:
                logger.info("\nFirst 5 links found:")
                for i, link in enumerate(links_with_p[:5], 1):
                    logger.info(f"{i}. {link.get('href', 'N/A')}")
            
            # Try JavaScript evaluation
            js_result = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href*="/p/"]'));
                    return {
                        count: links.length,
                        first5: links.slice(0, 5).map(l => l.href)
                    };
                }
            """)
            logger.info(f"\nJavaScript found {js_result['count']} product links")
            if js_result['first5']:
                logger.info("First 5 from JS:")
                for i, url in enumerate(js_result['first5'], 1):
                    logger.info(f"{i}. {url}")
            
            # Check for API calls that might load products
            logger.info("\nChecking for API calls...")
            network_requests = []
            page.on("response", lambda response: network_requests.append({
                "url": response.url,
                "status": response.status
            }))
            
            # Wait a bit more and check again
            await asyncio.sleep(5)
            
            # Try to find product containers
            product_containers = await page.evaluate("""
                () => {
                    // Look for common product container classes
                    const selectors = [
                        '[class*="product"]',
                        '[class*="item"]',
                        '[class*="card"]',
                        '[data-testid*="product"]',
                        '[id*="product"]'
                    ];
                    const results = {};
                    selectors.forEach(sel => {
                        const elements = document.querySelectorAll(sel);
                        results[sel] = elements.length;
                    });
                    return results;
                }
            """)
            logger.info(f"\nProduct container counts: {product_containers}")
            
            # Try to get all links on the page
            all_links = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href]'));
                    return {
                        total: links.length,
                        with_p: links.filter(l => l.href.includes('/p/')).length,
                        sample: links.slice(0, 10).map(l => ({href: l.href, text: l.textContent?.trim().substring(0, 50)}))
                    };
                }
            """)
            logger.info(f"\nTotal links on page: {all_links['total']}")
            logger.info(f"Links with '/p/': {all_links['with_p']}")
            if all_links['sample']:
                logger.info("\nSample links:")
                for i, link in enumerate(all_links['sample'], 1):
                    logger.info(f"{i}. {link['href'][:100]} - '{link['text']}'")
        
        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_scraper())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

