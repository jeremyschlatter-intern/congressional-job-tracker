# Congressional Job Tracker

Aggregating employment opportunities across the U.S. Congress into a single, searchable dashboard.

**Live site**: [jeremyschlatter-intern.github.io/congressional-job-tracker](https://jeremyschlatter-intern.github.io/congressional-job-tracker/)

## Data Sources

| Source | Jobs | Description |
|--------|------|-------------|
| **U.S. Senate** | ~84 | Senate Employment Office API - senator offices, committees, institutional offices |
| **U.S. House** | ~42 | House CSOD Career Portal - Clerk, Sergeant at Arms, Legislative Counsel, support offices |
| **USA Jobs** | Pending | GAO, Library of Congress, Capitol Police, Architect of the Capitol |

## Features

- **Search** across all fields (title, office, location, description)
- **Filter** by source, position type, location, political affiliation, job category
- **Sort** by post date or tracking date
- **Track** when jobs first appeared (first-seen date tracking)
- **RSS feed** at [`/feed.xml`](https://jeremyschlatter-intern.github.io/congressional-job-tracker/feed.xml)
- **JSON API** at [`/jobs.json`](https://jeremyschlatter-intern.github.io/congressional-job-tracker/jobs.json)
- **Auto-updates** via GitHub Actions (twice daily)

## Running Locally

```bash
# Install dependencies
pip install requests beautifulsoup4

# Run scrapers to collect job data
python scrape.py

# Build the static site
python build_site.py

# Serve locally
cd docs && python -m http.server 8000
```

## Adding USA Jobs Support

Register for an API key at [developer.usajobs.gov](https://developer.usajobs.gov/APIRequest/Index), then:

```bash
# Set credentials
export USAJOBS_API_KEY="your-key"
export USAJOBS_EMAIL="your-email"

# Or create a .env file
echo 'USAJOBS_API_KEY=your-key' >> .env
echo 'USAJOBS_EMAIL=your-email' >> .env

# Run scrapers
python scrape.py
```

## Architecture

- **Scrapers** (`scrapers/`): Python modules for each data source
- **Database** (`database.py`): SQLite with first-seen/last-seen tracking
- **Site generator** (`build_site.py`): Generates static HTML, JSON, and RSS
- **Output** (`docs/`): Static files served by GitHub Pages

## A project of [Palisade Research](https://palisaderesearch.org)
