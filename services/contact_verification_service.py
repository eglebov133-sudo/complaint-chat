"""
Сервис верификации контактов государственных органов
Использует Perplexity API через OpenRouter для real-time поиска
"""
import requests
import json
from typing import Dict, Optional
from config import Config


class ContactVerificationService:
    """Сервис для поиска и верификации контактов госорганов через Perplexity"""
    
    def __init__(self):
        self.api_key = Config.OPENROUTER_API_KEY
        self.base_url = Config.OPENROUTER_BASE_URL
        self.model = Config.PERPLEXITY_MODEL
        
    def _call_perplexity(self, prompt: str) -> Optional[str]:
        """Вызов Perplexity через OpenRouter"""
        if not self.api_key:
            print("ContactVerification: No API key")
            return None
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "Complaint Contact Verifier"
        }
        
        messages = [
            {
                "role": "system",
                "content": """Ты — помощник для поиска ПОЛНОЙ информации о подаче жалоб в российские государственные органы.

СТРОГИЕ ПРАВИЛА:
1. Ищи ТОЛЬКО на официальных источниках (.gov.ru, .ru домены госорганов)
2. НЕ выдумывай данные — если не нашёл, честно указывай null
3. Возвращай ТОЛЬКО актуальные, работающие ссылки
4. Формат ответа — ТОЛЬКО JSON, никакого текста до или после

Формат ответа:
{
    "found": true/false,
    "address": "Полный физический адрес (индекс, город, улица, дом) или null",
    "phone": "Телефон приёмной или горячей линии или null",
    "email": "email@example.gov.ru или null",
    "working_hours": "Часы работы приёмной (например 'Пн-Пт 9:00-18:00') или null",
    
    "portal_url": "https://... ссылка на портал подачи обращений или null",
    "portal_name": "Название портала или null",
    
    "submission_methods": ["Портал", "Email", "Личный приём", "Почта России"],
    "auth_required": "Описание требований к регистрации (Госуслуги/ЕСИА/простая регистрация/без регистрации)",
    "documents_needed": ["Список документов которые могут понадобиться"] или null,
    "processing_time": "Срок рассмотрения (например '30 дней')",
    
    "tips": "Практический совет по подаче (1-2 предложения)",
    "recommendation": "Краткое описание эффективности органа (1 предложение)",
    
    "confidence": "high/medium/low",
    "source": "URL источника информации"
}"""
            },
            {
                "role": "user", 
                "content": prompt
            }
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # Низкая температура для точности
            "max_tokens": 800  # Увеличено для развёрнутого ответа
        }
        
        try:
            print(f"ContactVerification: Calling Perplexity for contact lookup...")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if not response.ok:
                print(f"ContactVerification Error: {response.status_code} - {response.text[:200]}")
                return None
                
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            print(f"ContactVerification: Got response: {content[:200]}...")
            return content
            
        except Exception as e:
            print(f"ContactVerification Error: {e}")
            return None
    
    def verify_and_get_contacts(self, org_name: str, category: str = "") -> Dict:
        """
        Поиск полной информации об органе для подачи жалобы
        
        Args:
            org_name: Название организации (например "Роспотребнадзор")
            category: Категория жалобы для уточнения (например "защита прав потребителей")
            
        Returns:
            Dict с полной информацией о контактах, способах подачи, требованиях
        """
        context = f" по теме '{category}'" if category else ""
        prompt = f"""Найди ПОЛНУЮ информацию для подачи жалобы в {org_name}{context}.

Мне нужны:
1. Физический адрес органа (с индексом)
2. Телефон приёмной/горячей линии
3. Email для обращений
4. Часы работы приёмной
5. Ссылка на портал для онлайн-подачи
6. Какие способы подачи доступны (портал, email, лично, почтой)
7. Нужна ли регистрация (Госуслуги, ЕСИА, своя регистрация)
8. Какие документы могут понадобиться
9. Срок рассмотрения обращения
10. Практический совет по подаче

Ищи ТОЛЬКО на официальных источниках. Если не уверен — указывай null."""

        result = self._call_perplexity(prompt)
        
        if not result:
            return {
                "verified": False,
                "email": None,
                "portal_url": None,
                "error": "Не удалось получить данные"
            }
        
        # Парсим JSON ответ
        try:
            # Извлекаем JSON из ответа (может быть обёрнут в markdown)
            json_str = result
            if "```json" in result:
                json_str = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                json_str = result.split("```")[1].split("```")[0]
            
            data = json.loads(json_str.strip())
            
            print(f"ContactVerification: Got detailed info - addr: {data.get('address')}, phone: {data.get('phone')}")
            
            return {
                "verified": data.get("found", False) and data.get("confidence") in ["high", "medium"],
                # Контакты
                "address": data.get("address"),
                "phone": data.get("phone"),
                "email": data.get("email"),
                "working_hours": data.get("working_hours"),
                # Портал
                "portal_url": data.get("portal_url"),
                "portal_name": data.get("portal_name"),
                # Способы и требования
                "submission_methods": data.get("submission_methods", []),
                "auth_required": data.get("auth_required"),
                "documents_needed": data.get("documents_needed", []),
                "processing_time": data.get("processing_time"),
                # Советы
                "tips": data.get("tips"),
                "recommendation": data.get("recommendation"),
                # Метаданные
                "confidence": data.get("confidence", "low"),
                "source": data.get("source")
            }
            
        except json.JSONDecodeError as e:
            print(f"ContactVerification: Failed to parse JSON: {e}")
            return {
                "verified": False,
                "email": None,
                "portal_url": None,
                "error": "Ошибка парсинга ответа"
            }
    
    def check_url_alive(self, url: str) -> bool:
        """Проверка что URL доступен (возвращает 200)"""
        if not url:
            return False
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
            
        try:
            response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            return response.status_code < 400
        except:
            # Пробуем GET если HEAD не работает
            try:
                response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                return response.status_code < 400
            except:
                return False


# Singleton
contact_verification_service = ContactVerificationService()
