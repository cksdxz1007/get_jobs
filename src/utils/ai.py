# utils/ai.py
"""
AI 匹配模块 - 使用 Claude 分析职位与简历的匹配度
"""
from __future__ import annotations

import os
from typing import Optional

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AIMatcher:
    """AI 岗位匹配器"""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self.client = None
        if self.api_key and HAS_ANTHROPIC:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    async def match_score(self, job_title: str, job_desc: str, profile: dict) -> dict:
        """
        返回匹配分数和原因
        {
            "score": 0.0-1.0,
            "reason": str,
            "recommended": bool
        }
        """
        if not self.client:
            return {"score": 0.5, "reason": "No API key configured", "recommended": True}

        skills_text = ", ".join(profile.get("skills", []))
        roles_text = ", ".join(profile.get("desired_roles", []))
        summary = profile.get("summary", "")

        prompt = f"""你是一个求职顾问。请评估以下职位与候选人的匹配度。

## 候选人简历
- 姓名: {profile.get('name', '')}
- 摘要: {summary}
- 技能: {skills_text}
- 期望职位: {roles_text}
- 工作年限: {profile.get('years_experience', '')}

## 职位信息
- 职位: {job_title}
- 职位描述: {job_desc[:800] if job_desc else '无描述'}

## 评估要求
请仅返回一个JSON对象（不要有其他内容）：
{{"score": 0.0到1.0之间的浮点数, "reason": "简短的匹配原因（20字内）", "recommended": true或false}}

匹配标准：
- score >= 0.6: recommended = true（值得投递）
- score < 0.6: recommended = false（不适合）
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response.content[0].text.strip()

            # 解析 JSON
            import json, re
            match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {"score": 0.5, "reason": "Parse failed", "recommended": True}
        except Exception as e:
            return {"score": 0.5, "reason": f"Error: {e}", "recommended": True}

    async def generate_greeting(self, job: dict, profile: dict) -> str:
        """生成个性化的打招呼消息"""
        if not self.client:
            return f"您好，请问方便聊聊吗？"

        prompt = f"""为以下职位生成一句简短（50字内）的打招呼消息：

- 职位: {job.get('title', '')}
- 公司: {job.get('company', '')}
- 我的背景: {profile.get('summary', '')}, 技能: {', '.join(profile.get('skills', []))}

要求：专业、简洁、有礼貌。不要用"尊敬的"这种老套开头。

直接返回消息文本，不要解释。"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception:
            return f"您好，我对 {job.get('title', '')} 职位很感兴趣，方便聊聊吗？"