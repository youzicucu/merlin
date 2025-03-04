# app/data/sources/scrapers.py
import logging
import requests
from bs4 import BeautifulSoup
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy import signals
from scrapy.signalmanager import dispatcher

logger = logging.getLogger(__name__)

class SoccerstatsScraper:
    """用于抓取Soccerstats网站的数据"""
    def __init__(self):
        self.base_url = "https://www.soccerstats.com"
        
    def get_team_stats(self, team_url):
        try:
            response = requests.get(f"{self.base_url}/{team_url}")
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # 解析网页数据，提取所需统计信息
            stats = {}
            
            # 示例：获取进球数据
            goals_table = soup.select_one('.table_bd')
            if goals_table:
                # 这里写具体的数据提取逻辑，根据网站实际HTML结构来写
                stats['avg_goals_scored'] = self._extract_goals_scored(goals_table)
                stats['avg_goals_conceded'] = self._extract_goals_conceded(goals_table)
                stats['clean_sheets'] = self._extract_clean_sheets(soup)
            
            return stats
        except Exception as e:
            logger.error(f"Error scraping team stats: {e}")
            return None
    
    def _extract_goals_scored(self, table):
        """示例方法：从表格中提取进球数据"""
        # 实际实现需要根据soccerstats的HTML结构来写
        # 这只是一个占位示例
        return 1.5  # 示例返回值
    
    def _extract_goals_conceded(self, table):
        # 同上，占位示例
        return 0.8
    
    def _extract_clean_sheets(self, soup):
        # 同上，占位示例
        return 5


class FBrefSpider(scrapy.Spider):
    """抓取FBref网站的Scrapy爬虫"""
    name = 'fbref_spider'
    allowed_domains = ['fbref.com']
    
    def __init__(self, team_id=None, *args, **kwargs):
        super(FBrefSpider, self).__init__(*args, **kwargs)
        self.start_urls = [f'https://fbref.com/en/teams/{team_id}'] if team_id else ['https://fbref.com/en/']
        self.results = {}
    
    def parse(self, response):
        # 解析团队统计数据
        team_name = response.css('h1[itemprop="name"] span::text').get()
        
        # 提取各种统计指标
        stats_tables = response.css('table.stats_table')
        
        team_stats = {}
        for table in stats_tables:
            table_id = table.attrib.get('id', '')
            if 'shooting' in table_id:
                # 提取射门数据
                team_stats['shooting'] = self.parse_table(table)
            elif 'passing' in table_id:
                # 提取传球数据
                team_stats['passing'] = self.parse_table(table)
            # 可以添加更多类型的数据提取
        
        self.results[team_name] = team_stats
        return team_stats
    
    def parse_table(self, table):
        """解析FBref表格数据"""
        headers = [th.css('::text').get() for th in table.css('thead th')]
        rows = []
        for row in table.css('tbody tr'):
            row_data = {}
            for i, cell in enumerate(row.css('td')):
                if i < len(headers):
                    row_data[headers[i]] = cell.css('::text').get()
            rows.append(row_data)
        return rows


class FBrefScraper:
    """FBref网站爬虫的封装类，方便调用"""
    def __init__(self):
        self.results = {}
    
    def get_team_stats(self, team_id):
        """获取球队统计数据"""
        process = CrawlerProcess(settings={
            'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'LOG_LEVEL': 'ERROR'
        })
        
        def crawler_results(signal, sender, item, response, spider):
            self.results = item
            
        dispatcher.connect(crawler_results, signal=signals.item_scraped)
        
        process.crawl(FBrefSpider, team_id=team_id)
        process.start()
        
        return self.results