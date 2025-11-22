# Abercrombie & Fitch Scraper

A comprehensive scraper for Abercrombie & Fitch products that extracts product information, generates image embeddings using SigLIP, and stores everything in a Supabase database.

## Features

- ✅ Scrapes all products from category pages with pagination support
- ✅ Extracts comprehensive product information (title, price, description, images, etc.)
- ✅ Generates 768-dimensional image embeddings using `google/siglip-base-patch16-384`
- ✅ Stores products in Supabase with proper schema mapping
- ✅ Handles duplicates and updates existing products
- ✅ Robust error handling and logging

## Requirements

- Python 3.8+
- Playwright browser automation
- Supabase account and database

## Installation

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Install Playwright browsers:**
```bash
playwright install chromium
```

3. **Set up environment variables:**
   - The Supabase key is already configured in `config.py`, but you can override it with an environment variable `SUPABASE_KEY` if needed.

## Configuration

Edit `config.py` to customize:
- Supabase URL and API key
- Category URLs to scrape
- Pagination settings
- Browser settings (headless mode, timeouts)

## Quick Start

1. **Verify installation:**
```bash
python setup.py
```

2. **Test components:**
```bash
# Test database connection
python test_scraper.py database

# Test product scraping
python test_scraper.py scrape

# Test embedding generation
python test_scraper.py embedding

# Test full flow
python test_scraper.py
```

3. **Run the scraper:**
```bash
python main.py
```

## Usage

Run the scraper:
```bash
python main.py
```

The scraper will:
1. Discover all product URLs from category pages
2. Scrape detailed information from each product page
3. Generate image embeddings for each product
4. Save everything to your Supabase database

## Database Schema

The scraper maps data to the following Supabase table structure:

- `id`: Unique product ID (MD5 hash of URL)
- `source`: "scraper"
- `product_url`: Full product URL
- `image_url`: Main product image URL
- `brand`: "Abercrombie & Fitch"
- `title`: Product name
- `description`: Product description
- `category`: Product category
- `gender`: MAN, WOMAN, ACCESSORY, or OTHER
- `price`: Product price (float)
- `currency`: Currency code (EUR, USD, etc.)
- `size`: Available sizes
- `second_hand`: FALSE (always)
- `embedding`: 768-dimensional vector from SigLIP model
- `metadata`: JSON string with additional product info
- `created_at`: Timestamp (auto-generated)

## Logging

Logs are written to both:
- Console output
- `scraper.log` file

## Notes

- The scraper includes delays between requests to avoid overwhelming the server
- Products are upserted based on `(source, product_url)` unique constraint
- If embedding generation fails, the product is still saved without embedding
- The scraper handles pagination automatically by detecting URL patterns

## GitHub Actions Workflow

The repository includes a GitHub Actions workflow (`.github/workflows/daily-scrape.yml`) that:
- Runs automatically every day at midnight UTC
- Can be triggered manually from the GitHub Actions tab
- Installs all dependencies and Playwright browsers
- Runs the scraper and uploads logs as artifacts

### Setting up GitHub Actions

1. **Add Supabase Secret:**
   - Go to your repository settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `SUPABASE_KEY`
   - Value: Your Supabase service role key (the one in `config.py`)
   - Click "Add secret"

2. **Enable GitHub Actions:**
   - The workflow is already configured and will run automatically
   - To run manually: Go to Actions tab → "Daily Abercrombie & Fitch Scraper" → "Run workflow"

3. **Monitor Runs:**
   - Check the Actions tab to see workflow runs
   - Logs are automatically uploaded as artifacts for 7 days
   - Failed runs will show error details

## Troubleshooting

- **No products found**: Check if the website structure has changed and update selectors in `product_scraper.py`
- **Embedding errors**: Ensure you have sufficient memory/GPU for the SigLIP model
- **Database errors**: Verify your Supabase credentials and table schema
- **GitHub Actions failures**: Check that the `SUPABASE_KEY` secret is set correctly

