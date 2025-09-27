# manual_upload.py - 通用手动上传脚本
import asyncio
import os
import json
import argparse
from datetime import datetime, date
from dotenv import load_dotenv
import asyncpg

# 加载环境变量
load_dotenv()
NEON_DB_URL = os.getenv("DATABASE_URL")

# --- 代理配置 ---
proxy_for_all = "http://127.0.0.1:10809"
os.environ['HTTP_PROXY'] = proxy_for_all
os.environ['HTTPS_PROXY'] = proxy_for_all
print(f"--- 脚本已配置使用 HTTP 代理: {proxy_for_all} ---")

# Windows 下将事件循环策略切换为 Selector，避免某些库在 Proactor 下的兼容性问题
if os.name == 'nt':
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

async def connect_to_database_with_retry(max_retries=3, delay=5):
    """带重试机制的数据库连接"""
    for attempt in range(max_retries):
        try:
            print(f"尝试连接数据库 (第 {attempt + 1}/{max_retries} 次)...")
            conn = await asyncpg.connect(NEON_DB_URL)
            print("✅ 数据库连接成功！")
            return conn
        except Exception as e:
            print(f"❌ 第 {attempt + 1} 次连接失败: {e}")
            if attempt < max_retries - 1:
                print(f"等待 {delay} 秒后重试...")
                await asyncio.sleep(delay)
            else:
                raise e

