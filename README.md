# Abercrombie & Fitch Fashion Product Scraper

A comprehensive web scraper for Abercrombie & Fitch that extracts product data, generates AI embeddings using SigLIP, and stores everything in Supabase.

## Features

- 🕷️ **Browser Automation**: Uses Playwright for robust web scraping with dynamic content handling
- 🧠 **AI Embeddings**: Generates high-quality image embeddings using Google's SigLIP model
- 🗄️ **Database Integration**: Stores structured product data in Supabase with PostgreSQL
- ⚙️ **Modular Architecture**: Clean separation of concerns with database, embeddings, and scraping modules
- 📊 **Comprehensive Logging**: Detailed logging and monitoring throughout the pipeline
- 🔧 **YAML Configuration**: Easy-to-modify brand-specific configurations
- 📦 **Batch Processing**: Efficient batch operations for database inserts and embedding generation

## Architecture

```
├── config/                 # YAML configuration files
├── src/
│   ├── database/          # Supabase integration
│   ├── embeddings/        # SigLIP model processing
│   ├── scrapers/          # Brand-specific scrapers
│   └── utils/             # Logging and configuration
├── logs/                  # Log files
├── cache/                 # Image and model cache
└── main.py               # Entry point
```

## Database Schema

The scraper expects a Supabase table with this schema:

```sql
CREATE TABLE products (
  id text not null PRIMARY KEY,
  source text null,
  product_url text null,
  affiliate_url text null,
  image_url text not null,
  brand text null,
  title text not null,
  description text null,
  category text null,
  gender text null,
  price double precision null,
  currency text null,
  search_tsv tsvector null,
  created_at timestamp with time zone null default now(),
  metadata text null,
  size text null,
  second_hand boolean null default false,
  embedding public.vector null
);
```

## Installation

1. **Clone and setup environment:**
   ```bash
   git clone <repository-url>
   cd scraper-af
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # Linux/Mac
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers:**
   ```bash
   playwright install
   ```

4. **Setup environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials
   ```

## Configuration

### Environment Variables (.env)
```bash
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key
```

### Brand Configuration (config/abercrombie_fitch.yaml)

```yaml
brand:
  name: "Abercrombie & Fitch"
  source: "abercrombie_fitch"
  base_url: "https://www.abercrombie.com"
  category_url: "https://www.abercrombie.com/shop/eu/mens"
  currency: "EUR"
  gender: "men"
  second_hand: false

scraping:
  max_concurrent_pages: 3
  request_delay: 2
  max_retries: 3
  timeout: 30000

embeddings:
  model_name: "google/siglip-base-patch16-384"
  device: "auto"
  cache_dir: "./cache/embeddings"
```

## Usage

### Local Scraping

#### Basic Scraping
```bash
python main.py
```

#### Custom Options
```bash
# Scrape with custom URL
python main.py --start-url "https://www.abercrombie.com/shop/eu/womens"

# Limit products for testing
python main.py --max-products 10

# Dry run (no database saves)
python main.py --dry-run
```

### Automated Daily Scraping

The scraper includes a GitHub Actions workflow that runs automatically every day at midnight UTC.

#### Setup GitHub Secrets

To enable automated scraping, add these secrets to your GitHub repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add the following secrets:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_ANON_KEY`: Your Supabase anonymous key

#### Workflow Features

- **Daily Schedule**: Runs automatically at midnight UTC every day
- **Manual Trigger**: Can be triggered manually from the Actions tab
- **Configurable Limits**: Default max 50 products per run (configurable)
- **Dry Run Mode**: Safe testing mode that doesn't save to database
- **Comprehensive Logging**: Detailed logs and artifacts for debugging
- **Error Handling**: Proper failure notifications and status reporting

#### Manual Workflow Trigger

1. Go to the **Actions** tab in your GitHub repository
2. Select **"Daily Fashion Product Scrape"** workflow
3. Click **"Run workflow"**
4. Configure options:
   - **Max products**: Number of products to scrape (default: 50)
   - **Dry run**: Enable for testing without database writes

#### Workflow Status

Monitor workflow runs in the **Actions** tab. Each run provides:
- Execution logs
- Scraped data summary
- Error reports and artifacts
- Performance metrics

### Advanced Usage

```python
from src.scrapers.abercrombie_fitch import AbercrombieFitchScraper
from src.utils.config import Config

# Load config
config = Config("config/abercrombie_fitch.yaml")

# Create scraper
scraper = AbercrombieFitchScraper(config)

# Run scraping
import asyncio
result = asyncio.run(scraper.scrape(max_products=50))
print(f"Scraped {result['products_saved']} products")
```

## Scraping Strategy

The scraper implements several strategies for robust data extraction:

1. **Dynamic Content Handling**: Uses Playwright to wait for JavaScript-rendered content
2. **Pagination Support**: Automatically handles category pagination and "load more" buttons
3. **Rate Limiting**: Configurable delays between requests to respect website limits
4. **Error Recovery**: Continues scraping even if individual products fail
5. **Duplicate Prevention**: Checks for existing products before processing
6. **Concurrent Processing**: Processes multiple products simultaneously for efficiency

## AI Embeddings

The scraper uses Google's SigLIP model to generate 768-dimensional embeddings for product images:

- **Model**: `google/siglip-base-patch16-384`
- **Dimensions**: 768
- **Device**: Auto-detects CUDA/CPU
- **Caching**: Downloads and caches images locally
- **Batch Processing**: Generates embeddings for multiple images concurrently

## Logging

Comprehensive logging is provided at multiple levels:

- **Console Output**: Real-time progress with colored output
- **File Logging**: Detailed logs saved to `logs/scraper.log`
- **Log Rotation**: Automatic log rotation and cleanup
- **Structured Data**: JSON metadata stored with each product

## Error Handling

The scraper includes robust error handling:

- **Network Errors**: Automatic retries with exponential backoff
- **Parsing Errors**: Graceful handling of missing or malformed data
- **Database Errors**: Transaction rollback and error recovery
- **Resource Cleanup**: Proper cleanup of browser instances and connections

## Performance Optimization

Several optimizations are implemented:

- **Connection Pooling**: Reuses database connections
- **Image Caching**: Local caching of downloaded images
- **Batch Operations**: Bulk database inserts and embedding generation
- **Concurrent Processing**: Parallel product processing within rate limits
- **Memory Management**: Efficient cleanup of large objects

## Monitoring & Maintenance

### Health Checks
- Database connectivity verification
- Model loading validation
- Browser automation tests

### Maintenance Tasks
- Log rotation and cleanup
- Cache directory management
- Database index optimization

## Contributing

1. Follow the modular architecture
2. Add comprehensive logging
3. Include error handling
4. Update documentation
5. Test thoroughly before committing

## License

[Add your license information here]

## Support

For issues and questions:
- Check the logs in `logs/scraper.log`
- Verify configuration in `config/abercrombie_fitch.yaml`
- Ensure Supabase credentials are correct
- Test network connectivity to target website
