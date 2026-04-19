# db/database.py
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from ..models.job import Job


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    job_id TEXT NOT NULL,
    title TEXT,
    company TEXT,
    salary TEXT,
    area TEXT,
    experience TEXT,
    education TEXT,
    description TEXT,
    tags TEXT,
    recruiter_id TEXT,
    recruiter_name TEXT,
    recruiter_title TEXT,
    company_id TEXT,
    company_industry TEXT,
    company_scale TEXT,
    link TEXT,
    refresh_time TEXT,
    raw_data TEXT,
    applied_at TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, job_id)
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_applied_at ON jobs(applied_at);
"""


class Database:
    def __init__(self, db_path: str = "~/.jobflow/jobflow.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(DB_SCHEMA)

    def save_job(self, job: Job) -> bool:
        """保存或更新职位，返回是否是新插入"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT id FROM jobs WHERE platform=? AND job_id=?
                """,
                (job.platform, job.job_id),
            )
            row = cursor.fetchone()
            is_new = row is None

            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    id, platform, job_id, title, company, salary, area,
                    experience, education, description, tags, recruiter_id,
                    recruiter_name, recruiter_title, company_id, company_industry,
                    company_scale, link, refresh_time, raw_data, applied_at, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    job.id,
                    job.platform,
                    job.job_id,
                    job.title,
                    job.company,
                    job.salary,
                    job.area,
                    job.experience,
                    job.education,
                    job.description,
                    json.dumps(job.tags, ensure_ascii=False),
                    job.recruiter_id,
                    job.recruiter_name,
                    job.recruiter_title,
                    job.company_id,
                    job.company_industry,
                    job.company_scale,
                    job.link,
                    job.refresh_time,
                    json.dumps(job.raw_data, ensure_ascii=False) if job.raw_data else None,
                    job.applied_at.isoformat() if job.applied_at else None,
                    job.status,
                ),
            )
        return is_new

    def update_job_status(self, job_id: str, status: str, applied_at: datetime = None):
        with sqlite3.connect(str(self.db_path)) as conn:
            if applied_at:
                conn.execute(
                    "UPDATE jobs SET status=?, applied_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, applied_at.isoformat(), job_id),
                )
            else:
                conn.execute(
                    "UPDATE jobs SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, job_id),
                )

    def get_job(self, platform: str, job_id: str) -> Job | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE platform=? AND job_id=?",
                (platform, job_id),
            ).fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def is_applied(self, platform: str, job_id: str) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT status FROM jobs WHERE platform=? AND job_id=? AND status NOT IN ('pending','failed')",
                (platform, job_id),
            ).fetchone()
        return row is not None

    def get_applied_count_today(self, platform: str) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM jobs
                WHERE platform=? AND status='success' AND applied_at >= ?
                """,
                (platform, today),
            ).fetchone()
        return row[0] if row else 0

    def get_all_jobs(self, platform: str = None, status: str = None, limit: int = 100) -> list[Job]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM jobs WHERE 1=1"
            params = []
            if platform:
                query += " AND platform=?"
                params.append(platform)
            if status:
                query += " AND status=?"
                params.append(status)
            query += " ORDER BY applied_at DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(r) for r in rows]

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        tags_raw = row["tags"]
        tags = json.loads(tags_raw) if tags_raw else []
        raw_data_raw = row["raw_data"]
        raw_data = json.loads(raw_data_raw) if raw_data_raw else None
        applied_at = datetime.fromisoformat(row["applied_at"]) if row["applied_at"] else None
        return Job(
            platform=row["platform"],
            job_id=row["job_id"],
            title=row["title"],
            company=row["company"],
            salary=row["salary"],
            area=row["area"],
            experience=row["experience"],
            education=row["education"],
            description=row["description"],
            tags=tags,
            recruiter_id=row["recruiter_id"],
            recruiter_name=row["recruiter_name"],
            recruiter_title=row["recruiter_title"],
            company_id=row["company_id"],
            company_industry=row["company_industry"],
            company_scale=row["company_scale"],
            link=row["link"],
            refresh_time=row["refresh_time"],
            raw_data=raw_data,
            applied_at=applied_at,
            status=row["status"],
        )

    # --- Config KV ---
    def set_config(self, key: str, value: str):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, value),
            )

    def get_config(self, key: str) -> str | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row[0] if row else None