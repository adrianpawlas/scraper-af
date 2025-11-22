"""
Main script to orchestrate the Abercrombie & Fitch scraper
"""
import asyncio
import logging
import sys
from typing import List, Dict
from tqdm import tqdm
import config
from product_scraper import ProductScraper
from embedding_generator import EmbeddingGenerator
from database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ScraperOrchestrator:
    """Orchestrates the entire scraping process"""
    
    def __init__(self):
        self.scraper = ProductScraper()
        self.embedding_gen = None
        self.db = Database()
    
    def initialize_embedding_generator(self):
        """Initialize the embedding generator"""
        logger.info("Initializing embedding generator...")
        self.embedding_gen = EmbeddingGenerator(config.EMBEDDING_MODEL)
        logger.info("Embedding generator ready")
    
    async def scrape_category(self, category_url: str, max_pages: int = None) -> List[Dict]:
        """
        Scrape all products from a category
        
        Args:
            category_url: Category URL to scrape
            max_pages: Maximum number of pages to scrape
            
        Returns:
            List of product dictionaries
        """
        logger.info(f"Starting to scrape category: {category_url}")
        products = await self.scraper.scrape_all_products(category_url, max_pages)
        logger.info(f"Scraped {len(products)} products from category")
        return products
    
    def generate_embeddings(self, products: List[Dict]) -> List[Dict]:
        """
        Generate embeddings for all products
        
        Args:
            products: List of product dictionaries
            
        Returns:
            List of products with embeddings added
        """
        if not self.embedding_gen:
            self.initialize_embedding_generator()
        
        logger.info(f"Generating embeddings for {len(products)} products...")
        
        products_with_embeddings = []
        for product in tqdm(products, desc="Generating embeddings"):
            image_url = product.get('image_url')
            if image_url:
                embedding = self.embedding_gen.generate_embedding(image_url)
                if embedding:
                    product['embedding'] = embedding
                    products_with_embeddings.append(product)
                else:
                    logger.warning(f"Failed to generate embedding for {product.get('title', 'Unknown')}")
                    # Still add product without embedding
                    products_with_embeddings.append(product)
            else:
                logger.warning(f"No image URL for product {product.get('title', 'Unknown')}")
                products_with_embeddings.append(product)
        
        logger.info(f"Generated embeddings for {len(products_with_embeddings)} products")
        return products_with_embeddings
    
    def save_to_database(self, products: List[Dict]) -> int:
        """
        Save products to Supabase database
        
        Args:
            products: List of product dictionaries with embeddings
            
        Returns:
            Number of successfully saved products
        """
        logger.info(f"Saving {len(products)} products to database...")
        success_count = self.db.insert_products_batch(products)
        logger.info(f"Successfully saved {success_count}/{len(products)} products")
        return success_count
    
    async def run_full_scrape(self, category_urls: List[str], max_pages: int = None):
        """
        Run the complete scraping process for multiple categories
        
        Args:
            category_urls: List of category URLs to scrape
            max_pages: Maximum pages per category
        """
        all_products = []
        
        # Scrape all categories
        for category_url in category_urls:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing category: {category_url}")
            logger.info(f"{'='*60}\n")
            
            products = await self.scrape_category(category_url, max_pages)
            all_products.extend(products)
        
        # Remove duplicates based on product_url
        seen_urls = set()
        unique_products = []
        for product in all_products:
            url = product.get('product_url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_products.append(product)
        
        logger.info(f"\nTotal unique products scraped: {len(unique_products)}")
        
        # Generate embeddings
        logger.info("\nGenerating embeddings...")
        products_with_embeddings = self.generate_embeddings(unique_products)
        
        # Save to database
        logger.info("\nSaving to database...")
        saved_count = self.save_to_database(products_with_embeddings)
        
        logger.info(f"\n{'='*60}")
        logger.info("SCRAPING COMPLETE!")
        logger.info(f"Total products scraped: {len(unique_products)}")
        logger.info(f"Products with embeddings: {sum(1 for p in products_with_embeddings if p.get('embedding'))}")
        logger.info(f"Products saved to database: {saved_count}")
        logger.info(f"{'='*60}")


async def main():
    """Main entry point"""
    orchestrator = ScraperOrchestrator()
    
    # Define categories to scrape
    categories = [
        config.MENS_CATEGORY_URL,
        # Add more categories as needed
        # config.WOMENS_CATEGORY_URL,
    ]
    
    # Run the scraper
    await orchestrator.run_full_scrape(categories, max_pages=None)  # None = scrape all pages


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

