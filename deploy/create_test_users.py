"""Создание тестовых аккаунтов"""
import json, os, sys
sys.path.insert(0, '/opt/complaint-chat')
from werkzeug.security import generate_password_hash
from datetime import datetime

users_file = '/opt/complaint-chat/data/users.json'
with open(users_file, 'r', encoding='utf-8') as f:
    users = json.load(f)

users['test-annual@stuchim.ru'] = {
    'name': 'Тест Годовой',
    'password_hash': generate_password_hash('test123'),
    'password_raw': 'test123',
    'created_at': datetime.now().isoformat(),
    'user_type': 'individual',
    'fio': 'Тестов Тест Тестович',
    'phone': '+79001234567',
    'address': 'г. Москва, ул. Тестовая, д. 1',
    'payments': [{'amount': 2900, 'status': 'succeeded', 'tariff': 'annual', 'tariff_name': 'Годовой', 'payment_id': 'test_annual_001', 'recorded_at': datetime.now().isoformat()}],
    'complaints': [], 'events': [],
}

users['test-basic@stuchim.ru'] = {
    'name': 'Тест Базовый',
    'password_hash': generate_password_hash('test123'),
    'password_raw': 'test123',
    'created_at': datetime.now().isoformat(),
    'user_type': 'individual',
    'fio': 'Базовая Тестовна',
    'phone': '+79009876543',
    'address': 'г. Челябинск, ул. Примерная, д. 5',
    'payments': [{'amount': 290, 'status': 'succeeded', 'tariff': 'standard', 'tariff_name': 'Стандартный', 'payment_id': 'test_basic_001', 'recorded_at': datetime.now().isoformat()}],
    'complaints': [], 'events': [],
}

with open(users_file, 'w', encoding='utf-8') as f:
    json.dump(users, f, ensure_ascii=False, indent=2)

print(f'OK! Users: {len(users)}')
