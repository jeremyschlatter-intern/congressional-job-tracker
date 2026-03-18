#!/usr/bin/env python3
"""Generate the static HTML dashboard from the jobs database."""

import json
import os
import sys
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_connection, init_db

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs')


def get_jobs_data():
    """Get all active jobs as a list of dicts."""
    conn = get_connection()
    jobs = conn.execute("""
        SELECT id, source, title, office, location, url, posted_date,
               first_seen, last_seen, description, salary, category,
               position_type, experience_level, political_affiliation
        FROM jobs WHERE is_active = 1
        ORDER BY first_seen DESC
    """).fetchall()

    stats = {
        'total': len(jobs),
        'by_source': {},
        'by_category': {},
        'by_location_state': {},
    }

    result = []
    for j in jobs:
        d = dict(j)

        # Count by source
        src = d['source']
        stats['by_source'][src] = stats['by_source'].get(src, 0) + 1

        # Count by category
        cat = d.get('category') or 'Other'
        stats['by_category'][cat] = stats['by_category'].get(cat, 0) + 1

        # Parse location for state
        loc = d.get('location', '')
        if loc:
            parts = [p.strip() for p in loc.split(',')]
            state = parts[-1] if len(parts) >= 2 else loc
            stats['by_location_state'][state] = stats['by_location_state'].get(state, 0) + 1

        result.append(d)

    # Get last scrape times
    scrape_log = conn.execute("""
        SELECT source, MAX(scraped_at) as last_scraped,
               SUM(jobs_found) as total_found
        FROM scrape_log
        GROUP BY source
    """).fetchall()
    stats['last_scraped'] = {row['source']: row['last_scraped'] for row in scrape_log}

    conn.close()
    return result, stats


def source_label(source):
    return {
        'senate': 'U.S. Senate',
        'house': 'U.S. House',
        'usajobs': 'USA Jobs',
    }.get(source, source.title())


def source_color(source):
    return {
        'senate': '#1a365d',
        'house': '#742a2a',
        'usajobs': '#22543d',
    }.get(source, '#4a5568')


def source_bg(source):
    return {
        'senate': '#ebf4ff',
        'house': '#fff5f5',
        'usajobs': '#f0fff4',
    }.get(source, '#f7fafc')


