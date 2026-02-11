# Philippines Founders Scraper

Scrapes founders/CEOs of Philippines-based companies (10–500 employees) and outputs a CSV with **first name, last name, company name, and email**.

## Data Sources

| Source | What it provides | Free tier |
|---|---|---|
| **Apollo.io** (primary) | People search filtered by location, title, company size. Returns name, email, company, title. | 10,000 credits/month |
| **Hunter.io** (optional) | Email enrichment for records missing an email address. | 25 searches/month (free), 500/month (starter) |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env and add your Apollo.io API key (required)

# 3. Run the scraper (default target: 5,000 records)
python3 scraper.py

# 4. Output is saved to output/ph_founders.csv
```

## Getting API Keys

### Apollo.io (required)
1. Sign up at [apollo.io](https://www.apollo.io/) (free plan available)
2. Go to **Settings > Integrations > API**
3. Copy your API key into `.env`

### Hunter.io (optional — email enrichment)
1. Sign up at [hunter.io](https://hunter.io/)
2. Go to **Dashboard > API**
3. Copy your API key into `.env`

## Usage

```bash
# Default: collect 5,000 founders
python3 scraper.py

# Custom target and output
python3 scraper.py --target 7000 --output output/my_list.csv

# With Hunter.io email enrichment for missing emails
python3 scraper.py --enrich

# Limit Hunter enrichment to first 200 missing-email records
python3 scraper.py --enrich --enrich-limit 200
```

## Output Format

CSV file with columns:

| Column | Description |
|---|---|
| `first_name` | Founder's first name |
| `last_name` | Founder's last name |
| `company` | Company name |
| `email` | Email address (if available) |
| `title` | Job title (e.g., Founder, CEO) |

## Tips for Reaching 5,000+

- **Apollo.io free tier** gives 10,000 credits/month — each page of 100 results costs ~1 credit, so you can search through ~1M records per month.
- The scraper automatically cycles through multiple founder-related titles (founder, CEO, owner, managing director, president) to maximize unique results.
- If you need more than the free tier provides, Apollo's paid plans unlock deeper search access.
- Run with `--enrich` to fill in missing emails via Hunter.io.
