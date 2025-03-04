# scheduler.py
import schedule
import time
import logging
from app.data.sync import DataSynchronizer
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

def sync_all_data():
    logger.info("Starting data synchronization")
    syncer = DataSynchronizer()
    
    logger.info("Syncing competitions")
    syncer.sync_competitions()
    
    logger.info("Syncing matches")
    syncer.sync_matches()
    
    logger.info("Syncing team stats")
    syncer.sync_team_stats()
    
    logger.info("Data synchronization completed")

if __name__ == "__main__":
    # 每日早上和晚上同步数据
    schedule.every().day.at("07:00").do(sync_all_data)
    schedule.every().day.at("19:00").do(sync_all_data)
    
    # 首次运行立即同步
    sync_all_data()
    
    # 保持运行
    while True:
        schedule.run_pending()
        time.sleep(60)