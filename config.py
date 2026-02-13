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
    
    # Базовая модель для квиза и простых задач (Gemini 2.0 Flash — быстрая, умная, дешёвая)
    LLM_MODEL = os.getenv('LLM_MODEL', 'google/gemini-2.0-flash-001')
    
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
    
    # Rate limiting
    RATELIMIT_DEFAULT = "60 per minute"
    RATELIMIT_SEND = "5 per minute"
    
    # Drafts
    DRAFTS_DIR = './drafts'
