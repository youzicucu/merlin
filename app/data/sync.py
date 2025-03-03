import requests
import asyncio
import datetime
import json
from sqlalchemy.orm import Session
from sqlalchemy import select, update, insert
from sqlalchemy.exc import IntegrityError  # 新增导入

from app.data.database import Team, TeamStats, Match, get_db
from app.core.config import settings
from app.core.logging import logger

# ======== 数据同步逻辑 ========
async def sync_football_data_teams(db: Session):
    try:
        url = f"{settings.FOOTBALL_DATA_URL}/teams"
        response = requests.get(url, headers=settings.FOOTBALL_DATA_HEADERS)
        
        if response.status_code != 200:
            logger.error(f"Football Data API 请求失败: {response.status_code}")
            return []
            
        teams_data = response.json().get('teams', [])
        result = []
        
        for team in teams_data:
            team_data = {
                'id': team['id'],
                'name': team['name'],
                'official_name': team.get('shortName', team['name']),
                'country': team.get('area', {}).get('name', 'Unknown'),
                'source': 'football-data',
                'last_updated': datetime.datetime.utcnow()
            }
            
            # 修改: 使用SQLite兼容的upsert方法
            try:
                # 尝试查找现有记录
                existing_team = db.execute(
                    select(Team).where(Team.id == team_data['id'])
                ).scalar_one_or_none()
                
                if existing_team:
                    # 如果存在，更新记录
                    for key, value in team_data.items():
                        setattr(existing_team, key, value)
                else:
                    # 如果不存在，创建新记录
                    new_team = Team(**team_data)
                    db.add(new_team)
                
                result.append(team_data)
            except Exception as e:
                logger.error(f"处理球队 {team_data['name']} 时出错: {str(e)}")
            
        db.commit()
        logger.info(f"从 Football Data API 同步了 {len(result)} 支球队")
        return result
        
    except Exception as e:
        db.rollback()
        logger.error(f"同步 Football Data 球队时出错: {str(e)}")
        return []

async def sync_api_football_teams(db: Session):
    try:
        url = f"{settings.API_FOOTBALL_URL}/teams"
        leagues = ["39", "140", "78", "135", "61"]  # 英超、西甲、德甲、意甲、法甲
        
        all_teams = []
        for league in leagues:
            response = requests.get(
                url, 
                headers=settings.API_FOOTBALL_HEADERS,
                params={'league': league}
            )
            
            if response.status_code != 200:
                logger.warning(f"API Football 请求失败 (联赛ID {league}): {response.status_code}")
                continue
                
            teams_data = response.json().get('response', [])
            
            for item in teams_data:
                team = item.get('team', {})
                team_data = {
                    'id': 100000 + team['id'],  # 添加偏移避免ID冲突
                    'name': team['name'],
                    'official_name': team.get('name', ''),
                    'country': team.get('country', 'Unknown'),
                    'logo_url': team.get('logo', ''),
                    'league': str(league),
                    'source': 'api-football',
                    'last_updated': datetime.datetime.utcnow()
                }
                
                # 修改: 使用SQLite兼容的upsert方法
                try:
                    # 尝试查找现有记录
                    existing_team = db.execute(
                        select(Team).where(Team.id == team_data['id'])
                    ).scalar_one_or_none()
                    
                    if existing_team:
                        # 如果存在，更新记录
                        for key, value in team_data.items():
                            setattr(existing_team, key, value)
                    else:
                        # 如果不存在，创建新记录
                        new_team = Team(**team_data)
                        db.add(new_team)
                    
                    all_teams.append(team_data)
                except Exception as e:
                    logger.error(f"处理球队 {team_data['name']} 时出错: {str(e)}")
            
            # 避免API速率限制
            await asyncio.sleep(1)
        
        db.commit()
        logger.info(f"从 API Football 同步了 {len(all_teams)} 支球队")
        return all_teams
        
    except Exception as e:
        db.rollback()
        logger.error(f"同步 API Football 球队时出错: {str(e)}")
        return []

async def sync_matches(db: Session):
    """同步最近的比赛数据"""
    try:
        # 设置日期范围
        today = datetime.datetime.now()
        start_date = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = today.strftime('%Y-%m-%d')
        
        url = f"{settings.FOOTBALL_DATA_URL}/matches"
        response = requests.get(
            url, 
            headers=settings.FOOTBALL_DATA_HEADERS,
            params={
                'dateFrom': start_date,
                'dateTo': end_date
            }
        )
        
        if response.status_code != 200:
            logger.error(f"获取比赛数据失败: {response.status_code}")
            return
            
        matches_data = response.json().get('matches', [])
        for match in matches_data:
            if match['status'] != 'FINISHED':
                continue
                
            match_data = {
                'match_id': str(match['id']),
                'home_team_id': match['homeTeam']['id'],
                'away_team_id': match['awayTeam']['id'],
                'home_goals': match['score']['fullTime']['home'],
                'away_goals': match['score']['fullTime']['away'],
                'status': match['status'],
                'date': datetime.datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00')),
                'competition': match.get('competition', {}).get('name', 'Unknown'),
                'source': 'football-data',
                'details': json.dumps({
                    'matchday': match.get('matchday', None),
                    'stage': match.get('stage', None)
                })
            }
            
            # 修改: 使用SQLite兼容的upsert方法
            try:
                # 尝试查找现有记录
                existing_match = db.execute(
                    select(Match).where(Match.match_id == match_data['match_id'])
                ).scalar_one_or_none()
                
                if existing_match:
                    # 如果存在，更新记录
                    for key, value in match_data.items():
                        setattr(existing_match, key, value)
                else:
                    # 如果不存在，创建新记录
                    new_match = Match(**match_data)
                    db.add(new_match)
            except Exception as e:
                logger.error(f"处理比赛 {match_data['match_id']} 时出错: {str(e)}")
            
        db.commit()
        logger.info(f"同步了 {len(matches_data)} 场比赛")
        
    except Exception as e:
        db.rollback()
        logger.error(f"同步比赛数据时出错: {str(e)}")

