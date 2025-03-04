import requests
import asyncio
import datetime
import json
from sqlalchemy.orm import Session
from sqlalchemy import select, update, insert
from sqlalchemy.exc import IntegrityError

from app.data.database import Team, TeamStats, Match, get_db
from app.core.config import settings
from app.core.logging import logger
from app.data.sources.football_data_org import FootballDataOrgAPI
from app.data.sources.juhe_api import JuheFootballAPI
from app.data.sources.scrapers.soccerstats_scraper import run_soccerstats_scraper
from app.data.sources.scrapers.fbref_scraper import run_fbref_scraper

# 定义联赛ID映射(需要根据各数据源的实际ID进行调整)
LEAGUE_MAPPINGS = {
    'PL': {
        'football_data': 'PL', 
        'juhe': '2', 
        'soccerstats': 'england',
        'fbref': '9'  # FBref的英超ID
    },
    'BL1': {
        'football_data': 'BL1', 
        'juhe': '4', 
        'soccerstats': 'germany',
        'fbref': '20'  # FBref的德甲ID
    },
    'SA': {
        'football_data': 'SA', 
        'juhe': '7', 
        'soccerstats': 'italy',
        'fbref': '11'  # FBref的意甲ID
    },
    'PD': {
        'football_data': 'PD', 
        'juhe': '5', 
        'soccerstats': 'spain',
        'fbref': '12'  # FBref的西甲ID
    },
    'FL1': {
        'football_data': 'FL1', 
        'juhe': '3', 
        'soccerstats': 'france',
        'fbref': '13'  # FBref的法甲ID
    }
}

# ======== 数据同步逻辑 ========
async def sync_football_data_teams(db: Session):
    try:
        # 创建football-data.org API客户端
        api = FootballDataOrgAPI()
        
        # 获取每个联赛的球队
        all_teams = []
        for league_key, ids in LEAGUE_MAPPINGS.items():
            # 获取每个联赛ID对应的球队
            competition_id = ids['football_data']
            url = f"{api.base_url}/competitions/{competition_id}/teams"
            
            logger.info(f"从football-data.org获取 {league_key} 联赛球队数据")
            response = requests.get(url, headers=api.headers)
            
            if response.status_code != 200:
                logger.error(f"Football Data API 请求失败: {response.status_code}")
                continue
                
            teams_data = response.json().get('teams', [])
            logger.info(f"获取到 {len(teams_data)} 支 {league_key} 联赛球队")
            
            for team in teams_data:
                team_data = {
                    'id': team['id'],
                    'name': team['name'],
                    'official_name': team.get('shortName', team['name']),
                    'country': team.get('area', {}).get('name', 'Unknown'),
                    'source': 'football-data',
                    'last_updated': datetime.datetime.utcnow(),
                    'league': league_key
                }
                
                # 使用SQLite兼容的upsert方法
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
        logger.info(f"从 Football Data API 同步了 {len(all_teams)} 支球队")
        return all_teams
        
    except Exception as e:
        db.rollback()
        logger.error(f"同步 Football Data 球队时出错: {str(e)}")
        return []

