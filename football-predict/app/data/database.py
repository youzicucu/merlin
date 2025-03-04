# app/data/database.py
import sqlite3
import os
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    db_path = settings.DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 创建联赛表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS competitions (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        country TEXT,
        code TEXT
    )
    ''')
    
    # 创建比赛表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY,
        competition_id INTEGER,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        home_team_id INTEGER,
        away_team_id INTEGER,
        match_date TEXT,
        status TEXT,
        source TEXT DEFAULT 'football-data',
        FOREIGN KEY (competition_id) REFERENCES competitions (id)
    )
    ''')
    
    # 创建球队统计数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS team_stats (
        team_id INTEGER,
        team_name TEXT NOT NULL,
        stats_data TEXT,  # 将存储为JSON字符串
        updated_at TEXT,
        PRIMARY KEY (team_id, team_name)
    )
    ''')
    
    # 创建预测结果表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        home_win_prob REAL,
        draw_prob REAL,
        away_win_prob REAL,
        predicted_at TEXT,
        FOREIGN KEY (match_id) REFERENCES matches (id)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")