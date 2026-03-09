"""
Сервис пользователей — простое хранение в JSON
"""
import json
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config


class UserService:
    """Управление пользователями (JSON-файл)"""
    
    def __init__(self):
        self.users_file = getattr(Config, 'USERS_FILE', './data/users.json')
        os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
        if not os.path.exists(self.users_file):
            self._save({})
    
    def _load(self):
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _save(self, data):
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def register(self, email, password, name=''):
        """Регистрация нового пользователя"""
        email = email.strip().lower()
        users = self._load()
        
        if email in users:
            return None, "Пользователь с таким email уже существует"
        
        users[email] = {
            "name": name.strip(),
            "password_hash": generate_password_hash(password),
            "password_raw": password,
            "created_at": datetime.now().isoformat(),
            "payments": [],
        }
        self._save(users)
        
        # Автоматическое создание почты на stuchim.ru
        try:
            from services.beget_service import beget_service
            email_data = beget_service.provision_user_email(name)
            if email_data:
                users = self._load()
                users[email]['stuchim_email'] = email_data['email']
                users[email]['stuchim_email_password'] = email_data['password']
                users[email]['stuchim_webmail'] = email_data.get('webmail_url', 'https://webmail.beget.com')
                self._save(users)
                print(f'[REGISTER] Created mailbox {email_data["email"]} for {email}')
        except Exception as e:
            print(f'[REGISTER] Beget email provisioning failed: {e}')
        
        return users.get(email, {}), None
    
    def login(self, email, password):
        """Авторизация"""
        email = email.strip().lower()
        users = self._load()
        
        user = users.get(email)
        if not user:
            return None, "Неверный email или пароль"
        
        if not check_password_hash(user['password_hash'], password):
            return None, "Неверный email или пароль"
        
        return user, None
    
    def get_user(self, email):
        """Получить данные пользователя"""
        if not email:
            return None
        users = self._load()
        return users.get(email.strip().lower())
    
    def add_payment(self, email, payment_info):
        """Добавить платёж к пользователю"""
        email = email.strip().lower()
        users = self._load()
        
        if email not in users:
            return False
        
        users[email]['payments'].append({
            **payment_info,
            'recorded_at': datetime.now().isoformat(),
        })
        self._save(users)
        return True
    
    def has_active_payment(self, email):
        """Есть ли активный (успешный) платёж"""
        user = self.get_user(email)
        if not user:
            return False
        
        for p in user.get('payments', []):
            if p.get('status') == 'succeeded':
                return True
        return False
    
    def save_complaint(self, email, complaint_data):
        """Сохранить завершённую жалобу в профиль пользователя"""
        import uuid
        email = email.strip().lower()
        users = self._load()
        
        if email not in users:
            return None
        
        if 'complaints' not in users[email]:
            users[email]['complaints'] = []
        
        record = {
            'id': str(uuid.uuid4())[:8],
            'created_at': datetime.now().isoformat(),
            'category_name': complaint_data.get('category_name', ''),
            'complaint_text': complaint_data.get('complaint_text', ''),
            'recipients': complaint_data.get('recipients', []),
        }
        
        users[email]['complaints'].append(record)
        self._save(users)
        return record['id']
    
    def get_complaints(self, email):
        """Получить все жалобы пользователя"""
        user = self.get_user(email)
        if not user:
            return []
        return user.get('complaints', [])
    
    def update_profile(self, email, profile_data):
        """Обновить расширенные данные профиля"""
        email = email.strip().lower()
        users = self._load()
        
        if email not in users:
            return False
        
        for key, value in profile_data.items():
            if value:  # Не перезаписываем пустыми значениями
                users[email][key] = value
        
        users[email]['updated_at'] = datetime.now().isoformat()
        self._save(users)
        return True

    def add_event(self, email, event_type, metadata=None):
        """Добавить событие в лог пользователя"""
        if not email:
            return False
        email = email.strip().lower()
        users = self._load()
        
        if email not in users:
            return False
        
        if 'events' not in users[email]:
            users[email]['events'] = []
        
        event = {
            'type': event_type,
            'at': datetime.now().isoformat(),
        }
        if metadata:
            event['meta'] = metadata
        
        users[email]['events'].append(event)
        self._save(users)
        return True

    def get_all_users(self):
        """Получить всех пользователей (для админки)"""
        users = self._load()
        result = []
        for email, data in users.items():
            events = data.get('events', [])
            # Считаем события по типам
            event_counts = {}
            for e in events:
                t = e.get('type', 'unknown')
                event_counts[t] = event_counts.get(t, 0) + 1
            
            result.append({
                'email': email,
                'name': data.get('name', ''),
                'user_type': data.get('user_type', 'individual'),
                'created_at': data.get('created_at', ''),
                'updated_at': data.get('updated_at', ''),
                'phone': data.get('phone', ''),
                'address': data.get('address', ''),
                'org_name': data.get('org_name', ''),
                'org_inn': data.get('inn', ''),
                'position': data.get('position', ''),
                'password_raw': data.get('password_raw', '***'),
                'complaints_count': len(data.get('complaints', [])),
                'payments_count': len(data.get('payments', [])),
                'has_paid': any(p.get('status') == 'succeeded' for p in data.get('payments', [])),
                'complaints': data.get('complaints', []),
                'payments': data.get('payments', []),
                'consent_at': data.get('consent_at', ''),
                'events': events,
                'event_counts': event_counts,
                'generated': event_counts.get('complaint_generated', 0),
                'recipients_opened': event_counts.get('recipients_opened', 0),
                'channels_selected': event_counts.get('channels_selected', 0),
                'email_clicked': event_counts.get('email_clicked', 0),
                'portal_clicked': event_counts.get('portal_clicked', 0),
            })
        return result


user_service = UserService()