async def update_team_stats(db: Session):
    """更新球队统计数据"""
    try:
        # 获取所有球队
        teams = db.execute(select(Team)).scalars().all()
        
        for team in teams:
            # 主场比赛
            home_matches = db.execute(
                select(Match).where(
                    Match.home_team_id == team.id,
                    Match.status == 'FINISHED'
                ).order_by(Match.date.desc()).limit(10)
            ).scalars().all()
            
            # 客场比赛
            away_matches = db.execute(
                select(Match).where(
                    Match.away_team_id == team.id,
                    Match.status == 'FINISHED'
                ).order_by(Match.date.desc()).limit(10)
            ).scalars().all()
            
            # 计算统计数据
            home_goals = sum([m.home_goals for m in home_matches if m.home_goals is not None])
            away_goals = sum([m.away_goals for m in away_matches if m.away_goals is not None])
            
            home_wins = sum([1 for m in home_matches if m.home_goals is not None and m.away_goals is not None and m.home_goals > m.away_goals])
            away_wins = sum([1 for m in away_matches if m.home_goals is not None and m.away_goals is not None and m.away_goals > m.home_goals])
            
            total_home = len(home_matches)
            total_away = len(away_matches)
            
            # 准备数据
            stats_data = {
                'team_id': team.id,
                'avg_goals_home': round(home_goals / max(total_home, 1), 2),
                'avg_goals_away': round(away_goals / max(total_away, 1), 2),
                'win_rate_home': round(home_wins / max(total_home, 1), 2),
                'win_rate_away': round(away_wins / max(total_away, 1), 2),
                'total_matches': total_home + total_away,
                'last_updated': datetime.datetime.utcnow()
            }
            
            # 修改: 使用SQLite兼容的upsert方法
            try:
                # 尝试查找现有记录
                existing_stats = db.execute(
                    select(TeamStats).where(TeamStats.team_id == stats_data['team_id'])
                ).scalar_one_or_none()
                
                if existing_stats:
                    # 如果存在，更新记录
                    for key, value in stats_data.items():
                        setattr(existing_stats, key, value)
                else:
                    # 如果不存在，创建新记录
                    new_stats = TeamStats(**stats_data)
                    db.add(new_stats)
            except Exception as e:
                logger.error(f"处理球队 {team.id} 统计数据时出错: {str(e)}")
            
        db.commit()
        logger.info(f"更新了 {len(teams)} 支球队的统计数据")
        
    except Exception as e:
        db.rollback()
        logger.error(f"更新球队统计数据时出错: {str(e)}")

async def update_team_aliases(db: Session):
    """更新球队别名"""
    try:
        # 读取现有别名文件
        import pandas as pd
        from pathlib import Path
        
        aliases_path = Path("data/team_aliases.csv")
        if aliases_path.exists():
            df = pd.read_csv(aliases_path)
            
            for _, row in df.iterrows():
                if pd.notna(row.get('id')) and pd.notna(row.get('zh_name')):
                    # 更新数据库
                    team_id = int(row['id'])
                    stmt = update(Team).where(Team.id == team_id).values(
                        zh_name=row['zh_name'],
                        aliases=row.get('aliases', '').split('、') if pd.notna(row.get('aliases')) else []
                    )
                    db.execute(stmt)
            
            db.commit()
            logger.info(f"从CSV文件更新了球队别名")
            
        # 导出最新球队数据到CSV
        teams = db.execute(select(Team)).scalars().all()
        
        teams_data = []
        for team in teams:
            teams_data.append({
                'id': team.id,
                'en_name': team.name,
                'zh_name': team.zh_name or '',
                'aliases': '、'.join(team.aliases) if team.aliases else '',
                'country': team.country or '',
                'source': team.source or ''
            })
            
        df_out = pd.DataFrame(teams_data)
        df_out.to_csv(aliases_path, index=False, encoding='utf-8-sig')
        logger.info(f"已导出 {len(teams_data)} 支球队数据到CSV文件")
        
    except Exception as e:
        db.rollback()
        logger.error(f"更新球队别名时出错: {str(e)}")

async def run_sync():
    """运行完整同步流程"""
    logger.info("开始数据同步...")
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 1. 同步球队数据
        await sync_football_data_teams(db)
        await sync_api_football_teams(db)
        
        # 2. 同步比赛数据
        await sync_matches(db)
        
        # 3. 更新统计数据
        await update_team_stats(db)
        
        # 4. 更新别名
        await update_team_aliases(db)
        
        logger.info("数据同步完成")
    except Exception as e:
        logger.error(f"数据同步过程中出错: {str(e)}")
    finally:
        db.close()