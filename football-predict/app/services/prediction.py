# app/services/prediction.py
import logging
import pickle
import json
import pandas as pd
from app.data.database import get_db_connection
from app.utils.team_matching import match_team_names

logger = logging.getLogger(__name__)

class PredictionService:
    def __init__(self, model_path='models/football_model.pkl'):
        try:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            self.conn = get_db_connection()
            logger.info(f"Prediction model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Error loading prediction model: {e}")
            self.model = None
    
    def get_team_features(self, team_id=None, team_name=None):
        """从多个数据源获取球队特征"""
        if not team_id and not team_name:
            return None
            
        cursor = self.conn.cursor()
        
        if team_id:
            cursor.execute("SELECT stats_data FROM team_stats WHERE team_id = ?", (team_id,))
        else:
            # 尝试匹配名称
            matched_name = match_team_names(team_name)
            cursor.execute("SELECT stats_data FROM team_stats WHERE team_name = ?", (matched_name,))
            
        result = cursor.fetchone()
        if not result:
            logger.warning(f"No stats found for team: {team_name or team_id}")
            return None
            
        # 解析JSON数据
        try:
            stats_data = json.loads(result[0])
        except:
            logger.error(f"Error parsing stats data for team: {team_name or team_id}")
            return None
        
        # 处理和提取关键特征
        features = {}
        
        # 处理API数据
        if 'api_stats' in stats_data and stats_data['api_stats']:
            api_data = stats_data['api_stats']
            features['form'] = api_data.get('form', '')
            features['wins'] = api_data.get('won', 0)
            features['draws'] = api_data.get('draw', 0)
            features['losses'] = api_data.get('lost', 0)
        
        # 处理SoccerStats数据
        if 'soccerstats' in stats_data and stats_data['soccerstats']:
            ss_data = stats_data['soccerstats']
            features['avg_goals_scored'] = ss_data.get('avg_goals_scored', 0)
            features['avg_goals_conceded'] = ss_data.get('avg_goals_conceded', 0)
            features['clean_sheets'] = ss_data.get('clean_sheets', 0)
        
        # 处理FBref数据
        if 'fbref' in stats_data and stats_data['fbref']:
            fb_data = stats_data['fbref']
            if 'shooting' in fb_data:
                features['shots_per_game'] = fb_data['shooting'][0].get('Sh/90', 0) if fb_data['shooting'] else 0
                features['shots_on_target'] = fb_data['shooting'][0].get('SoT/90', 0) if fb_data['shooting'] else 0
            if 'passing' in fb_data:
                features['pass_completion'] = fb_data['passing'][0].get('Cmp%', 0) if fb_data['passing'] else 0
        
        return features
    
    def prepare_match_features(self, home_team, away_team):
        """准备比赛特征数据用于预测"""
        home_features = self.get_team_features(team_name=home_team)
        away_features = self.get_team_features(team_name=away_team)
        
        if not home_features or not away_features:
            logger.error(f"Missing features for {home_team} vs {away_team}")
            return None
        
        # 组合特征
        match_features = {
            'home_wins': home_features.get('wins', 0),
            'home_draws': home_features.get('draws', 0), 
            'home_losses': home_features.get('losses', 0),
            'home_avg_goals': home_features.get('avg_goals_scored', 0),
            'home_avg_conceded': home_features.get('avg_goals_conceded', 0),
            'home_shots_pg': home_features.get('shots_per_game', 0),
            'away_wins': away_features.get('wins', 0),
            'away_draws': away_features.get('draws', 0),
            'away_losses': away_features.get('losses', 0),
            'away_avg_goals': away_features.get('avg_goals_scored', 0),
            'away_avg_conceded': away_features.get('avg_goals_conceded', 0),
            'away_shots_pg': away_features.get('shots_per_game', 0),
        }
        
        return pd.DataFrame([match_features])
    
    def predict_match(self, home_team, away_team):
        """预测比赛结果"""
        if not self.model:
            return {
                'error': 'Model not loaded'
            }
        
        try:
            features = self.prepare_match_features(home_team, away_team)
            if features is None:
                return {
                    'error': f'Could not find team data for {home_team} or {away_team}'
                }
            
            # 使用模型进行预测
            prediction = self.model.predict_proba(features)[0]
            
            # 存储预测结果
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO predictions 
                (home_team, away_team, home_win_prob, draw_prob, away_win_prob, predicted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    home_team, away_team, 
                    prediction[0], prediction[1], prediction[2],
                    datetime.now().isoformat()
                )
            )
            self.conn.commit()
            
            return {
                'home_win_probability': round(prediction[0] * 100, 2),
                'draw_probability': round(prediction[1] * 100, 2),
                'away_win_probability': round(prediction[2] * 100, 2),
                'home_team': home_team,
                'away_team': away_team
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                'error': f'Prediction failed: {str(e)}'
            }