async def upload_data_to_db(json_file_path, target_date=None):
    """上传指定JSON文件的数据到数据库"""
    if not NEON_DB_URL:
        print("错误: 未找到 DATABASE_URL 环境变量。")
        return False

    # 检查JSON文件是否存在
    if not os.path.exists(json_file_path):
        print(f"❌ JSON文件不存在: {json_file_path}")
        return False
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except Exception as e:
        print(f"❌ 读取JSON文件失败: {e}")
        return False
    
    json_posts = json_data.get('posts', [])
    if not json_posts:
        print("❌ JSON文件中没有帖子数据")
        return False
    
    # 从meta中获取报告生成时间
    meta = json_data.get('meta', {})
    generation_time_str = meta.get('generation_time', '')
    
    if generation_time_str:
        try:
            generation_time = datetime.fromisoformat(generation_time_str.replace('Z', '+00:00'))
        except:
            # 如果解析失败，使用当前时间
            generation_time = datetime.now()
    else:
        # 如果没有生成时间，使用当前时间
        generation_time = datetime.now()
    
    # 如果指定了目标日期，使用该日期
    if target_date:
        try:
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            generation_time = datetime.combine(target_date, generation_time.time())
        except Exception as e:
            print(f"⚠️ 目标日期解析失败，使用原时间: {e}")
    
    print(f"📄 从JSON文件中读取到 {len(json_posts)} 条帖子记录")
    print(f"📅 使用时间戳: {generation_time}")
    
    conn = None
    try:
        print(f"数据库URL长度: {len(NEON_DB_URL)}")
        print(f"数据库URL前缀: {NEON_DB_URL[:20]}...")
        
        # 使用重试机制连接数据库
        conn = await connect_to_database_with_retry(max_retries=3, delay=10)
        
        # 确保表存在
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
        print("✅ 数据库表检查完成")
        
        success_count = 0
        error_count = 0
        
        print("开始上传数据到数据库...")
        
        for i, post in enumerate(json_posts):
            try:
                post_id = post.get('id')
                title = post.get('title')
                url = post.get('url')
                analysis = post.get('analysis', {})
                core_issue = analysis.get('core_issue')
                key_info = json.dumps(analysis.get('key_info', []))
                post_type = analysis.get('post_type')
                value_assessment = analysis.get('value_assessment')
                
                # 插入数据到数据库，使用指定的时间戳
                await conn.execute("""
                    INSERT INTO posts (id, title, url, core_issue, key_info, post_type, value_assessment, timestamp)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        url = EXCLUDED.url,
                        core_issue = EXCLUDED.core_issue,
                        key_info = EXCLUDED.key_info,
                        post_type = EXCLUDED.post_type,
                        value_assessment = EXCLUDED.value_assessment,
                        timestamp = EXCLUDED.timestamp;
                """, post_id, title, url, core_issue, key_info, post_type, value_assessment, generation_time)
                
                success_count += 1
                print(f"  ✅ {i+1}/{len(json_posts)}: {title[:50]}... (ID: {post_id})")
                
            except Exception as e:
                error_count += 1
                print(f"  ❌ {i+1}/{len(json_posts)}: 上传失败 - {e}")
                continue
        
        print(f"\n📊 上传结果:")
        print(f"  ✅ 成功: {success_count} 条")
        print(f"  ❌ 失败: {error_count} 条")
        print(f"  📈 成功率: {success_count/(success_count+error_count)*100:.1f}%")
        
        # 验证上传结果
        if target_date:
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            db_count = await conn.fetchval("""
                SELECT COUNT(*) FROM posts WHERE DATE(timestamp) = $1
            """, target_date)
            
            print(f"\n🔍 验证结果:")
            print(f"  数据库中{target_date}的记录数: {db_count}")
            print(f"  JSON文件中的记录数: {len(json_posts)}")
            
            if db_count >= len(json_posts):
                print("✅ 数据上传成功！所有记录都已保存到数据库。")
                return True
            elif db_count > 0:
                print(f"⚠️  部分数据上传成功！数据库中已有 {db_count} 条记录，JSON文件中有 {len(json_posts)} 条记录。")
                return True
            else:
                print("❌ 数据上传失败！数据库中没有找到对应日期的记录。")
                return False
        else:
            print("✅ 数据上传完成！")
            return True
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        print(f"错误类型: {type(e).__name__}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
        return False
    finally:
        if conn:
            await conn.close()
            print("数据库连接已关闭。")

def find_json_file_by_date(date_str):
    """根据日期查找对应的JSON文件"""
    possible_files = [
        f"linux.do_report_{date_str}.json",
        f"linux.do_report_{date_str.replace('-', '_')}.json",
        f"linux.do_report_{date_str.replace('-', '')}.json"
    ]
    
    for file_path in possible_files:
        if os.path.exists(file_path):
            return file_path
    
    return None

async def main():
    parser = argparse.ArgumentParser(description='手动上传Linux.do数据到数据库')
    parser.add_argument('--date', '-d', type=str, help='指定日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--file', '-f', type=str, help='指定JSON文件路径')
    parser.add_argument('--list', '-l', action='store_true', help='列出可用的JSON文件')
    
    args = parser.parse_args()
    
    # 列出可用的JSON文件
    if args.list:
        print("=== 可用的JSON文件 ===")
        json_files = [f for f in os.listdir('.') if f.startswith('linux.do_report_') and f.endswith('.json')]
        json_files.sort()
        for i, file in enumerate(json_files, 1):
            print(f"{i:2d}. {file}")
        return
    
    # 确定要上传的文件
    json_file_path = None
    target_date = None
    
    if args.file:
        json_file_path = args.file
        if args.date:
            target_date = args.date
    elif args.date:
        target_date = args.date
        json_file_path = find_json_file_by_date(args.date)
        if not json_file_path:
            print(f"❌ 未找到日期 {args.date} 对应的JSON文件")
            print("可用的文件:")
            json_files = [f for f in os.listdir('.') if f.startswith('linux.do_report_') and f.endswith('.json')]
            for file in json_files[:5]:  # 只显示前5个
                print(f"  - {file}")
            return
    else:
        print("❌ 请指定日期 (--date) 或文件路径 (--file)")
        print("使用 --help 查看帮助信息")
        return
    
    print(f"=== 手动上传数据到数据库 ===")
    print(f"📁 JSON文件: {json_file_path}")
    if target_date:
        print(f"📅 目标日期: {target_date}")
    
    success = await upload_data_to_db(json_file_path, target_date)
    
    if success:
        print(f"\n🎉 数据上传完成！")
    else:
        print(f"\n💥 数据上传失败！")

if __name__ == "__main__":
    asyncio.run(main())
