from fuzzywuzzy import fuzz
from sqlalchemy import select, or_
import pandas as pd
from sqlalchemy.orm import Session

from app.data.database import Team
from app.core.logging import logger

class TeamMatcher:
    def __init__(self, db: Session):
        self.db = db
        self.load_teams()
        
    def load_teams(self):
        try:
            # 从数据库加载所有球队
            teams = self.db.execute(select(Team)).scalars().all()
            self.teams = teams
            logger.info(f"加载了 {len(teams)} 支球队信息")
        except Exception as e:
            logger.error(f"从数据库加载球队信息失败: {str(e)}")
            self.teams = []
            
    def match_team(self, query_name: str, threshold: int = 75):
        """根据查询名称匹配最佳球队"""
        query_name = query_name.strip().lower()
        
        # 首先尝试精确匹配
        for team in self.teams:
            # 检查名称匹配
            if team.name.lower() == query_name:
                logger.info(f"精确匹配到球队名称: {query_name} -> {team.name}")
                return team
                
            # 检查中文名匹配
            if team.zh_name and team.zh_name.lower() == query_name:
                logger.info(f"精确匹配到中文名称: {query_name} -> {team.name}")
                return team
                
            # 检查别名匹配
            if team.aliases:
                for alias in team.aliases:
                    if alias.lower() == query_name:
                        logger.info(f"精确匹配到别名: {query_name} -> {team.name}")
                        return team
        
        # 如果没有精确匹配，尝试模糊匹配
        best_score = 0
        best_match = None
        
        for team in self.teams:
            # 检查各种名称形式
            name_forms = [team.name]
            if team.zh_name:
                name_forms.append(team.zh_name)
            if team.official_name:
                name_forms.append(team.official_name)
            if team.aliases:
                name_forms.extend(team.aliases)
                
            # 计算每种形式的匹配分数
            for name in name_forms:
                if not name:
                    continue
                score = fuzz.ratio(query_name, name.lower())
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = team
        
        if best_match:
            logger.info(f"模糊匹配到球队: {query_name} -> {best_match.name} (得分: {best_score})")
            return best_match
        
        logger.warning(f"未找到匹配球队: {query_name}")
        return None
        
    def search_in_db(self, query_name: str):
        """直接在数据库中搜索"""
        try:
            # 准备查询条件
            query_name = f"%{query_name}%"
            
            # 在多个字段中搜索
            stmt = select(Team).where(
                or_(
                    Team.name.ilike(query_name),
                    Team.zh_name.ilike(query_name),
                    Team.official_name.ilike(query_name)
                )
            ).limit(5)
            
            teams = self.db.execute(stmt).scalars().all()
            return teams
        except Exception as e:
            logger.error(f"数据库搜索球队失败: {str(e)}")
            return []

# 辅助函数用于创建 TeamMatcher 实例
def get_team_matcher(db: Session):
    return TeamMatcher(db)
