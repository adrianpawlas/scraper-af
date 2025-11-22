"""
Main scraper for Abercrombie & Fitch products
"""
import asyncio
import logging
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
import time
from urllib.parse import urljoin, urlparse, parse_qs
import re
from bs4 import BeautifulSoup
import config

logger = logging.getLogger(__name__)


class ProductScraper:
    """Scraper for Abercrombie & Fitch products"""
    
    def __init__(self):
        self.base_url = config.EU_BASE_URL
        self.items_per_page = config.ITEMS_PER_PAGE
        
    async def init_browser(self) -> Browser:
        """Initialize Playwright browser"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=config.HEADLESS,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        return browser
    
    async def get_product_urls_from_page(self, page: Page, category_url: str) -> List[str]:
        """
        Extract all product URLs from a category listing page
        
        Args:
            page: Playwright page object
            category_url: URL of the category page
            
        Returns:
            List of product URLs
        """
        product_urls = []
        
        try:
            logger.info(f"Loading category page: {category_url}")
            await page.goto(category_url, wait_until="networkidle", timeout=config.BROWSER_TIMEOUT)
            await asyncio.sleep(2)  # Wait for dynamic content
            
            # Wait for products to load - try waiting for specific elements
            try:
                # Wait for product grid or product cards to appear
                await page.wait_for_selector('a[href*="/p/"]', timeout=10000)
            except:
                # If selector doesn't appear, wait a bit more for dynamic content
                await asyncio.sleep(3)
            
            # Get page content after waiting
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find product links - Abercrombie typically uses specific selectors
            # Try multiple possible selectors
            product_links = []
            
            # Method 1: Look for links containing /p/ (product pages)
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                # Check for product URLs - they contain /p/ and product codes
                if '/p/' in href and href not in product_links:
                    # Filter out non-product links
                    if any(x in href.lower() for x in ['/p/', 'product', 'item']) and 'category' not in href.lower():
                        full_url = urljoin(self.base_url, href)
                        product_links.append(full_url)
            
            # Method 2: Look for data attributes that might contain product URLs
            product_elements = soup.find_all(attrs={'data-product-url': True})
            for elem in product_elements:
                url = elem.get('data-product-url')
                if url and '/p/' in url:
                    full_url = urljoin(self.base_url, url)
                    if full_url not in product_links:
                        product_links.append(full_url)
            
            # Method 3: Try to find product links via JavaScript evaluation
            try:
                js_product_urls = await page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href*="/p/"]'));
                        return links.map(link => link.href).filter(href => href && href.includes('/p/'));
                    }
                """)
                for url in js_product_urls:
                    if url and '/p/' in url and url not in product_links:
                        product_links.append(url)
            except Exception as e:
                logger.debug(f"JavaScript extraction failed: {e}")
            
            # Remove duplicates and clean URLs
            seen = set()
            for url in product_links:
                # Remove query parameters for consistency
                parsed = urlparse(url)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if clean_url not in seen and '/p/' in clean_url:
                    seen.add(clean_url)
                    product_urls.append(clean_url)
            
            logger.info(f"Found {len(product_urls)} products on page")
            
        except Exception as e:
            logger.error(f"Error extracting product URLs from {category_url}: {e}")
        
        return product_urls
    
    async def get_all_product_urls(self, category_url: str, max_pages: int = None) -> List[str]:
        """
        Get all product URLs from a category by paginating through all pages
        
        Args:
            category_url: Base category URL
            max_pages: Maximum number of pages to scrape (None for all)
            
        Returns:
            List of all product URLs
        """
        browser = await self.init_browser()
        page = await browser.new_page()
        
        all_product_urls = []
        page_num = 0
        
        try:
            # First, get categoryId from the first page
            await page.goto(category_url, wait_until="networkidle", timeout=config.BROWSER_TIMEOUT)
            await asyncio.sleep(2)
            
            current_url = page.url
            parsed = urlparse(current_url)
            query_params = parse_qs(parsed.query)
            
            category_id = query_params.get('categoryId', [None])[0]
            if not category_id:
                # Try to extract from page content or URL structure
                # For mens category, categoryId seems to be 84605
                if 'mens' in category_url.lower():
                    category_id = '84605'
                elif 'womens' in category_url.lower():
                    category_id = '84606'  # Common pattern, may need adjustment
                else:
                    category_id = '84605'  # Default
            
            logger.info(f"Using categoryId: {category_id}")
            
            # Paginate through all pages
            start = 0
            while True:
                if max_pages and page_num >= max_pages:
                    break
                
                # Build paginated URL
                paginated_url = f"{category_url}?categoryId={category_id}&filtered=true&rows={self.items_per_page}&start={start}"
                
                logger.info(f"Scraping page {page_num + 1} (start={start})")
                
                # Get product URLs from this page
                product_urls = await self.get_product_urls_from_page(page, paginated_url)
                
                if not product_urls:
                    logger.info("No more products found, stopping pagination")
                    break
                
                all_product_urls.extend(product_urls)
                logger.info(f"Total products found so far: {len(all_product_urls)}")
                
                # Check if there are more pages
                # Try to find next page button
                try:
                    await page.goto(paginated_url, wait_until="networkidle", timeout=config.BROWSER_TIMEOUT)
                    await asyncio.sleep(2)
                    
                    # Look for next page button/arrow
                    next_button = await page.query_selector('button[aria-label*="next" i], button[aria-label*="Next" i], a[aria-label*="next" i], a[aria-label*="Next" i]')
                    if not next_button:
                        # Try other selectors
                        next_button = await page.query_selector('[data-testid*="next"], .pagination-next, .next-page')
                    
                    if not next_button:
                        # Check if we've reached the end
                        content = await page.content()
                        if 'start=' + str(start + self.items_per_page) not in content:
                            logger.info("Reached last page")
                            break
                    
                    # If we got the same number of products as items_per_page, likely more pages
                    if len(product_urls) < self.items_per_page:
                        logger.info("Fewer products than items per page, likely last page")
                        break
                    
                except Exception as e:
                    logger.warning(f"Error checking for next page: {e}")
                
                start += self.items_per_page
                page_num += 1
                
                # Safety limit
                if start > 1000:  # Reasonable limit
                    logger.warning("Reached safety limit for pagination")
                    break
            
            # Remove duplicates
            all_product_urls = list(dict.fromkeys(all_product_urls))
            logger.info(f"Total unique products found: {len(all_product_urls)}")
            
        finally:
            await browser.close()
        
        return all_product_urls
    
    async def scrape_product_details(self, page: Page, product_url: str) -> Optional[Dict]:
        """
        Scrape detailed information from a product page
        
        Args:
            page: Playwright page object
            product_url: URL of the product page
            
        Returns:
            Dictionary with product details or None if failed
        """
        try:
            logger.info(f"Scraping product: {product_url}")
            await page.goto(product_url, wait_until="networkidle", timeout=config.BROWSER_TIMEOUT)
            await asyncio.sleep(2)  # Wait for dynamic content
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            product_data = {
                'product_url': product_url,
                'source': config.SOURCE_NAME,
                'brand': config.BRAND_NAME,
                'second_hand': config.SECOND_HAND,
            }
            
            # Extract title
            title_selectors = [
                'h1[data-testid="product-title"]',
                'h1.product-title',
                'h1',
                '[data-testid="product-name"]',
                '.product-name',
            ]
            title = None
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                # Try to find in meta tags
                meta_title = soup.find('meta', property='og:title')
                if meta_title:
                    title = meta_title.get('content', '').strip()
            
            product_data['title'] = title or 'Unknown Product'
            
            # Extract price - try multiple methods
            price = None
            currency = None
            
            # Method 1: Try selectors
            price_selectors = [
                '[data-testid="product-price"]',
                '.product-price',
                '.price',
                '[class*="price"]',
                '[data-testid="price"]',
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Extract price number and currency
                    price_match = re.search(r'[\d,]+\.?\d*', price_text.replace(',', ''))
                    if price_match:
                        try:
                            price = float(price_match.group().replace(',', ''))
                            # Extract currency
                            if '€' in price_text or 'EUR' in price_text.upper():
                                currency = 'EUR'
                            elif '$' in price_text or 'USD' in price_text.upper():
                                currency = 'USD'
                            elif '£' in price_text or 'GBP' in price_text.upper():
                                currency = 'GBP'
                            else:
                                currency = 'EUR'  # Default for EU site
                            break
                        except ValueError:
                            continue
            
            # Method 2: Try to extract from page content using regex
            if not price:
                page_text = soup.get_text()
                # Look for price patterns like "€45.90" or "45,90 €"
                price_patterns = [
                    r'€\s*([\d,]+\.?\d*)',
                    r'([\d,]+\.?\d*)\s*€',
                    r'\$\s*([\d,]+\.?\d*)',
                    r'([\d,]+\.?\d*)\s*\$',
                ]
                for pattern in price_patterns:
                    match = re.search(pattern, page_text)
                    if match:
                        try:
                            price_str = match.group(1).replace(',', '')
                            price = float(price_str)
                            if '€' in pattern or 'EUR' in page_text:
                                currency = 'EUR'
                            elif '$' in pattern or 'USD' in page_text:
                                currency = 'USD'
                            else:
                                currency = 'EUR'
                            break
                        except ValueError:
                            continue
            
            # Try JSON-LD structured data
            if not price:
                json_ld = soup.find('script', type='application/ld+json')
                if json_ld:
                    import json
                    try:
                        data = json.loads(json_ld.string)
                        if isinstance(data, dict):
                            offers = data.get('offers', {})
                            if isinstance(offers, dict):
                                price = offers.get('price')
                                currency = offers.get('priceCurrency', 'EUR')
                    except:
                        pass
            
            product_data['price'] = price
            product_data['currency'] = currency or 'EUR'
            
            # Extract image URL
            image_selectors = [
                'img[data-testid="product-image"]',
                'img.product-image',
                '.product-image img',
                'meta[property="og:image"]',
            ]
            image_url = None
            
            # Try meta tag first
            og_image = soup.find('meta', property='og:image')
            if og_image:
                image_url = og_image.get('content', '').strip()
            
            # Try img tags
            if not image_url:
                for selector in image_selectors:
                    img_elem = soup.select_one(selector)
                    if img_elem:
                        image_url = img_elem.get('src') or img_elem.get('data-src') or img_elem.get('data-lazy-src')
                        if image_url:
                            image_url = urljoin(self.base_url, image_url)
                            break
            
            if not image_url:
                # Fallback: find first large image
                images = soup.find_all('img')
                for img in images:
                    src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if src and ('product' in src.lower() or 'item' in src.lower()):
                        image_url = urljoin(self.base_url, src)
                        break
            
            product_data['image_url'] = image_url or ''
            
            # Extract description
            description_selectors = [
                '[data-testid="product-description"]',
                '.product-description',
                '.product-details',
                'meta[property="og:description"]',
            ]
            description = None
            for selector in description_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    break
            
            if not description:
                meta_desc = soup.find('meta', property='og:description')
                if meta_desc:
                    description = meta_desc.get('content', '').strip()
            
            product_data['description'] = description
            
            # Extract gender from URL or category
            gender = 'OTHER'
            if '/mens' in product_url or '/mens/' in product_url:
                gender = 'MAN'
            elif '/womens' in product_url or '/womens/' in product_url:
                gender = 'WOMAN'
            else:
                # Try to find in breadcrumbs or category
                breadcrumbs = soup.find_all(['nav', 'ol', 'ul'], class_=re.compile('breadcrumb', re.I))
                for breadcrumb in breadcrumbs:
                    text = breadcrumb.get_text().lower()
                    if 'men' in text or 'mens' in text:
                        gender = 'MAN'
                        break
                    elif 'women' in text or 'womens' in text:
                        gender = 'WOMAN'
                        break
            
            product_data['gender'] = gender
            
            # Extract category
            category = None
            category_elem = soup.find(['nav', 'ol'], class_=re.compile('breadcrumb', re.I))
            if category_elem:
                links = category_elem.find_all('a')
                if links:
                    category = links[-1].get_text(strip=True)
            
            product_data['category'] = category
            
            # Extract size information
            size_info = None
            size_selectors = [
                '[data-testid="size-selector"]',
                '.size-selector',
                '.product-sizes',
            ]
            for selector in size_selectors:
                size_elem = soup.select_one(selector)
                if size_elem:
                    sizes = [s.get_text(strip=True) for s in size_elem.find_all(['button', 'span', 'div'])]
                    if sizes:
                        size_info = ', '.join(sizes)
                        break
            
            product_data['size'] = size_info
            
            # Collect all metadata
            metadata = {
                'url': product_url,
                'title': product_data.get('title'),
                'price': price,
                'currency': currency,
                'description': description,
                'category': category,
                'gender': gender,
                'size': size_info,
            }
            
            # Try to extract additional info from JSON-LD
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                import json
                try:
                    data = json.loads(json_ld.string)
                    metadata['structured_data'] = data
                except:
                    pass
            
            product_data['metadata'] = str(metadata) if metadata else None
            
            # Generate ID from product URL
            # Extract product ID from URL or use hash
            import hashlib
            product_id = hashlib.md5(product_url.encode()).hexdigest()
            product_data['id'] = product_id
            
            logger.info(f"Successfully scraped: {product_data['title']}")
            return product_data
            
        except Exception as e:
            logger.error(f"Error scraping product {product_url}: {e}")
            return None
    
    async def scrape_all_products(self, category_url: str, max_pages: int = None) -> List[Dict]:
        """
        Scrape all products from a category
        
        Args:
            category_url: Base category URL
            max_pages: Maximum pages to scrape
            
        Returns:
            List of product dictionaries
        """
        # First, get all product URLs
        product_urls = await self.get_all_product_urls(category_url, max_pages)
        
        if not product_urls:
            logger.warning("No product URLs found")
            return []
        
        # Scrape each product
        browser = await self.init_browser()
        page = await browser.new_page()
        
        products = []
        try:
            for i, url in enumerate(product_urls, 1):
                logger.info(f"Scraping product {i}/{len(product_urls)}")
                product = await self.scrape_product_details(page, url)
                if product:
                    products.append(product)
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(1)
        finally:
            await browser.close()
        
        return products

