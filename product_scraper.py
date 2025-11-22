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
        """Initialize Playwright browser with stealth settings"""
        playwright = await async_playwright().start()
        # Try Firefox first as it's often less detectable, fallback to Chromium
        try:
            browser = await playwright.firefox.launch(
                headless=config.HEADLESS,
                args=['--no-sandbox'] if config.HEADLESS else []
            )
            logger.info("Using Firefox browser")
        except Exception as e:
            logger.warning(f"Firefox not available, using Chromium: {e}")
            browser = await playwright.chromium.launch(
                headless=config.HEADLESS,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            logger.info("Using Chromium browser")
        return browser
    
    async def create_stealth_page(self, browser: Browser) -> Page:
        """Create a page with comprehensive stealth settings to avoid detection"""
        # Use Firefox user agent if using Firefox, Chrome otherwise
        browser_type = browser.browser_type.name if hasattr(browser, 'browser_type') else 'chromium'
        
        if browser_type == 'firefox':
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
        else:
            user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=user_agent,
            locale='en-US',
            timezone_id='America/New_York',
            color_scheme='light',
        )
        page = await context.new_page()
        
        # Comprehensive anti-detection script (only for Chromium)
        if browser_type == 'chromium':
            await page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
            """)
        
        return page
    
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
            # Use load event instead of domcontentloaded for better compatibility
            await page.goto(category_url, wait_until="load", timeout=config.BROWSER_TIMEOUT)
            
            # Wait for page to be interactive and content to load
            await asyncio.sleep(10)
            
            # Try to wait for product links to appear with multiple attempts
            product_links_found = False
            for attempt in range(3):
                try:
                    await page.wait_for_selector('a[href*="/p/"]', timeout=5000)
                    logger.debug(f"Product links detected on page (attempt {attempt + 1})")
                    product_links_found = True
                    break
                except:
                    if attempt < 2:
                        logger.debug(f"Waiting for products... (attempt {attempt + 1})")
                        await asyncio.sleep(3)
                        # Try scrolling to trigger loading
                        await page.evaluate("window.scrollBy(0, 300)")
            
            if not product_links_found:
                logger.warning("Product links not found after waiting, continuing anyway...")
            
            # Scroll down gradually to trigger lazy loading
            await page.evaluate("""
                async () => {
                    for (let i = 0; i < 8; i++) {
                        window.scrollBy(0, 400);
                        await new Promise(resolve => setTimeout(resolve, 300));
                    }
                }
            """)
            await asyncio.sleep(3)
            
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            
            # Try to wait for product elements - check multiple possible selectors
            product_selectors = [
                'a[href*="/p/"]',
                '[data-testid*="product"]',
                '[class*="product-card"]',
                '[class*="product-item"]',
            ]
            
            found_products = False
            for selector in product_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    found_products = True
                    logger.debug(f"Found products using selector: {selector}")
                    break
                except:
                    continue
            
            if not found_products:
                logger.warning("No product selectors found, continuing anyway...")
                await asyncio.sleep(2)  # Wait a bit more
            
            # Primary method: Use JavaScript evaluation (most reliable for dynamic content)
            product_links = []
            try:
                # Try multiple times with delays if needed
                for attempt in range(2):
                    js_product_urls = await page.evaluate("""
                        () => {
                            try {
                                const links = Array.from(document.querySelectorAll('a[href*="/p/"]'));
                                const urls = [];
                                
                                for (const link of links) {
                                    let href = link.href || link.getAttribute('href');
                                    if (!href) continue;
                                    
                                    // Handle relative URLs
                                    if (href.startsWith('/')) {
                                        href = window.location.origin + href;
                                    } else if (!href.startsWith('http')) {
                                        try {
                                            href = new URL(href, window.location.href).href;
                                        } catch {
                                            continue;
                                        }
                                    }
                                    
                                    // Filter out non-product links
                                    if (!href.includes('/p/') || href.includes('category')) {
                                        continue;
                                    }
                                    
                                    // Remove query parameters and fragments
                                    try {
                                        const url = new URL(href);
                                        urls.push(url.origin + url.pathname);
                                    } catch {
                                        const clean = href.split('?')[0].split('#')[0];
                                        if (clean.includes('/p/')) {
                                            urls.push(clean);
                                        }
                                    }
                                }
                                
                                // Remove duplicates
                                return [...new Set(urls)];
                            } catch (e) {
                                return [];
                            }
                        }
                    """)
                    
                    if js_product_urls and len(js_product_urls) > 0:
                        product_links.extend(js_product_urls)
                        logger.info(f"JavaScript found {len(js_product_urls)} product URLs")
                        break
                    elif attempt == 0:
                        logger.debug("No products found, waiting and retrying...")
                        await asyncio.sleep(3)
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(2)
                else:
                    logger.warning("JavaScript found 0 product URLs after retries")
            except Exception as e:
                logger.warning(f"JavaScript extraction failed: {e}", exc_info=True)
            
            # Fallback: Parse HTML if JavaScript didn't find anything
            if not product_links:
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Look for links containing /p/ (product pages)
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href', '')
                    if '/p/' in href and 'category' not in href.lower():
                        full_url = urljoin(self.base_url, href)
                        parsed = urlparse(full_url)
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if clean_url not in product_links:
                            product_links.append(clean_url)
                
                # Look for data attributes
                product_elements = soup.find_all(attrs={'data-product-url': True})
                for elem in product_elements:
                    url = elem.get('data-product-url')
                    if url and '/p/' in url:
                        full_url = urljoin(self.base_url, url)
                        parsed = urlparse(full_url)
                        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if clean_url not in product_links:
                            product_links.append(clean_url)
            
            # Remove duplicates and clean URLs
            seen = set()
            for url in product_links:
                # Remove query parameters and fragments for consistency
                try:
                    parsed = urlparse(url)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    # Only add if it's a product URL (contains /p/ and looks like a product)
                    if clean_url not in seen and '/p/' in clean_url and 'category' not in clean_url.lower():
                        seen.add(clean_url)
                        product_urls.append(clean_url)
                except Exception as e:
                    logger.debug(f"Error parsing URL {url}: {e}")
                    continue
            
            logger.info(f"Found {len(product_urls)} products on page")
            if len(product_urls) == 0:
                # Debug: log what we found
                logger.debug(f"Total links found in HTML: {len(all_links)}")
                logger.debug(f"Product elements with data attributes: {len(product_elements)}")
                # Try one more time with a longer wait
                await asyncio.sleep(5)
                content2 = await page.content()
                soup2 = BeautifulSoup(content2, 'html.parser')
                links2 = soup2.find_all('a', href=lambda x: x and '/p/' in x)
                logger.debug(f"After additional wait, found {len(links2)} links with /p/")
            
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
        page = await self.create_stealth_page(browser)
        
        all_product_urls = []
        page_num = 0
        
        try:
            # First, get categoryId from the first page
            await page.goto(category_url, wait_until="domcontentloaded", timeout=config.BROWSER_TIMEOUT)
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
        page = await self.create_stealth_page(browser)
        
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

