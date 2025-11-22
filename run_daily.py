#!/usr/bin/env python3
"""
Daily scraper runner script
Can be used locally or in automation
"""

import argparse
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scrapers.abercrombie_fitch import AbercrombieFitchScraper
from utils.config import Config
from utils.logger import setup_logging
import asyncio


async def run_daily_scrape(max_products: int = 50, dry_run: bool = False):
    """Run the daily scraping routine"""

    print("🤖 Starting daily Abercrombie & Fitch scrape...")
    print(f"📊 Max products: {max_products}")
    print(f"🔧 Dry run: {dry_run}")
    print("-" * 50)

    # Load configuration
    config_path = "config/abercrombie_fitch.yaml"
    if not Path(config_path).exists():
        print(f"❌ Configuration file not found: {config_path}")
        return False

    config = Config(config_path)

    # Setup logging
    setup_logging(config.logging.level, config.logging.file)

    # Create scraper
    scraper = AbercrombieFitchScraper(config, dry_run=dry_run)

    try:
        # Run scraping
        result = await scraper.scrape(max_products=max_products)

        print("-" * 50)
        print("✅ Daily scrape completed!")
        print(f"📈 Products found: {result.get('products_found', 0)}")
        print(f"💾 Products saved: {result.get('products_saved', 0)}")
        print(f"🎯 Success: {result.get('success', False)}")

        if not result.get('success', False):
            print(f"❌ Error: {result.get('error', 'Unknown error')}")
            return False

        return True

    except Exception as e:
        print(f"❌ Daily scrape failed: {e}")
        return False

    finally:
        await scraper.cleanup()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Daily Abercrombie & Fitch Scraper")
    parser.add_argument(
        "--max-products",
        type=int,
        default=50,
        help="Maximum products to scrape (default: 50)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no database writes)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/abercrombie_fitch.yaml",
        help="Path to configuration file"
    )

    args = parser.parse_args()

    # Check for required environment variables
    if not args.dry_run:
        if not os.getenv('SUPABASE_URL') or not os.getenv('SUPABASE_ANON_KEY'):
            print("❌ SUPABASE_URL and SUPABASE_ANON_KEY environment variables required")
            print("💡 Use --dry-run for testing without database")
            sys.exit(1)

    # Run the scrape
    success = asyncio.run(run_daily_scrape(
        max_products=args.max_products,
        dry_run=args.dry_run
    ))

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
