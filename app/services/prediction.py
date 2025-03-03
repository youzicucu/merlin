import joblib
import os
import numpy as np
import pickle
from sqlalchemy import select
from sqlalchemy.orm import Session
from sklearn.ensemble import RandomForestClassifier

from app.data.database import Team, TeamStats
from app.utils.team_matching import get_team_matcher
from app.core.logging import logger

def create_default_model(save_path=None):
    """创建一个简单的默认预测模型"""
    logger.warning("创建默认预测模型...")
    model = RandomForestClassifier(n_estimators=10)
    
    # 使用一些假数据拟合模型
    X = np.array([[1.5, 1.0, 0.6], [1.2, 1.8, 0.4], [2.0, 0.8, 0.7]])
    y = np.array(['win', 'lose', 'draw'])
    model.fit(X, y)
    
    # 如果提供了保存路径，则保存模型
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            pickle.dump(model, f)
        logger.info(f"默认模型已保存至 {save_path}")
    
    return model

class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.model = self._load_model()
        self.team_matcher = get_team_matcher(db)
        
    def _load_model(self):
        """加载预测模型，尝试多个路径，如果失败则创建默认模型"""
        # 尝试多个可能的路径
        possible_paths = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "football_model.pkl"),
            "models/football_model.pkl",
            "/opt/render/project/src/models/football_model.pkl"
        ]
        
        for path in possible_paths:
            try:
                if os.path.exists(path):
                    logger.info(f"找到模型文件: {path}")
                    model = joblib.load(path)
                    logger.info("✅ 模型加载成功")
                    return model
            except Exception as e:
                logger.warning(f"尝试从 {path} 加载模型失败: {str(e)}")
        
        # 如果所有路径都失败，记录目录信息
        curr_dir = os.getcwd()
        logger.error(f"无法找到模型文件，当前工作目录: {curr_dir}")
        
        try:
            logger.error(f"目录内容: {os.listdir(curr_dir)}")
            if os.path.exists('models'):
                logger.error(f"models目录内容: {os.listdir('models')}")
            else:
                logger.error("models目录不存在!")
        except Exception as e:
            logger.error(f"列出目录内容时出错: {str(e)}")
        
        # 创建并返回默认模型
        logger.warning("创建默认预测模型作为备选方案")
        default_model_path = os.path.join(curr_dir, "models", "football_model.pkl")
        return create_default_model(default_model_path)
            
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
            probabilities = {str(label): float(prob) for label, prob in zip(class_labels, proba)}
        
        # 构建结果
        result = {
            "prediction": str(prediction),
            "features": {
                "home_team": home_team.name,
                "away_team": away_team.name,
                "home_avg_goals": float(home_stats['avg_goals']),
                "away_avg_goals": float(away_stats['avg_goals']),
                "home_win_rate": float(home_stats['win_rate']),
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