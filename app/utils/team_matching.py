from fuzzywuzzy import fuzz
from sqlalchemy import select, or_
import pandas as pd
from sqlalchemy.orm import Session
import json

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
    
    def _get_aliases_list(self, aliases_data):
        """将别名数据转换为列表，无论其原始格式如何"""
        if not aliases_data:
            return []
            
        if isinstance(aliases_data, list):
            return aliases_data
            
        if isinstance(aliases_data, str):
            # 尝试解析JSON
            try:
                parsed = json.loads(aliases_data)
                if isinstance(parsed, list):
                    return parsed
                return [aliases_data]  # 如果不是列表，就当作单一字符串
            except json.JSONDecodeError:
                # 不是JSON，尝试按顿号分割
                return aliases_data.split('、')
                
        # 其他情况，尝试转换为字符串后按顿号分割
        try:
            return str(aliases_data).split('、')
        except:
            logger.warning(f"无法处理的别名格式: {type(aliases_data)} - {aliases_data}")
            return []
            
    def match_team(self, query_name: str, threshold: int = 65):
        """根据查询名称匹配最佳球队"""
        original_query = query_name
        query_name = query_name.strip()
        # 对英文名称转小写，保留中文原样
        query_name_lower = query_name.lower()
        
        logger.debug(f"尝试匹配球队名称: {query_name}")
        
        # 首先尝试精确匹配
        for team in self.teams:
            # 检查名称匹配 (英文用小写比较)
            if team.name and team.name.lower() == query_name_lower:
                logger.info(f"精确匹配到球队名称: {query_name} -> {team.name}")
                return team
                
            # 检查中文名匹配 (中文直接比较，不转小写)
            if team.zh_name and (team.zh_name == query_name):
                logger.info(f"精确匹配到中文名称: {query_name} -> {team.name} (中文名: {team.zh_name})")
                return team
                
            # 检查别名匹配
            if team.aliases:
                aliases_list = self._get_aliases_list(team.aliases)
                for alias in aliases_list:
                    if isinstance(alias, str) and (alias == query_name):
                        logger.info(f"精确匹配到别名: {query_name} -> {team.name} (别名: {alias})")
                        return team
        
        # 尝试退回到搜索API使用的数据库搜索方法
        logger.info(f"精确匹配失败，尝试数据库搜索: {original_query}")
        db_results = self.search_in_db(original_query)
        if db_results and len(db_results) > 0:
            best_match = db_results[0]
            logger.info(f"数据库搜索匹配到球队: {original_query} -> {best_match.name}")
            return best_match
        
        # 如果没有精确匹配，尝试模糊匹配
        best_score = 0
        best_match = None
        
        for team in self.teams:
            # 检查各种名称形式
            name_forms = []
            if team.name:
                name_forms.append(team.name)
            if team.zh_name:
                name_forms.append(team.zh_name)
            if team.official_name:
                name_forms.append(team.official_name)
            if team.aliases:
                name_forms.extend(self._get_aliases_list(team.aliases))
                
            # 计算每种形式的匹配分数
            for name in name_forms:
                if not name or not isinstance(name, str):
                    continue
                score = fuzz.ratio(query_name, name.lower())
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = team
                    logger.debug(f"找到更好的匹配: {query_name} -> {name} (得分: {score})")
        
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