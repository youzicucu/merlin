# app/data/sources/juhe.py
import requests
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class JuheAPI:
    def __init__(self):
        self.base_url = "http://apis.juhe.cn/fapig/football/query"
        self.key = settings.JUHE_API_KEY
    
    def get_matches(self, league=None, date=None):
        """获取比赛数据"""
        params = {
            "key": self.key
        }
        
        if league:
            params['league'] = league
        if date:
            params['date'] = date
            
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching matches from Juhe: {e}")
            return None
    
    def get_standings(self, league):
        """获取联赛积分榜"""
        standings_url = "http://apis.juhe.cn/fapig/football/standings"
        params = {
            "key": self.key,
            "league": league
        }
        
        try:
            response = requests.get(standings_url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching standings from Juhe: {e}")
            return None