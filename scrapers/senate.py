"""Scraper for Senate Employment Office job vacancies."""

import requests
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection, upsert_job, mark_inactive, log_scrape, init_db

API_URL = "https://careers.employment.senate.gov/api/v1/jobs"
SOURCE = "senate"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://careers.employment.senate.gov/',
}


def fetch_all_jobs():
    """Fetch all jobs from the Senate Employment API."""
    all_jobs = []
    page = 1

    while True:
        resp = requests.get(f"{API_URL}?page={page}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        jobs = data.get('data', [])
        if not jobs:
            break

        all_jobs.extend(jobs)

        meta = data.get('meta', {})
        last_page = meta.get('last_page', 1)
        if page >= last_page:
            break
        page += 1

    return all_jobs


def parse_job(raw):
    """Parse a raw Senate API job into our standard format."""
    # Extract custom fields
    custom = {item['path']: item['value'] for item in raw.get('customBlockList', [])}

    # Extract salary from custom blocks if available
    salary = custom.get('local_salary', None)

    # Determine category from custom blocks
    category = custom.get('local_job_type', None)

    # Political affiliation from company or custom blocks
    political = custom.get('local_political_affiliation', None)

    return {
        'source': SOURCE,
        'source_id': str(raw['id']),
        'title': raw.get('title', ''),
        'office': raw.get('company', {}).get('name', ''),
        'location': raw.get('location', ''),
        'url': raw.get('url', ''),
        'posted_date': raw.get('posted_date', ''),
        'description': raw.get('shortDescription', ''),
        'salary': salary,
        'category': category,
        'position_type': custom.get('local_position_type', ''),
        'experience_level': custom.get('local_experience_level', ''),
        'political_affiliation': political,
        'raw_data': json.dumps(raw),
    }


def scrape():
    """Run the Senate scraper."""
    init_db()
    conn = get_connection()

    try:
        raw_jobs = fetch_all_jobs()
        print(f"[Senate] Fetched {len(raw_jobs)} jobs from API")

        new_count = 0
        active_ids = []

        for raw in raw_jobs:
            job_data = parse_job(raw)
            active_ids.append(job_data['source_id'])
            is_new = upsert_job(conn, job_data)
            if is_new:
                new_count += 1
                print(f"  NEW: {job_data['title']} @ {job_data['office']}")

        # Mark jobs no longer in the feed as inactive
        mark_inactive(conn, SOURCE, active_ids)

        log_scrape(conn, SOURCE, len(raw_jobs), new_count)
        conn.commit()
        print(f"[Senate] Done: {len(raw_jobs)} total, {new_count} new")

    except Exception as e:
        log_scrape(conn, SOURCE, 0, 0, str(e))
        conn.commit()
        print(f"[Senate] Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    scrape()
