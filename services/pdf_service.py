"""
PDF сервис для генерации жалоб в формате PDF
Использует reportlab для создания документов
"""

import os
import tempfile
from datetime import datetime
from typing import Dict, Optional
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class PDFService:
    """Сервис генерации PDF документов"""
    
    def __init__(self):
        self._register_fonts()
        self.styles = self._create_styles()
    
    def _register_fonts(self):
        """Регистрация шрифтов с поддержкой кириллицы"""
        # Пробуем найти системные шрифты
        font_paths = [
            # Windows
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        
        font_registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font_name = os.path.basename(font_path).replace('.ttf', '')
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    self.default_font = font_name
                    font_registered = True
                    break
                except:
                    continue
        
        if not font_registered:
            # Если шрифты не найдены — используем встроенный (без кириллицы)
            self.default_font = "Helvetica"
    
    def _create_styles(self) -> Dict:
        """Создание стилей для документа"""
        styles = getSampleStyleSheet()
        
        # Основной текст
        styles.add(ParagraphStyle(
            name='RuNormal',
            fontName=self.default_font,
            fontSize=12,
            leading=16,
            alignment=TA_JUSTIFY,
            spaceAfter=6
        ))
        
        # Заголовок документа
        styles.add(ParagraphStyle(
            name='RuTitle',
            fontName=self.default_font,
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=12,
            spaceBefore=12,
            fontWeight='bold'
        ))
        
        # Шапка (адресная часть)
        styles.add(ParagraphStyle(
            name='RuHeader',
            fontName=self.default_font,
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=4
        ))
        
        # Подпись
        styles.add(ParagraphStyle(
            name='RuSignature',
            fontName=self.default_font,
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceBefore=24
        ))
        
        return styles
    
    def generate_complaint_pdf(
        self,
        complaint_text: str,
        recipient_name: str,
        user_data: Dict,
        category_name: str = ""
    ) -> bytes:
        """
        Генерирует PDF документ жалобы
        
        Args:
            complaint_text: Текст жалобы
            recipient_name: Название получателя
            user_data: Данные пользователя (fio, address, phone, email)
            category_name: Категория жалобы
            
        Returns:
            bytes: PDF документ в виде байтов
        """
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2.5*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # Текст жалобы уже содержит полную шапку от LLM
        # Просто форматируем его - разбиваем на абзацы
        paragraphs = complaint_text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Заменяем одинарные переносы на <br/>
                para = para.replace('\n', '<br/>')
                story.append(Paragraph(para, self.styles['RuNormal']))
                story.append(Spacer(1, 6))
        
        story.append(Spacer(1, 24))
        
        # Дата и подпись (добавляем только если их нет в тексте)
        fio = user_data.get('fio', '[ФИО]')
        current_date = datetime.now().strftime("%d.%m.%Y")
        
        if "Подпись:" not in complaint_text and "_____________" not in complaint_text:
            signature = f"""
            Дата: {current_date}<br/><br/>
            Подпись: _______________ / {fio} /
            """
            story.append(Paragraph(signature, self.styles['RuSignature']))
        
        # Генерируем PDF
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def save_complaint_pdf(
        self,
        complaint_text: str,
        recipient_name: str,
        user_data: Dict,
        category_name: str = "",
        output_path: Optional[str] = None
    ) -> str:
        """
        Сохраняет PDF жалобы в файл
        
        Returns:
            str: Путь к сохранённому файлу
        """
        pdf_bytes = self.generate_complaint_pdf(
            complaint_text, recipient_name, user_data, category_name
        )
        
        if output_path is None:
            # Создаём временный файл
            fd, output_path = tempfile.mkstemp(suffix='.pdf', prefix='complaint_')
            os.close(fd)
        
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)
        
        return output_path


# Singleton
pdf_service = PDFService()
