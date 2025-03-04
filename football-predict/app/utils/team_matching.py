from fuzzywuzzy import fuzz
from sqlalchemy import select, or_
import pandas as pd
from sqlalchemy.orm import Session
import json
import os
import csv
from datetime import datetime

from app.data.database import Team
from app.core.logging import logger

class TeamMatcher:
    def __init__(self, db: Session):
        self.db = db
        self.load_teams()
        # 添加内存缓存，避免重复查询
        self.match_cache = {}
        # 添加别名记忆功能，记住成功的匹配
        self.learned_aliases = {}
        # 跟踪匹配成功率统计
        self.stats = {
            'total_queries': 0,
            'exact_matches': 0,
            'fuzzy_matches': 0,
            'cache_hits': 0,
            'failed_matches': 0
        }
        
    def load_teams(self):
        try:
            # 从数据库加载所有球队
            teams = self.db.execute(select(Team)).scalars().all()
            self.teams = teams
            logger.info(f"加载了 {len(teams)} 支球队信息")
            
            # 构建名称到ID的映射，用于快速查找
            self.name_to_id = {}
            for team in teams:
                # 添加各种名称形式
                if team.name:
                    self.name_to_id[team.name.lower()] = team.id
                if team.zh_name:
                    self.name_to_id[team.zh_name] = team.id
                if team.official_name:
                    self.name_to_id[team.official_name.lower()] = team.id
                # 添加别名
                if team.aliases:
                    aliases_list = self._get_aliases_list(team.aliases)
                    for alias in aliases_list:
                        if isinstance(alias, str) and alias:
                            self.name_to_id[alias.lower()] = team.id
            
            logger.info(f"构建了 {len(self.name_to_id)} 个名称映射")
            
            # 加载学习过的别名
            self._load_learned_aliases()
            
        except Exception as e:
            logger.error(f"从数据库加载球队信息失败: {str(e)}")
            self.teams = []
            self.name_to_id = {}
    
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
    
    def _normalize_team_name(self, name):
        """规范化球队名称"""
        if not name or not isinstance(name, str):
            return ""
            
        # 基本清理
        normalized = name.strip()
        
        # 常见数据源差异处理
        replacements = {
            # 英文名称常见变体
            "FC": "",
            "Football Club": "",
            "United": "Utd",
            # 中英文混合情况
            "足球俱乐部": "",
            "联": ""
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        # 移除多余空格
        normalized = " ".join(normalized.split())
        
        return normalized
            
    def match_team(self, query_name: str, threshold: int = 65, source: str = None):
        """根据查询名称匹配最佳球队"""
        self.stats['total_queries'] += 1
        
        if not query_name:
            self.stats['failed_matches'] += 1
            return None
            
        original_query = query_name
        query_name = query_name.strip()
        
        # 检查缓存
        cache_key = f"{query_name}:{source}"
        if cache_key in self.match_cache:
            self.stats['cache_hits'] += 1
            result = self.match_cache[cache_key]
            return result
            
        # 检查学习到的别名
        if query_name.lower() in self.learned_aliases:
            team_id = self.learned_aliases[query_name.lower()]
            for team in self.teams:
                if team.id == team_id:
                    self.match_cache[cache_key] = team
                    self.stats['exact_matches'] += 1
                    return team
        
        # 对英文名称转小写，保留中文原样
        query_name_lower = query_name.lower()
        
        logger.debug(f"尝试匹配球队名称: {query_name} (来源: {source})")
        
        # 首先尝试精确匹配
        for team in self.teams:
            # 检查名称匹配 (英文用小写比较)
            if team.name and team.name.lower() == query_name_lower:
                logger.info(f"精确匹配到球队名称: {query_name} -> {team.name}")
                self.match_cache[cache_key] = team
                self.stats['exact_matches'] += 1
                return team
                
            # 检查中文名匹配 (中文直接比较，不转小写)
            if team.zh_name and (team.zh_name == query_name):
                logger.info(f"精确匹配到中文名称: {query_name} -> {team.name} (中文名: {team.zh_name})")
                self.match_cache[cache_key] = team
                self.stats['exact_matches'] += 1
                return team
                
            # 检查别名匹配
            if team.aliases:
                aliases_list = self._get_aliases_list(team.aliases)
                for alias in aliases_list:
                    if isinstance(alias, str) and (alias.lower() == query_name_lower):
                        logger.info(f"精确匹配到别名: {query_name} -> {team.name} (别名: {alias})")
                        self.match_cache[cache_key] = team
                        self.stats['exact_matches'] += 1
                        return team
        
        # 尝试使用规范化名称精确匹配
        normalized_query = self._normalize_team_name(query_name)
        normalized_query_lower = normalized_query.lower()
        
        if normalized_query_lower:
            for team in self.teams:
                # 规范化团队名称进行比较
                if team.name:
                    normalized_team = self._normalize_team_name(team.name).lower()
                    if normalized_team == normalized_query_lower:
                        logger.info(f"规范化匹配到球队: {query_name} -> {team.name}")
                        # 学习这个新别名
                        self._learn_alias(query_name, team.id)
                        self.match_cache[cache_key] = team
                        self.stats['exact_matches'] += 1
                        return team
        
        # 尝试退回到搜索API使用的数据库搜索方法
        logger.debug(f"精确匹配失败，尝试数据库搜索: {original_query}")
        db_results = self.search_in_db(original_query)
        if db_results and len(db_results) > 0:
            best_match = db_results[0]
            logger.info(f"数据库搜索匹配到球队: {original_query} -> {best_match.name}")
            # 学习这个新别名
            self._learn_alias(query_name, best_match.id)
            self.match_cache[cache_key] = best_match
            self.stats['exact_matches'] += 1
            return best_match
        
        # 如果没有精确匹配，尝试模糊匹配
        best_score = 0
        best_match = None
        
        for team in self.teams:
            # 检查各种名称形式
            name_forms = []
            if team.name:
                name_forms.append(team.name)
                name_forms.append(self._normalize_team_name(team.name))
            if team.zh_name:
                name_forms.append(team.zh_name)
            if team.official_name:
                name_forms.append(team.official_name)
                name_forms.append(self._normalize_team_name(team.official_name))
            if team.aliases:
                name_forms.extend(self._get_aliases_list(team.aliases))
                
            # 计算每种形式的匹配分数
            for name in name_forms:
                if not name or not isinstance(name, str):
                    continue
                    
                # 尝试两种比较方式
                score1 = fuzz.ratio(query_name_lower, name.lower())
                score2 = fuzz.token_sort_ratio(query_name_lower, name.lower())
                score = max(score1, score2)
                
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = team
                    logger.debug(f"找到更好的匹配: {query_name} -> {name} (得分: {score})")
        
        if best_match:
            logger.info(f"模糊匹配到球队: {query_name} -> {best_match.name} (得分: {best_score})")
            # 如果匹配分数非常高，可以学习这个别名
            if best_score >= 85:
                self._learn_alias(query_name, best_match.id)
            self.match_cache[cache_key] = best_match
            self.stats['fuzzy_matches'] += 1
            return best_match
        
        logger.warning(f"未找到匹配球队: {query_name} (来源: {source})")
        # 记录未匹配的名称，以便后续改进
        self._record_unmatched(query_name, source)
        self.match_cache[cache_key] = None
        self.stats['failed_matches'] += 1
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
    
    def _learn_alias(self, alias, team_id):
        """学习新的别名映射"""
        alias_lower = alias.lower()
        if alias_lower not in self.learned_aliases:
            self.learned_aliases[alias_lower] = team_id
            # 保存到文件
            self._save_learned_aliases()
            logger.info(f"学习了新别名映射: {alias} -> {team_id}")
    
    def _load_learned_aliases(self):
        """加载学习过的别名"""
        filename = "data/learned_aliases.csv"
        if not os.path.exists(filename):
            return
            
        try:
            self.learned_aliases = {}
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # 跳过标题行
                for row in reader:
                    if len(row) >= 2:
                        alias, team_id = row[0], int(row[1])
                        self.learned_aliases[alias.lower()] = team_id
            logger.info(f"从文件加载了 {len(self.learned_aliases)} 个学习别名")
        except Exception as e:
            logger.error(f"加载学习别名失败: {str(e)}")
    
    def _save_learned_aliases(self):
        """保存学习过的别名"""
        filename = "data/learned_aliases.csv"
        dir_name = os.path.dirname(filename)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            
        try:
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['alias', 'team_id'])
                for alias, team_id in self.learned_aliases.items():
                    writer.writerow([alias, team_id])
            logger.debug(f"保存了 {len(self.learned_aliases)} 个学习别名到文件")
        except Exception as e:
            logger.error(f"保存学习别名失败: {str(e)}")
    
    def _record_unmatched(self, name, source=None):
        """记录未匹配的名称"""
        filename = "data/unmatched_teams.csv"
        dir_name = os.path.dirname(filename)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
            
        try:
            # 检查文件是否存在，不存在则创建标题行
            file_exists = os.path.exists(filename)
            
            with open(filename, 'a', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['name', 'source', 'timestamp'])
                writer.writerow([name, source or '', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        except Exception as e:
            logger.error(f"记录未匹配名称失败: {str(e)}")
    
    def update_aliases_from_file(self, file_path="data/team_aliases.csv"):
        """从文件更新球队别名"""
        if not os.path.exists(file_path):
            logger.warning(f"别名文件不存在: {file_path}")
            return False
            
        try:
            df = pd.read_csv(file_path)
            updated_count = 0
            
            for _, row in df.iterrows():
                if pd.notna(row.get('id')) and pd.notna(row.get('aliases')):
                    team_id = int(row['id'])
                    aliases = row['aliases'].split('、')
                    
                    # 查找球队
                    for team in self.teams:
                        if team.id == team_id:
                            # 更新别名
                            team.aliases = aliases
                            updated_count += 1
                            
                            # 同时更新数据库
                            self.db.execute(
                                """
                                UPDATE teams 
                                SET aliases = :aliases
                                WHERE id = :id
                                """, 
                                {"aliases": json.dumps(aliases), "id": team_id}
                            )
                            break
            
            self.db.commit()
            logger.info(f"从文件更新了 {updated_count} 支球队的别名")
            
            # 重新加载团队数据以更新内存中的映射
            self.load_teams()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"从文件更新别名失败: {str(e)}")
            return False
    
    def export_aliases_to_file(self, file_path="data/team_aliases.csv"):
        """导出球队别名到文件"""
        try:
            teams_data = []
            for team in self.teams:
                aliases = self._get_aliases_list(team.aliases)
                teams_data.append({
                    'id': team.id,
                    'name': team.name or '',
                    'zh_name': team.zh_name or '',
                    'aliases': '、'.join(aliases) if aliases else '',
                    'country': team.country or '',
                    'source': team.source or '',
                    'league': getattr(team, 'league', '')
                })
                
            df = pd.DataFrame(teams_data)
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"已导出 {len(teams_data)} 支球队数据到CSV文件")
            return True
        except Exception as e:
            logger.error(f"导出别名到文件失败: {str(e)}")
            return False
    
    def get_stats(self):
        """获取匹配统计信息"""
        stats = self.stats.copy()
        if stats['total_queries'] > 0:
            stats['success_rate'] = round(
                (stats['exact_matches'] + stats['fuzzy_matches']) / 
                stats['total_queries'] * 100, 2
            )
            stats['cache_hit_rate'] = round(
                stats['cache_hits'] / stats['total_queries'] * 100, 2
            )
        else:
            stats['success_rate'] = 0
            stats['cache_hit_rate'] = 0
        return stats

# 辅助函数用于创建 TeamMatcher 实例
def get_team_matcher(db: Session):
    return TeamMatcher(db)