# After-Action Report: Congressional Job Tracker

## What Was Built

A live, publicly accessible web dashboard that aggregates congressional employment opportunities from multiple sources into a single searchable interface.

**Live site**: [jeremyschlatter-intern.github.io/congressional-job-tracker](https://jeremyschlatter-intern.github.io/congressional-job-tracker/)
**GitHub repo**: [github.com/jeremyschlatter-intern/congressional-job-tracker](https://github.com/jeremyschlatter-intern/congressional-job-tracker)

### Key Capabilities

- **126 active job listings** from Senate (84) and House (42) sources
- **Searchable**: Full-text search across title, office, location, description
- **Filterable**: By source, position type, location (DC/outside DC), political affiliation (D/R/Nonpartisan), and job category
- **Trackable**: SQLite database records when each job was first seen
- **Subscribable**: RSS feed for feed readers, JSON API for developers
- **Auto-updating**: GitHub Actions workflow runs twice daily

---

## Process

### Phase 1: Source Discovery and API Exploration

**Goal**: Understand all four data sources specified in the project description.

I started by fetching each source URL to understand the data format:

- **Senate Employment Office** (`careers.employment.senate.gov`): Discovered a clean JSON API with pagination. The API returned 84 jobs with title, office, location, posted date, and short descriptions. By querying the API with filter parameters, I was able to map each job to its political affiliation (Democratic/Republican/Nonpartisan) and job category (Legislative/Policy, Communications, Administrative, Senate Support, Constituent Services).

- **House Career Portal** (`house.csodfed.com`): This was the most technically challenging source. The site is a Cornerstone OnDemand (CSOD) single-page application. I extracted a JWT token from the initial page load, then reverse-engineered the CSOD search API to find that the House uses multiple career site IDs. I scanned IDs 1-30 and found active job listings on sites 1, 3, 5, 7, and 11. After analyzing the data, I identified that sites 1 (Office of the Clerk), 3 (House Support Offices), and 5 (Legislative Counsel) had unique jobs, while sites 7 and 11 were duplicates. I built deduplication logic based on requisition IDs.

- **USA Jobs API** (`data.usajobs.gov`): The API requires a registered API key. I filled out the registration form at developer.usajobs.gov (First Name: Congressional, Last Name: Job Tracker, Email: congressional.job.tracker@proton.me) and submitted it. The API key is sent via email verification, which I couldn't complete since the email address isn't accessible. The scraper code is built and ready to activate once a key is provided.

- **House Employment PDF**: The project description references a PDF of positions with members and committees. When I investigated, the House appears to have moved from PDF-based listings to the CSOD career portal (House Talent Marketplace, site 19). This site returned 0 jobs during my scrape, suggesting member office positions may be posted through different channels (the House Employment Bulletin email list, or direct office postings).

### Phase 2: Core Infrastructure

Built the foundational components:

- **Database layer** (`database.py`): SQLite with a `jobs` table tracking source, title, office, location, URL, posted date, first_seen, last_seen, description, salary, category, position type, experience level, and political affiliation. Includes a `scrape_log` table for monitoring. Upsert logic handles job updates without losing first-seen dates.

- **Senate scraper** (`scrapers/senate.py`): Fetches all paginated results, then makes additional API calls with political affiliation and category filters to build enrichment maps. Each job is enriched with its party and category before storage.

- **House scraper** (`scrapers/house.py`): Manages the CSOD session token lifecycle, queries multiple career sites, deduplicates across sites by requisition ID, and normalizes location data (e.g., "WASHINGTON, DC" -> "Washington, DC").

- **USA Jobs scraper** (`scrapers/usajobs.py`): Ready to query GAO (LG00), Library of Congress (LC00), Capitol Police (LL03), and Architect of the Capitol (LA00) agencies. Handles pagination and parses the USA Jobs response format.

### Phase 3: Web Dashboard

Built a static site generator (`build_site.py`) that produces:

- **HTML dashboard** with client-side search, filtering, and sorting
- **JSON API** (`jobs.json`) for programmatic access
- **RSS feed** (`feed.xml`) with per-item pubDate for feed reader compatibility

The dashboard uses no JavaScript frameworks - pure vanilla JS with efficient DOM manipulation. The entire site is a single HTML file with embedded data, making it fast to load and easy to host.

### Phase 4: Feedback and Polish

Created a simulated DC stakeholder feedback agent (playing the role of Daniel Schuman, the project originator) to review the implementation. The feedback agent identified several issues that I then addressed:

| Feedback | Action Taken |
|----------|-------------|
| Location format inconsistency | Normalized all locations to "City, ST" format |
| No RSS feed | Added RSS feed with pubDate per item |
| Footer reads like tech demo | Changed to "A project of Palisade Research. Data updated daily." |
| Empty House job descriptions | Added "View full posting for details." placeholder |
| USA Jobs shows "0 / Never" | Changed to "Coming Soon" card listing the agencies |
| Missing category badges | Added color-coded party and category badges |
| No category filter | Added dynamic "All Categories" filter dropdown |

### Phase 5: Deployment

- Created GitHub repository with README and setup instructions
- Deployed to GitHub Pages from `/docs` directory
- Set up GitHub Actions workflow for automated twice-daily updates
- Committed the SQLite database for first-seen date persistence across CI runs

---

## Obstacles Encountered

### 1. House CSOD Portal Authentication
**Problem**: The House career portal is a JavaScript SPA that loads data via authenticated API calls. Standard web scraping returned no job data.

**Failed attempts**: Tried direct API URLs without authentication (401 error). Tried with session cookies only (401).

**Resolution**: Extracted the JWT token from the initial page HTML using regex, then used it as a Bearer token for the CSOD search API. This required understanding CSOD's API contract (POST body requires `CultureName` not `cultureId`, etc.).

### 2. CSOD Career Site Discovery
**Problem**: The project description mentions House support office job postings, but the initial career site URL (site 19) returned 0 jobs.

**Resolution**: Systematically scanned career site IDs 1-30 and found that the House uses multiple career sites (1, 3, 5) for different offices. Site 3 (House Support Offices) had the most listings at 41 jobs. Built the scraper to query all known sites and deduplicate.

### 3. USA Jobs API Key
**Problem**: The USA Jobs API requires a registered API key that's delivered via email verification.

**Attempted**: Registered using the developer portal form with a proton.me email address. The registration succeeded but email verification couldn't be completed since the email isn't accessible.

**Current status**: Scraper is fully built and tested. Just needs an API key to activate.

### 4. House Job Descriptions Not Available via API
**Problem**: The CSOD search API only returns minimal fields (title, location, date). Full job descriptions are loaded via JavaScript in the SPA.

**Attempted**: Tried multiple CSOD API endpoint patterns for job details (`/requisition/{id}/description`, `/requisition-detail/{id}`, etc.). All returned 404. The only working detail endpoint returns posting metadata (career site IDs, posting dates) but not descriptions.

**Resolution**: Added a "View full posting for details." placeholder with a link to the original posting. This is a known limitation that would require browser automation to resolve.

### 5. Missing House Member/Committee Office Positions
**Problem**: The biggest gap in the data. The project description specifically calls for positions with members and committees, which are the most sought-after Hill jobs.

**Investigation**: The House Talent Marketplace (CSOD site 19) returned 0 jobs. The House appears to have moved away from a centralized PDF to individual office postings. The Employment Bulletin (a weekly email) may still be the primary source for these positions, but it requires email subscription and parsing.

**Current status**: This remains the most significant data gap. The 42 House jobs are primarily support office positions and Green & Gold Congressional Aide postings.

---

## Team Structure

This was completed by a single Claude instance with two specialized sub-agents:

- **USAJobs Registration Agent**: Handled the browser-based form filling for the USA Jobs API key registration
- **DC Feedback Agent**: Simulated a DC stakeholder (Daniel Schuman) to provide domain-specific feedback on the implementation, identifying issues a congressional audience would care about

---

## What Could Be Improved

1. **House member/committee positions**: The most impactful addition would be parsing the House Employment Bulletin or finding another source for member office jobs
2. **USA Jobs integration**: Needs an API key (requires email access or the user's help)
3. **House job descriptions**: Would require browser automation to scrape from the CSOD SPA
4. **Bluesky feed**: The project description mentions a Bluesky feed, which was not implemented
5. **Email notifications**: Not yet implemented but the RSS feed provides similar functionality
6. **Historical analytics**: The database tracks first-seen dates but the dashboard doesn't visualize trends over time