def build_html(jobs, stats):
    now = datetime.utcnow().strftime('%B %d, %Y at %I:%M %p UTC')

    # Prepare jobs JSON for the frontend
    jobs_json = json.dumps(jobs, default=str)

    # Build stats cards
    source_cards = ''
    for src in ['senate', 'house', 'usajobs']:
        count = stats['by_source'].get(src, 0)
        last = stats.get('last_scraped', {}).get(src, 'Never')
        if last != 'Never':
            try:
                dt = datetime.fromisoformat(last)
                last = dt.strftime('%b %d, %Y %I:%M %p')
            except:
                pass
        source_cards += f'''
        <div class="stat-card" style="border-left: 4px solid {source_color(src)}">
            <div class="stat-number">{count}</div>
            <div class="stat-label">{source_label(src)}</div>
            <div class="stat-meta">Last updated: {last}</div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Congressional Job Tracker</title>
    <link rel="alternate" type="application/rss+xml" title="Congressional Job Tracker" href="feed.xml">
    <style>
        :root {{
            --navy: #1a365d;
            --red: #742a2a;
            --gold: #b7791f;
            --bg: #f7f8fa;
            --card-bg: #ffffff;
            --text: #1a202c;
            --text-secondary: #4a5568;
            --border: #e2e8f0;
            --shadow: 0 1px 3px rgba(0,0,0,0.08);
            --shadow-lg: 0 4px 12px rgba(0,0,0,0.1);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        .header {{
            background: linear-gradient(135deg, var(--navy) 0%, #2c5282 100%);
            color: white;
            padding: 2rem 0;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}

        .header::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M54.627 0l.83.828-1.415 1.415L51.8 0h2.827zM5.373 0l-.83.828L5.96 2.243 8.2 0H5.374zM48.97 0l3.657 3.657-1.414 1.414L46.143 0h2.828zM11.03 0L7.372 3.657 8.787 5.07 13.857 0H11.03zm32.284 0L49.8 6.485 48.384 7.9l-7.9-7.9h2.83zM16.686 0L10.2 6.485 11.616 7.9l7.9-7.9h-2.83zM22.344 0L13.858 8.485 15.272 9.9l9.9-9.9h-2.828zM32 0l-3.486 3.485-1.414-1.414L30.172 0H32z' fill='%23ffffff' fill-opacity='0.05' fill-rule='evenodd'/%3E%3C/svg%3E");
        }}

        .header-content {{
            position: relative;
            z-index: 1;
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 1.5rem;
        }}

        .header h1 {{
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 0.25rem;
        }}

        .header p {{
            font-size: 1.05rem;
            opacity: 0.85;
            max-width: 600px;
            margin: 0 auto;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 1.5rem;
        }}

        .stats-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}

        .stat-card {{
            background: var(--card-bg);
            padding: 1.25rem;
            border-radius: 8px;
            box-shadow: var(--shadow);
        }}

        .stat-number {{
            font-size: 2rem;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 0.25rem;
        }}

        .stat-label {{
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .stat-meta {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
            opacity: 0.7;
        }}

        .controls {{
            background: var(--card-bg);
            padding: 1.25rem;
            border-radius: 8px;
            box-shadow: var(--shadow);
            margin-bottom: 1.5rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            align-items: center;
        }}

        .search-box {{
            flex: 1;
            min-width: 250px;
            padding: 0.6rem 1rem;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .search-box:focus {{
            border-color: var(--navy);
            box-shadow: 0 0 0 3px rgba(26,54,93,0.1);
        }}

        .filter-select {{
            padding: 0.6rem 0.75rem;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 0.9rem;
            background: white;
            cursor: pointer;
            outline: none;
        }}

        .filter-select:focus {{
            border-color: var(--navy);
        }}

        .results-count {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-left: auto;
            white-space: nowrap;
        }}

        .jobs-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .job-card {{
            background: var(--card-bg);
            border-radius: 8px;
            box-shadow: var(--shadow);
            padding: 1.25rem 1.5rem;
            transition: box-shadow 0.2s, transform 0.1s;
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 0.75rem;
            align-items: start;
        }}

        .job-card:hover {{
            box-shadow: var(--shadow-lg);
            transform: translateY(-1px);
        }}

        .job-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--navy);
            text-decoration: none;
            display: inline-block;
            margin-bottom: 0.25rem;
        }}

        .job-title:hover {{
            text-decoration: underline;
        }}

        .job-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            align-items: center;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }}

        .job-meta-item {{
            display: flex;
            align-items: center;
            gap: 0.25rem;
        }}

        .job-meta-item svg {{
            width: 14px;
            height: 14px;
            flex-shrink: 0;
            opacity: 0.6;
        }}

        .job-desc {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
            line-height: 1.5;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .badge {{
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            white-space: nowrap;
        }}

        .badge-source {{
            color: white;
        }}

        .badge-new {{
            background: #fefcbf;
            color: #975a16;
            border: 1px solid #ecc94b;
        }}

        .badge-category {{
            background: #e2e8f0;
            color: #4a5568;
        }}

        .job-right {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.4rem;
        }}

        .first-seen {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            opacity: 0.6;
        }}

        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: var(--text-secondary);
        }}

        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        .footer a {{
            color: var(--navy);
        }}

        .new-indicator {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #ecc94b;
            margin-right: 0.25rem;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        @media (max-width: 768px) {{
            .header h1 {{ font-size: 1.5rem; }}
            .job-card {{ grid-template-columns: 1fr; }}
            .job-right {{ flex-direction: row; align-items: center; }}
            .controls {{ flex-direction: column; }}
            .search-box {{ min-width: unset; width: 100%; }}
            .results-count {{ margin-left: 0; }}
        }}

        .sort-btn {{
            padding: 0.4rem 0.75rem;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 0.85rem;
            background: white;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .sort-btn:hover {{ background: #f7fafc; }}
        .sort-btn.active {{ background: var(--navy); color: white; border-color: var(--navy); }}

        .loading {{
            display: flex; justify-content: center; padding: 2rem;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>Congressional Job Tracker</h1>
            <p>Aggregating employment opportunities across the U.S. Congress. Updated {now}.</p>
        </div>
    </div>

    <div class="container">
        <div class="stats-row">
            <div class="stat-card" style="border-left: 4px solid var(--gold)">
                <div class="stat-number" id="total-count">{stats['total']}</div>
                <div class="stat-label">Active Positions</div>
                <div class="stat-meta">Across all sources</div>
            </div>
            {source_cards}
        </div>

        <div class="controls">
            <input type="text" class="search-box" id="search"
                   placeholder="Search jobs by title, office, location...">

            <select class="filter-select" id="filter-source">
                <option value="">All Sources</option>
                <option value="senate">U.S. Senate</option>
                <option value="house">U.S. House</option>
                <option value="usajobs">USA Jobs</option>
            </select>

            <select class="filter-select" id="filter-type">
                <option value="">All Types</option>
                <option value="Employment">Employment</option>
                <option value="Internships">Internships</option>
            </select>

            <select class="filter-select" id="filter-location">
                <option value="">All Locations</option>
                <option value="DC">Washington, DC</option>
                <option value="other">Outside DC</option>
            </select>

            <select class="filter-select" id="filter-party">
                <option value="">All Affiliations</option>
                <option value="Democratic">Democratic</option>
                <option value="Republican">Republican</option>
                <option value="Nonpartisan">Nonpartisan</option>
            </select>

            <select class="filter-select" id="filter-category">
                <option value="">All Categories</option>
            </select>

            <button class="sort-btn active" id="sort-posted" onclick="sortJobs('posted')">Recently Posted</button>
            <button class="sort-btn" id="sort-newest" onclick="sortJobs('newest')">Recently Tracked</button>

            <span class="results-count" id="results-count"></span>
        </div>

        <div class="jobs-list" id="jobs-list">
        </div>

        <div class="empty-state" id="empty-state" style="display:none">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom:1rem;opacity:0.4">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <p>No jobs match your search criteria.</p>
        </div>
    </div>

    <div class="footer">
        <p>Data sourced from
            <a href="https://careers.employment.senate.gov/" target="_blank">Senate Employment Office</a>,
            <a href="https://house.csodfed.com/ux/ats/careersite/3/home?c=house" target="_blank">House Career Portal</a>, and
            <a href="https://www.usajobs.gov/" target="_blank">USA Jobs</a>.
            &bull; <a href="jobs.json">JSON API</a>
            &bull; <a href="feed.xml">RSS Feed</a>
        </p>
        <p style="margin-top:0.5rem">
            A project of <a href="https://palisaderesearch.org" target="_blank">Palisade Research</a>. Data updated daily.
        </p>
    </div>

    <script>
    const JOBS = {jobs_json};
    let currentSort = 'posted';
    let filteredJobs = [...JOBS];

    const svgIcons = {{
        office: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18M3 7V5a2 2 0 012-2h14a2 2 0 012 2v2M6 21V9m4 12V9m4 12V9m4 12V9"/></svg>',
        location: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
        salary: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>',
    }};

    const sourceColors = {{
        senate: {{ bg: '#ebf4ff', color: '#1a365d' }},
        house: {{ bg: '#fff5f5', color: '#742a2a' }},
        usajobs: {{ bg: '#f0fff4', color: '#22543d' }},
    }};

    const sourceLabels = {{
        senate: 'U.S. Senate',
        house: 'U.S. House',
        usajobs: 'USA Jobs',
    }};

    function isNewJob(job) {{
        // Use posted_date if available, fall back to first_seen
        const dateStr = job.posted_date || job.first_seen;
        if (!dateStr) return false;
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return false;
        const now = new Date();
        const diffDays = (now - d) / (1000 * 60 * 60 * 24);
        return diffDays <= 7;
    }}

    function formatDate(dateStr) {{
        if (!dateStr) return '';
        try {{
            // Handle various date formats
            let d;
            if (dateStr.includes('T')) {{
                d = new Date(dateStr);
            }} else if (dateStr.includes('/')) {{
                const parts = dateStr.split('/');
                d = new Date(parts[2], parts[0]-1, parts[1]);
            }} else {{
                d = new Date(dateStr);
            }}
            if (isNaN(d.getTime())) return dateStr;
            return d.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric', year: 'numeric' }});
        }} catch(e) {{
            return dateStr;
        }}
    }}

    function renderJob(job) {{
        const sc = sourceColors[job.source] || {{ bg: '#f7fafc', color: '#4a5568' }};
        const isNew = isNewJob(job);
        const desc = job.description ? `<div class="job-desc">${{escapeHtml(job.description)}}</div>` : '';

        let metaItems = '';
        if (job.office) {{
            metaItems += `<span class="job-meta-item">${{svgIcons.office}} ${{escapeHtml(job.office)}}</span>`;
        }}
        if (job.location) {{
            metaItems += `<span class="job-meta-item">${{svgIcons.location}} ${{escapeHtml(job.location)}}</span>`;
        }}
        if (job.posted_date) {{
            metaItems += `<span class="job-meta-item">${{svgIcons.calendar}} Posted ${{formatDate(job.posted_date)}}</span>`;
        }}
        if (job.salary) {{
            metaItems += `<span class="job-meta-item">${{svgIcons.salary}} ${{escapeHtml(job.salary)}}</span>`;
        }}

        let badges = '';
        if (isNew) {{
            badges += `<span class="badge badge-new"><span class="new-indicator"></span>New</span>`;
        }}
        if (job.political_affiliation) {{
            const partyColors = {{
                'Democratic': 'background:#dbeafe;color:#1e40af;border:1px solid #93c5fd',
                'Republican': 'background:#fee2e2;color:#991b1b;border:1px solid #fca5a5',
                'Nonpartisan': 'background:#e2e8f0;color:#475569;border:1px solid #cbd5e1',
            }};
            const ps = partyColors[job.political_affiliation] || '';
            badges += `<span class="badge" style="${{ps}}">${{escapeHtml(job.political_affiliation)}}</span>`;
        }}
        if (job.position_type === 'Internships') {{
            badges += `<span class="badge badge-category">Internship</span>`;
        }}
        if (job.category) {{
            badges += `<span class="badge badge-category">${{escapeHtml(job.category)}}</span>`;
        }}

        return `
        <div class="job-card">
            <div>
                <a href="${{escapeHtml(job.url || '#')}}" target="_blank" class="job-title">${{escapeHtml(job.title)}}</a>
                <div class="job-meta">${{metaItems}}</div>
                ${{desc}}
            </div>
            <div class="job-right">
                <span class="badge badge-source" style="background:${{sc.color}}">${{sourceLabels[job.source] || job.source}}</span>
                ${{badges}}
                <span class="first-seen">Tracked since ${{formatDate(job.first_seen)}}</span>
            </div>
        </div>`;
    }}

    function escapeHtml(str) {{
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }}

    function filterAndRender() {{
        const searchTerm = document.getElementById('search').value.toLowerCase();
        const sourceFilter = document.getElementById('filter-source').value;
        const typeFilter = document.getElementById('filter-type').value;
        const locationFilter = document.getElementById('filter-location').value;
        const partyFilter = document.getElementById('filter-party').value;
        const categoryFilter = document.getElementById('filter-category').value;

        filteredJobs = JOBS.filter(job => {{
            // Search
            if (searchTerm) {{
                const searchable = [
                    job.title, job.office, job.location, job.description,
                    job.category, job.political_affiliation
                ].filter(Boolean).join(' ').toLowerCase();
                if (!searchable.includes(searchTerm)) return false;
            }}

            // Source filter
            if (sourceFilter && job.source !== sourceFilter) return false;

            // Type filter
            if (typeFilter && job.position_type !== typeFilter) return false;

            // Location filter
            if (locationFilter === 'DC') {{
                const loc = (job.location || '').toLowerCase();
                if (!loc.includes('washington') && !loc.includes('d.c.') && !loc.includes('dc')) return false;
            }} else if (locationFilter === 'other') {{
                const loc = (job.location || '').toLowerCase();
                if (loc.includes('washington') || loc.includes('d.c.') || loc.includes(', dc')) return false;
            }}

            // Political affiliation filter
            if (partyFilter && job.political_affiliation !== partyFilter) return false;

            // Category filter
            if (categoryFilter && job.category !== categoryFilter) return false;

            return true;
        }});

        // Sort and render
        sortJobs(currentSort);
    }}

    function sortJobs(sortType, render = true) {{
        currentSort = sortType;

        document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(`sort-${{sortType}}`).classList.add('active');

        if (sortType === 'newest') {{
            filteredJobs.sort((a, b) => {{
                // Sort by first_seen, then posted_date as tiebreaker
                const cmp = (b.first_seen || '').localeCompare(a.first_seen || '');
                if (cmp !== 0) return cmp;
                return parseDate(b.posted_date) - parseDate(a.posted_date);
            }});
        }} else if (sortType === 'posted') {{
            filteredJobs.sort((a, b) => {{
                const da = parseDate(a.posted_date);
                const db = parseDate(b.posted_date);
                return db - da;
            }});
        }}

        if (render) renderJobs();
    }}

    function parseDate(str) {{
        if (!str) return 0;
        const d = new Date(str);
        return isNaN(d.getTime()) ? 0 : d.getTime();
    }}

    function renderJobs() {{
        const list = document.getElementById('jobs-list');
        const empty = document.getElementById('empty-state');
        const count = document.getElementById('results-count');

        if (filteredJobs.length === 0) {{
            list.innerHTML = '';
            empty.style.display = 'block';
            count.textContent = '0 results';
            return;
        }}

        empty.style.display = 'none';
        count.textContent = `${{filteredJobs.length}} position${{filteredJobs.length !== 1 ? 's' : ''}}`;
        list.innerHTML = filteredJobs.map(renderJob).join('');
    }}

    // Event listeners
    document.getElementById('search').addEventListener('input', debounce(filterAndRender, 200));
    document.getElementById('filter-source').addEventListener('change', filterAndRender);
    document.getElementById('filter-type').addEventListener('change', filterAndRender);
    document.getElementById('filter-location').addEventListener('change', filterAndRender);
    document.getElementById('filter-party').addEventListener('change', filterAndRender);
    document.getElementById('filter-category').addEventListener('change', filterAndRender);

    // Populate category filter dynamically
    const categories = [...new Set(JOBS.map(j => j.category).filter(Boolean))].sort();
    const catSelect = document.getElementById('filter-category');
    categories.forEach(cat => {{
        const opt = document.createElement('option');
        opt.value = cat;
        opt.textContent = cat;
        catSelect.appendChild(opt);
    }});

    function debounce(fn, ms) {{
        let timer;
        return (...args) => {{
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), ms);
        }};
    }}

    // Initial render
    filterAndRender();
    </script>
</body>
</html>'''

    return html


