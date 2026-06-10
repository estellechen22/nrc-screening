# 主播风险筛查系统 · API 申请指引

## 概览

本系统正常运行需要申请以下外部 API 密钥，共计 **2 个服务**，全部有免费额度，无需付费即可完成测试与初期使用。

| 序号 | 服务 | 用途 | 免费额度 | 申请耗时（预估） |
|:---:|------|------|:---:|:---:|
| ① | YouTube Data API v3 | 获取频道数据、视频列表、播放量 | 10,000 单位/天（约 100 次频道查询） | ~10 分钟 |
| ② | Perspective API | 检测文本中的毒性/侮辱/身份攻击 | 50,000 字符/天 免费 | ~5 分钟 |

另外需要自设一个管理员口令（`ADMIN_TOKEN`），用于保护配置接口，1 分钟搞定。

---

## ① YouTube Data API v3

**用途**：覆盖筛查第一层（数据真实性验证）、第二层（视频列表获取）、第五层（竞争关系分析）。

### 申请步骤

#### 1. 创建 Google Cloud 项目
- 打开 [Google Cloud Console](https://console.cloud.google.com/)
- 登录你的 Google 账号
- 顶部项目下拉 → **新建项目** → 输入名称（如 `Creator Screening`）→ 创建

#### 2. 启用 YouTube Data API v3
- 左侧菜单 → **API 和服务** → **库**
- 搜索 `YouTube Data API v3`
- 点击进入 → **启用**

#### 3. 创建 API 密钥
- 左侧菜单 → **API 和服务** → **凭据**
- 点击顶部 **+ 创建凭据** → **API 密钥**
- 复制生成的密钥（形如 `AIzaSy...`）
- ⚠️ **建议**：点击 API 密钥旁的编辑按钮，在「API 限制」中选择「YouTube Data API v3」，限制该密钥只能用于此 API，降低泄露风险

#### 4. 配置到本项目
- 将密钥填入项目根目录的 `.env` 文件：
```
YOUTUBE_API_KEY=AIzaSy你的密钥
```

### 免费额度说明
- 每日配额：10,000 单位
- 每次 `channels.list` 调用消耗 1 单位
- 每次 `playlistItems.list` 调用消耗 1 单位
- 每次 `videos.list`（最多 50 个视频）消耗 1 单位
- 对一个 200 条视频的频道做基础筛查，预计消耗约 15-25 单位
- 每天可以筛查 **约 400-600 个创作者**

> 如需更高配额，可在 Google Cloud Console 提交配额提升申请（通常 1-3 个工作日内审批）。

---

## ② Perspective API

**用途**：覆盖第三层（政治敏感信号检测）的深度语义分析，检测文本中的毒性、侮辱、身份攻击等。

### 申请步骤

#### 1. 申请 API 访问权限
- 打开 [Perspective API 官网](https://developers.perspectiveapi.com/)
- 点击 **Get started** 或 **Request API access**
- 填写表单：
  - **公司/组织名称**：Tencent（或你的团队名）
  - **用途说明**：简述为"用于游戏海外发行前对 YouTube 创作者的内容进行品牌安全筛查"即可
- 提交后通常即时或几分钟内获得批准

#### 2. 获取 API 密钥
- 审批通过后，进入 [Google Cloud Console](https://console.cloud.google.com/)
- 找到 Perspective API 对应的项目
- API 和服务 → 凭据 → 查看已有的 API 密钥，或新建一个
- 复制密钥

#### 3. 启用 API（如果尚未）
- API 和服务 → 库 → 搜索 `Perspective API`
- 点击进入 → 启用

#### 4. 配置到本项目
```
PERSPECTIVE_API_KEY=你的Perspective_API密钥
```

### 免费额度说明
- 每日：50,000 字符（按输入文本长度计）
- 每条待检测文本通常 100-500 字符
- 每天可检测约 100-500 条评论/字幕片段
- 对前期逐个人工筛查的场景，完全够用

---

## ③ ADMIN_TOKEN（管理员口令）

系统从 Step 6 开始，配置接口（修改 API Key、关键词库）需要携带 `X-Admin-Token` 请求头。

### 设置方法
- 在 `.env` 文件中自设一个复杂口令：
```
ADMIN_TOKEN=你自己选的口令_越长越好
```
- 例如：`ADMIN_TOKEN=nrc_screening_2026_secure_v1`
- 在前端「接入配置」页面的「X-Admin-Token」输入框中填入相同口令即可操作

---

## ④ 最终 .env 文件示例

将以下内容保存为项目根目录的 `.env` 文件（从 `.env.example` 复制后填入实际值）：

```env
# YouTube Data API v3
YOUTUBE_API_KEY=AIzaSy你的真实密钥

# Perspective API
PERSPECTIVE_API_KEY=你的Perspective密钥

# 管理员口令
ADMIN_TOKEN=你自设的复杂口令

# 数据库路径（一般不用改）
DATABASE_PATH=./data/screening.db

# 服务端口（一般不用改）
PORT=8000

# 日志级别
LOG_LEVEL=INFO
```

---

## 附加说明

### 未配置 Key 时的行为
- 系统设计为「占位降级」模式：缺失任何 API Key 不会报错
- 筛查会以 mock/占位数据返回，流程可完整跑通
- 配置完成 Key 后，新提交的筛查任务自动使用真实接口
- 无需重启服务（`runtime-config` 保存即生效）

### 申请过程中的常见问题

| 问题 | 解决方案 |
|------|---------|
| Google Cloud 提示需要验证手机号/信用卡 | 正常流程，不会扣费（免费额度内）。信用卡仅用于身份验证 |
| Perspective API 申请未立即通过 | 检查表单描述是否清晰，通常 2-24 小时内会审批 |
| YouTube API 配额不够用 | 在 Google Cloud Console → IAM 和管理 → 配额 → 申请提升 |

> 如果你在申请过程中遇到任何问题，把错误页面截图发给我，我可以帮你诊断。
