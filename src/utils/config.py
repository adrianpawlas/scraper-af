"""
Configuration management for the scraper
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class BrandConfig:
    """Brand-specific configuration"""
    name: str
    source: str
    base_url: str
    category_url: str
    currency: str
    gender: str
    second_hand: bool


@dataclass
class ScrapingConfig:
    """Scraping configuration"""
    max_concurrent_pages: int
    request_delay: int
    max_retries: int
    timeout: int
    selectors: Dict[str, str]
    pagination: Dict[str, Any]


@dataclass
class DatabaseConfig:
    """Database configuration"""
    table_name: str
    batch_size: int
    url: Optional[str] = None
    key: Optional[str] = None


@dataclass
class EmbeddingConfig:
    """Embedding configuration"""
    model_name: str
    dimensions: int
    device: str
    cache_dir: str


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str
    format: str
    file: str


@dataclass
class Config:
    """Main configuration class"""
    brand: BrandConfig
    scraping: ScrapingConfig
    database: DatabaseConfig
    embeddings: EmbeddingConfig
    logging: LoggingConfig

    def __init__(self, config_path: str):
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Load brand config
        brand_data = data['brand']
        self.brand = BrandConfig(**brand_data)

        # Load scraping config
        scraping_data = data['scraping']
        self.scraping = ScrapingConfig(**scraping_data)

        # Load database config with environment variables
        db_data = data['database']
        db_data['url'] = os.getenv('SUPABASE_URL')
        db_data['key'] = os.getenv('SUPABASE_ANON_KEY')
        self.database = DatabaseConfig(**db_data)

        # Load embedding config
        embedding_data = data['embeddings']
        self.embeddings = EmbeddingConfig(**embedding_data)

        # Load logging config
        logging_data = data['logging']
        self.logging = LoggingConfig(**logging_data)

        # Validate configuration
        self._validate()

    def _validate(self):
        """Validate configuration values"""
        if not self.database.url:
            raise ValueError("SUPABASE_URL environment variable is required")
        if not self.database.key:
            raise ValueError("SUPABASE_ANON_KEY environment variable is required")

        if self.scraping.max_concurrent_pages < 1:
            raise ValueError("max_concurrent_pages must be >= 1")

        if self.scraping.request_delay < 0:
            raise ValueError("request_delay must be >= 0")
