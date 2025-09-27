# scraper.py
import asyncio
import os
import re
import json
from datetime import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import requests
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import time
import asyncpg

# --- 代理配置 ---
proxy_for_all = "http://127.0.0.1:10809"
os.environ['HTTP_PROXY'] = proxy_for_all
os.environ['HTTPS_PROXY'] = proxy_for_all
print(f"--- 脚本已配置使用 HTTP 代理: {proxy_for_all} ---")
# -------------------------

# --- 配置 ---
load_dotenv()
WARM_UP_URL = "https://linux.do/" 
RSS_URL = "https://linux.do/latest.rss" 
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
NEON_DB_URL = os.getenv("DATABASE_URL") # 从环境变量加载 Neon 数据库 URL
POST_COUNT_LIMIT = 30 # 稍微减少数量，因为每个帖子的处理更复杂了

# --- 摘要单个帖子，并要求返回JSON ---
def analyze_single_post_with_deepseek(post):
    """使用DeepSeek对单个帖子进行结构化分析，并返回一个JSON对象。"""
    clean_content = re.sub(r'<.*?>', ' ', post.get('content', ''))
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    excerpt = (clean_content[:800] + '...') if len(clean_content) > 800 else clean_content

    if not excerpt or len(excerpt.strip()) < 10:
        return {
            "error": "内容过短或为空，无法进行AI摘要。",
            "core_issue": "N/A", "key_info": [], "post_type": "未知", "value_assessment": "低"
        }

    # 使用DeepSeek API进行分析
    prompt = f"""
    你是一名信息提取专家。请分析以下论坛帖子内容，并严格按照指定的JSON格式返回结果。
    你的回复必须是一个有效的JSON对象，不要包含任何解释性文字或Markdown的```json ```标记。

    **帖子标题**: {post['title']}
    **内容节选**: {excerpt}

    **请输出以下结构的JSON**:
    {{
      "core_issue": "这里用一句话概括帖子的核心议题",
      "key_info": [
        "关键信息或解决方案点1",
        "关键信息或解决方案点2"
      ],
      "post_type": "从[技术问答, 资源分享, 新闻资讯, 优惠活动, 日常闲聊, 求助, 讨论, 产品评测]中选择一个",
      "value_assessment": "从[高, 中, 低]中选择一个"
    }}
    """
    
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 400,
            "temperature": 0.3
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            proxies={"http": proxy_for_all, "https": proxy_for_all}
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # 尝试解析AI返回的文本为JSON
            cleaned_text = ai_response.strip().replace("```json", "").replace("```", "").strip()
            analysis_data = json.loads(cleaned_text)
            return analysis_data
        else:
            print(f"    - DeepSeek API调用失败: {response.status_code} - {response.text}")
            return {
                "error": f"DeepSeek API调用失败: {response.status_code}",
                "core_issue": "API调用失败", "key_info": [], "post_type": "错误", "value_assessment": "低"
            }
        
    except json.JSONDecodeError:
        print(f"    - JSON解析失败! AI返回了非JSON格式的内容: '{ai_response[:100]}...'")
        return {
            "error": "AI返回了非JSON格式的内容", "raw_response": ai_response,
            "core_issue": "AI分析失败", "key_info": [], "post_type": "错误", "value_assessment": "低"
        }
    except Exception as e:
        print(f"    - 对帖子 '{post['title'][:20]}...' 的摘要失败: {e}")
        return {
            "error": f"DeepSeek API调用失败: {e}",
            "core_issue": "AI分析失败", "key_info": [], "post_type": "错误", "value_assessment": "低"
        }

