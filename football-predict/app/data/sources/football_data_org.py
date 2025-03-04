# app/data/sources/football_data.py
import requests
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class FootballDataAPI:
    def __init__(self):
        self.base_url = "https://api.football-data.org/v4"
        self.headers = {
            "X-Auth-Token": settings.FOOTBALL_DATA_API_KEY
        }
    
    def get_competitions(self):
        """获取所有比赛"""
        try:
            response = requests.get(f"{self.base_url}/competitions", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching competitions: {e}")
            return None
    
    def get_matches(self, competition_id, date_from=None, date_to=None):
        """获取指定比赛的赛程"""
        params = {}
        if date_from:
            params['dateFrom'] = date_from
        if date_to:
            params['dateTo'] = date_to
            
        try:
            response = requests.get(
                f"{self.base_url}/competitions/{competition_id}/matches", 
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching matches: {e}")
            return None
    
    def get_team_stats(self, team_id):
        """获取球队统计数据"""
        try:
            response = requests.get(f"{self.base_url}/teams/{team_id}", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching team stats: {e}")
            return None