# models/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class AIConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None


class BrowserConfig(BaseModel):
    headless: bool = False
    slowmo: int = 50


class LiepinConfig(BaseModel):
    cookie_path: str = "~/.jobflow/cookies/liepin.json"
    daily_limit: int = 100
    delay_min: float = 3.0
    delay_max: float = 8.0


class TelegramConfig(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    notify_on_success: bool = True
    notify_on_failure: bool = False


class DBConfig(BaseModel):
    path: str = "~/.jobflow/jobflow.db"


class AppConfig(BaseModel):
    platform: str = "liepin"
    keywords: list[str] = field(default_factory=lambda: ["Python 工程师"])
    ai: AIConfig = Field(default_factory=AIConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    liepin: LiepinConfig = Field(default_factory=LiepinConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    db: DBConfig = Field(default_factory=DBConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        path = Path(path).expanduser()
        try:
            with open(path) as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"配置文件格式错误: {e}") from e

        # 展开环境变量 ${VAR} 或 ${VAR:default}
        raw = _expand_env(raw)
        return cls(**raw)


def _expand_env(value):
    """递归展开 YAML 中的 ${ENV_VAR} 或 ${ENV_VAR:default}"""
    if isinstance(value, str):
        import os
        if value.startswith("${") and value.endswith("}"):
            inner = value[2:-1]
            if ":" in inner:
                var, default = inner.split(":", 1)
                return os.getenv(var.strip(), default.strip())
            else:
                return os.getenv(inner.strip(), "")
        return value
    elif isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env(item) for item in value]
    return value