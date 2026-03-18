"""Database module for Congressional Job Tracker."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jobs.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT,
            title TEXT NOT NULL,
            office TEXT,
            location TEXT,
            url TEXT,
            posted_date TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            description TEXT,
            salary TEXT,
            category TEXT,
            position_type TEXT,
            experience_level TEXT,
            political_affiliation TEXT,
            is_active INTEGER DEFAULT 1,
            raw_data TEXT,
            UNIQUE(source, source_id)
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
        CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(is_active);
        CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen);
        CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs(posted_date);

        CREATE TABLE IF NOT EXISTS scrape_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            scraped_at TEXT NOT NULL,
            jobs_found INTEGER DEFAULT 0,
            new_jobs INTEGER DEFAULT 0,
            error TEXT
        );
    """)
    conn.commit()
    conn.close()


def upsert_job(conn, job_data):
    """Insert or update a job. Returns True if this is a new job."""
    now = datetime.utcnow().isoformat()

    # Check if job already exists
    existing = conn.execute(
        "SELECT id, is_active FROM jobs WHERE source = ? AND source_id = ?",
        (job_data['source'], job_data['source_id'])
    ).fetchone()

    if existing:
        # Update last_seen and reactivate if needed
        conn.execute("""
            UPDATE jobs SET
                last_seen = ?,
                title = ?,
                office = ?,
                location = ?,
                url = ?,
                description = ?,
                salary = ?,
                category = ?,
                position_type = ?,
                experience_level = ?,
                political_affiliation = ?,
                is_active = 1,
                raw_data = ?
            WHERE source = ? AND source_id = ?
        """, (
            now,
            job_data.get('title'),
            job_data.get('office'),
            job_data.get('location'),
            job_data.get('url'),
            job_data.get('description'),
            job_data.get('salary'),
            job_data.get('category'),
            job_data.get('position_type'),
            job_data.get('experience_level'),
            job_data.get('political_affiliation'),
            job_data.get('raw_data'),
            job_data['source'],
            job_data['source_id'],
        ))
        return False
    else:
        conn.execute("""
            INSERT INTO jobs (
                source, source_id, title, office, location, url,
                posted_date, first_seen, last_seen, description,
                salary, category, position_type, experience_level,
                political_affiliation, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_data['source'],
            job_data['source_id'],
            job_data.get('title'),
            job_data.get('office'),
            job_data.get('location'),
            job_data.get('url'),
            job_data.get('posted_date'),
            now,
            now,
            job_data.get('description'),
            job_data.get('salary'),
            job_data.get('category'),
            job_data.get('position_type'),
            job_data.get('experience_level'),
            job_data.get('political_affiliation'),
            job_data.get('raw_data'),
        ))
        return True


def mark_inactive(conn, source, active_source_ids):
    """Mark jobs as inactive if they're no longer in the source."""
    if not active_source_ids:
        return
    placeholders = ','.join('?' * len(active_source_ids))
    conn.execute(f"""
        UPDATE jobs SET is_active = 0
        WHERE source = ? AND source_id NOT IN ({placeholders})
        AND is_active = 1
    """, [source] + list(active_source_ids))


def log_scrape(conn, source, jobs_found, new_jobs, error=None):
    conn.execute("""
        INSERT INTO scrape_log (source, scraped_at, jobs_found, new_jobs, error)
        VALUES (?, ?, ?, ?, ?)
    """, (source, datetime.utcnow().isoformat(), jobs_found, new_jobs, error))


def get_all_active_jobs():
    conn = get_connection()
    jobs = conn.execute("""
        SELECT * FROM jobs WHERE is_active = 1
        ORDER BY first_seen DESC
    """).fetchall()
    conn.close()
    return [dict(j) for j in jobs]


def get_stats():
    conn = get_connection()
    stats = {}
    stats['total_active'] = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE is_active = 1"
    ).fetchone()[0]
    stats['total_ever'] = conn.execute(
        "SELECT COUNT(*) FROM jobs"
    ).fetchone()[0]
    stats['by_source'] = {
        row['source']: row['count']
        for row in conn.execute(
            "SELECT source, COUNT(*) as count FROM jobs WHERE is_active = 1 GROUP BY source"
        ).fetchall()
    }
    stats['latest_scrape'] = conn.execute(
        "SELECT source, scraped_at, jobs_found, new_jobs FROM scrape_log ORDER BY scraped_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return stats


if __name__ == '__main__':
    init_db()
    print(f"Database initialized at {DB_PATH}")
