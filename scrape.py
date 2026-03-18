#!/usr/bin/env python3
"""Run all scrapers and update the database."""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import init_db, get_stats

def main():
    init_db()
    print(f"=== Congressional Job Tracker - Scrape Run ===")
    print(f"Time: {datetime.utcnow().isoformat()}Z")
    print()

    # Run Senate scraper
    try:
        from scrapers.senate import scrape as scrape_senate
        scrape_senate()
    except Exception as e:
        print(f"[Senate] FAILED: {e}")
    print()

    # Run House scraper
    try:
        from scrapers.house import scrape as scrape_house
        scrape_house()
    except Exception as e:
        print(f"[House] FAILED: {e}")
    print()

    # Run USA Jobs scraper
    try:
        from scrapers.usajobs import scrape as scrape_usajobs
        scrape_usajobs()
    except Exception as e:
        print(f"[USAJobs] FAILED: {e}")
    print()

    # Print summary
    stats = get_stats()
    print(f"=== Summary ===")
    print(f"Total active jobs: {stats['total_active']}")
    print(f"Total ever tracked: {stats['total_ever']}")
    print(f"By source:")
    for source, count in stats['by_source'].items():
        print(f"  {source}: {count}")

if __name__ == '__main__':
    main()
