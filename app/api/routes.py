from fastapi import APIRouter, Request, HTTPException, Response, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.data.database import get_db
from app.services.prediction import get_prediction_service
from app.core.logging import logger

# 创建路由
router = APIRouter()

# 请求模型
class TeamPredictionRequest(BaseModel):
    home_team: str
    away_team: str

@router.post("/predict/teams")
async def predict_with_teams(data: TeamPredictionRequest, response: Response, db: Session = Depends(get_db)):
    """预测两支球队之间的比赛结果"""
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    
    try:
        logger.info(f"收到预测请求: 主队={data.home_team}, 客队={data.away_team}")
        
        # 获取预测服务
        prediction_service = get_prediction_service(db)
        
        # 执行预测
        result = prediction_service.predict_match(data.home_team, data.away_team)
        
        return result
    except ValueError as e:
        logger.error(f"预测请求参数错误: {str(e)}")
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.error(f"预测失败: {str(e)}")
        raise HTTPException(500, f"预测失败: {str(e)}")

@router.get("/teams/search")
async def search_teams(q: str, db: Session = Depends(get_db)):
    """搜索球队"""
    from app.utils.team_matching import get_team_matcher
    
    try:
        if not q or len(q) < 2:
            return {"teams": []}
            
        team_matcher = get_team_matcher(db)
        teams = team_matcher.search_in_
@router.get("/teams/search")
async def search_teams(q: str, db: Session = Depends(get_db)):
    """搜索球队"""
    from app.utils.team_matching import get_team_matcher
    
    try:
        if not q or len(q) < 2:
            return {"teams": []}
            
        team_matcher = get_team_matcher(db)
        teams = team_matcher.search_in_db(q)
        
        result = [
            {
                "id": team.id,
                "name": team.name,
                "zh_name": team.zh_name,
                "country": team.country
            }
            for team in teams
        ]
        
        return {"teams": result}
    except Exception as e:
        logger.error(f"搜索球队失败: {str(e)}")
        raise HTTPException(500, f"搜索失败: {str(e)}")

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "service": "football-prediction-api"}
