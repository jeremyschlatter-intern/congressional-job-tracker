"""Scraper for House of Representatives job postings via CSOD career portal.

Covers multiple House career sites:
  - Site 1: Office of the Clerk
  - Site 3: House Support Offices (main aggregated site)
  - Site 5: Office of the Legislative Counsel
  - Site 19: House Talent Marketplace (member/committee positions)
"""

import requests
import re
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection, upsert_job, mark_inactive, log_scrape, init_db

SOURCE = "house"
BASE_URL = "https://house.csodfed.com"
ENTRY_URL = f"{BASE_URL}/ux/ats/careersite/19/home?c=house"
SEARCH_URL = f"{BASE_URL}/services/x/career-site/v1/search"
DETAIL_URL = f"{BASE_URL}/services/x/career-site/v1/requisition"

# Career sites to scrape and their office names
CAREER_SITES = {
    1: "Office of the Clerk",
    3: "House Support Offices",
    5: "Office of the Legislative Counsel",
    19: "House Talent Marketplace",
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}


def get_session_token():
    """Get a JWT token from the CSOD portal."""
    session = requests.Session()
    r = session.get(ENTRY_URL, headers={
        'User-Agent': HEADERS['User-Agent'],
        'Accept': 'text/html',
    }, timeout=15)
    r.raise_for_status()

    match = re.search(r'"token":"([^"]+)"', r.text)
    if not match:
        raise RuntimeError("Could not extract CSOD JWT token")

    return session, match.group(1)


def fetch_jobs_for_site(session, token, site_id, page_size=100):
    """Fetch all jobs from a career site."""
    all_reqs = []
    page = 1

    auth_headers = {
        **HEADERS,
        'Authorization': f'Bearer {token}',
        'Referer': ENTRY_URL,
    }

    while True:
        resp = session.post(SEARCH_URL, headers=auth_headers, json={
            'careerSiteId': site_id,
            'searchText': '',
            'CultureName': 'en-US',
            'pageNumber': page,
            'pageSize': page_size,
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        reqs = data.get('data', {}).get('requisitions', [])
        if not reqs:
            break

        all_reqs.extend(reqs)
        total = data.get('data', {}).get('totalCount', 0)

        if len(all_reqs) >= total:
            break
        page += 1

    return all_reqs


def normalize_date(date_str):
    """Normalize date format: '3/17/2026' -> 'March 17, 2026'."""
    if not date_str:
        return date_str
    try:
        from datetime import datetime
        # Try m/d/yyyy format
        dt = datetime.strptime(date_str, '%m/%d/%Y')
        return dt.strftime('%B %d, %Y')
    except ValueError:
        return date_str


def parse_job(raw, site_id, office_name):
    """Parse a CSOD requisition into our standard format."""
    locations = raw.get('locations', [])
    if locations:
        loc = locations[0]
        city = loc.get('city', '')
        state = loc.get('state', '')
        if city and state and city != 'None':
            # Normalize: "WASHINGTON, DC" -> "Washington, DC"
            city_norm = city.title()
            if state == 'DC' and city_norm == 'Washington':
                location = "Washington, DC"
            else:
                location = f"{city_norm}, {state}"
        elif state:
            location = state
        else:
            location = ''
    else:
        location = ''

    req_id = raw.get('requisitionId', '')
    url = f"{BASE_URL}/ux/ats/careersite/{site_id}/home/requisition/{req_id}?c=house"

    return {
        'source': SOURCE,
        'source_id': str(req_id),
        'title': raw.get('displayJobTitle', ''),
        'office': office_name,
        'location': location,
        'url': url,
        'posted_date': normalize_date(raw.get('postingEffectiveDate', '')),
        'description': '',
        'salary': '',
        'category': 'House Support' if site_id in (1, 3, 5) else 'House Member/Committee',
        'position_type': 'Employment',
        'experience_level': '',
        'political_affiliation': '',
        'raw_data': json.dumps(raw),
    }


def scrape():
    """Run the House scraper."""
    init_db()
    conn = get_connection()

    try:
        session, token = get_session_token()
        print(f"[House] Got CSOD session token")

        total_found = 0
        total_new = 0
        all_active_ids = []
        seen_req_ids = set()

        for site_id, office_name in CAREER_SITES.items():
            try:
                raw_jobs = fetch_jobs_for_site(session, token, site_id)
                print(f"[House] {office_name} (site {site_id}): {len(raw_jobs)} jobs")

                for raw in raw_jobs:
                    req_id = str(raw.get('requisitionId', ''))
                    # Skip duplicates across sites
                    if req_id in seen_req_ids:
                        continue
                    seen_req_ids.add(req_id)

                    job_data = parse_job(raw, site_id, office_name)
                    all_active_ids.append(job_data['source_id'])
                    is_new = upsert_job(conn, job_data)
                    if is_new:
                        total_new += 1
                        print(f"  NEW: {job_data['title']} @ {job_data['location']}")
                    total_found += 1

            except Exception as e:
                print(f"[House] Error fetching site {site_id} ({office_name}): {e}")

        mark_inactive(conn, SOURCE, all_active_ids)
        log_scrape(conn, SOURCE, total_found, total_new)
        conn.commit()
        print(f"[House] Done: {total_found} total (deduplicated), {total_new} new")

    except Exception as e:
        log_scrape(conn, SOURCE, 0, 0, str(e))
        conn.commit()
        print(f"[House] Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    scrape()
