"""Scraper for USA Jobs legislative branch positions.

Covers: GAO, Library of Congress, Capitol Police, Architect of the Capitol.
Requires a USA Jobs API key set in environment variable USAJOBS_API_KEY
and email in USAJOBS_EMAIL.
"""

import requests
import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_connection, upsert_job, mark_inactive, log_scrape, init_db

API_URL = "https://data.usajobs.gov/api/search"
SOURCE = "usajobs"

# Legislative branch agencies we want to track
AGENCIES = {
    'LG00': 'Government Accountability Office',
    'LC00': 'Library of Congress',
    'LL03': 'U.S. Capitol Police',
    'LA00': 'Architect of the Capitol',
}


def get_api_credentials():
    """Get API credentials from environment or config file."""
    api_key = os.environ.get('USAJOBS_API_KEY', '')
    email = os.environ.get('USAJOBS_EMAIL', '')

    # Try config file
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(config_path):
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('USAJOBS_API_KEY='):
                    api_key = line.split('=', 1)[1].strip().strip('"\'')
                elif line.startswith('USAJOBS_EMAIL='):
                    email = line.split('=', 1)[1].strip().strip('"\'')

    return api_key, email


def fetch_jobs_for_agency(agency_code, api_key, email):
    """Fetch all jobs for a given agency code."""
    headers = {
        'Host': 'data.usajobs.gov',
        'User-Agent': email,
        'Authorization-Key': api_key,
    }

    all_jobs = []
    page = 1

    while True:
        params = {
            'Organization': agency_code,
            'ResultsPerPage': 500,
            'Page': page,
            'Fields': 'Full',
        }

        resp = requests.get(API_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results = data.get('SearchResult', {})
        items = results.get('SearchResultItems', [])

        if not items:
            break

        all_jobs.extend(items)

        count = int(results.get('SearchResultCount', 0))
        total = int(results.get('SearchResultCountAll', 0))

        if len(all_jobs) >= total:
            break
        page += 1

    return all_jobs


def parse_job(raw):
    """Parse a USA Jobs API result into our standard format."""
    match = raw.get('MatchedObjectDescriptor', {})

    # Get salary info
    remuneration = match.get('PositionRemuneration', [{}])
    salary = ''
    if remuneration:
        r = remuneration[0]
        min_range = r.get('MinimumRange', '')
        max_range = r.get('MaximumRange', '')
        description = r.get('Description', '')
        if min_range and max_range:
            salary = f"${min_range} - ${max_range} {description}"

    # Get location
    locations = match.get('PositionLocation', [])
    location = ', '.join(
        loc.get('LocationName', '') for loc in locations
    ) if locations else ''

    # Get category
    categories = match.get('JobCategory', [])
    category = ', '.join(
        cat.get('Name', '') for cat in categories
    ) if categories else ''

    # Get posting dates
    pub_date = match.get('PublicationStartDate', '')
    if pub_date:
        try:
            dt = datetime.strptime(pub_date, '%Y-%m-%dT%H:%M:%S.%f')
            pub_date = dt.strftime('%B %d, %Y')
        except ValueError:
            pass

    org = match.get('OrganizationName', '')
    dept = match.get('DepartmentName', '')
    office = f"{org}" if org else dept

    return {
        'source': SOURCE,
        'source_id': match.get('PositionID', str(match.get('PositionURI', ''))),
        'title': match.get('PositionTitle', ''),
        'office': office,
        'location': location,
        'url': match.get('PositionURI', ''),
        'posted_date': pub_date,
        'description': match.get('UserArea', {}).get('Details', {}).get('MajorDuties', [''])[0] if match.get('UserArea', {}).get('Details', {}).get('MajorDuties') else match.get('QualificationSummary', ''),
        'salary': salary,
        'category': category,
        'position_type': match.get('PositionSchedule', [{}])[0].get('Name', '') if match.get('PositionSchedule') else '',
        'experience_level': match.get('JobGrade', [{}])[0].get('Code', '') if match.get('JobGrade') else '',
        'political_affiliation': '',
        'raw_data': json.dumps(raw),
    }


def scrape():
    """Run the USA Jobs scraper."""
    api_key, email = get_api_credentials()

    if not api_key or not email:
        print("[USAJobs] No API credentials found. Set USAJOBS_API_KEY and USAJOBS_EMAIL")
        print("          in environment or in .env file.")
        print("          Register at https://developer.usajobs.gov/APIRequest/Index")
        return

    init_db()
    conn = get_connection()

    try:
        total_found = 0
        total_new = 0
        all_active_ids = []

        for code, name in AGENCIES.items():
            try:
                raw_jobs = fetch_jobs_for_agency(code, api_key, email)
                print(f"[USAJobs] {name}: {len(raw_jobs)} jobs")

                for raw in raw_jobs:
                    job_data = parse_job(raw)
                    all_active_ids.append(job_data['source_id'])
                    is_new = upsert_job(conn, job_data)
                    if is_new:
                        total_new += 1
                        print(f"  NEW: {job_data['title']} @ {job_data['office']}")
                    total_found += len(raw_jobs)

            except Exception as e:
                print(f"[USAJobs] Error fetching {name}: {e}")

        mark_inactive(conn, SOURCE, all_active_ids)
        log_scrape(conn, SOURCE, total_found, total_new)
        conn.commit()
        print(f"[USAJobs] Done: {total_found} total, {total_new} new")

    except Exception as e:
        log_scrape(conn, SOURCE, 0, 0, str(e))
        conn.commit()
        print(f"[USAJobs] Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    scrape()
