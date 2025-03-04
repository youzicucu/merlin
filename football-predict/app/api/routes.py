# app/api/routes.py
from flask import Blueprint, request, jsonify
from app.services.prediction import PredictionService
import logging

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)
prediction_service = PredictionService()

@api_bp.route('/predict', methods=['POST'])
def predict_match():
    """预测比赛结果API"""
    data = request.json
    
    if not data or 'home_team' not in data or 'away_team' not in data:
        return jsonify({
            'error': 'Missing required parameters: home_team, away_team'
        }), 400
    
    home_team = data['home_team']
    away_team = data['away_team']
    
    logger.info(f"Prediction request for: {home_team} vs {away_team}")
    result = prediction_service.predict_match(home_team, away_team)
    
    if 'error' in result:
        return jsonify(result), 400
        
    return jsonify(result)

@api_bp.route('/matches', methods=['GET'])
def get_upcoming_matches():
    """获取即将到来的比赛"""
    from app.data.database import get_db_connection
    import datetime
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    days = request.args.get('days', 7, type=int)
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    future = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
    
    cursor.execute(
        """
        SELECT m.id, m.home_team, m.away_team, m.match_date, c.name as competition
        FROM matches m
        LEFT JOIN competitions c ON m.competition_id = c.id
        WHERE m.match_date BETWEEN ? AND ?
        ORDER BY m.match_date
        """,
        (today, future)
    )
    
    matches = [{
        'id': row['id'],
        'home_team': row['home_team'],
        'away_team': row['away_team'],
        'date': row['match_date'],
        'competition': row['competition']
    } for row in cursor.fetchall()]
    
    return jsonify({'matches': matches})