# --- 生成AI报告，处理结构化数据 ---
def generate_ai_summary_report(posts_data):
    if not posts_data:
        return {"summary_analysis": {"error": "没有帖子数据"}, "processed_posts": []}

    print("\n--- 开始生成逐帖结构化分析 ---")
    processed_posts = [] 
    for i, post in enumerate(posts_data):
        print(f"正在分析第 {i+1}/{len(posts_data)} 篇: {post['title']}")
        # 将分析结果（一个字典）存入 'analysis' 键
        post['analysis'] = analyze_single_post_with_deepseek(post)
        processed_posts.append(post)
        
        if i < len(posts_data) - 1:
            print("    ...等待3秒以遵守API速率限制...")
            time.sleep(3) 
            
    print("--- 逐帖分析全部完成 ---\n")

    print("--- 开始生成今日整体洞察报告 (JSON格式) ---")
    # 为了生成整体报告，我们将每个帖子的标题和分析结果打包发给AI
    summaries_for_prompt = []
    for post in processed_posts:
        if 'error' not in post['analysis']:
            summaries_for_prompt.append({
                "title": post['title'],
                "analysis": post['analysis']
            })

    # 使用json.dumps来创建一个紧凑的字符串表示形式
    all_summaries_text = json.dumps(summaries_for_prompt, ensure_ascii=False, indent=2)

    overall_prompt = f"""
    你是一名资深的论坛内容分析师。以下是今天论坛热门帖子的JSON格式摘要列表。
    请根据这些信息，生成一份高度浓缩的中文"今日热点洞察"报告，并严格以指定的JSON格式返回。
    你的回复必须是一个有效的JSON对象，不要包含任何解释性文字或Markdown的```json ```标记。

    **今日帖子摘要合集 (JSON格式):**
    {all_summaries_text}
    ---
    **请输出以下结构的JSON**:
    {{
      "overview": "用一两句话总结今天社区的整体氛围和讨论焦点。",
      "highlights": {{
        "tech_savvy": ["提炼1-3条最硬核的技术干货"],
        "resources_deals": ["提炼1-3条最值得关注的优惠或资源分享"],
        "hot_topics": ["提炼1-3个引发最广泛讨论的话题"]
      }},
      "conclusion": "用一句话对今天的内容做个风趣或深刻的总结。"
    }}
    """
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": overall_prompt}
            ],
            "max_tokens": 800,
            "temperature": 0.3
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            proxies={"http": proxy_for_all, "https": proxy_for_all}
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            cleaned_text = ai_response.strip().replace("```json", "").replace("```", "").strip()
            summary_analysis = json.loads(cleaned_text)
            print("--- 整体洞察报告生成完毕 ---")
        else:
            print(f"生成整体洞察报告失败: {response.status_code} - {response.text}")
            summary_analysis = {
                "error": f"DeepSeek API调用失败: {response.status_code}",
                "overview": "今日AI总结生成失败，请查看日志。",
                "highlights": {},
                "conclusion": ""
            }
    except Exception as e:
        print(f"生成整体洞察报告失败: {e}")
        summary_analysis = {
            "error": f"AI生成整体报告失败: {e}",
            "overview": "今日AI总结生成失败，请查看日志。",
            "highlights": {},
            "conclusion": ""
        }

    return {
        "summary_analysis": summary_analysis,
        "processed_posts": processed_posts
    }

# --- 生成JSON报告文件 ---
def generate_json_report(report_data, posts_count):
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"linux.do_report_{today_str}.json"

    # 准备最终的JSON结构
    final_json = {
        "meta": {
            "report_date": today_str,
            "title": f"Linux.do 每日热帖报告 ({today_str})",
            "source": "Linux.do",
            "post_count": posts_count
        },
        "summary": report_data.get('summary_analysis', {}),
        "posts": []
    }

    for post in report_data.get('processed_posts', []):
        final_json["posts"].append({
            "id": post.get('id', 'N/A'),
            "title": post.get('title', '无标题'),
            "url": post.get('link', '#'),
            # 这里我们直接使用AI分析出的结构化数据
            "analysis": post.get('analysis', {})
        })

    with open(filename, 'w', encoding='utf-8') as f:
        # 使用 ensure_ascii=False 来正确处理中文字符
        # 使用 indent=2 来美化输出，方便阅读
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    print(f"JSON报告已生成: {filename}")

