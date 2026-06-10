# 洛克王国世界 · 创作者背调筛查系统 PRD

> 版本: v1.0 | 日期: 2026-06-08 | 状态: 规划中（待确认后进入开发）

---

## 一、产品概述

### 1.1 产品定义

面向《洛克王国世界》海外发行团队的前期创作者/KOL 背调筛查系统。在邀请主播参与线下试玩会之前，通过 AI 自动化分析创作者的 YouTube/Twitch 频道数据，产出多维度风险评估报告，辅助人工二次审查决策。

### 1.2 核心目标

| 目标 | 度量 |
|------|------|
| 筛查效率 | 单个创作者从输入URL到产出完整报告 ≤ 3分钟 |
| 风险覆盖 | 六层筛查体系覆盖政治立场、游戏忠诚度、频道话术、品牌安全、竞争关系、影响力真实性 |
| 人工友好 | 不仅输出总分，而是每层独立评分 + 风险信号原文 + 风险关键词，保留人工复核空间 |
| 批量能力 | 支持一次导入10-50个创作者URL列表，批量跑筛查 |

### 1.3 用户画像

- **第一用户**：海外发行负责人（你），直接使用系统进行创作者背调
- **使用场景**：单人操作，无需审批流程，本地运行

---

## 二、功能需求

### 2.1 核心功能清单

```
F1 创作者搜索与筛查
  ├─ F1.1 输入创作者URL → 自动识别平台（YouTube/Twitch/Twitter/TikTok）
  ├─ F1.2 点击"开始筛查" → 后端异步执行六层分析
  ├─ F1.3 实时展示筛查进度（日志流）
  └─ F1.4 完成后展示综合评分 + 六层详细结果

F2 批量导入筛查
  ├─ F2.1 上传 Excel/CSV 文件（列：平台，URL，备注）
  ├─ F2.2 后台异步逐条筛查
  └─ F2.3 批量完成后导出汇总 Excel

F3 筛查详情展示
  ├─ F3.1 综合评分仪表盘（环形图 + 判定结论 + 一票否决标识）
  ├─ F3.2 每层独立卡片，可展开查看：
  │     - 子项评分明细（如"粉丝增长曲线: ✅ 自然增长"）
  │     - 风险信号列表（原文 + 日期 + 严重等级）
  │     - 风险关键词标签云
  └─ F3.3 各层评分以0-100展示，保留人工判断空间

F4 历史记录
  ├─ F4.1 历史筛查记录列表（按时间排序，支持搜索）
  ├─ F4.2 点击查看过往筛查详情
  ├─ F4.3 删除/重新筛查
  └─ F4.4 两个创作者并排对比视图（可选）

F5 报告导出
  ├─ F5.1 单个创作者导出 Excel（含六层详细评分 + 风险信号）
  └─ F5.2 批量筛查导出汇总 Excel（创作者横向对比）

F6 关键词库管理
  ├─ F6.1 查看/编辑政治敏感关键词库（JSON配置）
  ├─ F6.2 查看/编辑竞品关键词库
  └─ F6.3 导入/导出关键词配置
```

### 2.2 六层筛查体系（已确定）

| 层级 | 名称 | 输入 | 输出 | 状态 |
|------|------|------|------|:---:|
| L1 | 基础数据真实性验证 | 频道API数据 | 真实性分数(0-100) + 异常指标 | 已确定 |
| L2 | 内容历史全量回溯 | 视频字幕/音频转写文本 | 内容风险热力图 + 风险信号列表 | 已确定 |
| L3 | 政治敏感信号检测 | 字幕文本 + 关键词库 + Perspective API | 政治风险等级(SAFE/LOW/MEDIUM/HIGH) + 命中关键词 | 已确定 |
| L4 | 品牌安全综合评分 | L3输出 + YouTube分级 + GARM映射 | 品牌安全分数(0-100) | 已确定 |
| L5 | 竞争关系图谱分析 | 视频元数据 | 竞品关系深度 + 适配度评分 | 已确定 |
| L6 | 影响力真实性验证 | 评论数据 + 粉丝数据 | 影响力真实性分数(0-100) | 已确定 |

> ⚠️ 2026-06-08 确认：移除原计划的 L7（持续监控预警），该系统聚焦前期筛选。

### 2.3 一票否决规则（已确定）

| # | 条件 | 触发方式 |
|---|------|---------|
| 1 | 明确踩中台独/港独/涉疆/涉藏政治红线 | L3 关键词匹配 + Perspective API |
| 2 | 明确反华/种族歧视言论 | L3 关键词匹配 |
| 3 | 粉丝造假 ≥ 30% | L1 异常检测 |
| 4 | 仇恨言论占比 > 5% | L4 品牌安全 |
| 5 | 与 Pokémon Company/Nintendo 存在正在进行的商业合作 | L5 竞争图谱 |

