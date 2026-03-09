"""
Сервис оплаты через ЮКассу
"""
import uuid
from datetime import datetime, timedelta
from yookassa import Configuration, Payment
from config import Config


# Настройка ЮКассы
if Config.YOOKASSA_SHOP_ID and Config.YOOKASSA_SECRET_KEY:
    Configuration.account_id = Config.YOOKASSA_SHOP_ID
    Configuration.secret_key = Config.YOOKASSA_SECRET_KEY


class PaymentService:
    """Сервис для работы с ЮКассой"""
    
    def create_payment(self, tariff_id, session_id, description=""):
        """Создать платёж в ЮКассе"""
        tariff = Config.TARIFFS.get(tariff_id)
        if not tariff:
            raise ValueError(f"Неизвестный тариф: {tariff_id}")
        
        idempotence_key = str(uuid.uuid4())
        
        payment = Payment.create({
            "amount": {
                "value": str(tariff['price']) + ".00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": Config.YOOKASSA_RETURN_URL
            },
            "capture": True,
            "description": f"Клик и Порядок — {tariff['name']} ({tariff['description']})",
            "metadata": {
                "tariff_id": tariff_id,
                "session_id": session_id,
            },
            "receipt": {
                "customer": {
                    "email": "support@stuchim.ru"
                },
                "items": [{
                    "description": f"Услуга «{tariff['name']}» — {tariff['description']}",
                    "quantity": "1.00",
                    "amount": {
                        "value": str(tariff['price']) + ".00",
                        "currency": "RUB"
                    },
                    "vat_code": 1,  # Без НДС (ИП на УСН)
                    "payment_subject": "service",
                    "payment_mode": "full_payment"
                }]
            }
        }, idempotence_key)
        
        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
            "status": payment.status,
        }
    
    def check_payment(self, payment_id):
        """Проверить статус платежа"""
        try:
            payment = Payment.find_one(payment_id)
            return {
                "payment_id": payment.id,
                "status": payment.status,  # pending, waiting_for_capture, succeeded, canceled
                "paid": payment.paid,
                "tariff_id": payment.metadata.get("tariff_id") if payment.metadata else None,
            }
        except Exception as e:
            print(f"[PAYMENT] Error checking payment {payment_id}: {e}")
            return None
    
    def is_paid(self, session_data):
        """Проверить, оплачена ли текущая сессия (standard или premium)"""
        return self.get_tariff_level(session_data) in ('standard', 'premium')
    
    def get_tariff_level(self, session_data):
        """Определить текущий уровень тарифа: free / standard / premium"""
        payment_info = session_data.get("data", {}).get("payment")
        if not payment_info or payment_info.get("status") != "succeeded":
            return 'free'
        
        tariff_id = payment_info.get("tariff_id", "")
        tariff = Config.TARIFFS.get(tariff_id, {})
        
        # Проверяем срок для тарифов с ограничением по дням
        days_limit = tariff.get("days")
        if days_limit:
            paid_at = payment_info.get("paid_at")
            if paid_at:
                expiry = datetime.fromisoformat(paid_at) + timedelta(days=days_limit)
                if datetime.now() > expiry:
                    return 'free'
        
        return tariff_id if tariff_id in ('standard', 'premium') else 'free'
    
    def can_download(self, session_data):
        """Доступно ли скачивание PDF (standard или premium)"""
        return self.get_tariff_level(session_data) in ('standard', 'premium')
    
    def can_send(self, session_data):
        """Доступна ли автоматическая рассылка (только premium)"""
        return self.get_tariff_level(session_data) == 'premium'
    
    def has_channels(self, session_data):
        """Доступны ли каналы связи — порталы, email, телефоны (standard или premium)"""
        return self.get_tariff_level(session_data) in ('standard', 'premium')
    
    def get_tariffs(self):
        """Вернуть список платных тарифов для фронтенда"""
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "price": t["price"],
                "period": t.get("period", ""),
                "description": t["description"],
                "features": t["features"],
                "popular": t.get("popular", False),
            }
            for t in Config.TARIFFS.values()
            if t["price"] > 0  # Не показываем бесплатный в paywall
        ]


payment_service = PaymentService()
