# models/__init__.py
from .job import Job, ApplyResult, SearchResult
from .config import AppConfig, AIConfig, BrowserConfig, LiepinConfig, TelegramConfig, DBConfig

__all__ = [
    "Job", "ApplyResult", "SearchResult",
    "AppConfig", "AIConfig", "BrowserConfig", "LiepinConfig", "TelegramConfig", "DBConfig",
]