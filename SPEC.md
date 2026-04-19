# JobFlow — Python 轻量化自动求职投递工具

> 从 get_jobs (Java) 重写为 Python，主打猎聘平台，渐进式扩展到 Boss/前程无忧/智联/拉勾

## 1. 背景与目标

### 为什么重写
- get_jobs 使用 Java Spring Boot，内存占用 300-500MB，冷启动 10-30s
- Python 版本预期内存 50-100MB，冷启动 1-3s
- 更轻量的依赖，更容易部署和分发

### 目标
1. 完整支持 **猎聘** 自动搜索 + 自动打招呼/投递
2. 渐进式支持 Boss直聘、前程无忧、智联招聘、拉勾
3. AI 智能匹配岗位（复用 Claude）
4. Telegram 通知投递结果
5. 支持 Docker 部署

---

## 2. 技术架构

```
src/
├── api/               # HTTP API 层 (FastAPI)
│   ├── __init__.py
│   ├── routes.py      # /jobs /apply /config 路由
│   └── schemas.py     # Pydantic 请求/响应模型
├── automation/        # 浏览器自动化核心
│   ├── browser.py     # Playwright 初始化、反检测、生命周期
│   ├── cookies.py     # Cookie 存储、刷新、验证
│   └── stealth.js     # 反检测注入脚本
├── platforms/         # 平台适配层
│   ├── base.py        # 抽象基类 PlatformHandler
│   ├── liepin.py       # 猎聘实现 (优先级: P0)
│   ├── boss.py         # Boss直聘 (优先级: P1)
│   ├── job51.py        # 前程无忧 (优先级: P1)
│   ├── zhilian.py      # 智联招聘 (优先级: P2)
│   └── lagou.py        # 拉勾 (优先级: P2)
├── db/
│   ├── __init__.py
│   ├── models.py      # Pydantic 模型 = schema
│   ├── database.py    # SQLite 连接 + CRUD
│   └── migrations.py  # 数据库初始化
├── models/            # 数据模型
│   ├── job.py         # Job 职位模型
│   ├── config.py      # 配置模型
│   └── notification.py # 通知模型
├── utils/
│   ├── ai.py          # Anthropic/OpenAI 集成
│   ├── http.py        # HTTP 客户端 (httpx)
│   └── log.py         # 日志工具
├── main.py            # 入口
├── config.yaml        # 配置文件
└── requirements.txt   # 依赖
```

---

## 3. 平台实现规范

### 3.1 基类设计

```python
class PlatformHandler(ABC):
    @abstractmethod
    def login(self) -> bool: ...

    @abstractmethod
    def search(self, keyword: str, **filters) -> list[Job]: ...

    @abstractmethod
    def apply(self, job: Job) -> ApplyResult: ...

    @abstractmethod
    def check_applied(self, job_id: str) -> bool: ...
```

### 3.2 猎聘 (liepin.py) 实现要点

**登录方式：** 微信扫码（调用二维码生成接口）

**搜索流程：**
1. 构建 URL: `https://www.liepin.com/zhaopin/?keyword={kw}&city={cityCode}`
2. 拦截 XHR: `https://www.liepin.com/searchfront4c/pc-search-job`
3. 解析 JSON 响应，取 `jobCardList` 字段
4. 翻页遍历（最多 50 页）

**投递流程（聊一聊）：**
1. 滚动卡片到可视区
2. Hover 卡片底部 HR 区域，显示"聊一聊"按钮
3. 鼠标微调 + 点击（模拟真人）
4. 等待聊天窗口打开，关闭

**字段映射：**
```
jobId, title, salary, dq(地区), requireEduLevel, requireWorkYears,
compId, compName, compIndustry, compScale,
recruiterId, recruiterName, recruiterTitle, refreshTime
```

**反检测策略：**
- 复用原版 `stealth.min.js`
- 随机延迟 3-8s
- 随机鼠标移动路径

---

## 4. 数据库设计 (SQLite)

```sql
-- jobs 投递记录表
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,          -- 职位ID (平台+jobId)
    platform TEXT NOT NULL,       -- liepin/boss/job51/zhilian/lagou
    job_id TEXT NOT NULL,
    title TEXT,
    company TEXT,
    salary TEXT,
    area TEXT,
    recruiter_name TEXT,
    applied_at DATETIME,
    status TEXT DEFAULT 'pending' -- pending/success/failed/skipped
);

-- config 配置表 (KV store)
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at DATETIME
);
```

---

## 5. AI 匹配模块

```python
# ai.py
async def match_score(job: Job, profile: dict[str, Any]) -> float:
    """
    用 Claude 分析职位描述与简历的匹配度
    返回 0.0-1.0 的匹配分数
    """
    prompt = f"""
    简历摘要: {profile['summary']}
    技能: {', '.join(profile['skills'])}
    期望职位: {', '.join(profile['desired_roles'])}

    职位: {job.title}
    公司: {job.company}
    描述: {job.description[:500]}

    请评估匹配度，返回 JSON: {{"score": 0.0-1.0, "reason": "原因"}}
    """
```

---

## 6. Telegram 通知

```python
async def notify_telegram(message: str):
    """
    定时推送投递统计，早报/晚报
    实时通知（投递成功/失败/异常）
    """
```

---

## 7. 配置 (config.yaml)

```yaml
platform: liepin
keywords:
  - Python 工程师
  - 后端开发
  - AI 工程师

ai:
  provider: anthropic  # anthropic | openai
  model: claude-sonnet-4-20250514
  api_key: ${ANTHROPIC_API_KEY}

browser:
  headless: false
  slowmo: 50

liepin:
  cookie_path: ~/.jobflow/cookies/liepin.json
  daily_limit: 100
  delay_min: 3
  delay_max: 8

telegram:
  bot_token: ${TELEGRAM_BOT_TOKEN}
  chat_id: ${TELEGRAM_CHAT_ID}
  notify_on_success: true
  notify_on_failure: false

db:
  path: ~/.jobflow/jobflow.db
```

---

## 8. 实现优先级

### Phase 0: 骨架 + 猎聘核心
- [ ] `main.py` 入口 + CLI
- [ ] `config.yaml` 解析
- [ ] `browser.py` Playwright 初始化 + 反检测
- [ ] `cookies.py` Cookie 管理
- [ ] `liepin.py` 登录 + 搜索 + API拦截解析
- [ ] `liepin.py` "聊一聊"自动投递
- [ ] `database.py` SQLite 基础 CRUD
- [ ] `jobs` 表记录投递历史

### Phase 1: 扩展平台
- [ ] `boss.py` Boss直聘
- [ ] `job51.py` 前程无忧

### Phase 2: AI + 通知
- [ ] `ai.py` Claude 匹配打分
- [ ] Telegram 早晚报
- [ ] 实时通知

### Phase 3: API + 前端
- [ ] FastAPI HTTP 路由
- [ ] Web 管理界面（可选）

---

## 9. 验收标准

### 猎聘自动化最低完成标准
1. ✅ 能通过 Cookie 文件自动登录（不需每次扫码）
2. ✅ 能搜索关键词并解析出职位列表
3. ✅ 能对搜索到的职位自动点击"聊一聊"
4. ✅ 投递记录写入 SQLite，重复投递不重复记录
5. ✅ 每天投递次数可配置，有每日上限
6. ✅ 遇到验证码/异常能暂停并通知 Telegram