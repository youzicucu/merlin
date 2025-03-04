from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

from app.core.config import settings
from app.core.logging import logger

Base = declarative_base()

class Team(Base):
    __tablename__ = 'teams'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    official_name = Column(String(100))
    zh_name = Column(String(100))
    aliases = Column(JSON)
    league = Column(String(50))
    country = Column(String(50))
    logo_url = Column(String(255))
    source = Column(String(20))
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class TeamStats(Base):
    __tablename__ = 'team_stats'
    
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer)
    avg_goals_home = Column(Float, default=0.0)
    avg_goals_away = Column(Float, default=0.0) 
    win_rate_home = Column(Float, default=0.0)
    win_rate_away = Column(Float, default=0.0)
    total_matches = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class Match(Base):
    __tablename__ = 'matches'
    
    id = Column(Integer, primary_key=True)
    match_id = Column(String(50), unique=True)
    home_team_id = Column(Integer)
    away_team_id = Column(Integer)
    home_goals = Column(Integer)
    away_goals = Column(Integer)
    status = Column(String(20))
    date = Column(DateTime)
    competition = Column(String(50))
    source = Column(String(20))
    details = Column(JSON, nullable=True)

# 数据库连接和会话
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 显式创建数据库表
def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建完成")
    except Exception as e:
        logger.error(f"数据库表创建失败: {str(e)}")

# 检查表是否存在
def check_tables_exist():
    inspector = inspect(engine)
    tables = ['teams', 'team_stats', 'matches']
    missing_tables = [table for table in tables if not inspector.has_table(table)]
    return len(missing_tables) == 0

# 确保所有表存在
def init_db():
    try:
        # 检查表是否存在，不存在则创建
        if not check_tables_exist():
            create_tables()
        else:
            logger.info("数据库表已存在")
        
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        # 如果出错，尝试强制创建表
        create_tables()

# 获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 获取数据库引擎
def get_engine():
    return engine