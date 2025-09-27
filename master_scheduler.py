# master_scheduler.py - 主调度脚本
import subprocess
import sys
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('master_scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_script(script_path, working_dir):
    """运行指定的脚本"""
    try:
        logger.info(f"开始运行: {script_path}")
        result = subprocess.run([
            sys.executable, script_path
        ], cwd=working_dir, capture_output=True, text=True, timeout=1800)  # 30分钟超时
        
        if result.returncode == 0:
            logger.info(f"✅ {script_path} 执行成功")
            return True
        else:
            logger.error(f"❌ {script_path} 执行失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"⏰ {script_path} 执行超时")
        return False
    except Exception as e:
        logger.error(f"💥 {script_path} 执行异常: {e}")
        return False

def main():
    """主调度函数"""
    logger.info("=== 开始执行主调度任务 ===")
    
    # 定义要运行的脚本
    scripts = [
        {
            "name": "Linux.do 爬虫",
            "script": "scripts/scraper.py",
            "working_dir": "linuxdo"
        },
        {
            "name": "Reddit 爬虫", 
            "script": "reddit_scraper.py",
            "working_dir": "reddit_scraper"
        }
    ]
    
    success_count = 0
    total_count = len(scripts)
    
    for script_info in scripts:
        logger.info(f"--- 执行 {script_info['name']} ---")
        success = run_script(script_info['script'], script_info['working_dir'])
        if success:
            success_count += 1
    
    logger.info(f"=== 调度任务完成 ===")
    logger.info(f"成功: {success_count}/{total_count}")
    
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    if not success:
        logger.error("主调度任务执行失败")
        sys.exit(1)
    else:
        logger.info("主调度任务执行成功")
