# app/core/config.py
import os
from dotenv import load_dotenv

# 加载.env文件中的环境变量
load_dotenv()

class Settings:
    # 原有API密钥
    FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY")
    JUHE_API_KEY = os.getenv("JUHE_API_KEY")
    
    # 数据库路径
    DB_PATH = os.getenv("DB_PATH", "data/football.db")
    
    # 日志设置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # 爬虫设置
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    
    # 是否开启数据抓取功能
    ENABLE_SCRAPING = os.getenv("ENABLE_SCRAPING", "True").lower() in ("true", "1", "t")
    
    # 数据更新频率(小时)
    DATA_UPDATE_INTERVAL = int(os.getenv("DATA_UPDATE_INTERVAL", "12"))

# 创建一个全局可访问的设置对象
settings = Settings()