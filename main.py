#!/usr/bin/env python3
"""
Abercrombie & Fitch Product Scraper
Main entry point for the scraping pipeline
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scrapers.abercrombie_fitch import AbercrombieFitchScraper
from utils.logger import setup_logging
from utils.config import Config


async def main():
    """Main scraping function"""
    parser = argparse.ArgumentParser(description="Abercrombie & Fitch Product Scraper")
    parser.add_argument(
        "--config",
        type=str,
        default="config/abercrombie_fitch.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--max-products",
        type=int,
        default=None,
        help="Maximum number of products to scrape (for testing)"
    )
    parser.add_argument(
        "--start-url",
        type=str,
        default=None,
        help="Custom start URL (overrides config)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without saving to database"
    )

    args = parser.parse_args()

    # Load configuration
    config = Config(args.config)

    # Setup logging
    setup_logging(config.logging.level, config.logging.file)

    # Create scraper
    scraper = AbercrombieFitchScraper(config, dry_run=args.dry_run)

    try:
        # Run scraping
        await scraper.scrape(
            start_url=args.start_url,
            max_products=args.max_products
        )

        print("✅ Scraping completed successfully!")

    except KeyboardInterrupt:
        print("\n🛑 Scraping interrupted by user")
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        sys.exit(1)
    finally:
        await scraper.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
