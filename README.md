# Linux.do & Reddit 爬虫项目

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)](https://github.com/unendev/Linuxdo-Reddit-Scraper)

一个功能强大的多平台数据爬虫项目，专门用于从 Linux.do 和 Reddit 技术论坛收集、分析和生成技术内容报告。

## 🚀 项目特性

### Linux.do 爬虫
- **智能爬取**: 使用 Playwright + Stealth 技术绕过反爬虫检测
- **RSS 解析**: 自动解析 RSS 源获取最新帖子
- **内容提取**: 深度提取帖子内容、作者信息、发布时间等
- **AI 分析**: 集成 DeepSeek API 进行内容分析和摘要生成
- **数据存储**: 支持 PostgreSQL 数据库存储
- **错误处理**: 完善的重试机制和错误恢复
- **代理支持**: 内置代理配置，支持网络访问

### Reddit 爬虫
- **多子版块支持**: 可配置爬取不同技术子版块
- **热门内容**: 自动获取热门技术讨论
- **内容分析**: AI 驱动的技术趋势分析
- **报告生成**: 自动生成 Markdown 格式的技术报告

## 📁 项目结构

```
linuxdo-scraper/
├── linuxdo/                           # Linux.do 爬虫模块
│   ├── scripts/                       # 核心脚本
│   │   ├── scraper.py                # 主爬虫脚本 (异步 + 重试机制)
│   │   ├── manual_upload.py          # 通用数据上传工具
│   │   ├── upload_0925_data.py       # 特定日期数据上传
│   │   ├── test_db.py               # 数据库连接测试
│   │   └── test_proxy.py            # 代理连接测试
│   ├── data/                         # 原始数据存储
│   │   └── linux.do_report_*.json    # 每日爬取数据
│   ├── reports/                      # 生成报告
│   │   └── Linux.do_Daily_Report_*.md # 每日分析报告
│   └── logs/                         # 运行日志
│       ├── scraper.log              # 爬虫运行日志
│       ├── scheduler.log           # 调度器日志
│       └── data_monitor.log         # 数据监控日志
├── reddit_scraper/                    # Reddit 爬虫模块
│   ├── reddit_scraper.py            # Reddit 爬虫主脚本
│   ├── reddit_scraper.log           # Reddit 爬虫日志
│   ├── Reddit_technology_Report_*.md # Reddit 技术报告
│   └── reddit_technology_report_*.json # Reddit 数据文件
├── .gitignore                        # Git 忽略文件配置
└── README.md                        # 项目说明文档
```

## 🛠️ 安装与配置

### 1. 环境要求
- Python 3.8+
- PostgreSQL 数据库
- DeepSeek API 密钥

### 2. 安装依赖
```bash
# 克隆项目
git clone https://github.com/unendev/Linuxdo-Reddit-Scraper.git
cd linuxdo-scraper

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 环境配置
创建 `.env` 文件：
```env
# 数据库配置
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# AI API 配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 代理配置 (可选)
HTTP_PROXY=http://127.0.0.1:10809
HTTPS_PROXY=http://127.0.0.1:10809
```

## 🚀 使用方法

### Linux.do 爬虫

#### 基本使用
```bash
cd linuxdo
python scripts/scraper.py
```

#### 手动上传数据
```bash
# 上传指定日期的数据
python scripts/manual_upload.py --date 2025-09-25

# 查看可用文件
python scripts/manual_upload.py --list

# 上传特定文件
python scripts/manual_upload.py --file linux.do_report_2025-09-25.json
```

#### 测试功能
```bash
# 测试数据库连接
python scripts/test_db.py

# 测试代理连接
python scripts/test_proxy.py
```

### Reddit 爬虫

#### 基本使用
```bash
cd reddit_scraper
python reddit_scraper.py
```

#### 自定义子版块
修改 `reddit_scraper.py` 中的 `SUBREDDIT` 变量：
```python
SUBREDDIT = "technology"  # 可改为 "programming", "sysadmin" 等
```

## 📊 数据输出

### Linux.do 数据格式
```json
{
  "date": "2025-09-27",
  "total_posts": 25,
  "posts": [
    {
      "title": "帖子标题",
      "author": "作者",
      "published": "2025-09-27T10:30:00Z",
      "content": "帖子内容...",
      "summary": "AI生成的摘要",
      "url": "https://linux.do/t/xxx"
    }
  ]
}
```

### Reddit 数据格式
```json
{
  "date": "2025-09-27",
  "subreddit": "technology",
  "total_posts": 10,
  "posts": [
    {
      "title": "帖子标题",
      "author": "作者",
      "published": "2025-09-27T10:30:00Z",
      "content": "帖子内容...",
      "summary": "AI生成的摘要",
      "url": "https://reddit.com/r/technology/comments/xxx"
    }
  ]
}
```

## 🔧 高级配置

### 代理设置
项目默认使用 `http://127.0.0.1:10809` 代理，可在脚本中修改：
```python
proxy_for_all = "http://your-proxy:port"
```

### 爬取限制
- Linux.do: 默认限制 30 个帖子
- Reddit: 默认限制 10 个帖子
- 可在脚本中调整 `POST_COUNT_LIMIT` 参数

### 重试机制
- 最大重试次数: 3 次
- 重试延迟: 5 秒
- 支持指数退避策略

## 📈 监控与日志

### 日志文件
- `scraper.log`: 详细的爬虫运行日志
- `scheduler.log`: 定时任务执行日志
- `data_monitor.log`: 数据质量监控日志

### 监控指标
- 爬取成功率
- 数据完整性
- API 调用频率
- 错误类型统计

## 🤝 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📝 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## ⚠️ 免责声明

本项目仅用于学习和研究目的。使用时请遵守相关网站的服务条款和robots.txt规则，尊重网站的使用政策。

## 📞 联系方式

- 项目链接: [https://github.com/unendev/Linuxdo-Reddit-Scraper](https://github.com/unendev/Linuxdo-Reddit-Scraper)
- 问题反馈: [Issues](https://github.com/unendev/Linuxdo-Reddit-Scraper/issues)

---

⭐ 如果这个项目对您有帮助，请给它一个星标！
