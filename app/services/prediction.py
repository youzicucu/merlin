import joblib
import os
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.database import Team, TeamStats
from app.utils.team_matching import get_team_matcher
from app.core.logging import logger

class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.model = self._load_model()
        self.team_matcher = get_team_matcher(db)
        
    def _load_model(self):
        """加载预测模型"""
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "football_model.pkl")
        try:
            model = joblib.load(model_path)
            logger.info("✅ 模型加载成功")
            return model
        except Exception as e:
            logger.error(f"❌ 模型加载失败: {str(e)}")
            return None
            
    def get_team_stats(self, team_id: int, is_home: bool):
        """获取球队统计数据"""
        try:
            stats = self.db.execute(
                select(TeamStats).where(TeamStats.team_id == team_id)
            ).scalar_one_or_none()
            
            if not stats:
                logger.warning(f"未找到球队统计数据 (ID: {team_id})")
                return {
                    'avg_goals': 0.0,
                    'win_rate': 0.0
                }
            
            if is_home:
                return {
                    'avg_goals': stats.avg_goals_home,
                    'win_rate': stats.win_rate_home
                }
            else:
                return {
                    'avg_goals': stats.avg_goals_away,
                    'win_rate': stats.win_rate_away
                }
                
        except Exception as e:
            logger.error(f"获取球队统计数据失败: {str(e)}")
            return {
                'avg_goals': 0.0,
                'win_rate': 0.0
            }
            
    def predict_match(self, home_team_name: str, away_team_name: str):
        """预测比赛结果"""
        if not self.model:
            logger.error("预测模型未加载")
            raise ValueError("预测模型未加载，无法进行预测")
            
        # 匹配球队
        home_team = self.team_matcher.match_team(home_team_name)
        away_team = self.team_matcher.match_team(away_team_name)
        
        if not home_team:
            raise ValueError(f"未找到主队: {home_team_name}")
        if not away_team:
            raise ValueError(f"未找到客队: {away_team_name}")
            
        # 获取统计数据
        home_stats = self.get_team_stats(home_team.id, True)
        away_stats = self.get_team_stats(away_team.id, False)
        
        # 准备模型输入
        features = np.array([[
            home_stats['avg_goals'],
            away_stats['avg_goals'],
            home_stats['win_rate']
        ]])
        
        # 预测
        prediction = self.model.predict(features)[0]
        
        # 准备概率(如果模型支持)
        probabilities = {}
        if hasattr(self.model, 'predict_proba'):
            proba = self.model.predict_proba(features)[0]
            class_labels = self.model.classes_
            probabilities = {label: float(prob) for label, prob in zip(class_labels, proba)}
        
        # 构建结果
        result = {
            "prediction": prediction,
            "features": {
                "home_team": home_team.name,
                "away_team": away_team.name,
                "home_avg_goals": home_stats['avg_goals'],
                "away_avg_goals": away_stats['avg_goals'],
                "home_win_rate": home_stats['win_rate'],
                "away_win_rate": 0.0  # 当前模型未使用
            }
        }
        
        if probabilities:
            result["probabilities"] = probabilities
            
        logger.info(f"预测结果: {home_team.name} vs {away_team.name} -> {prediction}")
        return result

# 创建预测服务实例
def get_prediction_service(db: Session):
    return PredictionService(db)
