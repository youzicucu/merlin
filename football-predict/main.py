import uvicorn
import asyncio
from app import app
from app.data.sync import run_sync
from app.core.logging import logger
from app.data.database import init_db  # 添加导入

async def startup():
    """应用启动任务"""
    try:
        # 先初始化数据库
        init_db()  # 添加这一行初始化数据库
        
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