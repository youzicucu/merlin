# app/data/sources/juhe_football.py
import requests
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class JuheFootballAPI:
    def __init__(self):
        self.base_url = "http://apis.juhe.cn/fapig/football/query"
        self.api_key = settings.JUHE_API_KEY
    
    def get_matches(self, league_id=None, date=None):
        """获取比赛数据"""
        try:
            params = {
                "key": self.api_key
            }
            
            if league_id:
                params['league_id'] = league_id
            if date:
                params['date'] = date
                
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('error_code') == 0:
                return data.get('result', [])
            else:
                logger.error(f"Juhe API error: {data.get('reason')}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching matches from Juhe API: {e}")
            return None
    
    def get_team_info(self, team_id):
        """获取球队信息"""
        try:
            params = {
                "key": self.api_key,
                "team_id": team_id
            }
            
            response = requests.get(
                self.base_url.replace("query", "team"),  # 假设的球队信息接口
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            if data.get('error_code') == 0:
                return data.get('result', {})
            else:
                logger.error(f"Juhe API error: {data.get('reason')}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching team info from Juhe API: {e}")
            return None