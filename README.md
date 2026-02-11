# Philippines Founders Scraper

Scrapes founders/owners/managers of Philippines-based companies (10–500 employees) and outputs a CSV with **first name, last name, company name, and email**.

**No API keys required** — uses free public business directories.

## Data Source

| Source | Companies | Data Available |
|---|---|---|
| **BusinessList.ph** | 214,000+ | Contact person, email, employee count, company name, phone |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the scraper (default target: 5,000 records)
python3 scraper.py

# 3. Output is saved to output/ph_founders.csv
```

## Usage

```bash
# Default: collect 5,000 founders
python3 scraper.py

# Custom target and output path
python3 scraper.py --target 7000 --output output/my_list.csv

# Speed up with more concurrent workers (default: 3, max: 5)
python3 scraper.py --workers 5

# Resume from where you left off (uses checkpoint file)
python3 scraper.py --resume

# Combine options
python3 scraper.py --target 10000 --workers 4 --resume
```

## Output Format

CSV file with columns:

| Column | Description |
|---|---|
| `first_name` | Contact person's first name |
| `last_name` | Contact person's last name |
| `company` | Company name |
| `email` | Email address (if available) |
| `title` | Role (e.g., Manager, Owner, Founder, CEO) |

## Features

- **No API keys needed** — scrapes public business directory pages
- **Checkpoint/resume** — saves progress every page; resume with `--resume` if interrupted
- **Concurrent scraping** — 3 workers by default (configurable up to 5)
- **Employee filter** — only includes companies with 10–500 employees
- **Name validation** — filters out invalid/junk contact names
- **60+ Philippine cities** — covers Manila, Quezon City, Makati, Cebu, Davao, and more
- **Polite scraping** — random delays between requests to respect the server

## How It Works

1. Iterates through listing pages for each Philippine city (`/location/{city}/{page}`)
2. Extracts company detail page URLs from each listing page
3. Scrapes each company detail page for: contact person name, email, employee count, company name
4. Filters for companies with 10–500 employees (companies without employee data are included)
5. Saves results to CSV with periodic checkpoints

## Estimated Runtime

| Target | Workers | Approx. Time |
|---|---|---|
| 1,000 | 3 | ~30 min |
| 5,000 | 3 | ~2.5 hrs |
| 5,000 | 5 | ~1.5 hrs |
