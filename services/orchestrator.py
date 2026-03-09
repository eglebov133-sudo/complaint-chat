"""
Оркестратор для управления субагентами
Координирует flow: Registration → Category → Quiz → Complaint → Preview → Recipients → Send
"""

from typing import Dict, Optional, List
from enum import Enum
from services.agents import quiz_agent, complaint_agent, recipient_agent, send_agent


class FlowStep(Enum):
    """Шаги процесса"""
    REGISTRATION = "registration"
    CATEGORY = "category"
    QUIZ = "quiz"
    GENERATING_COMPLAINT = "generating_complaint"
    PREVIEW = "preview"
    EDIT_COMPLAINT = "edit_complaint"
    RECIPIENTS = "recipients"
    CONFIRM_SEND = "confirm_send"
    SENDING = "sending"
    COMPLETE = "complete"


class Orchestrator:
    """
    Оркестратор управляет потоком работы и вызывает нужных агентов
    """
    
    FLOW_ORDER = [
        FlowStep.REGISTRATION,
        FlowStep.CATEGORY,
        FlowStep.QUIZ,
        FlowStep.GENERATING_COMPLAINT,
        FlowStep.PREVIEW,
        FlowStep.EDIT_COMPLAINT,
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
        step_str = state.get("step", "registration")
        try:
            return FlowStep(step_str)
        except ValueError:
            return FlowStep.REGISTRATION
    
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
        """
        current_step = self.get_current_step(state)
        
        handlers = {
            FlowStep.REGISTRATION: self._handle_registration,
            FlowStep.CATEGORY: self._handle_category_select,
            FlowStep.QUIZ: self._handle_quiz,
            FlowStep.GENERATING_COMPLAINT: self._handle_generating,
            FlowStep.PREVIEW: self._handle_preview,
            FlowStep.EDIT_COMPLAINT: self._handle_edit_complaint,
            FlowStep.RECIPIENTS: self._handle_recipients,
            FlowStep.CONFIRM_SEND: self._handle_confirm,
            FlowStep.SENDING: self._handle_sending,
            FlowStep.COMPLETE: self._handle_complete
        }
        
        handler = handlers.get(current_step, self._handle_registration)
        return handler(state, user_input)
    
    # ==================== REGISTRATION ====================
    
    def _handle_registration(self, state: Dict, user_input: Optional[str]) -> Dict:
        """
        Регистрация в чате — пошаговый сбор профиля.
        Если пользователь уже авторизован — пропускаем к категориям.
        """
        # Уже авторизован — пропускаем регистрацию
        if state.get("data", {}).get("is_authenticated"):
            return self._handle_category_select(state, None)
        
        reg = state.get("data", {}).get("registration", {})
        
        # Шаг 0: Согласие на обработку ПД (ФЗ-152)
        if not reg.get("consent_given"):
            return {
                "message": "⚖️ **Клик и Порядок** — бесплатный помощник для защиты ваших прав\n\n**Что я сделаю для вас:**\n• Выясню обстоятельства и составлю юридически грамотную жалобу\n• Подберу конкретные статьи законов под вашу ситуацию\n• Определю куда подавать — от районной инспекции до прокуратуры\n• Подготовлю готовый документ для отправки\n\n🕐 Занимает **5 минут** вместо часов изучения законов.\n\n💡 *Каждый гражданин РФ имеет право обращаться в государственные органы — это закреплено в ст. 33 Конституции. Пользуйтесь этим правом.*\n\nДля начала мне потребуются ваши данные (ФИО, адрес, контакты) — в соответствии с **ФЗ-152 «О персональных данных»**.\n\n• [Политика конфиденциальности](/privacy)  •  [Соглашение](/terms)",
                "options": [
                    {"id": "consent_accept", "text": "✅ Принимаю и начинаю"},
                    {"id": "consent_decline", "text": "❌ Не принимаю"}
                ],
                "input_type": "options",
                "step": "registration",
                "can_go_back": False
            }
        
        # Шаг 1: Тип пользователя
        if not reg.get("user_type"):
            return {
                "message": "Отлично! Давайте создадим ваш профиль. **Кто вы?**",
                "options": [
                    {"id": "individual", "text": "👤 Физическое лицо"},
                    {"id": "ip", "text": "📋 Индивидуальный предприниматель"},
                    {"id": "organization", "text": "🏢 Юридическое лицо"}
                ],
                "input_type": "options",
                "step": "registration",
                "can_go_back": False
            }
        
        # Шаг 2: ФИО
        if not reg.get("fio"):
            return {
                "message": "**Ваши фамилия, имя, отчество?**",
                "input_type": "autocomplete_fio",
                "step": "registration",
                "can_go_back": False
            }
        
        # Шаг 3: Адрес
        if not reg.get("address"):
            return {
                "message": "**Ваш адрес?**",
                "input_type": "autocomplete_address",
                "step": "registration",
                "can_go_back": False
            }
        
        # Шаг 4: Телефон
        if not reg.get("phone"):
            return {
                "message": "**Ваш телефон?**",
                "input_type": "text",
                "step": "registration",
                "can_go_back": False
            }
        
        # Шаг 5: Email
        if not reg.get("email"):
            return {
                "message": "**Ваш email?** (будет использоваться для входа)",
                "input_type": "text",
                "step": "registration",
                "can_go_back": False
            }
        
        # Шаг 6: Пароль
        if not reg.get("password"):
            return {
                "message": "**Придумайте пароль** (минимум 6 символов)",
                "input_type": "password",
                "step": "registration",
                "can_go_back": False
            }
        
        # Шаги для юрлица / ИП
        if reg["user_type"] in ("organization", "ip"):
            if not reg.get("org_inn"):
                return {
                    "message": "**ИНН или название вашей организации?**\n\nМы автоматически подтянем реквизиты.",
                    "input_type": "autocomplete_company",
                    "step": "registration",
                    "can_go_back": False
                }
            
            if not reg.get("position"):
                return {
                    "message": "**Ваша должность?**",
                    "input_type": "text",
                    "step": "registration",
                    "can_go_back": False
                }
        
        # Все данные собраны — регистрация произойдёт в app.py
        # Переходим к категориям
        return {
            "message": "registration_complete",
            "step": "registration_complete",
            "can_go_back": False
        }
    
    # ==================== CATEGORY ====================
    
    def _handle_category_select(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Показываем категории с учётом типа пользователя"""
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
            "can_go_back": False
        }
    
    # ==================== QUIZ ====================
    
    def _handle_category(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Обработка выбора категории — первый вопрос квиза"""
        context = {
            "category": state.get("data", {}).get("category", "other"),
            "category_name": state.get("data", {}).get("category_name", ""),
            "user_type": state.get("data", {}).get("user_type", "individual"),
            "qa_pairs": state.get("qa_pairs", []),
            "company_data": state.get("data", {}).get("company_data", {}),
            "user_data": state.get("data", {}).get("user_data", {})
        }
        
        result = self.agents["quiz"].process(context)
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
            "qa_pairs": state.get("qa_pairs", []),
            "company_data": state.get("data", {}).get("company_data", {}),
            "user_data": state.get("data", {}).get("user_data", {})
        }
        
        result = self.agents["quiz"].process(context)
        
        if result.get("ready"):
            # Квиз завершён — переход к генерации жалобы (без сбора контактов)
            return self._handle_generating(state, None)
        
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
                formatted.append({"id": opt, "text": opt})
            elif isinstance(opt, dict):
                formatted.append(opt)
            else:
                formatted.append({"id": str(opt), "text": str(opt)})
        
        return formatted
    
    # ==================== COMPLAINT GENERATION ====================
    
    def _handle_generating(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Генерация текста жалобы"""
        context = {
            "category_name": state.get("data", {}).get("category_name", ""),
            "qa_pairs": state.get("qa_pairs", []),
            "user_data": state.get("data", {}).get("user_data", {}),
            "company_data": state.get("data", {}).get("company_data", {})
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
                    {"id": "edit", "text": "✏️ Хочу внести правки"}
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
    
    # ==================== PREVIEW ====================
    
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
                {"id": "edit", "text": "✏️ Хочу внести правки"}
            ],
            "can_go_back": True
        }
    
    def _handle_edit_complaint(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Обработка правок пользователя — перегенерация жалобы с учётом замечаний"""
        if not user_input or user_input == "edit":
            # Показываем приглашение к вводу замечаний
            return {
                "message": "✏️ **Внесите ваши правки**\n\nОпишите, что нужно изменить, добавить или убрать из текста жалобы. Например:\n• _Добавить информацию о свидетелях_\n• _Убрать абзац про моральный ущерб_\n• _Уточнить дату — это было 15 марта, а не 10_\n• _Более жёсткий тон в требованиях_\n\nНапишите ваши замечания и я перегенерирую жалобу с их учётом:",
                "input_type": "textarea",
                "step": "edit_complaint",
                "can_go_back": True
            }
        
        # Пользователь прислал замечания — перегенерируем жалобу
        context = {
            "category_name": state.get("data", {}).get("category_name", ""),
            "qa_pairs": state.get("qa_pairs", []),
            "user_data": state.get("data", {}).get("user_data", {}),
            "company_data": state.get("data", {}).get("company_data", {}),
            "previous_complaint": state.get("data", {}).get("complaint_text", ""),
            "user_edits": user_input
        }
        
        result = self.agents["complaint"].process(context)
        
        if result.get("success"):
            complaint_text = result["complaint_text"]
            return {
                "message": f"✅ **Жалоба обновлена с учётом ваших правок!** Проверьте текст:\n\n---\n\n{complaint_text}\n\n---",
                "complaint_text": complaint_text,
                "step": "preview",
                "input_type": "preview",
                "options": [
                    {"id": "approve", "text": "✅ Всё верно, продолжить"},
                    {"id": "edit", "text": "✏️ Хочу внести ещё правки"}
                ],
                "can_go_back": True
            }
        
        return {
            "message": "❌ Ошибка при обновлении жалобы. Попробуем ещё раз?",
            "options": [
                {"id": "retry", "text": "🔄 Попробовать снова"},
                {"id": "back", "text": "◀️ Вернуться назад"}
            ],
            "step": "edit_complaint",
            "can_go_back": True
        }
    
    # ==================== RECIPIENTS ====================
    
    def _handle_recipients(self, state: Dict, user_input: Optional[str]) -> Dict:
        """Выбор получателей — вызов Recipient агента + обогащение через Perplexity"""
        context = {
            "category": state.get("data", {}).get("category", "other"),
            "category_name": state.get("data", {}).get("category_name", ""),
            "qa_pairs": state.get("qa_pairs", []),
            "complaint_text": state.get("data", {}).get("complaint_text", ""),
            "user_data": state.get("data", {}).get("user_data", {}),
            "company_data": state.get("data", {}).get("company_data", {})
        }
        
        result = self.agents["recipient"].process(context)
        recipients = result.get("recipients", [])
        
        # Обогащаем данными через Perplexity
        from services.contact_verification_service import contact_verification_service
        recipient_details = {}
        category_name = state.get("data", {}).get("category_name", "")
        
        options = []
        for rec in recipients:
            rec_id = rec["id"]
            rec_name = rec["name"]
            
            try:
                details = contact_verification_service.verify_and_get_contacts(rec_name, category_name)
                recipient_details[rec_id] = details
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
                "level": rec.get("level", ""),
                "effectiveness": rec.get("effectiveness", ""),
                "address": details.get("address"),
                "phone": details.get("phone"),
                "email": details.get("email") or rec.get("email"),
                "working_hours": details.get("working_hours"),
                "website": details.get("portal_url") or rec.get("website"),
                "portal_name": details.get("portal_name"),
                "submission_methods": details.get("submission_methods", []),
                "auth_required": details.get("auth_required"),
                "documents_needed": details.get("documents_needed", []),
                "processing_time": details.get("processing_time"),
                "tips": details.get("tips"),
                "recommendation": details.get("recommendation")
            })
        
        options.append({"id": "custom", "text": "📧 Другой адрес (ввести вручную)"})
        
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
    
    # ==================== CONFIRM & SEND ====================
    
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
            
            recipient_details = state.get("data", {}).get("recipient_details", {})
            enriched_results = []
            
            for r in results:
                rec_id = r.get("recipient_id", "")
                details = recipient_details.get(rec_id, {})
                
                enriched = {
                    **r,
                    "address": details.get("address") or r.get("address"),
                    "phone": details.get("phone"),
                    "working_hours": details.get("working_hours"),
                    "website": details.get("portal_url") or r.get("website"),
                    "portal_name": details.get("portal_name"),
                    "submission_methods": details.get("submission_methods", []),
                    "auth_required": details.get("auth_required"),
                    "documents_needed": details.get("documents_needed", []),
                    "processing_time": details.get("processing_time"),
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
