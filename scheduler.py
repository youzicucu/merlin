import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.data.sync import run_sync
from app.core.config import settings
from app.core.logging import logger

async def main():
    # 创建异步调度器
    scheduler = AsyncIOScheduler()
    
    # 添加定时同步任务
    scheduler.add_job(
        run_sync,
        'cron',
        hour=settings.SYNC_CRON_HOUR,
        minute=settings.SYNC_CRON_MINUTE,
        id='data_sync'
    )
    
    # 立即执行一次同步
    await run_sync()
    
    # 启动调度器
    scheduler.start()
    logger.info(f"定时任务启动完成，每天 {settings.SYNC_CRON_HOUR}:{settings.SYNC_CRON_MINUTE} 执行数据同步")
    
    try:
        # 保持程序运行
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("定时任务正在关闭...")
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
