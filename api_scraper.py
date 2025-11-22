"""
API-based scraper for Abercrombie & Fitch using their GraphQL API
"""
import asyncio
import logging
import json
import re
from typing import List, Dict, Optional
from urllib.parse import urlencode, parse_qs, urlparse
import requests
from playwright.async_api import async_playwright, Page
import config

logger = logging.getLogger(__name__)


class APIScraper:
    """Scraper using Abercrombie & Fitch API"""
    
    def __init__(self):
        self.base_api_url = "https://www.abercrombie.com/api/bff/catalog"
        self.base_url = config.EU_BASE_URL
        
        # API parameters (extracted from network request)
        self.api_params = {
            'catalogId': '11556',
            'storeId': '19159',
            'langId': '-1',
            'brand': 'anf',
            'store': 'a-eu',
            'currency': 'EUR',
            'country': 'NO',  # Can be changed for different countries
            'urlRoot': '/shop/eu',
            'storePreview': 'false',
            'aemContentAuthoring': '0',
            'operationName': 'CATEGORY_PAGE_DYNAMIC_DATA_QUERY',
        }
        
        # GraphQL query hash (from the URL)
        self.query_hash = '9d42192a5a5c1845fdacc7b98ff64d37f079eae6cb4705c3bf2f3c2a4ebf589f'
        
    def get_category_id_from_url(self, category_url: str) -> Optional[str]:
        """
        Extract categoryId from URL
        
        Args:
            category_url: Category page URL
            
        Returns:
            Category ID string or None
        """
        # Try to extract from URL query params
        parsed = urlparse(category_url)
        query_params = parse_qs(parsed.query)
        
        category_id = query_params.get('categoryId', [None])[0]
        return category_id
    
    async def discover_subcategories(self, category_url: str) -> List[Dict]:
        """
        Discover subcategories from a main category page
        
        Args:
            category_url: Main category URL (e.g., /mens)
            
        Returns:
            List of subcategory dicts with url and categoryId
        """
        # For now, hardcode some known men's subcategories to test API scraping
        logger.info(f"Using hardcoded men's subcategories for testing")
        subcategories = [
            {'url': 'https://www.abercrombie.com/shop/eu/mens-new-arrivals', 'categoryId': '84591', 'name': 'New Arrivals'},
            {'url': 'https://www.abercrombie.com/shop/eu/mens-bottoms--1', 'categoryId': '6570775', 'name': 'Bottoms'},
        ]
        logger.info(f"Found {len(subcategories)} hardcoded subcategories")
        return subcategories
    
    def build_api_url(self, category_id: str, start: int = 0, rows: int = 90, facet: str = None) -> str:
        """
        Build the API URL with proper parameters
        
        Args:
            category_id: Category ID
            start: Starting index for pagination
            rows: Number of items per page
            
        Returns:
            Complete API URL
        """
        # Build variables JSON
        # Use facet from user's working example for mens-bottoms
        if facet:
            facet_list = [facet]
        elif category_id == '6570775':  # mens-bottoms category
            facet_list = ['fit:("Athletic" "Classic")']
        else:
            facet_list = []
        
        variables = {
            "categoryId": category_id,
            "facet": facet_list,
            "filter": "",
            "requestSocialProofData": True,
            "rows": str(rows),
            "sort": "",
            "start": str(start),
            "seqSlot": "1",
            "grouped": False,
            "isUnifiedCategoryPage": True,
            "kicIds": ""
        }
        
        # Build extensions JSON
        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": self.query_hash
            }
        }
        
        # Build query parameters - use compact JSON (no spaces) like user's URL
        params = self.api_params.copy()
        params['variables'] = json.dumps(variables, separators=(',', ':'))
        params['extensions'] = json.dumps(extensions, separators=(',', ':'))
        
        # Build URL
        url = f"{self.base_api_url}?{urlencode(params)}"
        return url
    
    async def fetch_category_data(self, page: Page, category_id: str, start: int = 0, rows: int = 90, facet: str = None) -> Optional[Dict]:
        """
        Fetch category data from API using Playwright (to get proper cookies/session)
        
        Args:
            page: Playwright page object (with session)
            category_id: Category ID
            start: Starting index
            rows: Number of items
            facet: Optional facet filter (e.g., 'fit:("Athletic" "Classic")')
            
        Returns:
            JSON response data or None
        """
        url = self.build_api_url(category_id, start, rows, facet)
        
        try:
            logger.info(f"Fetching API data: start={start}, rows={rows}")
            logger.debug(f"API URL: {url[:200]}...")
            
            # Use Playwright to fetch the API (it will include cookies automatically)
            response = await page.request.get(url)
            
            logger.debug(f"Response status: {response.status}")
            
            if response.status != 200:
                logger.error(f"API returned status {response.status}")
                if response.status == 403:
                    logger.warning("403 Forbidden - trying with requests library instead...")
                    # Fallback: try with requests (sometimes works if API doesn't require auth)
                    return await self.fetch_category_data_requests(category_id, start, rows, facet)
                return None
            
            data = await response.json()
            logger.debug(f"Response data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            return data
            
        except Exception as e:
            logger.error(f"Error fetching API data: {e}")
            # Fallback to requests
            return await self.fetch_category_data_requests(category_id, start, rows, facet)
    
    async def fetch_category_data_requests(self, category_id: str, start: int = 0, rows: int = 90, facet: str = None) -> Optional[Dict]:
        """Fallback: Fetch using requests library"""
        url = self.build_api_url(category_id, start, rows, facet)
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': f'{self.base_url}/mens',
                'Origin': 'https://www.abercrombie.com',
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Requests fallback also failed: {e}")
            return None
    
    def extract_products_from_response(self, api_response: Dict) -> List[Dict]:
        """
        Extract product information from API response
        
        Args:
            api_response: API JSON response
            
        Returns:
            List of product dictionaries
        """
        products = []
        
        try:
            # Debug: log response structure
            logger.debug(f"API response keys: {list(api_response.keys())}")
            
            # Navigate through the response structure
            data = api_response.get('data', {})
            logger.debug(f"Data keys: {list(data.keys())}")
            
            category = data.get('category', {})
            logger.debug(f"Category keys: {list(category.keys())}")
            
            # Try different possible locations for products
            products_data = category.get('products', [])
            if not products_data:
                products_data = category.get('productList', [])
            if not products_data:
                products_data = category.get('items', [])
            if not products_data:
                # Maybe products are at root level?
                products_data = data.get('products', [])
            
            logger.info(f"Found {len(products_data)} products in response")
            
            # Debug: log first product structure
            if products_data:
                logger.info(f"First product keys: {list(products_data[0].keys())}")
                logger.info(f"First product sample: {json.dumps(products_data[0], indent=2, ensure_ascii=False)[:1000]}")
            
            for product in products_data:
                try:
                    # Extract product information - try multiple field names
                    product_id = product.get('id') or product.get('productId') or product.get('itemId') or ''
                    product_name = product.get('name') or product.get('title') or product.get('displayName') or ''
                    # Try productPageUrl first (this is what the API uses)
                    # productPageUrl is usually a full path like /shop/eu/p/...
                    product_url_path = product.get('productPageUrl') or product.get('url') or product.get('productUrl') or product.get('link') or ''
                    
                    # Build product info
                    product_info = {
                        'id': product_id,
                        'title': product_name,
                        'product_url': self.build_product_url(product_url_path),
                        'price': self.extract_price(product),
                        'currency': 'EUR',  # From API params
                        'image_url': self.extract_image_url(product),
                        'description': product.get('shortDescription') or product.get('description') or '',
                        'category': self.extract_category(product),
                        'gender': 'MAN',  # Default for mens-bottoms
                        'size': self.extract_sizes(product),
                        'brand': config.BRAND_NAME,
                        'source': config.SOURCE_NAME,
                        'second_hand': config.SECOND_HAND,
                        'metadata': json.dumps(product, ensure_ascii=False) if product else None,
                    }
                    
                    # Generate ID from product URL if not available
                    if not product_info['id'] and product_info['product_url']:
                        import hashlib
                        product_info['id'] = hashlib.md5(product_info['product_url'].encode()).hexdigest()
                    elif not product_info['id']:
                        # Use product name as fallback
                        import hashlib
                        product_info['id'] = hashlib.md5(product_name.encode()).hexdigest() if product_name else ''
                    
                    # Only add if we have at least a title or URL
                    if product_info['title'] or product_info['product_url']:
                        products.append(product_info)
                    else:
                        logger.warning(f"Skipping product with no title or URL: {product.get('id', 'unknown')}")
                    
                except Exception as e:
                    logger.warning(f"Error extracting product: {e}", exc_info=True)
                    continue
            
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
        
        return products
    
    def build_product_url(self, product_path: str) -> str:
        """Build full product URL from path"""
        if not product_path:
            return ''
        if product_path.startswith('http'):
            return product_path
        # productPageUrl from API already includes /shop/eu, so base_url is https://www.abercrombie.com
        # But base_url is set to https://www.abercrombie.com/shop/eu, so we need to handle this
        if product_path.startswith('/shop/eu'):
            # Already has /shop/eu, use base domain
            return f"https://www.abercrombie.com{product_path}"
        elif product_path.startswith('/'):
            return f"{self.base_url}{product_path}"
        else:
            return f"{self.base_url}/{product_path}"
    
    def extract_price(self, product: Dict) -> Optional[float]:
        """Extract price from product data"""
        try:
            # Try different price fields
            price_data = product.get('price', {})
            if isinstance(price_data, dict):
                # Try originalPrice or discountPrice
                price_str = price_data.get('originalPrice') or price_data.get('discountPrice') or price_data.get('value') or price_data.get('amount') or price_data.get('price')
                if price_str:
                    # Extract number from string like "€75" or "75"
                    import re
                    numbers = re.findall(r'[\d.]+', str(price_str))
                    if numbers:
                        return float(numbers[0].replace(',', '.'))
            else:
                price = price_data
                if price:
                    return float(str(price).replace(',', ''))
            
            # Try sale price
            sale_price = product.get('salePrice', {})
            if isinstance(sale_price, dict):
                price = sale_price.get('value') or sale_price.get('amount')
                if price:
                    return float(str(price).replace(',', ''))
            
            # Try memberPrice
            member_price = product.get('memberPrice')
            if member_price:
                if isinstance(member_price, dict):
                    price_str = member_price.get('originalPrice') or member_price.get('discountPrice')
                    if price_str:
                        import re
                        numbers = re.findall(r'[\d.]+', str(price_str))
                        if numbers:
                            return float(numbers[0].replace(',', '.'))
                else:
                    return float(str(member_price).replace(',', ''))
            
        except (ValueError, TypeError) as e:
            logger.debug(f"Error extracting price: {e}")
        
        return None
    
    def extract_image_url(self, product: Dict) -> str:
        """Extract main product image URL"""
        try:
            # Try imageSet (used by API)
            image_set = product.get('imageSet', {})
            if image_set:
                # Get primary image ID (KIC format)
                image_id = image_set.get('primaryFaceOutImage') or image_set.get('primaryHoverImage') or image_set.get('prodImage')
                if image_id:
                    # Build image URL from KIC ID
                    # Format: https://anf.scene7.com/is/image/anf/{KIC_ID}_prod1
                    # Note: image_id already includes _prod1 suffix sometimes, so check
                    if '_prod1' in image_id or '_model1' in image_id:
                        return f"https://anf.scene7.com/is/image/anf/{image_id}"
                    else:
                        return f"https://anf.scene7.com/is/image/anf/{image_id}_prod1"
            
            # Try different image fields
            images = product.get('images', [])
            if images and len(images) > 0:
                # Get first image
                img = images[0] if isinstance(images[0], str) else images[0].get('url', '')
                if img:
                    return img if img.startswith('http') else f"https://www.abercrombie.com{img}"
            
            # Try thumbnail
            thumbnail = product.get('thumbnail', '')
            if thumbnail:
                return thumbnail if thumbnail.startswith('http') else f"https://www.abercrombie.com{thumbnail}"
            
            # Try imageUrl
            image_url = product.get('imageUrl', '')
            if image_url:
                return image_url if image_url.startswith('http') else f"https://www.abercrombie.com{image_url}"
                
        except Exception as e:
            logger.debug(f"Error extracting image: {e}")
        
        return ''
    
    def extract_category(self, product: Dict) -> Optional[str]:
        """Extract category from product data"""
        try:
            categories = product.get('categories', [])
            if categories:
                return categories[0] if isinstance(categories[0], str) else categories[0].get('name', '')
        except:
            pass
        return None
    
    def extract_gender(self, product: Dict) -> str:
        """Extract gender from product data"""
        try:
            # Check gender field directly (API provides this)
            gender = product.get('gender', '')
            if gender.upper() == 'M' or gender.upper() == 'MALE' or gender.upper() == 'MAN':
                return 'MAN'
            elif gender.upper() == 'F' or gender.upper() == 'FEMALE' or gender.upper() == 'WOMAN':
                return 'WOMAN'
            
            # Fallback: Check URL or category for gender
            url = product.get('productPageUrl') or product.get('url', '')
            if '/mens' in url.lower() or '/mens/' in url.lower():
                return 'MAN'
            elif '/womens' in url.lower() or '/womens/' in url.lower():
                return 'WOMAN'
        except:
            pass
        return 'OTHER'
    
    def extract_sizes(self, product: Dict) -> Optional[str]:
        """Extract available sizes"""
        try:
            sizes = product.get('sizes', [])
            if sizes:
                size_list = [s if isinstance(s, str) else s.get('name', '') for s in sizes]
                return ', '.join(size_list)
        except:
            pass
        return None
    
    async def init_browser_page(self):
        """Initialize a browser page for API calls"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=config.HEADLESS)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        )
        page = await context.new_page()
        return page, browser
    
    async def scrape_subcategory(self, category_id: str, category_url: str = None, max_pages: int = None) -> List[Dict]:
        """
        Scrape a specific subcategory using its categoryId
        
        Args:
            category_id: Category ID
            category_url: Optional category URL for reference
            max_pages: Maximum pages to scrape
            
        Returns:
            List of product dictionaries
        """
        logger.info(f"Scraping subcategory {category_id}")
        
        # Initialize browser page to get cookies
        page, browser = await self.init_browser_page()
        
        try:
            if not category_url:
                category_url = f"{self.base_url}/mens-bottoms--1?categoryId={category_id}"

            # Visit the subcategory page first to establish session/cookies
            logger.info(f"Visiting {category_url} to establish session...")
            await page.goto(category_url, wait_until="load", timeout=60000)
            await asyncio.sleep(3)  # Wait for page to initialize

            all_products = []

            # Try using browser's fetch API directly with the working URL pattern
            try:
                api_url = self.build_api_url(category_id, 0, 90)
                logger.info(f"Fetching API using browser's fetch API...")
                logger.info(f"API URL: {api_url}")

                # Use page.evaluate to call fetch from browser context
                api_response = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const response = await fetch(`{api_url}`, {{
                                method: 'GET',
                                headers: {{
                                    'Accept': 'application/json',
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                                }},
                                credentials: 'include'
                            }});
                            if (response.ok) {{
                                const text = await response.text();
                                try {{
                                    return JSON.parse(text);
                                }} catch (e) {{
                                    console.log('JSON parse error:', e);
                                    console.log('Response text:', text.substring(0, 500));
                                    return null;
                                }}
                            }} else {{
                                console.log('Response status:', response.status);
                                const text = await response.text();
                                console.log('Response text:', text.substring(0, 200));
                                return null;
                            }}
                        }} catch (e) {{
                            console.log('Fetch error:', e);
                            return null;
                        }}
                    }}
                """)

                if api_response and 'data' in api_response:
                    products = self.extract_products_from_response(api_response)
                    all_products.extend(products)
                    logger.info(f"Page 1: Found {len(products)} products using browser fetch")
                else:
                    logger.warning("Browser fetch returned invalid response, trying fallback...")

            except Exception as e:
                logger.error(f"Browser fetch failed: {e}")

            # If no products found, try the fallback method
            if not all_products:
                logger.warning("All fetch methods failed, trying requests fallback...")
                api_response = await self.fetch_category_data(page, category_id, 0, 90)
                if api_response:
                    products = self.extract_products_from_response(api_response)
                    all_products.extend(products)
            
            # Fetch additional pages
            if max_pages is None or max_pages > 1:
                start = 90
                rows = 90
                page_num = 1
                
                while True:
                    if max_pages and page_num >= max_pages - 1:  # -1 because we already got page 1
                        break
                    
                    # Fetch data from API using the page (with cookies)
                    api_response = await self.fetch_category_data(page, category_id, start, rows)
                    
                    if not api_response:
                        logger.warning("No API response, stopping")
                        break
                    
                    # Extract products
                    products = self.extract_products_from_response(api_response)
                    
                    if not products:
                        logger.info("No more products found, stopping pagination")
                        break
                    
                    all_products.extend(products)
                    logger.info(f"Page {page_num + 1}: Found {len(products)} products (Total: {len(all_products)})")
                    
                    # Check if there are more pages
                    if len(products) < rows:
                        logger.info("Fewer products than rows, likely last page")
                        break
                    
                    # Move to next page
                    start += rows
                    page_num += 1
                    
                    # Safety limit
                    if start > 1000:
                        logger.warning("Reached safety limit")
                        break
                    
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(1)
            
            # Remove duplicates based on product URL
            seen_urls = set()
            unique_products = []
            skipped_no_url = 0
            for product in all_products:
                url = product.get('product_url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_products.append(product)
                elif not url:
                    skipped_no_url += 1
            
            if skipped_no_url > 0:
                logger.warning(f"Skipped {skipped_no_url} products with no URL")
            
            logger.info(f"Subcategory {category_id}: Total unique products: {len(unique_products)} (from {len(all_products)} total)")
            
            # Debug: log first product if we have any
            if unique_products:
                logger.debug(f"Sample product: {json.dumps(unique_products[0], indent=2, ensure_ascii=False)[:500]}")
            elif all_products:
                logger.warning(f"Had {len(all_products)} products but all were filtered out")
                logger.debug(f"Sample filtered product: {json.dumps(all_products[0], indent=2, ensure_ascii=False)[:500]}")
            
            return unique_products
            
        finally:
            await browser.close()
    
    async def scrape_category(self, category_url: str, max_pages: int = None) -> List[Dict]:
        """
        Scrape all products from a category by discovering and scraping subcategories
        
        Args:
            category_url: Main category page URL (e.g., /mens)
            max_pages: Maximum pages per subcategory
            
        Returns:
            List of product dictionaries from all subcategories
        """
        logger.info(f"Scraping category: {category_url}")
        
        # Check if this is a subcategory (has categoryId in URL)
        category_id = self.get_category_id_from_url(category_url)
        
        if category_id:
            # This is already a subcategory, scrape it directly
            logger.info(f"Direct subcategory detected: {category_id}")
            return await self.scrape_subcategory(category_id, category_url, max_pages)
        
        # This is a main category, discover subcategories first
        logger.info("Main category detected, discovering subcategories...")
        subcategories = await self.discover_subcategories(category_url)
        
        if not subcategories:
            logger.warning("No subcategories found, trying to scrape main category directly")
            # Fallback: try to scrape main category (might not work)
            return []
        
        # Scrape each subcategory
        all_products = []
        for i, subcat in enumerate(subcategories, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Scraping subcategory {i}/{len(subcategories)}: {subcat.get('name', 'Unknown')} (ID: {subcat['categoryId']})")
            logger.info(f"{'='*60}")
            
            try:
                products = await self.scrape_subcategory(
                    subcat['categoryId'],
                    subcat['url'],
                    max_pages
                )
                all_products.extend(products)
                logger.info(f"Subcategory complete: {len(products)} products")
            except Exception as e:
                logger.error(f"Error scraping subcategory {subcat['categoryId']}: {e}")
                continue
        
        # Remove duplicates across all subcategories
        seen_urls = set()
        unique_products = []
        for product in all_products:
            url = product.get('product_url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_products.append(product)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"TOTAL UNIQUE PRODUCTS FROM ALL SUBCATEGORIES: {len(unique_products)}")
        logger.info(f"{'='*60}")
        
        return unique_products

