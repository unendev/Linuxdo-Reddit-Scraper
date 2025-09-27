# Linux.do & Reddit 爬虫项目

这是一个用于爬取 Linux.do 和 Reddit 技术论坛数据的项目。

## 项目结构

```
linuxdo-scraper/
├── linuxdo/                    # Linux.do 爬虫相关文件
│   ├── scripts/                # 脚本文件
│   │   ├── scraper.py         # 主爬虫脚本
│   │   ├── manual_upload.py   # 通用手动上传脚本
│   │   ├── upload_0925_data.py # 9月25日专用上传脚本
│   │   ├── test_db.py         # 数据库测试脚本
│   │   └── test_proxy.py      # 代理测试脚本
│   ├── data/                  # JSON数据文件
│   │   └── linux.do_report_*.json
│   ├── reports/               # Markdown报告文件
│   │   └── Linux.do_Daily_Report_*.md
│   ├── logs/                  # 日志文件
│   │   ├── scraper.log
│   │   ├── scheduler.log
│   │   └── data_monitor.log
│   ├── debug/                 # 调试文件
│   │   ├── debug_rss_content_*.html
│   │   ├── error_screenshot_*.png
│   │   └── health_report_*.json
│   ├── run_scraper.bat        # 运行脚本
│   ├── start.bat              # 启动脚本
│   └── 数据库使用指南.md       # 数据库使用说明
├── reddit_scraper/            # Reddit 爬虫相关文件
│   ├── reddit_scraper.py      # Reddit 爬虫脚本
│   ├── reddit_scraper.log     # Reddit 爬虫日志
│   └── Reddit_technology_Report_*.md
├── venv/                      # Python 虚拟环境
└── README.md                  # 项目说明
```

## 使用方法

### Linux.do 爬虫

1. **运行爬虫**：
   ```bash
   cd linuxdo
   python scripts/scraper.py
   ```

2. **手动上传数据**：
   ```bash
   cd linuxdo
   python scripts/manual_upload.py --date 2025-09-25
   ```

3. **查看可用文件**：
   ```bash
   python scripts/manual_upload.py --list
   ```

### Reddit 爬虫

1. **运行爬虫**：
   ```bash
   cd reddit_scraper
   python reddit_scraper.py
   ```

## 环境配置

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置环境变量（.env文件）：
   ```
   # Neon 数据库配置 (PostgreSQL 云数据库)
   DATABASE_URL=postgresql://username:password@ep-xxx.us-east-1.aws.neon.tech/neondb
   
   # DeepSeek AI API 配置
   DEEPSEEK_API_KEY=your_deepseek_api_key
   ```

3. 配置代理（如需要）：
   - 脚本已配置使用 `http://127.0.0.1:10809` 代理

## 注意事项

- 确保代理服务器正常运行
- **Neon 数据库连接**：项目使用 Neon (PostgreSQL 云数据库) 存储数据
- 数据库连接需要正确的环境变量配置
- 脚本支持自动重试和错误处理
- 所有数据都会保存到 Neon PostgreSQL 数据库中

## 数据库说明

### Neon 数据库
项目使用 **Neon** 作为 PostgreSQL 云数据库服务：

- **服务商**: Neon (https://neon.tech)
- **数据库类型**: PostgreSQL
- **连接方式**: 通过 `DATABASE_URL` 环境变量
- **功能**: 存储爬取的帖子数据、元数据和统计信息

### 数据库表结构
```sql
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    published TIMESTAMP,
    content TEXT,
    summary TEXT,
    url TEXT,
    source TEXT,  -- 'linuxdo' 或 'reddit'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 测试数据库连接
```bash
cd linuxdo
python scripts/test_db.py
```

## 文件说明

- **scraper.py**: 主要的 Linux.do 爬虫脚本，集成 Neon 数据库存储
- **manual_upload.py**: 通用的手动上传脚本，支持指定日期或文件
- **reddit_scraper.py**: Reddit 技术论坛爬虫脚本
- **test_db.py**: Neon 数据库连接测试脚本
- **数据库使用指南.md**: 详细的数据库使用说明
