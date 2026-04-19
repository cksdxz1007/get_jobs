# models/job.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    """统一职位模型"""
    platform: str                    # liepin / boss / job51 / zhilian / lagou
    job_id: str                      # 平台内唯一ID
    title: str
    company: str
    salary: Optional[str] = None
    area: Optional[str] = None
    experience: Optional[str] = None  # 经验要求 e.g. "3-5年"
    education: Optional[str] = None   # 学历要求 e.g. "本科"
    description: Optional[str] = None  # 职位描述（完整）
    tags: list[str] = field(default_factory=list)
    recruiter_id: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_title: Optional[str] = None
    company_id: Optional[str] = None
    company_industry: Optional[str] = None
    company_scale: Optional[str] = None
    link: Optional[str] = None
    refresh_time: Optional[str] = None  # 更新时间
    # 内部字段
    raw_data: Optional[dict] = None      # 原始 JSON
    applied_at: Optional[datetime] = None
    status: str = "pending"             # pending / success / failed / skipped

    @property
    def id(self) -> str:
        """全局唯一ID: platform_jobId"""
        return f"{self.platform}_{self.job_id}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "platform": self.platform,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "salary": self.salary,
            "area": self.area,
            "experience": self.experience,
            "education": self.education,
            "recruiter_name": self.recruiter_name,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "status": self.status,
        }


@dataclass
class ApplyResult:
    """投递结果"""
    job: Job
    success: bool
    message: str
    error: Optional[str] = None


@dataclass
class SearchResult:
    """搜索结果统计"""
    platform: str
    keyword: str
    total: int
    new_jobs: int
    applied: int
    skipped: int
    failed: int
    jobs: list[Job]