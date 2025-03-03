import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# 加载环境变量
load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "智能足球预测系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    # API Keys
    FOOTBALL_DATA_API_KEY: str = os.getenv("FOOTBALL_DATA_API_KEY", "")
    API_FOOTBALL_KEY: str = os.getenv("API_FOOTBALL_KEY", "")
    
    # API URLs
    FOOTBALL_DATA_URL: str = "https://api.football-data.org/v4"
    API_FOOTBALL_URL: str = "https://v3.football.api-sports.io"
    
    # 数据库设置
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/football.db")
    
    # 缓存设置
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 默认1小时
    CACHE_MAXSIZE: int = int(os.getenv("CACHE_MAXSIZE", "100"))
    
    # 同步设置
    SYNC_CRON_HOUR: int = int(os.getenv("SYNC_CRON_HOUR", "3"))
    SYNC_CRON_MINUTE: int = int(os.getenv("SYNC_CRON_MINUTE", "0"))
    
    # API 头信息
    @property
    def FOOTBALL_DATA_HEADERS(self):
        return {"X-Auth-Token": self.FOOTBALL_DATA_API_KEY}
    
    @property
    def API_FOOTBALL_HEADERS(self):
        return {"x-apisports-key": self.API_FOOTBALL_KEY}

# 全局设置实例
settings = Settings()