async def create_posts_table():
    """连接到Neon数据库并创建posts表，如果它不存在的话。"""
    if not NEON_DB_URL:
        print("错误: 未找到 DATABASE_URL 环境变量。无法连接到数据库。")
        return

    conn = None
    try:
        conn = await asyncpg.connect(NEON_DB_URL)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                core_issue TEXT,
                key_info JSONB,
                post_type TEXT,
                value_assessment TEXT,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("数据库表 'posts' 检查或创建成功。")
    except Exception as e:
        print(f"创建数据库表失败: {e}")
    finally:
        if conn:
            await conn.close()

async def insert_posts_into_db(posts_data):
    """将处理后的帖子数据插入到Neon数据库中。"""
    if not NEON_DB_URL:
        print("错误: 未找到 DATABASE_URL 环境变量。无法连接到数据库。")
        return

    conn = None
    try:
        conn = await asyncpg.connect(NEON_DB_URL)
        print("开始将帖子数据插入到数据库...")
        for post in posts_data:
            post_id = post.get('id')
            title = post.get('title')
            url = post.get('link')
            analysis = post.get('analysis', {})
            core_issue = analysis.get('core_issue')
            key_info = json.dumps(analysis.get('key_info', []))
            post_type = analysis.get('post_type')
            value_assessment = analysis.get('value_assessment')

            await conn.execute("""
                INSERT INTO posts (id, title, url, core_issue, key_info, post_type, value_assessment)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    url = EXCLUDED.url,
                    core_issue = EXCLUDED.core_issue,
                    key_info = EXCLUDED.key_info,
                    post_type = EXCLUDED.post_type,
                    value_assessment = EXCLUDED.value_assessment,
                    timestamp = CURRENT_TIMESTAMP;
            """, post_id, title, url, core_issue, key_info, post_type, value_assessment)
            print(f"  - 帖子 '{title[:30]}...' (ID: {post_id}) 已插入/更新。")
        print("所有帖子数据已成功插入/更新到数据库。")
    except Exception as e:
        print(f"插入帖子数据到数据库失败: {e}")
    finally:
        if conn:
            await conn.close()

# --- 生成Markdown报告，使其适配新的数据结构 ---
def generate_markdown_report(report_data, posts_count):
    today_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"Linux.do_Daily_Report_{today_str}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"# Linux.do 每日热帖报告 ({today_str})\n\n")
        
        # 渲染精华提炼部分
        f.write("## 🚀 今日精华提炼\n\n")
        summary = report_data.get('summary_analysis', {})
        f.write(f"**今日概览:** {summary.get('overview', 'N/A')}\n\n")
        f.write(f"**高价值信息速递:**\n")
        highlights = summary.get('highlights', {})
        if highlights.get('tech_savvy'):
            f.write(f"*   **技术干货:**\n")
            for item in highlights['tech_savvy']:
                f.write(f"    *   {item}\n")
        if highlights.get('resources_deals'):
            f.write(f"*   **优惠/资源**:\n")
            for item in highlights['resources_deals']:
                f.write(f"    *   {item}\n")
        if highlights.get('hot_topics'):
            f.write(f"*   **热议话题**:\n")
            for item in highlights['hot_topics']:
                f.write(f"    *   {item}\n")
        f.write(f"\n**今日结语:** {summary.get('conclusion', 'N/A')}\n\n")
        f.write("---\n\n")

        # 渲染逐帖摘要部分
        f.write("## 📰 逐帖摘要与分析\n\n")
        posts = report_data.get('processed_posts', [])
        if posts:
            for post in posts:
                title = post.get('title', '无标题')
                link = post.get('link', '#')
                analysis = post.get('analysis', {})
                
                f.write(f"### [{title}]({link})\n\n")
                # 使用Markdown引用格式展示结构化分析结果
                f.write(f"> 1.  **核心议题**: {analysis.get('core_issue', 'N/A')}\n")
                f.write(f"> 2.  **关键信息/解决方案**:\n")
                for info in analysis.get('key_info', []):
                    f.write(f">     *   {info}\n")
                if not analysis.get('key_info'):
                     f.write(f">     *   无\n")
                f.write(f"> 3.  **帖子类型**: {analysis.get('post_type', 'N/A')}\n")
                f.write(f"> 4.  **价值评估**: {analysis.get('value_assessment', 'N/A')}\n\n")
        else:
            f.write("今日未能抓取到新帖子。\n")
            
        # 渲染原始帖子列表
        f.write("---\n\n")
        f.write(f"## 📋 原始帖子列表 (共 {posts_count} 篇)\n\n")
        if posts:
            for post in posts:
                f.write(f"- [{post.get('title', '无标题')}]({post.get('link', '#')})\n")
        else:
            f.write("今日未能抓取到任何原始帖子。\n")

    print(f"Markdown报告已生成: {filename}")

