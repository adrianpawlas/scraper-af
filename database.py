"""
Supabase database operations
"""
import logging
from typing import List, Dict, Optional
from supabase import create_client, Client
import config

logger = logging.getLogger(__name__)


class Database:
    """Handle database operations with Supabase"""
    
    def __init__(self):
        """Initialize Supabase client"""
        self.client: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        logger.info("Supabase client initialized")
    
    def insert_product(self, product: Dict) -> bool:
        """
        Insert a single product into the database
        
        Args:
            product: Product dictionary with all required fields
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare data for insertion
            data = {
                'id': product.get('id'),
                'source': product.get('source', config.SOURCE_NAME),
                'product_url': product.get('product_url'),
                'affiliate_url': product.get('affiliate_url'),
                'image_url': product.get('image_url', ''),
                'brand': product.get('brand', config.BRAND_NAME),
                'title': product.get('title', ''),
                'description': product.get('description'),
                'category': product.get('category'),
                'gender': product.get('gender'),
                'price': product.get('price'),
                'currency': product.get('currency', 'EUR'),
                'size': product.get('size'),
                'second_hand': product.get('second_hand', config.SECOND_HAND),
                'metadata': product.get('metadata'),
                'embedding': product.get('embedding'),  # Will be added after embedding generation
            }
            
            # Remove None values for optional fields (but keep empty strings where required)
            data = {k: v for k, v in data.items() if v is not None}
            
            # Insert or update (upsert based on unique constraint)
            response = self.client.table('products').upsert(
                data,
                on_conflict='source,product_url'
            ).execute()
            
            logger.info(f"Successfully inserted/updated product: {product.get('title', 'Unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Error inserting product {product.get('product_url', 'Unknown')}: {e}")
            return False
    
    def insert_products_batch(self, products: List[Dict]) -> int:
        """
        Insert multiple products into the database
        
        Args:
            products: List of product dictionaries
            
        Returns:
            Number of successfully inserted products
        """
        success_count = 0
        
        for product in products:
            if self.insert_product(product):
                success_count += 1
        
        logger.info(f"Inserted {success_count}/{len(products)} products")
        return success_count
    
    def product_exists(self, product_url: str) -> bool:
        """
        Check if a product already exists in the database
        
        Args:
            product_url: Product URL to check
            
        Returns:
            True if product exists, False otherwise
        """
        try:
            response = self.client.table('products').select('id').eq(
                'source', config.SOURCE_NAME
            ).eq('product_url', product_url).execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking if product exists: {e}")
            return False
    
    def update_product_embedding(self, product_id: str, embedding: List[float]) -> bool:
        """
        Update the embedding for an existing product
        
        Args:
            product_id: Product ID
            embedding: Embedding vector (768 dimensions)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table('products').update({
                'embedding': embedding
            }).eq('id', product_id).execute()
            
            logger.info(f"Updated embedding for product {product_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating embedding for product {product_id}: {e}")
            return False

