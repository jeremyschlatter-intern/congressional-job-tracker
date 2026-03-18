# Congressional Job Tracker - Implementation Plan

## Goal
Build a web-based dashboard that aggregates all congressional job postings from multiple sources, tracks when they first appear, and presents them in a searchable, filterable interface.

## Data Sources

### 1. Senate Job Vacancies
- **Source**: `careers.employment.senate.gov/api/v1/jobs`
- **Format**: JSON API with pagination (25/page)
- **Fields**: title, company/office, location, posted_date, url, description
- **Filters available**: location, position type, company, experience, category, political affiliation, salary

### 2. USA Jobs (Legislative Branch Agencies)
- **Source**: `data.usajobs.gov/api/search`
- **Agency codes**: GAO (LG00), Library of Congress (LC00), Capitol Police (LL03), Architect of the Capitol (LA00)
- **Format**: JSON API
- **Needs**: API key (will try to use without, or request one)

### 3. House Member & Committee Positions
- **Source**: `house.csodfed.com` (Cornerstone OnDemand career portal)
- **Approach**: Scrape the CSOD career site API or use browser automation
- **Alternative**: Check if Employment Bulletin has an accessible format

### 4. House Support Office Positions
- **Source**: Same CSOD portal, different career sites per office
- **Offices**: Chief Administrative Officer, Clerk, Sergeant at Arms, Legislative Counsel

## Architecture

```
┌─────────────────────────────────────────────┐
│             Scrapers/Collectors              │
│  senate_api.py | usajobs_api.py | house.py  │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│           SQLite Database (jobs.db)          │
│  jobs table: id, source, title, office,     │
│  location, url, posted_date, first_seen,    │
│  last_seen, description, salary, category   │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│        Static Site Generator (build.py)     │
│  Generates HTML dashboard from DB data      │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│          Web Dashboard (index.html)         │
│  Searchable, filterable job listings        │
│  Source badges, first-seen tracking         │
└─────────────────────────────────────────────┘
```

## Implementation Steps

1. Set up project structure and database schema
2. Implement Senate API scraper
3. Implement USA Jobs API scraper
4. Implement House CSOD scraper
5. Build static site generator
6. Create polished web dashboard with search/filter
7. Add update automation (cron or script)
8. Test, iterate, polish

## Tech Stack
- Python 3 with requests, sqlite3, BeautifulSoup
- HTML/CSS/JS for the dashboard (no framework needed - keep it simple)
- SQLite for data persistence
- GitHub Pages-ready static output
