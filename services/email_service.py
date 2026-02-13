"""
Сервис отправки email
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from config import Config


class EmailService:
    def __init__(self):
        self.smtp_host = Config.SMTP_HOST
        self.smtp_port = Config.SMTP_PORT
        self.smtp_user = Config.SMTP_USER
        self.smtp_password = Config.SMTP_PASSWORD
        self.email_from = Config.EMAIL_FROM or Config.SMTP_USER
        
    def is_configured(self) -> bool:
        """Проверка настройки email"""
        return bool(self.smtp_user and self.smtp_password)
    
    def send_complaint(
        self,
        to_emails: List[str],
        subject: str,
        complaint_text: str,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
        send_copy_to_sender: bool = True
    ) -> dict:
        """
        Отправка жалобы на указанные email адреса
        
        Returns:
            dict: {"success": bool, "sent_to": [...], "failed": [...], "error": str or None}
        """
        
        if not self.is_configured():
            return {
                "success": False,
                "sent_to": [],
                "failed": to_emails,
                "error": "Email не настроен. Укажите SMTP_USER и SMTP_PASSWORD в .env"
            }
        
        # Формируем список получателей
        recipients = list(to_emails)
        if send_copy_to_sender and sender_email:
            recipients.append(sender_email)
        
        # Убираем пустые и дубликаты
        recipients = list(set(filter(None, recipients)))
        
        if not recipients:
            return {
                "success": False,
                "sent_to": [],
                "failed": [],
                "error": "Не указаны получатели"
            }
        
        sent_to = []
        failed = []
        last_error = None
        
        try:
            # Подключаемся к SMTP серверу
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                
                for recipient in recipients:
                    try:
                        msg = self._create_message(
                            to_email=recipient,
                            subject=subject,
                            body=complaint_text,
                            sender_name=sender_name
                        )
                        server.send_message(msg)
                        sent_to.append(recipient)
                    except Exception as e:
                        failed.append(recipient)
                        last_error = str(e)
                        
        except smtplib.SMTPAuthenticationError:
            return {
                "success": False,
                "sent_to": [],
                "failed": recipients,
                "error": "Ошибка авторизации SMTP. Проверьте логин и пароль."
            }
        except Exception as e:
            return {
                "success": False,
                "sent_to": sent_to,
                "failed": [r for r in recipients if r not in sent_to],
                "error": str(e)
            }
        
        return {
            "success": len(sent_to) > 0,
            "sent_to": sent_to,
            "failed": failed,
            "error": last_error
        }
    
    def _create_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        sender_name: Optional[str] = None
    ) -> MIMEMultipart:
        """Создание email сообщения"""
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{sender_name} <{self.email_from}>" if sender_name else self.email_from
        msg['To'] = to_email
        
        # Текстовая версия
        text_part = MIMEText(body, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # HTML версия (простое форматирование)
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <pre style="white-space: pre-wrap; font-family: inherit;">{body}</pre>
        </body>
        </html>
        """
        html_part = MIMEText(html_body, 'html', 'utf-8')
        msg.attach(html_part)
        
        return msg


# Singleton instance
email_service = EmailService()
