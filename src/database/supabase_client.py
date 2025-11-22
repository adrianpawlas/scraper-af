"""
Supabase database client for the scraper
"""

from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
from supabase import create_client, Client
from loguru import logger


class SupabaseClient:
    """Supabase database client wrapper"""

    def __init__(self, url: str, key: str, table_name: str = "products"):
        """
        Initialize Supabase client

        Args:
            url: Supabase project URL
            key: Supabase anon key
            table_name: Database table name
        """
        self.client: Client = create_client(url, key)
        self.table_name = table_name
        logger.info("Supabase client initialized")

    async def insert_product(self, product_data: Dict[str, Any]) -> bool:
        """
        Insert a single product into the database

        Args:
            product_data: Product data dictionary

        Returns:
            Success status
        """
        try:
            # Generate UUID if not provided
            if 'id' not in product_data:
                product_data['id'] = str(uuid.uuid4())

            # Ensure created_at is set
            if 'created_at' not in product_data:
                product_data['created_at'] = datetime.utcnow().isoformat()

            # Insert product
            response = self.client.table(self.table_name).insert(product_data).execute()

            if response.data:
                logger.info(f"Inserted product: {product_data.get('title', 'Unknown')}")
                return True
            else:
                logger.warning(f"Failed to insert product: {product_data.get('title', 'Unknown')}")
                return False

        except Exception as e:
            logger.error(f"Error inserting product: {e}")
            return False

    async def insert_products_batch(self, products: List[Dict[str, Any]]) -> int:
        """
        Insert multiple products in a batch

        Args:
            products: List of product data dictionaries

        Returns:
            Number of successfully inserted products
        """
        if not products:
            return 0

        try:
            # Add UUIDs and timestamps if not present
            for product in products:
                if 'id' not in product:
                    product['id'] = str(uuid.uuid4())
                if 'created_at' not in product:
                    product['created_at'] = datetime.utcnow().isoformat()

            # Insert batch
            response = self.client.table(self.table_name).insert(products).execute()

            inserted_count = len(response.data) if response.data else 0
            logger.info(f"Inserted {inserted_count}/{len(products)} products in batch")

            return inserted_count

        except Exception as e:
            logger.error(f"Error inserting products batch: {e}")
            return 0

    async def product_exists(self, product_url: str) -> bool:
        """
        Check if a product already exists in the database

        Args:
            product_url: Product URL to check

        Returns:
            True if product exists
        """
        try:
            response = self.client.table(self.table_name)\
                .select("id")\
                .eq("product_url", product_url)\
                .limit(1)\
                .execute()

            return len(response.data) > 0

        except Exception as e:
            logger.error(f"Error checking product existence: {e}")
            return False

    async def get_recent_products(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recently added products

        Args:
            limit: Maximum number of products to return

        Returns:
            List of product dictionaries
        """
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()

            return response.data or []

        except Exception as e:
            logger.error(f"Error getting recent products: {e}")
            return []

    async def update_product_embedding(self, product_id: str, embedding: List[float]) -> bool:
        """
        Update product embedding

        Args:
            product_id: Product ID
            embedding: Embedding vector

        Returns:
            Success status
        """
        try:
            response = self.client.table(self.table_name)\
                .update({"embedding": embedding})\
                .eq("id", product_id)\
                .execute()

            return len(response.data) > 0

        except Exception as e:
            logger.error(f"Error updating product embedding: {e}")
            return False

    async def get_products_without_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get products that don't have embeddings yet

        Args:
            limit: Maximum number of products to return

        Returns:
            List of product dictionaries
        """
        try:
            response = self.client.table(self.table_name)\
                .select("*")\
                .is_("embedding", "null")\
                .limit(limit)\
                .execute()

            return response.data or []

        except Exception as e:
            logger.error(f"Error getting products without embeddings: {e}")
            return []