# --- 核心爬虫逻辑 ---
async def fetch_linuxdo_posts_optimized():
    print("开始执行优化版爬取任务...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": proxy_for_all}
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0"
            }
        )
        stealth = Stealth()
        await stealth.apply_stealth_async(context)
        page = await context.new_page()

        try:
            print(f"正在访问首页进行预热: {WARM_UP_URL}")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await page.goto(WARM_UP_URL, wait_until="domcontentloaded", timeout=180000)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"预热尝试 {attempt + 1} 失败，重新尝试...")
                    await asyncio.sleep(2)

            print("预热完成，会话已建立。")
            await asyncio.sleep(3)

            print(f"正在通过浏览器直接访问 RSS 源: {RSS_URL}")
            for attempt in range(max_retries):
                try:
                    await page.goto(RSS_URL, wait_until="networkidle", timeout=120000)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    print(f"RSS访问尝试 {attempt + 1} 失败，重新尝试...")
                    await asyncio.sleep(2)

            await asyncio.sleep(1)

            rss_text = await page.evaluate("document.documentElement.outerHTML")

            with open("debug_rss_content.html", 'w', encoding='utf-8') as f:
                f.write(rss_text)
            print(f"已保存调试内容到 debug_rss_content.html (长度: {len(rss_text)} 字符)")

            all_posts = []
            print("开始解析RSS内容...")

            print("尝试方式1：直接解析XML")
            try:
                root = ET.fromstring(rss_text)
                items = root.findall('.//channel/item')
                print(f"找到 {len(items)} 个item标签")
                for i, item in enumerate(items[:POST_COUNT_LIMIT]):
                    title = item.find('title')
                    link = item.find('link')
                    description = item.find('description')
                    if title is not None and link is not None:
                        title_text = title.text
                        link_text = link.text
                        description_text = description.text if description is not None else ""
                        print(f"  解析帖子 {i+1}: {title_text[:50]}... -> {link_text}")
                        match = re.search(r'/t/[^/]+/(\d+)', link_text)
                        if match:
                            topic_id = match.group(1)
                            all_posts.append({
                                "title": title_text,
                                "link": link_text,
                                "id": topic_id,
                                "description": description_text
                            })
                            print(f"    成功解析，ID: {topic_id}, 描述长度: {len(description_text)}")
                        else:
                            print(f"    无法匹配ID: {link_text}")
                    else:
                        print(f"  帖子 {i+1} 缺少title或link标签")
            except ET.ParseError as e:
                print(f"XML解析失败: {e}")

            # 方式2：从HTML中提取XML内容
            if not all_posts:
                print("尝试方式2：从HTML中提取XML内容")
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(rss_text, 'html.parser')
                    pre_tag = soup.find('pre')
                    if pre_tag:
                        xml_content = pre_tag.get_text()
                        print(f"从pre标签提取到 {len(xml_content)} 字符的XML内容")
                        import html
                        xml_content = html.unescape(xml_content)
                        root = ET.fromstring(xml_content)
                        items = root.findall('.//channel/item')
                        print(f"找到 {len(items)} 个item标签")
                        for i, item in enumerate(items[:POST_COUNT_LIMIT]):
                            title = item.find('title')
                            link = item.find('link')
                            description = item.find('description')
                            if title is not None and link is not None:
                                title_text = title.text
                                link_text = link.text
                                description_text = description.text if description is not None else ""
                                print(f"  解析帖子 {i+1}: {title_text[:50]}... -> {link_text}")
                                match = re.search(r'/t/[^/]+/(\d+)', link_text)
                                if match:
                                    topic_id = match.group(1)
                                    all_posts.append({"title": title_text, "link": link_text, "id": topic_id, "description": description_text})
                                    print(f"    成功解析，ID: {topic_id}")
                                else:
                                    print(f"    无法匹配ID: {link_text}")
                            else:
                                print(f"  帖子 {i+1} 缺少title或link标签")
                    else:
                        print("未找到pre标签")
                except Exception as e2:
                    print(f"HTML提取解析也失败: {e2}")

            # 方式3：正则表达式提取基本信息
            if not all_posts:
                print("尝试方式3：正则表达式提取基本信息 (兜底方案)")
                title_pattern = r'<title>([^<]+)</title>'
                link_pattern = r'<link>([^<]+)</link>'
                titles = re.findall(title_pattern, rss_text)
                links = re.findall(link_pattern, rss_text)

                for i, (title, link) in enumerate(zip(titles, links)):
                    if i >= POST_COUNT_LIMIT:
                        break
                    match = re.search(r'/t/[^/]+/(\d+)', link)
                    if match:
                        all_posts.append({"title": title, "link": link, "id": match.group(1), "description": ""})
            
            print(f"从 RSS 源成功解析到 {len(all_posts)} 个帖子。")
            
            posts_with_content = []
            for i, post in enumerate(all_posts):
                print(f"  > 正在处理帖子: {post['title']}")

                # 优先使用RSS描述中的内容作为帖子的'content'
                rss_content = post.get('description', '')

                # 清理RSS描述内容（移除HTML标签和多余空白）
                if rss_content:
                    clean_content = re.sub(r'<[^>]+>', ' ', rss_content)
                    clean_content = ' '.join(clean_content.split())
                    clean_content = clean_content.replace('\n', ' ').replace('\r', ' ')
                    clean_content = ' '.join(clean_content.split())

                    if len(clean_content.strip()) > 10:
                        post['content'] = clean_content
                        posts_with_content.append(post)
                        print(f"    + 使用RSS描述内容 (长度: {len(clean_content)} 字符)")
                    else:
                        post['content'] = f"帖子标题：{post['title']}"
                        posts_with_content.append(post)
                        print(f"    + RSS内容太短，使用标题作为内容")
                else:
                    post['content'] = f"帖子标题：{post['title']}"
                    posts_with_content.append(post)
                    print(f"    + 使用标题作为内容")

                if i < len(all_posts) - 1:
                    await asyncio.sleep(1)

            print(f"成功获取了 {len(posts_with_content)} 个帖子的详细内容。")
            return posts_with_content

        except Exception as e:
            print(f"爬取过程中发生严重错误: {e}")
            try:
                await page.screenshot(path="error_screenshot_optimized.png")
            except Exception as screenshot_error:
                print(f"无法保存错误截图: {screenshot_error}")
            return []
        finally:
            await browser.close()
            print("浏览器已关闭。")

# --- 主函数 ---
async def main():
    await create_posts_table()
    posts_data = await fetch_linuxdo_posts_optimized()
    if posts_data:
        report_data = generate_ai_summary_report(posts_data)
        
        # 插入数据到数据库
        if report_data.get('processed_posts'):
            await insert_posts_into_db(report_data['processed_posts'])

        # 现在同时生成两种格式的报告
        generate_json_report(report_data, len(posts_data))
        generate_markdown_report(report_data, len(posts_data))
    else:
        print("未能获取到任何帖子数据，任务结束。")
        # 即使失败，也生成一个空的报告文件，表示任务已运行
        empty_data = {"summary_analysis": {"overview": "未能抓取到任何帖子数据。"}, "processed_posts": []}
        generate_json_report(empty_data, 0)
        generate_markdown_report(empty_data, 0)

if __name__ == "__main__":
    asyncio.run(main())
