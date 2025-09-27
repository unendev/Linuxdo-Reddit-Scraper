import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import re
import json
import time
import os
from dotenv import load_dotenv

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- 配置 ---
load_dotenv()
# 可以将 'technology' 替换为任何你感兴趣的 subreddit
SUBREDDIT = "technology"
RSS_URL = f"https://www.reddit.com/r/{SUBREDDIT}/.rss?sort=hot"
POST_COUNT_LIMIT = 10  # 限制获取的帖子数量（减少数量以便获取详细内容）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# --- Reddit 爬虫函数 ---
def fetch_reddit_posts():
    """使用 requests 获取并解析 Reddit subreddit 的 RSS 源"""
    logger.info(f"开始从 r/{SUBREDDIT} 的 RSS 源爬取热门帖子...")
    
    headers = {
        # Reddit 需要一个 User-Agent，否则会返回 429 Too Many Requests
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(RSS_URL, headers=headers, timeout=20)
        # 检查请求是否成功
        response.raise_for_status()
        
        logger.info("成功获取 RSS 内容，开始解析...")
        
        # 使用 ET 解析 XML
        root = ET.fromstring(response.content)
        
        all_posts = []
        # Reddit 的 RSS entry 在 'entry' 标签里
        for i, entry in enumerate(root.findall('{http://www.w3.org/2005/Atom}entry')):
            if i >= POST_COUNT_LIMIT:
                break
            
            title_tag = entry.find('{http://www.w3.org/2005/Atom}title')
            link_tag = entry.find('{http://www.w3.org/2005/Atom}link')
            content_tag = entry.find('{http://www.w3.org/2005/Atom}content')
            author_tag = entry.find('{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name')

            if title_tag is not None and link_tag is not None:
                title = title_tag.text
                # link.get('href') 获取 'href' 属性
                link = link_tag.get('href')
                author = author_tag.text if author_tag is not None else "N/A"
                
                # Reddit 的 content 是 HTML，这里做个简单清理
                content_html = content_tag.text if content_tag is not None else ""
                # 移除HTML标签
                clean_content = re.sub(r'<.*?>', ' ', content_html)
                # 移除多余的链接和空白符
                clean_content = re.sub(r'\[link\]|\[comments\]', '', clean_content).strip()
                
                all_posts.append({
                    "title": title,
                    "link": link,
                    "author": author,
                    "content_preview": clean_content[:250] + '...' if len(clean_content) > 250 else clean_content
                })
                logger.info(f"  解析帖子 {i+1}: {title[:60]}...")
                
        logger.info(f"成功解析到 {len(all_posts)} 个帖子。")
        return all_posts

    except requests.exceptions.RequestException as e:
        logger.error(f"请求 Reddit RSS 源失败: {e}")
        return []
    except ET.ParseError as e:
        logger.error(f"XML 解析失败: {e}")
        return []
    except Exception as e:
        logger.error(f"处理帖子时发生未知错误: {e}")
        return []

# --- 获取帖子详细内容和评论 ---
def fetch_post_details(post_url):
    """获取 Reddit 帖子的详细内容和热门评论"""
    try:
        # 将 Reddit URL 转换为 JSON API URL
        json_url = post_url.rstrip('/') + '.json'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(json_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Reddit JSON API 返回一个包含帖子和评论的数组
        post_data = data[0]['data']['children'][0]['data']
        comments_data = data[1]['data']['children']
        
        # 提取帖子内容
        post_content = post_data.get('selftext', '')
        if not post_content:
            post_content = post_data.get('title', '')
        
        # 清理内容
        clean_content = re.sub(r'&[a-zA-Z]+;', ' ', post_content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        
        # 提取热门评论（最多5条）
        top_comments = []
        for comment in comments_data[:5]:
            if comment['kind'] == 't1':  # t1 表示评论
                comment_data = comment['data']
                comment_text = comment_data.get('body', '')
                if comment_text and comment_text != '[deleted]' and comment_text != '[removed]':
                    # 清理评论内容
                    clean_comment = re.sub(r'&[a-zA-Z]+;', ' ', comment_text)
                    clean_comment = re.sub(r'\s+', ' ', clean_comment).strip()
                    if len(clean_comment) > 20:  # 只保留有意义的评论
                        top_comments.append({
                            'author': comment_data.get('author', 'N/A'),
                            'score': comment_data.get('score', 0),
                            'text': clean_comment[:300] + '...' if len(clean_comment) > 300 else clean_comment
                        })
        
        return {
            'content': clean_content,
            'comments': top_comments,
            'upvotes': post_data.get('ups', 0),
            'downvotes': post_data.get('downs', 0),
            'score': post_data.get('score', 0),
            'num_comments': post_data.get('num_comments', 0)
        }
        
    except Exception as e:
        logger.error(f"获取帖子详情失败 {post_url}: {e}")
        return {
            'content': '无法获取内容',
            'comments': [],
            'upvotes': 0,
            'downvotes': 0,
            'score': 0,
            'num_comments': 0
        }

# --- AI 分析函数 (复用 linuxdo-scraper 的提示词) ---
def analyze_single_post_with_deepseek(post, retry_count=0):
    """使用DeepSeek对单个帖子进行结构化分析，并返回一个JSON对象。"""
    try:
        # 准备内容，包含帖子和评论
        content = post.get('content', '')
        comments_text = '\n'.join([f"评论: {c['text']}" for c in post.get('comments', [])])
        full_content = f"{content}\n\n热门评论:\n{comments_text}"
        
        clean_content = re.sub(r'<.*?>', ' ', full_content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()
        excerpt = (clean_content[:800] + '...') if len(clean_content) > 800 else clean_content

        if not excerpt or len(excerpt.strip()) < 10:
            logger.warning(f"帖子 '{post.get('title', 'N/A')}' 内容过短，跳过AI分析")
            return {
                "error": "内容过短或为空，无法进行AI摘要。",
                "core_issue": "N/A", "key_info": [], "post_type": "未知", "value_assessment": "低"
            }

        # 使用适合 Reddit 的 DeepSeek API 提示词
        prompt = f"""
        你是一名社交媒体内容分析师。请分析以下 Reddit 帖子内容，并严格按照指定的JSON格式返回结果。
        你的回复必须是一个有效的JSON对象，不要包含任何解释性文字或Markdown的```json ```标记。

        **帖子标题**: {post['title']}
        **内容节选**: {excerpt}

        **请输出以下结构的JSON**:
        {{
          "core_issue": "这里用一句话概括帖子的核心议题或讨论焦点",
          "key_info": [
            "关键观点或信息点1",
            "关键观点或信息点2"
          ],
          "post_type": "从[技术讨论, 新闻分享, 问题求助, 观点讨论, 资源分享, 娱乐内容, 社会议题, 产品评测, 其他]中选择一个",
          "value_assessment": "从[高, 中, 低]中选择一个"
        }}
        """
        
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
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # 尝试解析AI返回的文本为JSON
            cleaned_text = ai_response.strip().replace("```json", "").replace("```", "").strip()
            analysis_data = json.loads(cleaned_text)
            logger.info(f"帖子 '{post['title'][:30]}...' AI分析成功")
            return analysis_data
        else:
            logger.error(f"DeepSeek API调用失败: {response.status_code} - {response.text}")
            return {
                "error": f"DeepSeek API调用失败: {response.status_code}",
                "core_issue": "API调用失败", "key_info": [], "post_type": "错误", "value_assessment": "低"
            }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败! AI返回了非JSON格式的内容: '{ai_response[:100] if 'ai_response' in locals() else 'N/A'}...'")
        return {
            "error": "AI返回了非JSON格式的内容", 
            "raw_response": ai_response if 'ai_response' in locals() else "N/A",
            "core_issue": "AI分析失败", "key_info": [], "post_type": "错误", "value_assessment": "低"
        }
    except requests.exceptions.Timeout:
        logger.error(f"DeepSeek API请求超时")
        return {
            "error": "API请求超时",
            "core_issue": "API超时", "key_info": [], "post_type": "错误", "value_assessment": "低"
        }
    except Exception as e:
        logger.error(f"对帖子 '{post.get('title', 'N/A')[:20]}...' 的摘要失败: {e}")
        return {
            "error": f"DeepSeek API调用失败: {e}",
            "core_issue": "AI分析失败", "key_info": [], "post_type": "错误", "value_assessment": "低"
        }

# --- AI 整体洞察报告生成 (复用 linuxdo-scraper 的架构) ---
def generate_ai_summary_report(posts_data):
    """生成AI摘要报告，增强错误处理"""
    if not posts_data:
        logger.warning("没有帖子数据，生成空报告")
        return {"summary_analysis": {"error": "没有帖子数据"}, "processed_posts": []}

    logger.info("\n--- 开始生成逐帖结构化分析 ---")
    processed_posts = [] 
    
    for i, post in enumerate(posts_data):
        logger.info(f"正在分析第 {i+1}/{len(posts_data)} 篇: {post['title']}")
        
        try:
            # 将分析结果（一个字典）存入 'analysis' 键
            post['analysis'] = analyze_single_post_with_deepseek(post)
            processed_posts.append(post)
            
            if i < len(posts_data) - 1:
                logger.info("    ...等待3秒以遵守API速率限制...")
                time.sleep(3)
                
        except Exception as e:
            logger.error(f"分析帖子 {post.get('title', 'N/A')} 失败: {e}")
            post['analysis'] = {
                "error": f"分析失败: {e}",
                "core_issue": "分析失败", "key_info": [], "post_type": "错误", "value_assessment": "低"
            }
            processed_posts.append(post)
            
    logger.info("--- 逐帖分析全部完成 ---\n")

    # 生成整体洞察报告
    logger.info("--- 开始生成今日整体洞察报告 (JSON格式) ---")
    summaries_for_prompt = []
    for post in processed_posts:
        if 'error' not in post['analysis']:
            summaries_for_prompt.append({
                "title": post['title'],
                "analysis": post['analysis']
            })

    if not summaries_for_prompt:
        logger.warning("没有有效的帖子分析结果，生成默认报告")
        summary_analysis = {
            "overview": "今日未能获取到有效的帖子分析结果。",
            "highlights": {"tech_savvy": [], "resources_deals": [], "hot_topics": []},
            "conclusion": "请检查网络连接和API配置。"
        }
    else:
        # 使用json.dumps来创建一个紧凑的字符串表示形式
        all_summaries_text = json.dumps(summaries_for_prompt, ensure_ascii=False, indent=2)

        overall_prompt = f"""
        你是一名资深的社交媒体内容分析师。以下是今天 Reddit 热门帖子的JSON格式摘要列表。
        请根据这些信息，生成一份高度浓缩的中文"今日热点洞察"报告，并严格以指定的JSON格式返回。
        你的回复必须是一个有效的JSON对象，不要包含任何解释性文字或Markdown的```json ```标记。

        **今日帖子摘要合集 (JSON格式):**
        {all_summaries_text}
        ---
        **请输出以下结构的JSON**:
        {{
          "overview": "用一两句话总结今天 Reddit 社区的整体氛围和讨论焦点。",
          "highlights": {{
            "tech_savvy": ["提炼1-3条最硬核的技术干货或科技资讯"],
            "resources_deals": ["提炼1-3条最值得关注的资源分享或优惠信息"],
            "hot_topics": ["提炼1-3个引发最广泛讨论的热门话题或争议点"]
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
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content']
                cleaned_text = ai_response.strip().replace("```json", "").replace("```", "").strip()
                summary_analysis = json.loads(cleaned_text)
                logger.info("--- 整体洞察报告生成完毕 ---")
            else:
                logger.error(f"生成整体洞察报告失败: {response.status_code} - {response.text}")
                summary_analysis = {
                    "error": f"DeepSeek API调用失败: {response.status_code}",
                    "overview": "今日AI总结生成失败，请查看日志。",
                    "highlights": {},
                    "conclusion": ""
                }
        except Exception as e:
            logger.error(f"生成整体洞察报告失败: {e}")
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

# --- JSON 报告生成函数 (复用 linuxdo-scraper 的格式) ---
def generate_json_report(report_data, posts_count):
    """生成JSON报告文件，增强错误处理"""
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"reddit_{SUBREDDIT}_report_{today_str}.json"

        # 准备最终的JSON结构 (与 linuxdo-scraper 相同格式)
        final_json = {
            "meta": {
                "report_date": today_str,
                "title": f"Reddit r/{SUBREDDIT} 每日热帖报告 ({today_str})",
                "source": f"Reddit r/{SUBREDDIT}",
                "post_count": posts_count,
                "generation_time": datetime.now().isoformat(),
                "status": "success" if posts_count > 0 else "no_data"
            },
            "summary": report_data.get('summary_analysis', {}),
            "posts": []
        }

        for post in report_data.get('processed_posts', []):
            final_json["posts"].append({
                "id": post.get('id', 'N/A'),
                "title": post.get('title', '无标题'),
                "url": post.get('link', '#'),
                "analysis": post.get('analysis', {})
            })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON报告已生成: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"生成JSON报告失败: {e}")
        return None

# --- Markdown 报告生成函数 ---
def generate_markdown_report(report_data, posts_count):
    """生成Markdown报告，增强错误处理 (复用 linuxdo-scraper 的格式)"""
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"Reddit_{SUBREDDIT}_Daily_Report_{today_str}.md"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Reddit r/{SUBREDDIT} 每日热帖报告 ({today_str})\n\n")
            
            # 添加状态信息
            if posts_count == 0:
                f.write("⚠️ **注意**: 今日未能抓取到任何帖子数据，可能是网络问题或RSS源异常。\n\n")
            
            # 渲染精华提炼部分
            f.write("## 🚀 今日精华提炼\n\n")
            summary = report_data.get('summary_analysis', {})
            
            if 'error' in summary:
                f.write(f"❌ **错误**: {summary.get('error', '未知错误')}\n\n")
            else:
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

        logger.info(f"Markdown报告已生成: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"生成Markdown报告失败: {e}")
        return None

# --- 主函数 (复用 linuxdo-scraper 的架构) ---
def main():
    """改进的主函数，增强错误处理和监控"""
    start_time = datetime.now()
    logger.info("=== 开始执行 Reddit 爬虫任务 ===")
    
    try:
        # 检查环境变量
        if not DEEPSEEK_API_KEY:
            logger.error("未找到 DEEPSEEK_API_KEY 环境变量")
            return False
        
        # 第一步：获取基础帖子列表
        posts = fetch_reddit_posts()
        
        if not posts:
            logger.error("未能获取到任何帖子数据")
            # 即使失败，也生成一个空的报告文件
            empty_data = {
                "summary_analysis": {
                    "error": "未能抓取到任何帖子数据，可能是网络问题或RSS源异常",
                    "overview": "今日未能抓取到任何帖子数据。"
                }, 
                "processed_posts": []
            }
            generate_json_report(empty_data, 0)
            generate_markdown_report(empty_data, 0)
            return False
        
        logger.info(f"成功获取到 {len(posts)} 条帖子数据")
        
        # 第二步：获取每个帖子的详细内容和评论
        detailed_posts = []
        for i, post in enumerate(posts):
            logger.info(f"正在处理第 {i+1}/{len(posts)} 个帖子: {post['title'][:50]}...")
            
            # 获取详细内容
            details = fetch_post_details(post['link'])
            
            # 合并数据
            detailed_post = {
                **post,
                **details
            }
            
            detailed_posts.append(detailed_post)
            logger.info(f"  完成处理: {post['title'][:30]}...")
        
        # 第三步：生成AI报告 (使用与 linuxdo-scraper 相同的架构)
        report_data = generate_ai_summary_report(detailed_posts)
        
        # 第四步：生成报告文件
        json_file = generate_json_report(report_data, len(detailed_posts))
        md_file = generate_markdown_report(report_data, len(detailed_posts))
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"=== 任务完成 ===")
        logger.info(f"处理时间: {duration:.2f} 秒")
        logger.info(f"处理帖子: {len(detailed_posts)} 条")
        logger.info(f"生成文件: {json_file}, {md_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"主函数执行失败: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        logger.error("Reddit 爬虫任务执行失败")
        exit(1)
    else:
        logger.info("Reddit 爬虫任务执行成功")
