"""
Сервис для автоматического создания почтовых ящиков на Beget
API Docs: https://beget.com/ru/kb/api/funkczii-upravleniya-pochtoj
"""
import os
import re
import json
import string
import secrets
import requests
from config import Config


# Транслитерация ГОСТ 7.79-2000 (ISO 9)
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
}


def transliterate(text):
    """Транслитерация русского текста в латиницу"""
    result = []
    for char in text.lower():
        if char in TRANSLIT_MAP:
            result.append(TRANSLIT_MAP[char])
        elif char in string.ascii_lowercase or char in string.digits:
            result.append(char)
        elif char in (' ', '-', '_', '.'):
            result.append('.')
    # Убираем дублирующие точки и обрезаем
    out = re.sub(r'\.{2,}', '.', ''.join(result)).strip('.')
    return out or ''


def generate_password(length=12):
    """Генерация надёжного пароля"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class BegetService:
    """Управление почтой через Beget API"""

    API_URL = 'https://api.beget.com/api'

    def __init__(self):
        self.login = getattr(Config, 'BEGET_LOGIN', '') or os.getenv('BEGET_LOGIN', '')
        self.password = getattr(Config, 'BEGET_PASSWORD', '') or os.getenv('BEGET_PASSWORD', '')
        self.domain = getattr(Config, 'BEGET_MAIL_DOMAIN', '') or os.getenv('BEGET_MAIL_DOMAIN', 'stuchim.ru')

    def _is_configured(self):
        return bool(self.login and self.password)

    def _call(self, method, input_data=None):
        """Вызов Beget API"""
        if not self._is_configured():
            print('[BEGET] API credentials not configured')
            return None

        params = {
            'login': self.login,
            'passwd': self.password,
            'output_format': 'json',
        }
        if input_data is not None:
            params['input_data'] = json.dumps(input_data)

        url = f'{self.API_URL}/{method}'
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get('status') == 'success':
                return data.get('answer', {}).get('result', data.get('answer'))
            else:
                error = data.get('answer', {}).get('errors', data)
                print(f'[BEGET] API error for {method}: {error}')
                return None
        except Exception as e:
            print(f'[BEGET] Request failed for {method}: {e}')
            return None

    # ======================== DOMAIN MAIL ========================

    def setup_domain_mail(self):
        """Настроить почту на домене (вызывать один раз)"""
        result = self._call('mail/setDomainMail', {
            'domain': self.domain,
        })
        if result is not None:
            print(f'[BEGET] Domain mail enabled for {self.domain}')
        return result

    # ======================== MAILBOX OPS ========================

    def list_mailboxes(self):
        """Получить список ящиков на домене"""
        result = self._call('mail/getMailboxList', {
            'domain': self.domain,
        })
        return result or []

    def create_mailbox(self, mailbox_name, password):
        """Создать почтовый ящик"""
        result = self._call('mail/createMailbox', {
            'domain': self.domain,
            'mailbox': mailbox_name,
            'mailbox_password': password,
        })
        if result is not None:
            print(f'[BEGET] Created mailbox: {mailbox_name}@{self.domain}')
            return True
        return False

    def mailbox_exists(self, mailbox_name):
        """Проверить, существует ли ящик"""
        mailboxes = self.list_mailboxes()
        if not mailboxes:
            return False
        for mb in mailboxes:
            if isinstance(mb, dict):
                if mb.get('mailbox') == mailbox_name or mb.get('mailbox_name') == mailbox_name:
                    return True
            elif isinstance(mb, str):
                if mb == mailbox_name:
                    return True
        return False

    # ======================== NAME GENERATION ========================

    def generate_mailbox_name(self, fio):
        """
        Генерация имени ящика из ФИО по мировым стандартам:
        "Иванов Иван Иванович" → "ivan.ivanov"
        (firstname.lastname — Google Workspace / Microsoft 365 format)
        """
        if not fio or not fio.strip():
            # Фоллбэк: user_<random>
            return f'user_{secrets.token_hex(3)}'

        parts = fio.strip().split()

        if len(parts) >= 2:
            # Фамилия Имя [Отчество] → firstname.lastname
            lastname = transliterate(parts[0])
            firstname = transliterate(parts[1])
            if firstname and lastname:
                base = f'{firstname}.{lastname}'
            elif lastname:
                base = lastname
            elif firstname:
                base = firstname
            else:
                base = f'user_{secrets.token_hex(3)}'
        elif len(parts) == 1:
            base = transliterate(parts[0])
            if not base:
                base = f'user_{secrets.token_hex(3)}'
        else:
            base = f'user_{secrets.token_hex(3)}'

        # Ограничиваем длину
        base = base[:30]

        # Проверяем уникальность — добавляем суффикс при дублях
        candidate = base
        suffix = 2
        while self.mailbox_exists(candidate):
            candidate = f'{base}{suffix}'
            suffix += 1

        return candidate

    # ======================== FULL PROVISIONING ========================

    def provision_user_email(self, fio):
        """
        Полный цикл: сгенерировать имя → создать ящик → вернуть данные.
        Returns: dict { email, password, mailbox_name } или None при ошибке
        """
        if not self._is_configured():
            print('[BEGET] Skipping email provisioning — API not configured')
            return None

        mailbox_name = self.generate_mailbox_name(fio)
        password = generate_password()

        success = self.create_mailbox(mailbox_name, password)
        if success:
            email = f'{mailbox_name}@{self.domain}'
            return {
                'email': email,
                'password': password,
                'mailbox_name': mailbox_name,
                'domain': self.domain,
                'webmail_url': 'https://webmail.beget.com',
            }
        return None


beget_service = BegetService()
