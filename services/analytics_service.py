"""
Сервис аналитики воронки — JSON-based event logging
Логирует каждый переход шага для каждого посетителя
"""
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, OrderedDict
import threading


class AnalyticsService:
    """Логирование и агрегация событий воронки"""
    
    # Порядок шагов для воронки
    FUNNEL_STEPS = OrderedDict([
        ('visit', 'Визит'),
        ('consent', 'Согласие ПД'),
        ('reg_user_type', 'Тип пользователя'),
        ('reg_fio', 'ФИО'),
        ('reg_address', 'Адрес'),
        ('reg_phone', 'Телефон'),
        ('reg_email', 'Email'),
        ('reg_password', 'Пароль'),
        ('category', 'Категория'),
        ('quiz_q1', 'Квиз: вопрос 1'),
        ('quiz_q2', 'Квиз: вопрос 2'),
        ('quiz_q3', 'Квиз: вопрос 3'),
        ('quiz_q4', 'Квиз: вопрос 4'),
        ('quiz_q5', 'Квиз: вопрос 5+'),
        ('complaint_generated', 'Жалоба готова'),
        ('recipients_selected', 'Адресаты выбраны'),
        ('complaint_sent', 'Отправлено'),
    ])
    
    def __init__(self, data_dir='./data'):
        self.data_dir = data_dir
        self.events_file = os.path.join(data_dir, 'analytics_events.jsonl')
        self._lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)
    
    def log_event(self, visitor_id: str, step: str, sub_step: str = '',
                  utm_data: Optional[Dict] = None, ip: str = '', 
                  user_agent: str = '', extra: Optional[Dict] = None):
        """Записать одно событие в JSONL файл"""
        event = {
            'vid': visitor_id,
            'ts': datetime.now().isoformat(),
            'step': step,
            'sub': sub_step,
            'utm_term': (utm_data or {}).get('utm_term', ''),
            'utm_source': (utm_data or {}).get('utm_source', ''),
            'utm_campaign': (utm_data or {}).get('utm_campaign', ''),
            'ip': ip,
            'ua': user_agent[:100] if user_agent else '',
        }
        if extra:
            event['extra'] = extra
        
        with self._lock:
            try:
                with open(self.events_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(event, ensure_ascii=False) + '\n')
            except Exception as e:
                print(f"[Analytics] Error writing event: {e}")
    
    def _read_events(self, date_from: Optional[str] = None, 
                     date_to: Optional[str] = None) -> List[Dict]:
        """Прочитать все события, опционально с фильтром по дате"""
        events = []
        if not os.path.exists(self.events_file):
            return events
        
        try:
            with open(self.events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        if date_from and ev['ts'] < date_from:
                            continue
                        if date_to and ev['ts'] > date_to:
                            continue
                        events.append(ev)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[Analytics] Error reading events: {e}")
        
        return events
    
    def get_funnel(self, date_from: Optional[str] = None, 
                   date_to: Optional[str] = None,
                   utm_filter: Optional[str] = None) -> Dict:
        """Агрегированная воронка: сколько уникальных посетителей на каждом шаге"""
        events = self._read_events(date_from, date_to)
        
        if utm_filter:
            events = [e for e in events if utm_filter.lower() in 
                      (e.get('utm_term', '') + e.get('utm_campaign', '')).lower()]
        
        # Для каждого visitor_id найти максимальный достигнутый шаг
        visitor_max_step = {}  # vid -> set of reached steps
        step_keys = list(self.FUNNEL_STEPS.keys())
        
        for ev in events:
            vid = ev['vid']
            step = ev['step']
            if vid not in visitor_max_step:
                visitor_max_step[vid] = set()
            visitor_max_step[vid].add(step)
        
        total = len(visitor_max_step)
        
        # Считаем сколько посетителей достигли каждого шага
        funnel = []
        for step_key, step_name in self.FUNNEL_STEPS.items():
            count = sum(1 for steps in visitor_max_step.values() if step_key in steps)
            pct = round(count / total * 100, 1) if total > 0 else 0
            funnel.append({
                'step': step_key,
                'name': step_name,
                'count': count,
                'pct': pct,
            })
        
        return {
            'total_visitors': total,
            'funnel': funnel,
            'period': {
                'from': date_from or 'all',
                'to': date_to or 'now',
            }
        }
    
    def get_visitors(self, page: int = 1, per_page: int = 50,
                     date_from: Optional[str] = None,
                     date_to: Optional[str] = None,
                     utm_filter: Optional[str] = None) -> Dict:
        """Список уникальных посетителей с их последним шагом"""
        events = self._read_events(date_from, date_to)
        
        if utm_filter:
            events = [e for e in events if utm_filter.lower() in
                      (e.get('utm_term', '') + e.get('utm_campaign', '')).lower()]
        
        # Группируем по visitor_id
        visitors = {}
        step_keys = list(self.FUNNEL_STEPS.keys())
        
        for ev in events:
            vid = ev['vid']
            if vid not in visitors:
                visitors[vid] = {
                    'id': vid,
                    'first_seen': ev['ts'],
                    'last_seen': ev['ts'],
                    'utm_term': ev.get('utm_term', ''),
                    'utm_source': ev.get('utm_source', ''),
                    'utm_campaign': ev.get('utm_campaign', ''),
                    'ip': ev.get('ip', ''),
                    'ua': ev.get('ua', ''),
                    'steps': set(),
                    'last_step': ev['step'],
                    'last_sub': ev.get('sub', ''),
                    'event_count': 0,
                }
            v = visitors[vid]
            v['last_seen'] = ev['ts']
            v['steps'].add(ev['step'])
            v['event_count'] += 1
            # Track deepest step
            cur_idx = step_keys.index(ev['step']) if ev['step'] in step_keys else -1
            last_idx = step_keys.index(v['last_step']) if v['last_step'] in step_keys else -1
            if cur_idx >= last_idx:
                v['last_step'] = ev['step']
                v['last_sub'] = ev.get('sub', '')
        
        # Convert sets and sort by last_seen DESC
        visitor_list = []
        for v in visitors.values():
            v['step_count'] = len(v['steps'])
            v['steps'] = sorted(v['steps'], key=lambda s: step_keys.index(s) if s in step_keys else 999)
            v['last_step_name'] = self.FUNNEL_STEPS.get(v['last_step'], v['last_step'])
            # Duration
            try:
                first = datetime.fromisoformat(v['first_seen'])
                last = datetime.fromisoformat(v['last_seen'])
                dur = (last - first).total_seconds()
                v['duration_sec'] = int(dur)
                if dur < 60:
                    v['duration'] = f"{int(dur)}с"
                elif dur < 3600:
                    v['duration'] = f"{int(dur // 60)}м{int(dur % 60)}с"
                else:
                    v['duration'] = f"{int(dur // 3600)}ч{int((dur % 3600) // 60)}м"
            except:
                v['duration'] = '—'
                v['duration_sec'] = 0
            visitor_list.append(v)
        
        visitor_list.sort(key=lambda x: x['last_seen'], reverse=True)
        
        total = len(visitor_list)
        start = (page - 1) * per_page
        end = start + per_page
        
        return {
            'visitors': visitor_list[start:end],
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
        }
    
    def get_visitor_events(self, visitor_id: str) -> List[Dict]:
        """Все события конкретного посетителя"""
        events = self._read_events()
        return [e for e in events if e['vid'] == visitor_id]


# Singleton
analytics_service = AnalyticsService()