---

## 三、系统架构设计

### 3.1 技术栈（已确认）

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| 前端 | HTML/CSS/JS（已有 `creator_screening_dashboard.html` 可作为UI基础） | 复用已有设计，减少前端重构 |
| 后端框架 | Python + FastAPI | 生态兼容（Python已有 yt-dlp/Whisper/NLP 库） |
| 数据库 | SQLite（本地文件） | 单人使用，无需独立数据库服务 |
| 任务队列 | FastAPI BackgroundTasks / 简单轮询 | 筛查任务异步执行，避免阻塞 |
| API密钥 | .env 文件 | 无需界面管理，首次部署配置 |
| 报告导出 | openpyxl（Excel） | 满足横向对比需求 |
| 部署 | 本地 `python app.py` → `http://localhost:8000` | 最简单 |

### 3.2 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                    前端 (HTML/JS)                     │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐           │
│  │ 搜索/批量 │ │ 结果展示   │ │ 历史记录  │           │
│  │  输入页   │ │ (六层详情) │ │  列表    │           │
│  └────┬─────┘ └─────┬─────┘ └────┬─────┘           │
│       │             │            │                   │
│     POST /screen  GET /result   GET /history          │
└───────┼─────────────┼────────────┼───────────────────┘
        │             │            │
┌───────┴─────────────┴────────────┴───────────────────┐
│                FastAPI 后端 (port 8000)                │
│                                                        │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐          │
│  │ API路由   │  │ 筛查引擎   │  │ 导出引擎  │          │
│  │ /screen  │  │ ScreenSvc │  │ ExportSvc│          │
│  │ /result  │  │ .run()    │  │ .excel() │          │
│  │ /history │  │           │  │          │          │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘          │
│       │              │              │                 │
│  ┌────┴──────┐ ┌─────┴──────┐ ┌───┴───────┐        │
│  │  SQLite   │ │  External  │ │ 关键词库   │        │
│  │ 数据库    │ │  API调用   │ │ JSON文件  │        │
│  │           │ │ ─────────  │ │           │        │
│  │ screen_   │ │ YouTube API│ │political_ │        │
│  │ results   │ │ Twitch API│ │keywords.  │        │
│  │ creators  │ │ Perspective│ │ json      │        │
│  │           │ │ yt-dlp CLI│ │competitor_│        │
│  │           │ │ Whisper CLI│ │keywords.  │        │
│  │           │ │            │ │ json      │        │
│  └───────────┘ └────────────┘ └───────────┘        │
└─────────────────────────────────────────────────────┘
```

### 3.3 数据模型设计

```sql
-- 创作者基本信息
CREATE TABLE creators (
    id TEXT PRIMARY KEY,          -- UUID
    platform TEXT NOT NULL,        -- 'youtube' | 'twitch' | 'twitter' | 'tiktok'
    url TEXT NOT NULL,             -- 原始URL
    channel_id TEXT,               -- 平台上的频道ID
    name TEXT,                     -- 创作者显示名
    handle TEXT,                   -- @用户名
    subs INTEGER,                  -- 粉丝数
    country TEXT,                  -- 国家/地区
    content_lang TEXT,             -- 主要语言
    category TEXT,                 -- 分类标签 (宝可梦垂类/杂食/二次元等)
    avatar_url TEXT,               -- 头像URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 筛查记录
CREATE TABLE screen_results (
    id TEXT PRIMARY KEY,           -- UUID
    creator_id TEXT NOT NULL REFERENCES creators(id),
    status TEXT NOT NULL DEFAULT 'pending',  -- pending|running|completed|failed
    composite_score REAL,          -- 综合评分 0-100
    verdict TEXT,                  -- 'approve' | 'review' | 'reject'
    veto_flags TEXT,               -- JSON: [{icon, text}, ...]
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 六层筛查详情
CREATE TABLE layer_results (
    id TEXT PRIMARY KEY,
    screen_result_id TEXT NOT NULL REFERENCES screen_results(id),
    layer_number INTEGER NOT NULL, -- 1-6
    layer_name TEXT NOT NULL,      -- 层级名称
    score REAL,                    -- 该层评分 0-100
    level TEXT,                    -- 'low-risk' | 'medium-risk' | 'high-risk'
    details TEXT,                  -- JSON: [{section, items: [{label, value, cls}]}]
    signals TEXT,                  -- JSON: [{icon, date, text}]
    risk_keywords TEXT,            -- JSON: [{text, type}]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 批量筛查任务
CREATE TABLE batch_jobs (
    id TEXT PRIMARY KEY,
    file_name TEXT,                -- 上传文件名
    total_count INTEGER,           -- 总数
    completed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running', -- running|completed|failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 3.4 API 设计

```
POST   /api/screen          # 提交单个筛查任务 (body: {url, platform?})
GET    /api/screen/{id}     # 获取筛查进度/结果
GET    /api/screen/{id}/layers  # 获取六层详情
DELETE /api/screen/{id}     # 删除筛查记录

POST   /api/batch           # 上传批量筛查文件 (multipart: file.xlsx)
GET    /api/batch/{id}      # 获取批量任务进度
GET    /api/batch/{id}/export  # 导出批量结果Excel

GET    /api/history         # 查询历史筛查记录 (支持分页、搜索、筛选)
GET    /api/history/{id}    # 查询单条历史记录

GET    /api/keywords/political  # 获取政治关键词库
PUT    /api/keywords/political  # 更新政治关键词库
GET    /api/keywords/competitor # 获取竞品关键词库
PUT    /api/keywords/competitor # 更新竞品关键词库

GET    /api/health          # 健康检查（API Key 是否配置等）
```

---

## 四、各层实现方案（技术细节）

### L1: 基础数据真实性验证

| 步骤 | 工具 | 内容 |
|------|------|------|
| 获取频道数据 | YouTube Data API v3 / Twitch Helix API | statistics + snippet |
| 获取视频列表 | YouTube playlistItems API / Twitch videos API | 视频ID、标题、播放量、发布日期 |
| 计算指标 | Python 脚本 | 互动率 = (likes+comments)/views; 粉播比 = avg_views/subs |
| 异常检测 | Python 脚本 | 台阶式粉丝增长 → 买粉; 粉播比<1% → 僵尸粉 |
| 结构化输出 | → SQLite layer_results | 真实性分数 + 各项指标 |

### L2: 内容历史全量回溯

| 步骤 | 工具 | 内容 |
|------|------|------|
| 获取视频列表 | yt-dlp --flat-playlist | 频道全部视频ID |
| 字幕下载（首选） | yt-dlp --skip-download --write-auto-sub | 仅下载文本，1-2分钟全量 |
| 音频转写（备选） | yt-dlp -x + Whisper tiny | 仅无字幕视频，后台转写 |
| NLP 分析 | Python (正则 + VADER) | 关键词匹配、情感极性、主题分布 |
| 风险热力图 | → SQLite layer_results | 按月份/话题的风险分布 |

### L3: 政治敏感信号检测（简化方案）

| 轮次 | 工具 | 覆盖率 |
|------|------|:---:|
| ① 关键词匹配 | Python 全文扫描 keywords_political.json | ~80% |
| ② Perspective API | HTTP POST 对命中视频做深度检测 | 二次确认 |
| ③ LLM 兜底 | WorkBuddy 对话中直接分析模糊文本 | ~5% |

### L4: 品牌安全 → 汇总 L3 + YouTube 分级

### L5: 竞争关系 → 视频标题/描述关键词分析

### L6: 影响力验证 → 评论分析 + 粉丝地理推断

---

## 五、项目文件结构

```
NRC/
├── creator_screening/           # 新建项目目录
│   ├── app.py                   # FastAPI 入口
│   ├── config.py                # 配置读取 (.env)
│   ├── database.py              # SQLite 初始化与连接
│   ├── models.py                # 数据模型 (Pydantic + SQL)
│   ├── routers/
│   │   ├── screen.py            # 筛查API
│   │   ├── history.py           # 历史记录API
│   │   ├── batch.py             # 批量筛查API
│   │   └── keywords.py          # 关键词库管理API
│   ├── services/
│   │   ├── screen_engine.py     # 筛查核心引擎 (编排六层)
│   │   ├── layer1_authenticity.py
│   │   ├── layer2_content.py    # yt-dlp + 字幕/Whisper
│   │   ├── layer3_political.py  # 关键词 + Perspective API
│   │   ├── layer4_brand_safety.py
│   │   ├── layer5_competition.py
│   │   └── layer6_influence.py
│   ├── export/
│   │   └── excel_exporter.py    # Excel 报告生成
│   ├── data/
│   │   ├── keywords_political.json  # 政治关键词库
│   │   ├── keywords_competitor.json # 竞品关键词库
│   │   └── subtitles/           # 下载的字幕文件 (临时)
│   ├── static/                  # 前端文件
│   │   └── dashboard.html       # 从已有的 HTML 迁移优化
│   └── requirements.txt
├── .env                         # API Keys (不提交到Git)
└── .workbuddy/
    └── memory/
```

---

## 六、前端页面规划

### 6.1 页面结构（单页应用，三视图切换）

```
┌─────────────────────────────────────────────────┐
│  Header: Logo | 导航: [筛查] [历史] [关键词库]   │
├─────────────────────────────────────────────────┤
│                                                  │
│  [视图1: 筛查页]                                  │
│  ┌──────────────────────────────────────┐        │
│  │  URL输入框 + 开始筛查按钮 + 批量上传  │        │
│  └──────────────────────────────────────┘        │
│  ┌─────────────┐ ┌──────────────────────┐       │
│  │ 综合评分     │ │  六层筛查详情卡片     │       │
│  │ 仪表盘      │ │  (可展开/折叠)       │       │
│  │ (sticky)    │ │  - 子项评分          │       │
│  │             │ │  - 风险信号          │       │
│  │             │ │  - 关键词标签        │       │
│  │             │ │                     │       │
│  │ [导出Excel] │ │                     │       │
│  └─────────────┘ └──────────────────────┘       │
│                                                  │
│  [视图2: 历史记录]                                │
│  ┌──────────────────────────────────────┐        │
│  │  搜索框 | 日期筛选 | 判定筛选         │        │
│  │  ┌─────────────────────────────────┐ │        │
│  │  │ 表格: 创作者 | 平台 | 评分 | ... │ │        │
│  │  │ (点击行 → 展开筛查详情)          │ │        │
│  │  └─────────────────────────────────┘ │        │
│  └──────────────────────────────────────┘        │
│                                                  │
│  [视图3: 关键词库]                                │
│  ┌──────────────────────────────────────┐        │
│  │  编辑政治/竞品关键词库 (文本JSON编辑)  │        │
│  └──────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

### 6.2 与现有 HTML 的关系

已有的 `creator_screening_dashboard.html` 已包含完整的 UI 设计和交互逻辑。开发时将：
- **保留**：CSS 样式系统、六层卡片组件、评分仪表盘、日志动画
- **改造**：搜索输入 → 改为调用后端 API、数据从 mock → 改为 API 数据、新增历史记录/批量上传/导出按钮
- **新增**：关键词库编辑器、批量上传组件、Excel 导出触发

---

## 七、里程碑

| Phase | 内容 | 交付物 |
|:---:|------|------|
| **Phase 0** | 环境搭建 + 关键词库初始化 | 项目骨架、SQLite schema、关键词JSON文件 |
| **Phase 1** | L1 + L2 实现 | 可运行的频道数据获取 + 字幕下载/分析 |
| **Phase 2** | L3 + L4 + L5 + L6 实现 | 完整的六层筛查引擎 |
| **Phase 3** | 前端改造 + API 对接 | 可用的完整 Web 界面 |
| **Phase 4** | 批量导入 + Excel 导出 | CSV上传、批量任务、报告生成 |
| **Phase 5** | 历史记录 + 关键词库管理 | 完整的后台管理功能 |
| **Phase 6** | 测试 + 调优 | 真实创作者测试、误报/漏报调优 |

---

## 八、风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| YouTube API 日配额限制（默认10,000单位/天） | 批量筛查可能触发限流 | L2 用 yt-dlp 替代 API（无需配额）；仅 L1 使用 API |
| 部分创作者关闭自动字幕 | L2 覆盖率降低 | 已设计 Whisper 备选方案 |
| Twitch VOD 保存期短（7-60天） | 无法回溯12个月 | 结合 Chat log + social media 补充 |
| Perspective API 对日/韩语准确率较低 | 非英语创作者误判 | L3 关键词库兜底 + 人工复核 |
| Whisper 转写速度（tiny模型 10min音频/30s） | 处理时间长 | 仅转写无字幕的15-20%视频，后台异步运行 |

---

## 九、待确认项（已标记）

- [ ] ✅ 技术栈：Python + FastAPI
- [ ] ✅ 数据库：SQLite
- [ ] ✅ 部署方式：本地 `python app.py`
- [ ] ✅ 报告格式：Excel 导出
- [ ] ✅ API密钥：环境变量 .env
- [ ] ✅ 复用已有 HTML 前端作为 UI 基础
- [ ] ❓ 是否需要 Docker 支持？（备选，非必需）
- [ ] ❓ 关键词库初始内容：是否需要我根据现有知识预填充一份完整的中/英/日政治关键词 JSON？
- [ ] ❓ 示例 YouTube/Twitch API Key 申请：是否需要我提供申请步骤指引？
