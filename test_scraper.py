"""
Test script to verify scraper components work correctly
"""
import asyncio
import logging
import sys
from product_scraper import ProductScraper
from embedding_generator import EmbeddingGenerator
from database import Database
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_product_scraping():
    """Test scraping a single product"""
    logger.info("Testing product scraping...")
    scraper = ProductScraper()
    
    # Test with one of the provided product URLs
    test_url = "https://www.abercrombie.com/shop/eu/p/relaxed-straight-jean-60571326?categoryId=84605&faceout=life&seq=03&pagefm=navigation-grid&prodvm=navigation-grid"
    
    browser = await scraper.init_browser()
    page = await browser.new_page()
    
    try:
        product = await scraper.scrape_product_details(page, test_url)
        if product:
            logger.info("✅ Product scraping successful!")
            logger.info(f"Title: {product.get('title')}")
            logger.info(f"Price: {product.get('price')} {product.get('currency')}")
            logger.info(f"Image URL: {product.get('image_url')}")
            logger.info(f"Gender: {product.get('gender')}")
            return product
        else:
            logger.error("❌ Product scraping failed")
            return None
    finally:
        await browser.close()


def test_embedding_generation():
    """Test embedding generation"""
    logger.info("Testing embedding generation...")
    
    # Test with a sample image URL (you can replace with actual product image)
    test_image_url = "https://www.abercrombie.com/dw/image/v2/BDVS_PRD/on/demandware.static/-/Sites-anf-master-catalog/default/dw12345678/images/product.jpg"
    
    try:
        gen = EmbeddingGenerator(config.EMBEDDING_MODEL)
        embedding = gen.generate_embedding(test_image_url)
        
        if embedding:
            logger.info("✅ Embedding generation successful!")
            logger.info(f"Embedding dimension: {len(embedding)}")
            if len(embedding) == 768:
                logger.info("✅ Correct dimension (768)")
            else:
                logger.warning(f"⚠️ Expected 768 dimensions, got {len(embedding)}")
            return embedding
        else:
            logger.error("❌ Embedding generation failed")
            return None
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return None


def test_database_connection():
    """Test database connection"""
    logger.info("Testing database connection...")
    
    try:
        db = Database()
        # Try a simple query
        response = db.client.table('products').select('id').limit(1).execute()
        logger.info("✅ Database connection successful!")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


async def test_full_flow():
    """Test the complete flow with one product"""
    logger.info("\n" + "="*60)
    logger.info("Testing complete flow...")
    logger.info("="*60 + "\n")
    
    # Test database connection
    if not test_database_connection():
        return
    
    # Test product scraping
    product = await test_product_scraping()
    if not product:
        return
    
    # Test embedding generation if we have an image URL
    if product.get('image_url'):
        embedding = test_embedding_generation()
        if embedding:
            product['embedding'] = embedding
    
    # Test database insertion
    logger.info("Testing database insertion...")
    db = Database()
    if db.insert_product(product):
        logger.info("✅ Database insertion successful!")
    else:
        logger.error("❌ Database insertion failed")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "scrape":
            asyncio.run(test_product_scraping())
        elif test_type == "embedding":
            test_embedding_generation()
        elif test_type == "database":
            test_database_connection()
        else:
            print("Usage: python test_scraper.py [scrape|embedding|database]")
    else:
        asyncio.run(test_full_flow())

