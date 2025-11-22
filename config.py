"""
Configuration file for Abercrombie & Fitch scraper
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase Configuration
SUPABASE_URL = "https://yqawmzggcgpeyaaynrjk.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4")

# Scraper Configuration
BASE_URL = "https://www.abercrombie.com"
EU_BASE_URL = "https://www.abercrombie.com/shop/eu"
MENS_CATEGORY_URL = "https://www.abercrombie.com/shop/eu/mens"
WOMENS_CATEGORY_URL = "https://www.abercrombie.com/shop/eu/womens"

# Pagination
ITEMS_PER_PAGE = 90
MAX_PAGES = 20  # Safety limit

# Scraper Settings
SOURCE_NAME = "scraper"
BRAND_NAME = "Abercrombie & Fitch"
SECOND_HAND = False

# Model Configuration
EMBEDDING_MODEL = "google/siglip-base-patch16-384"
EMBEDDING_DIM = 768

# Request Settings
REQUEST_TIMEOUT = 30
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# Browser Settings
HEADLESS = True  # Set to False for local debugging
BROWSER_TIMEOUT = 30000  # milliseconds