def build_rss(jobs):
    """Generate an RSS feed of recent jobs."""
    now = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
    site_url = 'https://jeremyschlatter-intern.github.io/congressional-job-tracker/'

    items = []
    # Include recent jobs (sorted by posted date, limit 50)
    sorted_jobs = sorted(jobs, key=lambda j: j.get('posted_date', '') or '', reverse=True)[:50]

    for job in sorted_jobs:
        title = xml_escape(job.get('title', ''))
        office = xml_escape(job.get('office', ''))
        location = xml_escape(job.get('location', ''))
        desc = xml_escape(job.get('description', '') or '')
        url = xml_escape(job.get('url', ''))
        source_label = {'senate': 'U.S. Senate', 'house': 'U.S. House', 'usajobs': 'USA Jobs'}.get(job.get('source', ''), '')
        party = job.get('political_affiliation', '')
        category = xml_escape(job.get('category', '') or '')

        desc_parts = []
        if office:
            desc_parts.append(f"Office: {office}")
        if location:
            desc_parts.append(f"Location: {location}")
        if party:
            desc_parts.append(f"Affiliation: {xml_escape(party)}")
        if desc:
            desc_parts.append(desc)

        item_desc = ' | '.join(desc_parts)

        items.append(f"""    <item>
      <title>{title} - {xml_escape(source_label)}</title>
      <link>{url}</link>
      <description>{item_desc}</description>
      <guid isPermaLink="false">{job.get('source', '')}-{job.get('source_id', job.get('id', ''))}</guid>
      {f'<category>{category}</category>' if category else ''}
    </item>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Congressional Job Tracker</title>
    <link>{site_url}</link>
    <description>Aggregating employment opportunities across the U.S. Congress</description>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{site_url}feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>"""
    return rss


def build():
    """Build the static site."""
    init_db()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    jobs, stats = get_jobs_data()
    html = build_html(jobs, stats)

    output_path = os.path.join(OUTPUT_DIR, 'index.html')
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"Built site with {stats['total']} jobs -> {output_path}")

    # Generate JSON data
    json_path = os.path.join(OUTPUT_DIR, 'jobs.json')
    with open(json_path, 'w') as f:
        json.dump({
            'generated': datetime.utcnow().isoformat(),
            'total': stats['total'],
            'stats': {k: v for k, v in stats.items() if k != 'last_scraped'},
            'jobs': jobs,
        }, f, indent=2, default=str)

    print(f"Generated JSON data -> {json_path}")

    # Generate RSS feed
    rss_path = os.path.join(OUTPUT_DIR, 'feed.xml')
    with open(rss_path, 'w') as f:
        f.write(build_rss(jobs))

    print(f"Generated RSS feed -> {rss_path}")


if __name__ == '__main__':
    build()
