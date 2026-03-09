"""
Сервис Яндекс Метрики — получение данных через API отчетов v1
Поисковые запросы, источники трафика, UTM, визиты
"""
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, List

METRIKA_API = 'https://api-metrika.yandex.net/stat/v1/data'
COUNTER_ID = '106967638'


class MetrikaService:
    """Клиент Yandex Metrika Reporting API"""

    def __init__(self):
        self.token = os.getenv('YANDEX_METRIKA_TOKEN', '')
        self.counter_id = COUNTER_ID

    def is_configured(self) -> bool:
        return bool(self.token)

    def _headers(self):
        return {'Authorization': f'OAuth {self.token}'}

    def _request(self, params: dict) -> dict:
        """Выполнить запрос к API Метрики"""
        params['id'] = self.counter_id
        params.setdefault('limit', 100)
        resp = requests.get(METRIKA_API, headers=self._headers(), params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _format_rows(self, data: dict) -> List[dict]:
        """Преобразовать ответ API в плоский список"""
        rows = []
        for item in data.get('data', []):
            dims = item.get('dimensions', [])
            mets = item.get('metrics', [])
            row = {}
            for i, d in enumerate(dims):
                row[f'dim{i}'] = d.get('name', d.get('id', ''))
            for i, m in enumerate(mets):
                row[f'metric{i}'] = m
            rows.append(row)
        return rows

    # ========== Основные отчеты ==========

    def get_traffic_summary(self, date_from: str = '', date_to: str = '') -> dict:
        """Сводка трафика: визиты, посетители, отказы, глубина, время на сайте"""
        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')

        data = self._request({
            'metrics': 'ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds',
            'dimensions': 'ym:s:date',
            'date1': date_from,
            'date2': date_to,
            'sort': '-ym:s:date',
            'limit': 30,
        })

        # Итого
        totals = data.get('totals', [0, 0, 0, 0, 0])
        by_day = []
        for item in data.get('data', []):
            d = item['dimensions'][0]
            m = item['metrics']
            by_day.append({
                'date': d.get('name', ''),
                'visits': int(m[0]),
                'users': int(m[1]),
                'bounce_rate': round(m[2], 1),
                'depth': round(m[3], 1),
                'avg_duration': int(m[4]),
            })

        return {
            'totals': {
                'visits': int(totals[0]),
                'users': int(totals[1]),
                'bounce_rate': round(totals[2], 1),
                'depth': round(totals[3], 1),
                'avg_duration': int(totals[4]),
            },
            'by_day': by_day,
            'period': {'from': date_from, 'to': date_to},
        }

    def get_search_phrases(self, date_from: str = '', date_to: str = '', limit: int = 50) -> dict:
        """Ключевики (utm_term) по которым приходили пользователи"""
        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')

        data = self._request({
            'metrics': 'ym:s:visits,ym:s:bounceRate,ym:s:avgVisitDurationSeconds',
            'dimensions': 'ym:s:lastUTMTerm',
            'date1': date_from,
            'date2': date_to,
            'sort': '-ym:s:visits',
            'limit': limit,
        })

        phrases = []
        for item in data.get('data', []):
            d = item['dimensions'][0]
            m = item['metrics']
            phrase = d.get('name', '')
            if not phrase or phrase == '(not set)' or phrase is None:
                continue
            phrases.append({
                'phrase': phrase,
                'visits': int(m[0]),
                'bounce_rate': round(m[1], 1),
                'avg_duration': int(m[2]),
            })

        return {'phrases': phrases, 'total': data.get('total_rows', 0)}

    def get_traffic_sources(self, date_from: str = '', date_to: str = '') -> dict:
        """Источники трафика"""
        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')

        data = self._request({
            'metrics': 'ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:avgVisitDurationSeconds',
            'dimensions': 'ym:s:lastTrafficSource',
            'date1': date_from,
            'date2': date_to,
            'sort': '-ym:s:visits',
            'limit': 20,
        })

        sources = []
        source_names = {
            'organic': '🔍 Поиск', 'ad': '📢 Реклама', 'direct': '🔗 Прямой',
            'referral': '🔄 Переходы', 'social': '📱 Соцсети',
            'internal': '🏠 Внутренний', 'recommend': '💡 Рекомендации',
            'messenger': '💬 Мессенджеры', 'email': '📧 Email',
            'savedpage': '📑 Сохранённые',
        }
        for item in data.get('data', []):
            d = item['dimensions'][0]
            m = item['metrics']
            src_id = d.get('id', d.get('name', ''))
            sources.append({
                'source': source_names.get(src_id, d.get('name', src_id)),
                'source_id': src_id,
                'visits': int(m[0]),
                'users': int(m[1]),
                'bounce_rate': round(m[2], 1),
                'avg_duration': int(m[3]),
            })

        return {'sources': sources}

    def get_utm_campaigns(self, date_from: str = '', date_to: str = '') -> dict:
        """UTM кампании с деталями"""
        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')

        data = self._request({
            'metrics': 'ym:s:visits,ym:s:bounceRate,ym:s:avgVisitDurationSeconds,ym:s:pageDepth',
            'dimensions': 'ym:s:lastUTMCampaign,ym:s:lastUTMSource,ym:s:lastUTMTerm',
            'date1': date_from,
            'date2': date_to,
            'sort': '-ym:s:visits',
            'limit': 100,
        })

        campaigns = []
        for item in data.get('data', []):
            dims = item['dimensions']
            m = item['metrics']
            campaigns.append({
                'campaign': dims[0].get('name', '(не указано)'),
                'source': dims[1].get('name', ''),
                'term': dims[2].get('name', ''),
                'visits': int(m[0]),
                'bounce_rate': round(m[1], 1),
                'avg_duration': int(m[2]),
                'depth': round(m[3], 1),
            })

        return {'campaigns': campaigns}

    def get_visits_detail(self, date_from: str = '', date_to: str = '', limit: int = 100) -> dict:
        """Per-visit data: keyword (utm_term), source, campaign, bounce, duration"""
        if not date_from:
            date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')

        data = self._request({
            'metrics': 'ym:s:visits,ym:s:bounceRate,ym:s:avgVisitDurationSeconds,ym:s:pageDepth',
            'dimensions': 'ym:s:date,ym:s:lastUTMTerm,ym:s:lastTrafficSource,ym:s:lastUTMCampaign,ym:s:lastUTMMedium',
            'date1': date_from,
            'date2': date_to,
            'sort': '-ym:s:date,-ym:s:visits',
            'limit': limit,
        })

        source_names = {
            'organic': '🔍 Поиск', 'ad': '📢 Реклама', 'direct': '🔗 Прямой',
            'referral': '🔄 Переходы', 'social': '📱 Соцсети',
            'internal': '🏠 Внутренний', 'recommend': '💡 Рекомендации',
            'messenger': '💬 Мессенджеры', 'email': '📧 Email',
        }

        visits = []
        for item in data.get('data', []):
            dims = item['dimensions']
            m = item['metrics']
            src_id = dims[2].get('id', dims[2].get('name', ''))
            medium = dims[4].get('name', '') or ''
            keyword = dims[1].get('name', '') or ''
            if medium in ('cpc', 'search'):
                source_label = '🔍 Поиск'
            elif medium in ('display', 'cpm', 'banner'):
                source_label = '📢 РСЯ'
            elif src_id == 'ad':
                source_label = '📢 Реклама'
            else:
                source_label = source_names.get(src_id, dims[2].get('name', src_id))
            # Classify keyword type
            if keyword == '---autotargeting':
                kw_type = 'автотаргет'
            elif keyword:
                kw_type = 'ключевик'
            else:
                kw_type = ''
            visits.append({
                'date': dims[0].get('name', ''),
                'keyword': keyword,
                'keyword_type': kw_type,
                'source': source_label,
                'source_id': src_id,
                'medium': medium,
                'campaign': dims[3].get('name', ''),
                'visits': int(m[0]),
                'bounce_rate': round(m[1], 1),
                'avg_duration': int(m[2]),
                'depth': round(m[3], 1),
            })

        return {'visits': visits, 'total': data.get('total_rows', 0)}


metrika_service = MetrikaService()
