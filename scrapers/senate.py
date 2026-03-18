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


POLITICAL_AFFILIATIONS = {
    680: 'Democratic',
    683: 'Republican',
    682: 'Nonpartisan',
}

CATEGORIES = [
    'Legislative / Policy',
    'Communications',
    'Administrative',
    'Senate Support',
    'Constituent Services',
]


def fetch_all_pages(url_suffix=""):
    """Fetch all paginated results from the Senate API."""
    all_jobs = []
    page = 1
    while True:
        sep = '&' if '?' in url_suffix else '?'
        resp = requests.get(f"{API_URL}{url_suffix}{sep}page={page}", headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get('data', [])
        if not jobs:
            break
        all_jobs.extend(jobs)
        if page >= data.get('meta', {}).get('last_page', 1):
            break
        page += 1
    return all_jobs


def fetch_all_jobs():
    """Fetch all jobs from the Senate Employment API."""
    return fetch_all_pages()


def build_enrichment_maps():
    """Build mappings from job ID to political affiliation and category."""
    affiliation_map = {}
    for filter_val, label in POLITICAL_AFFILIATIONS.items():
        for job in fetch_all_pages(f"?filter_1={filter_val}"):
            affiliation_map[job['id']] = label

    category_map = {}
    for cat in CATEGORIES:
        for job in fetch_all_pages(f"?job_type_filter={cat}"):
            category_map[job['id']] = cat

    return affiliation_map, category_map


def parse_job(raw, affiliation_map=None, category_map=None):
    """Parse a raw Senate API job into our standard format."""
    job_id = raw['id']

    # Extract custom fields
    custom = {item['path']: item['value'] for item in raw.get('customBlockList', [])}

    # Get enriched data
    political = (affiliation_map or {}).get(job_id, custom.get('local_political_affiliation', ''))
    category = (category_map or {}).get(job_id, custom.get('local_job_type', ''))
    salary = custom.get('local_salary', None)

    return {
        'source': SOURCE,
        'source_id': str(job_id),
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

        print("[Senate] Building enrichment maps (affiliation, category)...")
        affiliation_map, category_map = build_enrichment_maps()
        print(f"[Senate] Mapped {len(affiliation_map)} affiliations, {len(category_map)} categories")

        new_count = 0
        active_ids = []

        for raw in raw_jobs:
            job_data = parse_job(raw, affiliation_map, category_map)
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
