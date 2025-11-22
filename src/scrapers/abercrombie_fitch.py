"""
Abercrombie & Fitch product scraper
"""

import asyncio
import json
import re
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from loguru import logger

from database.supabase_client import SupabaseClient
from utils.config import Config


class AbercrombieFitchScraper:
    """Abercrombie & Fitch product scraper"""

    def __init__(self, config: Config, dry_run: bool = False):
        """
        Initialize scraper

        Args:
            config: Configuration object
            dry_run: If True, don't save to database
        """
        self.config = config
        self.dry_run = dry_run

        # Initialize components
        self.db_client = SupabaseClient(
            config.database.url,
            config.database.key,
            config.database.table_name
        )

        # Initialize embedder if available
        try:
            from embeddings.siglip_processor import SiglipEmbedder
            self.embedder = SiglipEmbedder(
                config.embeddings.model_name,
                config.embeddings.device,
                config.embeddings.cache_dir
            )
            logger.info("Embeddings enabled")
        except ImportError as e:
            logger.warning(f"Embeddings disabled due to import error: {e}")
            self.embedder = None

        # Browser instance
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

        # Tracking
        self.processed_urls: Set[str] = set()
        self.products_found = 0
        self.products_saved = 0

        logger.info("Abercrombie & Fitch scraper initialized")

    async def _setup_browser(self):
        """Setup Playwright browser"""
        import os
        
        # Detect CI environment and use headless mode
        is_ci = os.getenv('CI') == 'true' or os.getenv('GITHUB_ACTIONS') == 'true'
        headless_mode = is_ci or os.getenv('HEADLESS', 'true').lower() == 'true'
        
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=headless_mode,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu'
            ]
        )

        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )

        logger.info("Browser setup complete")

    async def _create_page(self) -> Page:
        """Create a new page with common settings"""
        page = await self.context.new_page()

        # Set reasonable timeouts
        page.set_default_timeout(self.config.scraping.timeout)
        page.set_default_navigation_timeout(self.config.scraping.timeout)

        return page

    async def _extract_product_urls(self, page: Page) -> List[str]:
        """
        Extract product URLs from current page

        Args:
            page: Playwright page object

        Returns:
            List of product URLs
        """
        try:
            # Wait for page to load
            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)  # Give time for dynamic content

            # Scroll to trigger lazy loading
            await page.evaluate("""
                window.scrollTo(0, document.body.scrollHeight / 2);
            """)
            await asyncio.sleep(2)
            
            await page.evaluate("""
                window.scrollTo(0, document.body.scrollHeight);
            """)
            await asyncio.sleep(2)
            
            await page.evaluate("""
                window.scrollTo(0, 0);
            """)
            await asyncio.sleep(1)

            # Try to find all links first and filter
            all_links = await page.query_selector_all('a')
            logger.info(f"Found {len(all_links)} total links on page")

            urls = []
            seen_hrefs = set()
            
            for link in all_links:
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    
                    # Check if it's a product URL
                    if '/p/' in href or '/shop/' in href:
                        # Normalize URL
                        if href.startswith('/'):
                            full_url = urljoin(self.config.brand.base_url, href)
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            continue
                        
                        # Extract product ID from URL
                        if '/p/' in full_url:
                            # Clean URL (remove query params)
                            clean_url = full_url.split('?')[0]
                            
                            if clean_url not in self.processed_urls and clean_url not in seen_hrefs:
                                urls.append(clean_url)
                                seen_hrefs.add(clean_url)
                                self.processed_urls.add(clean_url)
                except Exception as e:
                    logger.debug(f"Error processing link: {e}")
                    continue

            # Also try to extract from page content/JSON-LD
            try:
                # Check for JSON-LD structured data
                json_ld_scripts = await page.query_selector_all('script[type="application/ld+json"]')
                for script in json_ld_scripts:
                    try:
                        content = await script.text_content()
                        if content and '/p/' in content:
                            # Extract URLs from JSON
                            import json
                            data = json.loads(content)
                            if isinstance(data, dict):
                                if 'url' in data and '/p/' in str(data['url']):
                                    url = str(data['url']).split('?')[0]
                                    if url not in self.processed_urls:
                                        urls.append(url)
                                        self.processed_urls.add(url)
                    except:
                        pass
            except Exception as e:
                logger.debug(f"Error extracting from JSON-LD: {e}")

            logger.info(f"Found {len(urls)} unique product URLs on current page")
            
            # Debug: log first few URLs if found
            if urls:
                logger.info(f"Sample product URLs: {urls[:3]}")
            else:
                # Try to get page HTML snippet for debugging
                try:
                    body_text = await page.evaluate("document.body.innerText")
                    if 'product' in body_text.lower() or 'mens' in body_text.lower():
                        logger.warning("Page content found but no product URLs extracted - may need different selectors")
                except:
                    pass

            return urls

        except Exception as e:
            logger.error(f"Error extracting product URLs: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

    async def _extract_product_data(self, page: Page, product_url: str) -> Optional[Dict[str, Any]]:
        """
        Extract product data from product page

        Args:
            page: Playwright page object
            product_url: Product URL

        Returns:
            Product data dictionary or None if failed
        """
        try:
            # Navigate to product page
            await page.goto(product_url, wait_until='networkidle')

            # Wait for content to load
            await page.wait_for_selector('h1', timeout=10000)

            # Extract basic information
            title = await self._extract_text(page, self.config.scraping.selectors.get('product_title', 'h1'))
            if not title:
                title = await page.title()
                # Clean up title
                title = title.split('|')[0].strip() if '|' in title else title.strip()

            # Extract price
            price_text = await self._extract_text(page, self.config.scraping.selectors.get('product_price', '[data-testid="price"]'))
            price = self._parse_price(price_text)

            # Extract image URL
            image_url = await self._extract_image_url(page)

            # Extract description (look for various selectors)
            description = await self._extract_description(page)

            # Generate product ID from URL
            product_id = self._generate_product_id(product_url)

            # Check if product already exists
            if not self.dry_run and await self.db_client.product_exists(product_url):
                logger.info(f"Product already exists: {title}")
                return None

            product_data = {
                'id': product_id,
                'source': self.config.brand.source,
                'product_url': product_url,
                'image_url': image_url,
                'brand': self.config.brand.name,
                'title': title,
                'description': description,
                'category': 'mens',  # Could be extracted more specifically
                'gender': self.config.brand.gender,
                'price': price,
                'currency': self.config.brand.currency,
                'second_hand': self.config.brand.second_hand,
                'metadata': json.dumps({
                    'scraped_at': asyncio.get_event_loop().time(),
                    'user_agent': await page.evaluate('navigator.userAgent')
                })
            }

            # Remove None values
            product_data = {k: v for k, v in product_data.items() if v is not None}

            logger.info(f"Extracted product data: {title}")
            return product_data

        except Exception as e:
            logger.error(f"Error extracting product data from {product_url}: {e}")
            return None

    async def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        """Extract text content from selector"""
        try:
            element = await page.query_selector(selector)
            if element:
                return (await element.text_content()).strip()
        except Exception:
            pass
        return None

    async def _extract_image_url(self, page: Page) -> Optional[str]:
        """Extract main product image URL"""
        try:
            # Try configured selector first
            image_selector = self.config.scraping.selectors.get('product_image', 'img[data-testid="product-image"]')
            element = await page.query_selector(image_selector)
            if element:
                src = await element.get_attribute('src')
                if src:
                    return urljoin(self.config.brand.base_url, src)

            # Fallback: find largest image
            images = await page.query_selector_all('img')
            largest_image = None
            max_area = 0

            for img in images:
                src = await img.get_attribute('src')
                if not src or 'data:' in src or src.endswith('.svg'):
                    continue

                # Get dimensions if available
                width = await img.get_attribute('width')
                height = await img.get_attribute('height')

                if width and height:
                    try:
                        area = int(width) * int(height)
                        if area > max_area:
                            max_area = area
                            largest_image = src
                    except ValueError:
                        continue

            if largest_image:
                return urljoin(self.config.brand.base_url, largest_image)

        except Exception as e:
            logger.error(f"Error extracting image URL: {e}")

        return None

    async def _extract_description(self, page: Page) -> Optional[str]:
        """Extract product description"""
        description_selectors = [
            '[data-testid="product-description"]',
            '.product-description',
            '.description',
            '[class*="description"]',
            'meta[name="description"]'
        ]

        for selector in description_selectors:
            try:
                if selector.startswith('meta'):
                    content = await page.get_attribute(selector, 'content')
                else:
                    element = await page.query_selector(selector)
                    if element:
                        content = await element.text_content()

                if content and len(content.strip()) > 10:
                    return content.strip()
            except Exception:
                continue

        return None

    def _parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from text"""
        if not price_text:
            return None

        # Extract numeric values with common patterns
        patterns = [
            r'€\s*(\d+(?:[,.]\d+)?)',  # €123.45 or €123,45
            r'\$(\d+(?:[,.]\d+)?)',    # $123.45
            r'(\d+(?:[,.]\d+)?)\s*€',  # 123.45€
            r'(\d+(?:[,.]\d+)?)\s*\$', # 123.45$
        ]

        for pattern in patterns:
            match = re.search(pattern, price_text, re.IGNORECASE)
            if match:
                price_str = match.group(1).replace(',', '.')
                try:
                    return float(price_str)
                except ValueError:
                    continue

        return None

    def _generate_product_id(self, url: str) -> str:
        """Generate unique product ID from URL"""
        # Extract product code from URL
        match = re.search(r'/p/([^/?]+)', url)
        if match:
            return f"{self.config.brand.source}_{match.group(1)}"

        # Fallback to URL hash
        import hashlib
        return f"{self.config.brand.source}_{hashlib.md5(url.encode()).hexdigest()[:16]}"

    async def _process_product_batch(self, product_urls: List[str]) -> int:
        """
        Process a batch of product URLs

        Args:
            product_urls: List of product URLs to process

        Returns:
            Number of products successfully processed
        """
        if not product_urls:
            return 0

        products_to_save = []
        image_urls = []

        # Create pages for concurrent processing
        pages = []
        for _ in range(min(len(product_urls), self.config.scraping.max_concurrent_pages)):
            pages.append(await self._create_page())

        try:
            # Process products concurrently
            semaphore = asyncio.Semaphore(self.config.scraping.max_concurrent_pages)

            async def process_single(url: str, page_idx: int):
                async with semaphore:
                    page = pages[page_idx % len(pages)]
                    product_data = await self._extract_product_data(page, url)

                    if product_data:
                        products_to_save.append(product_data)
                        if product_data.get('image_url'):
                            image_urls.append(product_data['image_url'])

                    # Rate limiting
                    await asyncio.sleep(self.config.scraping.request_delay)

            # Create tasks
            tasks = []
            for i, url in enumerate(product_urls):
                tasks.append(process_single(url, i))

            # Run tasks
            await asyncio.gather(*tasks, return_exceptions=True)

            # Generate embeddings for products with images
            if image_urls and not self.dry_run and self.embedder:
                logger.info(f"Generating embeddings for {len(image_urls)} products")
                embeddings = await self.embedder.generate_embeddings_batch(
                    image_urls,
                    max_concurrent=self.config.scraping.max_concurrent_pages
                )

                # Add embeddings to product data
                for product in products_to_save:
                    img_url = product.get('image_url')
                    if img_url and img_url in embeddings:
                        product['embedding'] = embeddings[img_url]
            elif image_urls and not self.dry_run and not self.embedder:
                logger.warning("Skipping embedding generation - embedder not available")

            # Save to database
            if products_to_save and not self.dry_run:
                saved_count = await self.db_client.insert_products_batch(products_to_save)
                self.products_saved += saved_count
            else:
                self.products_saved += len(products_to_save)

            logger.info(f"Processed batch: {len(products_to_save)} products saved")
            return len(products_to_save)

        finally:
            # Close pages
            for page in pages:
                await page.close()

    async def _scrape_category_page(self, page: Page, url: str, max_products: Optional[int] = None) -> int:
        """
        Scrape all products from a category page with pagination

        Args:
            page: Playwright page object
            url: Category URL to start scraping from
            max_products: Maximum products to scrape (for testing)

        Returns:
            Total products processed
        """
        logger.info(f"Starting category scrape: {url}")

        # Navigate to page
        await page.goto(url, wait_until='domcontentloaded')
        
        # Wait for content to load
        await asyncio.sleep(5)  # Give more time for dynamic content
        
        # Try to wait for common product container selectors
        product_container_selectors = [
            '[data-testid*="product"]',
            '.product-grid',
            '.product-list',
            '[class*="product"]',
            '[class*="Product"]',
            'main',
            'article'
        ]
        
        for selector in product_container_selectors:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                logger.info(f"Found container with selector: {selector}")
                break
            except:
                continue

        total_processed = 0
        page_num = 1

        while True:
            logger.info(f"Processing page {page_num}")

            # Extract product URLs from current page
            product_urls = await self._extract_product_urls(page)

            if not product_urls:
                # If no products found, try one more time with longer wait
                if page_num == 1:
                    logger.warning("No products found on first page, waiting longer...")
                    await asyncio.sleep(5)
                    await page.reload(wait_until='networkidle')
                    await asyncio.sleep(5)
                    product_urls = await self._extract_product_urls(page)
                
                if not product_urls:
                    logger.info("No more products found, stopping pagination")
                    # Debug: save page HTML snippet
                    try:
                        page_title = await page.title()
                        logger.info(f"Page title: {page_title}")
                        page_url = page.url
                        logger.info(f"Current URL: {page_url}")
                    except:
                        pass
                    break

            # Process product batch
            batch_processed = await self._process_product_batch(product_urls)
            total_processed += batch_processed

            self.products_found += len(product_urls)

            # Check if we've reached the limit
            if max_products and total_processed >= max_products:
                logger.info(f"Reached maximum products limit: {max_products}")
                break

            # Try to go to next page
            next_page_found = await self._go_to_next_page(page)

            if not next_page_found:
                logger.info("No more pages to scrape")
                break

            page_num += 1

            # Small delay between pages
            await asyncio.sleep(1)

        return total_processed

    async def _go_to_next_page(self, page: Page) -> bool:
        """
        Navigate to next page in pagination

        Args:
            page: Current page

        Returns:
            True if successfully navigated to next page
        """
        try:
            # Try different pagination selectors
            pagination_selectors = [
                self.config.scraping.pagination.get('next_button', '[data-testid="pagination-next"]'),
                '[data-testid="pagination-next"]',
                '.pagination-next',
                '.next-page',
                'a[aria-label*="next"]',
                'a[href*="page="]'
            ]

            for selector in pagination_selectors:
                try:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        # Check if button is disabled
                        disabled = await next_button.get_attribute('disabled')
                        aria_disabled = await next_button.get_attribute('aria-disabled')

                        if disabled or aria_disabled == 'true':
                            return False

                        # Click next button
                        await next_button.click()
                        await page.wait_for_load_state('networkidle')
                        return True

                except Exception:
                    continue

            # Try load more button
            load_more_selectors = [
                self.config.scraping.pagination.get('load_more_button', '[data-testid="load-more"]'),
                '[data-testid="load-more"]',
                '.load-more',
                '.show-more'
            ]

            for selector in load_more_selectors:
                try:
                    load_more_button = await page.query_selector(selector)
                    if load_more_button:
                        await load_more_button.click()
                        await page.wait_for_timeout(2000)  # Wait for content to load
                        return True
                except Exception:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return False

    async def scrape(self, start_url: Optional[str] = None, max_products: Optional[int] = None) -> Dict[str, Any]:
        """
        Main scraping function

        Args:
            start_url: URL to start scraping from (overrides config)
            max_products: Maximum products to scrape

        Returns:
            Scraping statistics
        """
        start_url = start_url or self.config.brand.category_url

        try:
            # Setup browser
            await self._setup_browser()

            # Create main page
            page = await self._create_page()

            try:
                # Start scraping
                total_processed = await self._scrape_category_page(page, start_url, max_products)

                stats = {
                    'products_found': self.products_found,
                    'products_saved': self.products_saved,
                    'total_processed': total_processed,
                    'success': True
                }

                logger.info(f"Scraping completed: {stats}")
                return stats

            finally:
                await page.close()

        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return {
                'products_found': self.products_found,
                'products_saved': self.products_saved,
                'total_processed': 0,
                'success': False,
                'error': str(e)
            }

    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            logger.info("Browser cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
