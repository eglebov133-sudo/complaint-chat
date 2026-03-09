"""
Конфигурация приложения
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'complaint-chat-secret-key-change-in-production')
    
    # Session
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = './flask_session'
    SESSION_PERMANENT = False
    
    # LLM (OpenRouter)
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
    OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
    
    # Базовая модель для квиза и задач
    LLM_MODEL = os.getenv('LLM_MODEL', 'anthropic/claude-sonnet-4.6')
    
    # Claude Sonnet 4.5 для написания текста жалобы (умный, детальный)
    COMPLAINT_MODEL = os.getenv('COMPLAINT_MODEL', 'anthropic/claude-sonnet-4.5')
    
    # Claude Opus 4.6 для определения адресатов (экспертный анализ)
    RECIPIENT_MODEL = os.getenv('RECIPIENT_MODEL', 'anthropic/claude-opus-4.6')
    
    # Perplexity для поиска контактов
    PERPLEXITY_MODEL = os.getenv('PERPLEXITY_MODEL', 'perplexity/sonar')
    
    # Email
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    EMAIL_FROM = os.getenv('EMAIL_FROM', '')
    
    # DaData API (для подсказок организаций и адресов)
    DADATA_API_KEY = os.getenv('DADATA_API_KEY', '')
    
    # Beget API (автоматическое создание почты)
    BEGET_LOGIN = os.getenv('BEGET_LOGIN', '')
    BEGET_PASSWORD = os.getenv('BEGET_PASSWORD', '')
    BEGET_MAIL_DOMAIN = os.getenv('BEGET_MAIL_DOMAIN', 'stuchim.ru')
    
    # YooKassa Payment
    YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID', '')
    YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY', '')
    YOOKASSA_RETURN_URL = os.getenv('YOOKASSA_RETURN_URL', 'https://stuchim.ru/')
    
    # Тарифы (цены в рублях)
    TARIFFS = {
        'free': {
            'id': 'free',
            'name': 'Бесплатный',
            'price': 0,
            'description': 'Полная генерация жалобы и контакты адресатов',
            'features': [
                'Генерация текста жалобы',
                'Ссылки на законы и статьи',
                'Список адресатов (инстанций)',
                'Адреса и телефоны инстанций',
                'Режим работы приёмных',
                'Рекомендации по подаче',
                'Сроки рассмотрения обращений',
            ],
            'complaints': 999,
            'sending': False,
            'download': False,
            'channels': False,
        },
        'standard': {
            'id': 'standard',
            'name': 'Стандартный',
            'price': 290,
            'description': 'Готовый PDF + порталы + отслеживание',
            'features': [
                'Всё из бесплатного',
                'Скачивание готового PDF',
                'Email-адреса для обращений',
                'Прямые ссылки на порталы приёмных',
                'Инструкция по подаче на каждый портал',
                'Проверка контактов через AI',
                'Шаблон сопроводительного письма',
                'Приоритетная поддержка',
            ],
            'complaints': 1,
            'sending': False,
            'download': True,
            'channels': True,
            'popular': True,
        },
        'premium': {
            'id': 'premium',
            'name': 'Безлимит',
            'price': 980,
            'period': 'год',
            'description': 'Безлимитные жалобы на весь год',
            'features': [
                'Всё из стандартного',
                'Безлимитные жалобы (365 дней)',
                'Скачивание PDF без ограничений',
                'Приоритетная поддержка',
            ],
            'complaints': 999,
            'sending': False,
            'download': True,
            'channels': True,
            'days': 365,
        },
    }
    
    # Rate limiting
    RATELIMIT_DEFAULT = "60 per minute"
    RATELIMIT_SEND = "5 per minute"
    
    # Drafts
    DRAFTS_DIR = './drafts'
    
    # Users
    USERS_FILE = './data/users.json'

