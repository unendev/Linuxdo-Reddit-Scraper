# upload_0925_data.py - 上传9月25日数据到数据库
import asyncio
import os
import json
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

async def upload_0925_data():
    """上传9月25日数据到数据库"""
    if not NEON_DB_URL:
        print("错误: 未找到 DATABASE_URL 环境变量。")
        return False

    # 读取9月25日的JSON文件
    json_file = "linux.do_report_2025-09-25.json"
    if not os.path.exists(json_file):
        print(f"❌ JSON文件不存在: {json_file}")
        return False
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
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
    generation_time_str = meta.get('generation_time', '2025-09-25T19:12:52.637479')
    try:
        generation_time = datetime.fromisoformat(generation_time_str.replace('Z', '+00:00'))
    except:
        generation_time = datetime(2025, 9, 25, 19, 12, 52)  # 默认时间
    
    print(f"📄 从JSON文件中读取到 {len(json_posts)} 条帖子记录")
    print(f"📅 报告生成时间: {generation_time}")
    
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
                
                # 插入数据到数据库，使用报告的实际生成时间
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
        
        # 验证上传结果 - 检查9月25日的数据
        target_date = date(2025, 9, 25)
        db_count = await conn.fetchval("""
            SELECT COUNT(*) FROM posts WHERE DATE(timestamp) = $1
        """, target_date)
        
        print(f"\n🔍 验证结果:")
        print(f"  数据库中9月25日的记录数: {db_count}")
        print(f"  JSON文件中的记录数: {len(json_posts)}")
        
        if db_count >= len(json_posts):
            print("✅ 数据上传成功！所有记录都已保存到数据库。")
            return True
        elif db_count > 0:
            print(f"⚠️  部分数据上传成功！数据库中已有 {db_count} 条记录，JSON文件中有 {len(json_posts)} 条记录。")
            return True
        else:
            print("❌ 数据上传失败！数据库中没有找到9月25日的记录。")
            return False
        
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

async def main():
    print("=== 上传9月25日数据到数据库 ===")
    success = await upload_0925_data()
    
    if success:
        print("\n🎉 9月25日数据上传完成！")
    else:
        print("\n💥 9月25日数据上传失败！")

if __name__ == "__main__":
    asyncio.run(main())
