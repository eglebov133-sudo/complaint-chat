"""
Оркестратор для управления субагентами
Координирует flow: Quiz → Complaint → Preview → Recipients → Send
"""

from typing import Dict, Optional, List
from enum import Enum
from services.agents import quiz_agent, complaint_agent, recipient_agent, send_agent


class FlowStep(Enum):
    """Шаги процесса"""
    WELCOME = "welcome"
    USER_TYPE = "user_type"
    CATEGORY = "category"
    QUIZ = "quiz"
    COLLECTING_CONTACTS = "collecting_contacts"
    GENERATING_COMPLAINT = "generating_complaint"
    PREVIEW = "preview"
    RECIPIENTS = "recipients"
    CONFIRM_SEND = "confirm_send"
    SENDING = "sending"
    COMPLETE = "complete"


class Orchestrator:
    """
    Оркестратор управляет потоком работы и вызывает нужных агентов
    """
    
    # Порядок шагов (новый flow!)
    FLOW_ORDER = [
        FlowStep.WELCOME,
        FlowStep.USER_TYPE,
        FlowStep.CATEGORY,
        FlowStep.QUIZ,
        FlowStep.COLLECTING_CONTACTS,
        FlowStep.GENERATING_COMPLAINT,
        FlowStep.PREVIEW,        # Жалоба показывается ПЕРЕД выбором получателей
        FlowStep.RECIPIENTS,
        FlowStep.CONFIRM_SEND,
        FlowStep.SENDING,
        FlowStep.COMPLETE
    ]
    
    def __init__(self):
        self.agents = {
            "quiz": quiz_agent,
            "complaint": complaint_agent,
            "recipient": recipient_agent,
            "send": send_agent
        }
    
    def get_current_step(self, state: Dict) -> FlowStep:
        """Определяет текущий шаг на основе состояния"""
        
        step_str = state.get("step", "welcome")
        try:
            return FlowStep(step_str)
        except ValueError:
            return FlowStep.WELCOME
    
    def get_next_step(self, current_step: FlowStep) -> FlowStep:
        """Возвращает следующий шаг в flow"""
        
        try:
            current_idx = self.FLOW_ORDER.index(current_step)
            if current_idx < len(self.FLOW_ORDER) - 1:
                return self.FLOW_ORDER[current_idx + 1]
        except ValueError:
            pass
        
        return FlowStep.COMPLETE
    
    def get_previous_step(self, current_step: FlowStep) -> Optional[FlowStep]:
        """Возвращает предыдущий шаг для кнопки 'Назад'"""
        
        try:
            current_idx = self.FLOW_ORDER.index(current_step)
            if current_idx > 0:
                return self.FLOW_ORDER[current_idx - 1]
        except ValueError:
            pass
        
        return None
    
    def process(self, state: Dict, user_input: Optional[str] = None) -> Dict:
        """
        Основной метод обработки — роутинг к нужному агенту
        
        Args:
            state: Текущее состояние диалога
            user_input: Ввод пользователя (если есть)
            
        Returns:
            Ответ для отображения пользователю
        """
        
        current_step = self.get_current_step(state)
        
        # Роутинг к нужному обработчику
        handlers = {
            FlowStep.WELCOME: self._handle_welcome,
            FlowStep.USER_TYPE: self._handle_user_type,
            FlowStep.CATEGORY: self._handle_category,
            FlowStep.QUIZ: self._handle_quiz,
            FlowStep.COLLECTING_CONTACTS: self._handle_contacts,
            FlowStep.GENERATING_COMPLAINT: self._handle_generating,
            FlowStep.PREVIEW: self._handle_preview,
            FlowStep.RECIPIENTS: self._handle_recipients,
            FlowStep.CONFIRM_SEND: self._handle_confirm,
            FlowStep.SENDING: self._handle_sending,
            FlowStep.COMPLETE: self._handle_complete
        }
        
        handler = handlers.get(current_step, self._handle_welcome)
        return handler(state, user_input)
    
    def _handle_welcome(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Приветствие — выбор кто подаёт жалобу"""
        return {
            "message": "Здравствуйте! 👋\n\nЯ помогу вам составить и отправить жалобу.\n\n**Кто подаёт жалобу?**",
            "options": [
                {"id": "individual", "text": "👤 Лично от себя"},
                {"id": "organization", "text": "🏢 От имени организации / ИП"}
            ],
            "input_type": "options",
            "step": "user_type",
            "can_go_back": False
        }
    
    def _handle_user_type(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Выбран тип — показываем категории с учётом контекста"""
        user_type = state.get("data", {}).get("user_type", "individual")
        
        if user_type == "organization":
            options = [
                {"id": "contractor", "text": "🤝 Контрагент / Поставщик"},
                {"id": "government", "text": "🏛️ Госорган / Надзорный орган"},
                {"id": "tax", "text": "📋 Налоговая инспекция"},
                {"id": "bank", "text": "🏦 Банк / Лизинговая компания"},
                {"id": "landlord", "text": "🏢 Арендодатель / Арендатор"},
                {"id": "competitor", "text": "⚔️ Недобросовестная конкуренция"},
                {"id": "utilities", "text": "🔧 Коммунальные / Ресурсоснабжающие"},
                {"id": "subcontractor", "text": "👷 Подрядчик / Исполнитель"}
            ]
        else:
            options = [
                {"id": "zhkh", "text": "🏠 Управляющая компания / ЖКХ"},
                {"id": "employer", "text": "💼 Работодатель"},
                {"id": "shop", "text": "🛒 Магазин / Интернет-сервис"},
                {"id": "bank", "text": "🏦 Банк / МФО / Страховая"},
                {"id": "government", "text": "🏛️ Госорган / Чиновник"},
                {"id": "medical", "text": "🏥 Больница / Поликлиника"},
                {"id": "police_complaint", "text": "👮 Полиция (жалоба НА полицию)"},
                {"id": "neighbors", "text": "🏘️ Соседи"}
            ]
        
        return {
            "message": "**На кого хотите пожаловаться?**",
            "options": options,
            "input_type": "options",
            "step": "category",
            "can_go_back": True
        }
    
    def _handle_category(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Обработка выбора категории — переход к квизу"""
        
        # Получаем контекст для Quiz агента
        context = {
            "category": state.get("data", {}).get("category", "other"),
            "category_name": state.get("data", {}).get("category_name", ""),
            "user_type": state.get("data", {}).get("user_type", "individual"),
            "qa_pairs": state.get("qa_pairs", [])
        }
        
        # Вызываем Quiz агента
        result = self.agents["quiz"].process(context)
        
        # Конвертируем строковые опции в объекты {id, text}
        options = self._format_options(result.get("options"))
        
        return {
            "message": result.get("question", "Расскажите о вашей проблеме"),
            "options": options,
            "input_type": result.get("input_type", "options"),
            "step": "quiz",
            "can_go_back": True
        }
    
    def _handle_quiz(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Обработка квиза — вызов Quiz агента"""
        
        context = {
            "category": state.get("data", {}).get("category", "other"),
            "category_name": state.get("data", {}).get("category_name", ""),
            "user_type": state.get("data", {}).get("user_type", "individual"),
            "qa_pairs": state.get("qa_pairs", [])
        }
        
        result = self.agents["quiz"].process(context)
        
        if result.get("ready"):
            # Квиз завершён — переход к сбору контактов
            # Делегируем _handle_contacts чтобы показать правильный первый вопрос
            return self._handle_contacts(state, None)
        
        # Конвертируем строковые опции в объекты {id, text}
        options = self._format_options(result.get("options"))
        
        return {
            "message": result.get("question", "Продолжим..."),
            "options": options,
            "input_type": result.get("input_type", "options"),
            "step": "quiz",
            "can_go_back": True
        }
    
    def _format_options(self, options: Optional[List]) -> Optional[List[Dict]]:
        """Конвертирует опции в формат {id, text} для фронтенда"""
        if not options:
            return None
        
        formatted = []
        for i, opt in enumerate(options):
            if isinstance(opt, str):
                # Строка → объект
                formatted.append({"id": opt, "text": opt})
            elif isinstance(opt, dict):
                # Уже объект — оставляем как есть
                formatted.append(opt)
            else:
                formatted.append({"id": str(opt), "text": str(opt)})
        
        return formatted
    
    def _handle_contacts(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Сбор контактных данных"""
        
        user_data = state.get("data", {}).get("user_data", {})
        user_type = state.get("data", {}).get("user_type", "individual")
        
        if user_type == "organization":
            # Для юрлица: ИНН (DaData заполнит остальное) + контактный телефон
            if not user_data.get("org_name"):
                return {
                    "message": "**Введите ИНН или название вашей организации**\n\nМы автоматически подтянем все реквизиты.",
                    "input_type": "autocomplete_company",
                    "step": "collecting_contacts",
                    "can_go_back": True
                }
            
            if not user_data.get("phone"):
                return {
                    "message": "**Контактный телефон**",
                    "input_type": "text",
                    "step": "collecting_contacts",
                    "can_go_back": True
                }
        else:
            # Сбор данных физлица
            if not user_data.get("fio"):
                return {
                    "message": "**Как вас зовут?** (ФИО)",
                    "input_type": "autocomplete_fio",
                    "step": "collecting_contacts",
                    "can_go_back": True
                }
            
            if not user_data.get("address"):
                return {
                    "message": "**Ваш адрес проживания?**",
                    "input_type": "autocomplete_address",
                    "step": "collecting_contacts",
                    "can_go_back": True
                }
            
            if not user_data.get("phone"):
                return {
                    "message": "**Ваш телефон?**",
                    "input_type": "text",
                    "step": "collecting_contacts",
                    "can_go_back": True
                }
            
            if not user_data.get("email"):
                return {
                    "message": "**Ваш email?** (для получения копии жалобы)",
                    "input_type": "text",
                    "step": "collecting_contacts",
                    "can_go_back": True
                }
        
        # Все данные собраны — переход к генерации
        return {
            "message": "⏳ Генерирую текст жалобы...",
            "step": "generating_complaint",
            "is_loading": True,
            "can_go_back": True
        }
    
    def _handle_generating(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Генерация текста жалобы"""
        
        context = {
            "category_name": state.get("data", {}).get("category_name", ""),
            "qa_pairs": state.get("qa_pairs", []),
            "user_data": state.get("data", {}).get("user_data", {}),
            "company_data": state.get("data", {}).get("company_data", {})  # Реквизиты компании из DaData
        }
        
        result = self.agents["complaint"].process(context)
        
        if result.get("success"):
            complaint_text = result["complaint_text"]
            return {
                "message": f"✅ **Жалоба готова!** Проверьте текст:\n\n---\n\n{complaint_text}\n\n---",
                "complaint_text": complaint_text,
                "step": "preview",
                "input_type": "preview",
                "options": [
                    {"id": "approve", "text": "✅ Всё верно, продолжить"},
                    {"id": "edit", "text": "✏️ Хочу отредактировать"},
                    {"id": "regenerate", "text": "🔄 Сгенерировать заново"}
                ],
                "can_go_back": True
            }
        
        return {
            "message": "❌ Ошибка при генерации. Попробуем ещё раз?",
            "options": [
                {"id": "retry", "text": "🔄 Попробовать снова"},
                {"id": "back", "text": "◀️ Вернуться назад"}
            ],
            "step": "generating_complaint",
            "can_go_back": True
        }
    
    def _handle_preview(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Предпросмотр жалобы"""
        
        complaint_text = state.get("data", {}).get("complaint_text", "")
        
        return {
            "message": "**Текст жалобы:**\n\n" + complaint_text,
            "complaint_text": complaint_text,
            "step": "preview",
            "input_type": "preview",
            "options": [
                {"id": "approve", "text": "✅ Всё верно, выбрать получателей"},
                {"id": "edit", "text": "✏️ Отредактировать"},
                {"id": "regenerate", "text": "🔄 Сгенерировать заново"}
            ],
            "can_go_back": True
        }
    
    def _handle_recipients(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Выбор получателей — вызов Recipient агента + обогащение через Perplexity"""
        
        context = {
            "category": state.get("data", {}).get("category", "other"),
            "category_name": state.get("data", {}).get("category_name", ""),
            "qa_pairs": state.get("qa_pairs", []),
            "complaint_text": state.get("data", {}).get("complaint_text", ""),
            "user_data": state.get("data", {}).get("user_data", {}),  # Для определения региона заявителя
            "company_data": state.get("data", {}).get("company_data", {})  # Для определения подведомственности по адресу организации
        }
        
        result = self.agents["recipient"].process(context)
        recipients = result.get("recipients", [])
        
        # Обогащаем данными через Perplexity
        from services.contact_verification_service import contact_verification_service
        recipient_details = {}  # Кэш для PDF
        category_name = state.get("data", {}).get("category_name", "")
        
        options = []
        for rec in recipients:
            rec_id = rec["id"]
            rec_name = rec["name"]
            
            # Запрашиваем детальную информацию через Perplexity
            try:
                details = contact_verification_service.verify_and_get_contacts(rec_name, category_name)
                recipient_details[rec_id] = details  # Кэшируем для PDF
                print(f"[Orchestrator] Got details for {rec_name}: addr={details.get('address')}")
            except Exception as e:
                print(f"[Orchestrator] Failed to get details for {rec_name}: {e}")
                details = {}
            
            prefix = "⭐ " if rec.get("priority") == "primary" else ""
            options.append({
                "id": rec_id,
                "text": f"{prefix}{rec_name}",
                "name": rec_name,
                "description": rec.get("reason", ""),
                "reason": rec.get("reason", ""),
                "level": rec.get("level", ""),  # местный/региональный/федеральный
                "effectiveness": rec.get("effectiveness", ""),  # high/medium/low
                # Контакты из Perplexity
                "address": details.get("address"),
                "phone": details.get("phone"),
                "email": details.get("email") or rec.get("email"),
                "working_hours": details.get("working_hours"),
                "website": details.get("portal_url") or rec.get("website"),
                "portal_name": details.get("portal_name"),
                # Способы подачи
                "submission_methods": details.get("submission_methods", []),
                "auth_required": details.get("auth_required"),
                "documents_needed": details.get("documents_needed", []),
                "processing_time": details.get("processing_time"),
                # Советы
                "tips": details.get("tips"),
                "recommendation": details.get("recommendation")
            })
        
        options.append({"id": "custom", "text": "📧 Другой адрес (ввести вручную)"})
        
        # Сохраняем детали в state для использования при скачивании PDF
        if "data" not in state:
            state["data"] = {}
        state["data"]["recipient_details"] = recipient_details
        
        return {
            "message": "**Куда отправить жалобу?**\n\n🏠 местный — быстрее, знают специфику\n🏛️ региональный — если местный не помог\n🏛️ федеральный — серьёзные нарушения\n\n⭐ — рекомендуемые варианты:",
            "options": options,
            "input_type": "multiselect",
            "step": "recipients",
            "can_go_back": True
        }
    
    def _handle_confirm(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Подтверждение отправки"""
        
        selected = state.get("data", {}).get("selected_recipients", [])
        
        recipient_names = [r.get("name", r.get("id")) for r in selected]
        
        return {
            "message": f"**Готово к отправке!**\n\nПолучатели:\n" + "\n".join(f"• {name}" for name in recipient_names) + "\n\n**Отправить жалобу?**",
            "options": [
                {"id": "send", "text": "📤 Отправить"},
                {"id": "download", "text": "📥 Скачать PDF"},
                {"id": "back", "text": "◀️ Изменить получателей"}
            ],
            "input_type": "options",
            "step": "confirm_send",
            "can_go_back": True
        }
    
    def _handle_sending(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Отправка жалобы — подготовка результатов с обогащёнными данными"""
        
        context = {
            "complaint_text": state.get("data", {}).get("complaint_text", ""),
            "selected_recipients": state.get("data", {}).get("selected_recipients", []),
            "user_data": state.get("data", {}).get("user_data", {}),
            "category_name": state.get("data", {}).get("category_name", "")
        }
        
        result = self.agents["send"].process(context)
        
        if result.get("success"):
            results = result.get("results", [])
            
            # Обогащаем результаты данными из кэша recipient_details
            recipient_details = state.get("data", {}).get("recipient_details", {})
            enriched_results = []
            
            for r in results:
                rec_id = r.get("recipient_id", "")
                details = recipient_details.get(rec_id, {})
                
                enriched = {
                    **r,  # Базовые данные от агента
                    # Контакты из Perplexity
                    "address": details.get("address") or r.get("address"),
                    "phone": details.get("phone"),
                    "working_hours": details.get("working_hours"),
                    "website": details.get("portal_url") or r.get("website"),
                    "portal_name": details.get("portal_name"),
                    # Способы и требования
                    "submission_methods": details.get("submission_methods", []),
                    "auth_required": details.get("auth_required"),
                    "documents_needed": details.get("documents_needed", []),
                    "processing_time": details.get("processing_time"),
                    # Советы
                    "tips": details.get("tips"),
                    "recommendation": details.get("recommendation"),
                }
                enriched_results.append(enriched)
            
            message_parts = ["🎉 **Жалоба готова к отправке!**\n"]
            message_parts.append(f"Получателей: **{len(enriched_results)}**\n")
            message_parts.append("---\n")
            message_parts.append("Выберите удобный способ подачи для каждого органа ⬇️")
            
            return {
                "message": "".join(message_parts),
                "results": enriched_results,
                "input_type": "sending_results",
                "step": "complete",
                "can_go_back": False,
                "pdf_download_url": "/api/v2/download-pdf"
            }
        
        return {
            "message": "❌ Ошибка при подготовке отправки.",
            "step": "confirm_send",
            "can_go_back": True
        }
    
    def _handle_complete(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Завершение — показываем опции для нового диалога"""
        
        return {
            "message": "🎉 **Готово!**\n\nСпасибо за использование сервиса. Удачи с вашей жалобой!\n\nХотите подать ещё одну жалобу?",
            "options": [
                {"id": "new", "text": "📝 Новая жалоба"},
                {"id": "exit", "text": "👋 Выйти"}
            ],
            "input_type": "options",
            "step": "complete",
            "can_go_back": False
        }


# Singleton
orchestrator = Orchestrator()

