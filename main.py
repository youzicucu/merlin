import uvicorn
import asyncio
from app import app
from app.data.sync import run_sync
from app.core.logging import logger

async def startup():
    """应用启动任务"""
    try:
        logger.info("执行初始数据同步...")
        await run_sync()
    except Exception as e:
        logger.error(f"启动任务出错: {str(e)}")

if __name__ == "__main__":
    # 执行初始同步
    asyncio.run(startup())
    
    # 启动应用
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True
    )
