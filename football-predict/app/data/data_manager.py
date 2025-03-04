import logging
import pandas as pd
from datetime import datetime
from .database import get_db_connection
from .sources.football_data_org import FootballDataOrgAPI
from .sources.juhe_api import JuheFootballAPI
from .sources.scrapers.soccerstats_scraper import run_soccerstats_scraper
from .sources.scrapers.fbref_scraper import run_fbref_scraper

class DataManager:
    def __init__(self, db_connection):
        self.football_data_api = FootballDataOrgAPI()
        self.juhe_api = JuheFootballAPI()
        self.db_connection = db_connection
        self.logger = logging.getLogger(__name__)
        self.logger.info("数据管理器初始化完成")
    
    def get_official_api_data(self, competition_id, date_from=None, date_to=None):
        """获取官方API数据"""
        self.logger.info(f"开始获取官方API数据: 比赛ID={competition_id}, 日期范围={date_from}至{date_to}")
        
        # 获取football-data.org数据
        data1 = self.football_data_api.get_matches(competition_id, date_from, date_to)
        
        # 获取聚合数据API数据
        data2 = self.juhe_api.get_matches(league_id=competition_id, date=date_from)
        
        # 处理football-data.org数据
        processed_data1 = []
        if data1 and 'matches' in data1:
            for match in data1['matches']:
                try:
                    processed_match = {
                        'match_id': f"fd-{match.get('id')}",
                        'date': match.get('utcDate', '').split('T')[0],
                        'competition': competition_id,
                        'home_team': match.get('homeTeam', {}).get('name'),
                        'away_team': match.get('awayTeam', {}).get('name'),
                        'home_score': match.get('score', {}).get('fullTime', {}).get('home'),
                        'away_score': match.get('score', {}).get('fullTime', {}).get('away'),
                        'status': match.get('status'),
                        'source': 'football-data.org'
                    }
                    processed_data1.append(processed_match)
                except Exception as e:
                    self.logger.error(f"处理football-data.org比赛数据时出错: {str(e)}")
        
        # 处理聚合数据API数据
        processed_data2 = []
        if data2 and isinstance(data2, list):
            for match in data2:
                try:
                    processed_match = {
                        'match_id': f"juhe-{match.get('id')}",
                        'date': match.get('match_date', ''),
                        'competition': match.get('league_name', competition_id),
                        'home_team': match.get('home_team'),
                        'away_team': match.get('away_team'),
                        'home_score': match.get('home_score'),
                        'away_score': match.get('away_score'),
                        'status': match.get('status'),
                        'source': 'juhe'
                    }
                    processed_data2.append(processed_match)
                except Exception as e:
                    self.logger.error(f"处理聚合数据比赛数据时出错: {str(e)}")
        
        # 合并数据
        combined_data = processed_data1 + processed_data2
        self.logger.info(f"共获取到{len(combined_data)}条官方API数据")
        
        return combined_data
    
    def get_scraped_data(self, league):
        """获取Soccerstats爬虫数据"""
        self.logger.info(f"开始获取Soccerstats爬虫数据: 联赛={league}")
        
        # 运行Soccerstats爬虫
        soccerstats_data = run_soccerstats_scraper(league)
        
        # 处理爬虫数据
        processed_data = []
        for match in soccerstats_data:
            try:
                if 'home_team' in match and 'away_team' in match:
                    # 生成唯一ID
                    unique_id = f"ss-{match.get('date', '')}-{match.get('home_team')}-{match.get('away_team')}"
                    match_data = {
                        'match_id': unique_id,
                        'date': match.get('date'),
                        'competition': match.get('league'),
                        'home_team': match.get('home_team'),
                        'away_team': match.get('away_team'),
                        'home_score': match.get('home_score'),
                        'away_score': match.get('away_score'),
                        'status': 'FINISHED' if match.get('home_score') is not None else 'SCHEDULED',
                        'source': 'soccerstats'
                    }
                    processed_data.append(match_data)
            except Exception as e:
                self.logger.error(f"处理Soccerstats数据时出错: {str(e)}")
        
        self.logger.info(f"共获取到{len(processed_data)}条Soccerstats爬虫数据")
        return processed_data
    
    def get_fbref_data(self, league, season=None):
        """获取FBref爬虫数据"""
        self.logger.info(f"开始获取FBref数据: 联赛={league}, 赛季={season}")
        
        # 运行FBref爬虫
        fbref_data = run_fbref_spider(league, season)
        
        # 处理爬虫数据
        processed_data = []
        for match in fbref_data:
            try:
                if 'home_team' in match and 'away_team' in match:
                    # 生成唯一ID
                    unique_id = f"fb-{match.get('date', '')}-{match.get('home_team')}-{match.get('away_team')}"
                    match_data = {
                        'match_id': unique_id,
                        'date': match.get('date'),
                        'competition': match.get('league'),
                        'home_team': match.get('home_team'),
                        'away_team': match.get('away_team'),
                        'home_score': match.get('home_score'),
                        'away_score': match.get('away_score'),
                        'status': 'FINISHED' if match.get('home_score') is not None else 'SCHEDULED',
                        'source': 'fbref'
                    }
                    processed_data.append(match_data)
            except Exception as e:
                self.logger.error(f"处理FBref数据时出错: {str(e)}")
        
        self.logger.info(f"共获取到{len(processed_data)}条FBref数据")
        return processed_data
    
    def update_database(self, data):
        """更新数据库"""
        if not data:
            self.logger.warning("没有数据需要更新到数据库")
            return False
            
        try:
            # 将数据转换为DataFrame
            df = pd.DataFrame(data)
            
            # 使用to_sql方法将数据写入数据库
            # 如果表不存在则创建，如果存在则追加
            df.to_sql('matches', self.db_connection, if_exists='append', index=False)
            
            self.logger.info(f"成功将{len(data)}条数据写入数据库")
            return True
        except Exception as e:
            self.logger.error(f"更新数据库失败: {str(e)}")
            return False
    
    def sync_all_data(self, league_mappings, date_from=None, date_to=None):
        """同步所有数据源的数据"""
        all_data = []
        
        for league_key, ids in league_mappings.items():
            self.logger.info(f"开始获取 {league_key} 联赛数据")
            
            # 1. 获取官方API数据
            if 'football_data' in ids:
                api_data = self.get_official_api_data(ids['football_data'], date_from, date_to)
                if api_data:
                    for match in api_data:
                        match['competition'] = league_key  # 确保统一的联赛标识
                    all_data.extend(api_data)
                    self.logger.info(f"获取到 {len(api_data)} 条 {league_key} 联赛API数据")
        
            # 2. 获取Soccerstats爬虫数据
            if 'soccerstats' in ids:
                ss_data = self.get_scraped_data(ids['soccerstats'])
                if ss_data:
                    for match in ss_data:
                        match['competition'] = league_key  # 确保统一的联赛标识
                    all_data.extend(ss_data)
                    self.logger.info(f"获取到 {len(ss_data)} 条 {league_key} 联赛Soccerstats数据")
        
            # 3. 获取FBref爬虫数据
            if 'fbref' in ids:
                current_year = datetime.now().year
                fb_data = self.get_fbref_data(ids['fbref'], current_year)
                if fb_data:
                    for match in fb_data:
                        match['competition'] = league_key  # 确保统一的联赛标识
                    all_data.extend(fb_data)
                    self.logger.info(f"获取到 {len(fb_data)} 条 {league_key} 联赛FBref数据")
        
        # 数据去重
        unique_data = self._deduplicate_data(all_data)
        self.logger.info(f"去重后共有 {len(unique_data)} 条有效数据")
        
        return unique_data

    def _deduplicate_data(self, data):
        """去除重复数据"""
        if not data:
            return []
            
        # 使用比赛日期+主队+客队作为唯一键
        unique_data = []
        match_keys = set()
        
        for match in data:
            key = f"{match.get('date')}_{match.get('home_team')}_{match.get('away_team')}"
            if key not in match_keys:
                match_keys.add(key)
                unique_data.append(match)
            else:
                # 如果已存在，可能需要合并或选择最可靠的数据源
                for existing_match in unique_data:
                    existing_key = f"{existing_match.get('date')}_{existing_match.get('home_team')}_{existing_match.get('away_team')}"
                    if existing_key == key:
                        # 如果现有数据没有比分但新数据有，则更新比分
                        if (existing_match.get('home_score') is None and 
                            match.get('home_score') is not None):
                            existing_match['home_score'] = match.get('home_score')
                            existing_match['away_score'] = match.get('away_score')
                            existing_match['status'] = 'FINISHED'
                            # 记录数据来源合并
                            existing_match['source'] = f"{existing_match.get('source')}+{match.get('source')}"
                        break
        
        return unique_data
    
    @staticmethod
    def create_instance():
        """创建数据管理器实例的工厂方法"""
        db_connection = get_db_connection()
        return DataManager(db_connection)