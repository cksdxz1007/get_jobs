# platforms/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models.job import Job, ApplyResult, SearchResult


class PlatformHandler(ABC):
    """平台处理器抽象基类"""

    platform_name: str = ""

    @abstractmethod
    async def login(self, page) -> bool:
        """登录并保存 cookie，返回是否登录成功"""
        ...

    @abstractmethod
    async def search(self, keyword: str, page, **kwargs) -> list[Job]:
        """搜索职位，返回职位列表"""
        ...

    @abstractmethod
    async def apply(self, job: Job, page) -> ApplyResult:
        """对单个职位执行投递（打招呼/聊一聊）"""
        ...

    @abstractmethod
    async def is_logged_in(self, page) -> bool:
        """检查当前页面是否已登录"""
        ...

    def job_id_from_url(self, url: str) -> Optional[str]:
        """从 URL 中提取 job_id"""
        return None

    def build_search_url(self, keyword: str, **kwargs) -> str:
        """构建搜索 URL"""
        return ""