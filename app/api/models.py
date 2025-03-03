# app/api/models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

# 创建 Base 对象，用于定义模型
Base = declarative_base()

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    official_name = Column(String)
    zh_name = Column(String, nullable=True)  # 中文名称，可为空
    aliases = Column(String, nullable=True)  # 别名，存储为字符串（如 "Bayern, FCB"）
    league = Column(String, nullable=True)  # 联赛，可为空
    country = Column(String)
    logo_url = Column(String, nullable=True)  # 标志 URL，可为空
    source = Column(String)
    last_updated = Column(DateTime, default=datetime.utcnow)

class TeamStats(Base):
    __tablename__ = "team_stats"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), unique=True, index=True)
    avg_goals_home = Column(Float, default=0.0)
    avg_goals_away = Column(Float, default=0.0)
    win_rate_home = Column(Float, default=0.0)
    win_rate_away = Column(Float, default=0.0)
    total_matches = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Match(Base):
    __tablename__ = "matches"

    match_id = Column(String, primary_key=True, index=True)
    home_team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    home_goals = Column(Integer, nullable=True)
    away_goals = Column(Integer, nullable=True)
    status = Column(String)
    date = Column(DateTime)
    competition = Column(String)
    source = Column(String)
    details = Column(JSON, nullable=True)  # 存储比赛详情为 JSON
    last_updated = Column(DateTime, default=datetime.utcnow)