async def sync_juhe_football_teams(db: Session):
    try:
        # 创建聚合数据API客户端
        api = JuheFootballAPI()
        
        # 获取每个联赛的球队
        all_teams = []
        for league_key, ids in LEAGUE_MAPPINGS.items():
            juhe_league_id = ids['juhe']
            
            logger.info(f"从聚合数据获取 {league_key} 联赛球队数据")
            
            # 注意：聚合数据API可能需要特定参数获取球队信息
            # 下面代码假设有获取球队列表的接口，实际需根据API文档调整
            response = requests.get(
                api.base_url.replace("query", "teams"),  # 假设的球队列表API
                params={
                    "key": api.api_key,
                    "league_id": juhe_league_id
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"聚合数据API请求失败 (联赛ID {juhe_league_id}): {response.status_code}")
                continue
                
            data = response.json()
            if data.get("error_code") != 0:
                logger.warning(f"聚合数据API错误: {data.get('reason')}")
                continue
                
            teams_data = data.get('result', [])
            logger.info(f"获取到 {len(teams_data)} 支 {league_key} 联赛球队")
            
            for team in teams_data:
                team_data = {
                    'id': 200000 + int(team.get('team_id', 0)),  # 添加偏移避免ID冲突
                    'name': team.get('name', ''),
                    'official_name': team.get('name', ''),
                    'country': team.get('country', 'Unknown'),
                    'logo_url': team.get('logo', ''),
                    'league': league_key,
                    'source': 'juhe',
                    'last_updated': datetime.datetime.utcnow()
                }
                
                # 使用SQLite兼容的upsert方法
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
        logger.info(f"从聚合数据API同步了 {len(all_teams)} 支球队")
        return all_teams
        
    except Exception as e:
        db.rollback()
        logger.error(f"同步聚合数据球队时出错: {str(e)}")
        return []

async def sync_matches_from_apis(db: Session):
    """从官方API同步最近的比赛数据"""
    try:
        # 创建API客户端
        football_data_api = FootballDataOrgAPI()
        juhe_api = JuheFootballAPI()
        
        # 设置日期范围
        today = datetime.datetime.now()
        start_date = (today - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        end_date = (today + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        
        all_matches = []
        
        # 从football-data.org获取比赛数据
        for league_key, ids in LEAGUE_MAPPINGS.items():
            competition_id = ids['football_data']
            logger.info(f"从football-data.org获取 {league_key} 联赛比赛数据")
            
            data = football_data_api.get_matches(competition_id, start_date, end_date)
            
            if not data or 'matches' not in data:
                logger.warning(f"获取 {league_key} 联赛比赛数据失败")
                continue
                
            matches_data = data['matches']
            logger.info(f"获取到 {len(matches_data)} 场 {league_key} 联赛比赛")
            
            for match in matches_data:
                match_data = {
                    'match_id': str(match['id']),
                    'home_team_id': match['homeTeam']['id'] if 'id' in match['homeTeam'] else None,
                    'away_team_id': match['awayTeam']['id'] if 'id' in match['awayTeam'] else None,
                    'home_goals': match['score']['fullTime']['home'],
                    'away_goals': match['score']['fullTime']['away'],
                    'status': match['status'],
                    'date': datetime.datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00')),
                    'competition': match.get('competition', {}).get('name', league_key),
                    'source': 'football-data',
                    'details': json.dumps({
                        'matchday': match.get('matchday', None),
                        'stage': match.get('stage', None)
                    })
                }
                
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
                        
                    all_matches.append(match_data)
                except Exception as e:
                    logger.error(f"处理比赛 {match_data['match_id']} 时出错: {str(e)}")
            
            # 避免API速率限制
            await asyncio.sleep(1)
            
        # 从聚合数据API获取比赛数据
        for league_key, ids in LEAGUE_MAPPINGS.items():
            juhe_league_id = ids['juhe']
            logger.info(f"从聚合数据获取 {league_key} 联赛比赛数据")
            
            data = juhe_api.get_matches(league_id=juhe_league_id, date=start_date)
            
            if not data:
                logger.warning(f"获取 {league_key} 联赛比赛数据失败")
                continue
                
            for match in data:
                # 为聚合数据API的比赛生成一个唯一ID
                unique_id = f"juhe-{match.get('id', '')}"
                
                match_data = {
                    'match_id': unique_id,
                    # 需要将聚合数据的球队名称映射到自己的ID
                    # 这里使用名称搜索，实际可能需要更复杂的匹配机制
                    'home_team_name': match.get('home_team', ''),
                    'away_team_name': match.get('away_team', ''),
                    'home_goals': match.get('home_score'),
                    'away_goals': match.get('away_score'),
                    'status': match.get('status', ''),
                    'date': datetime.datetime.strptime(match.get('match_date', ''), '%Y-%m-%d'),
                    'competition': league_key,
                    'source': 'juhe',
                    'details': json.dumps({
                        'season': match.get('season', ''),
                        'round': match.get('round', '')
                    })
                }
                
                # 查找球队ID
                home_team = db.execute(
                    select(Team).where(Team.name == match_data['home_team_name'])
                ).scalar_one_or_none()
                
                away_team = db.execute(
                    select(Team).where(Team.name == match_data['away_team_name'])
                ).scalar_one_or_none()
                
                if home_team:
                    match_data['home_team_id'] = home_team.id
                if away_team:
                    match_data['away_team_id'] = away_team.id
                
                try:
                    # 尝试查找现有记录
                    existing_match = db.execute(
                        select(Match).where(Match.match_id == match_data['match_id'])
                    ).scalar_one_or_none()
                    
                    if existing_match:
                        # 如果存在，更新记录
                        for key, value in match_data.items():
                            if key not in ('home_team_name', 'away_team_name'):  # 跳过临时字段
                                setattr(existing_match, key, value)
                    else:
                        # 删除临时字段
                        match_data.pop('home_team_name', None)
                        match_data.pop('away_team_name', None)
                        # 如果不存在，创建新记录
                        new_match = Match(**match_data)
                        db.add(new_match)
                        
                    all_matches.append(match_data)
                except Exception as e:
                    logger.error(f"处理比赛 {match_data['match_id']} 时出错: {str(e)}")
            
            # 避免API速率限制
            await asyncio.sleep(1)
        
        db.commit()
        logger.info(f"从API同步了 {len(all_matches)} 场比赛")
        return all_matches
        
    except Exception as e:
        db.rollback()
        logger.error(f"同步API比赛数据时出错: {str(e)}")
        return []

async def sync_matches_from_scrapers(db: Session):
    """从爬虫同步比赛数据"""
    try:
        all_matches = []
        
        # 从Soccerstats获取比赛数据
        for league_key, ids in LEAGUE_MAPPINGS.items():
            ss_league = ids.get('soccerstats')
            if not ss_league:
                continue
                
            logger.info(f"从Soccerstats获取 {league_key} 联赛比赛数据")
            
            matches_data = run_soccerstats_scraper(ss_league)
            
            if not matches_data:
                logger.warning(f"获取 {league_key} 联赛Soccerstats比赛数据失败")
                continue
                
            logger.info(f"获取到 {len(matches_data)} 场 {league_key} 联赛Soccerstats比赛")
            
            for match in matches_data:
                # 为爬虫数据生成一个唯一ID
                unique_id = f"ss-{match.get('home_team', '')}-{match.get('away_team', '')}-{match.get('date', '')}"
                
                match_data = {
                    'match_id': unique_id,
                    # 需要将爬虫的球队名称映射到自己的ID
                    'home_team_name': match.get('home_team', ''),
                    'away_team_name': match.get('away_team', ''),
                    'home_goals': match.get('home_score'),
                    'away_goals': match.get('away_score'),
                    'status': 'FINISHED' if match.get('home_score') is not None else 'SCHEDULED',
                    'date': datetime.datetime.strptime(match.get('date', ''), '%Y-%m-%d'),
                    'competition': league_key,
                    'source': 'soccerstats',
                    'details': json.dumps({})
                }
                
                # 查找球队ID
                home_team = db.execute(
                    select(Team).where(Team.name == match_data['home_team_name'])
                ).scalar_one_or_none()
                
                away_team = db.execute(
                    select(Team).where(Team.name == match_data['away_team_name'])
                ).scalar_one_or_none()
                
                if home_team:
                    match_data['home_team_id'] = home_team.id
                if away_team:
                    match_data['away_team_id'] = away_team.id
                
                try:
                    # 尝试查找现有记录
                    existing_match = db.execute(
                        select(Match).where(Match.match_id == match_data['match_id'])
                    ).scalar_one_or_none()
                    
                    if existing_match:
                        # 如果存在，更新记录
                        for key, value in match_data.items():
                            if key not in ('home_team_name', 'away_team_name'):  # 跳过临时字段
                                setattr(existing_match, key, value)
                    else:
                        # 删除临时字段
                        match_data.pop('home_team_name', None)
                        match_data.pop('away_team_name', None)
                        # 如果不存在，创建新记录
                        new_match = Match(**match_data)
                        db.add(new_match)
                        
                    all_matches.append(match_data)
                except Exception as e:
                    logger.error(f"处理比赛 {match_data['match_id']} 时出错: {str(e)}")
        
        # 从FBref获取比赛数据
        for league_key, ids in LEAGUE_MAPPINGS.items():
            fb_league = ids.get('fbref')
            if not fb_league:
                continue
                
            logger.info(f"从FBref获取 {league_key} 联赛比赛数据")
            
            # 获取当前赛季
            current_year = datetime.datetime.now().year
            matches_data = run_fbref_scraper(fb_league, current_year)
            
            if not matches_data:
                logger.warning(f"获取 {league_key} 联赛FBref比赛数据失败")
                continue
                
            logger.info(f"获取到 {len(matches_data)} 场 {league_key} 联赛FBref比赛")
            
            for match in matches_data:
                # 为爬虫数据生成一个唯一ID
                unique_id = f"fb-{match.get('home_team', '')}-{match.get('away_team', '')}-{match.get('date', '')}"
                
                match_data = {
                    'match_id': unique_id,
                    # 需要将爬虫的球队名称映射到自己的ID
                    'home_team_name': match.get('home_team', ''),
                    'away_team_name': match.get('away_team', ''),
                    'home_goals': match.get('home_score'),
                    'away_goals': match.get('away_score'),
                    'status': 'FINISHED' if match.get('home_score') is not None else 'SCHEDULED',
                    'date': datetime.datetime.strptime(match.get('date', ''), '%Y-%m-%d'),
                    'competition': league_key,
                    'source': 'fbref',
                    'details': json.dumps({})
                }
                
                # 查找球队ID
                home_team = db.execute(
                    select(Team).where(Team.name == match_data['home_team_name'])
                ).scalar_one_or_none()
                
                away_team = db.execute(
                    select(Team).where(Team.name == match_data['away_team_name'])
                ).scalar_one_or_none()
                
                if home_team:
                    match_data['home_team_id'] = home_team.id
                if away_team:
                    match_data['away_team_id'] = away_team.id
                
                try:
                    # 尝试查找现有记录
                    existing_match = db.execute(
                        select(Match).where(Match.match_id == match_data['match_id'])
                    ).scalar_one_or_none()
                    
                    if existing_match:
                        # 如果存在，更新记录
                        for key, value in match_data.items():
                            if key not in ('home_team_name', 'away_team_name'):  # 跳过临时字段
                                setattr(existing_match, key, value)
                    else:
                        # 删除临时字段
                        match_data.pop('home_team_name', None)
                        match_data.pop('away_team_name', None)
                        # 如果不存在，创建新记录
                        new_match = Match(**match_data)
                        db.add(new_match)
                        
                    all_matches.append(match_data)
                except Exception as e:
                    logger.error(f"处理比赛 {match_data['match_id']} 时出错: {str(e)}")
        
        db.commit()
        logger.info(f"从爬虫同步了 {len(all_matches)} 场比赛")
        return all_matches
        
    except Exception as e:
        db.rollback()
        logger.error(f"同步爬虫比赛数据时出错: {str(e)}")
        return []

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
            
            # 使用SQLite兼容的upsert方法
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
                'source': team.source or '',
                'league': team.league or ''
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
        await sync_juhe_football_teams(db)
        
        # 2. 同步比赛数据
        await sync_matches_from_apis(db)
        await sync_matches_from_scrapers(db)
        
        # 3. 更新统计数据
        await update_team_stats(db)
        
        # 4. 更新别名
        await update_team_aliases(db)
        
        logger.info("数据同步完成")
        return True
    except Exception as e:
        logger.error(f"数据同步过程失败: {str(e)}")
        return False