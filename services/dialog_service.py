"""
Сервис управления диалогом - ДИНАМИЧЕСКИЙ AI-DRIVEN ПОДХОД
LLM сам решает, какие вопросы задавать и когда информации достаточно
"""
import uuid
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from data.recipients import COMPLAINT_CATEGORIES, RECIPIENTS, RECIPIENT_RECOMMENDATIONS
from config import Config
from services.llm_service import llm_service


class DialogState:
    """Состояние диалога пользователя"""
    
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.step = "gathering"  # gathering -> recipients -> preview
        self.history: List[Dict] = []
        self.data: Dict[str, Any] = {}
        self.qa_pairs: List[Dict] = []  # Собранные вопросы-ответы
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "step": self.step,
            "history": self.history,
            "data": self.data,
            "qa_pairs": self.qa_pairs,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DialogState':
        state = cls()
        state.id = data.get("id", state.id)
        state.step = data.get("step", "gathering")
        state.history = data.get("history", [])
        state.data = data.get("data", {})
        state.qa_pairs = data.get("qa_pairs", [])
        state.created_at = data.get("created_at", state.created_at)
        state.updated_at = data.get("updated_at", state.updated_at)
        return state
    
    def add_message(self, role: str, content: str, options: Optional[List] = None, input_type: str = "options"):
        """Добавить сообщение в историю"""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        if role == "assistant":
            msg["options"] = options
            msg["input_type"] = input_type
        self.history.append(msg)
        self.updated_at = datetime.now().isoformat()
    
    def add_qa_pair(self, question: str, answer: str):
        """Добавить пару вопрос-ответ"""
        self.qa_pairs.append({
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_last_assistant_message(self) -> Optional[Dict]:
        """Получить последнее сообщение ассистента"""
        for msg in reversed(self.history):
            if msg["role"] == "assistant":
                return msg
        return None
    
    def go_back(self) -> bool:
        """Вернуться на шаг назад"""
        if len(self.history) < 2:
            return False
        
        # Удаляем последний ответ пользователя и последний вопрос ассистента
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()
        if self.history and self.history[-1]["role"] == "assistant":
            self.history.pop()
        
        # Удаляем последнюю пару Q&A
        if self.qa_pairs:
            self.qa_pairs.pop()
        
        # Если вернулись в начало, сбрасываем step
        if len(self.qa_pairs) == 0:
            self.step = "gathering"
        
        return True
    
    def get_conversation_context(self) -> str:
        """Получить контекст разговора для LLM"""
        context_parts = []
        for qa in self.qa_pairs:
            context_parts.append(f"Вопрос: {qa['question']}\nОтвет: {qa['answer']}")
        return "\n\n".join(context_parts)


class DialogService:
    """Сервис управления диалогом - AI-driven"""
    
    def __init__(self):
        self.drafts_dir = Config.DRAFTS_DIR
        os.makedirs(self.drafts_dir, exist_ok=True)
    
    def get_initial_message(self) -> Dict:
        """Получить приветственное сообщение"""
        options = [
            {"id": "zhkh", "text": "🏠 Управляющая компания / ЖКХ"},
            {"id": "employer", "text": "💼 Работодатель"},
            {"id": "shop", "text": "🛒 Интернет-магазин / сервис"},
            {"id": "bank", "text": "🏦 Банк / МФО"},
            {"id": "government", "text": "🏛️ Государственный орган / чиновник"},
            {"id": "neighbors", "text": "👥 Соседи"}
        ]
        
        return {
            "message": "Здравствуйте! 👋\n\nЯ помогу вам составить и отправить жалобу. Расскажите, на кого вы хотите пожаловаться?",
            "options": options,
            "input_type": "options",
            "step": "gathering"
        }
    
    def process_input(self, state: DialogState, user_input: str) -> Dict:
        """Обработать ввод пользователя и вернуть следующее сообщение"""
        
        current_step = state.step
        
        # Сохраняем сообщение пользователя
        state.add_message("user", user_input)
        
        # Сохраняем последний вопрос и ответ
        last_assistant = state.get_last_assistant_message()
        if last_assistant and current_step == "gathering":
            # Извлекаем текст вопроса (без форматирования)
            question = last_assistant.get("content", "").split("\n")[0]
            state.add_qa_pair(question, user_input)
        
        # Обрабатываем в зависимости от текущего шага
        if current_step == "gathering":
            return self._handle_gathering(state, user_input)
        elif current_step == "recipients":
            return self._handle_recipients(state, user_input)
        elif current_step == "preview":
            return self._handle_preview(state, user_input)
        elif current_step == "edit_complaint":
            return self._handle_edit_complaint(state, user_input)
        else:
            return self._handle_gathering(state, user_input)
    
    def _handle_gathering(self, state: DialogState, user_input: str) -> Dict:
        """
        Сбор информации через AI - LLM сам решает какие вопросы задавать
        """
        from services.llm_service import llm_service
        
        # Первый ответ - определяем категорию
        if len(state.qa_pairs) <= 1:
            category_id = user_input.lower()
            category = COMPLAINT_CATEGORIES.get(category_id)
            if category:
                state.data["category"] = category_id
                state.data["category_name"] = category["name"]
            else:
                state.data["category"] = "other"
                state.data["category_name"] = user_input
        
        # Спрашиваем у LLM, нужны ли ещё вопросы
        llm_response = llm_service.generate_next_question(state)
        
        if llm_response:
            if llm_response.get("ready", False):
                # LLM решил что информации достаточно - переходим к выбору получателей
                return self._transition_to_recipients(state)
            else:
                # LLM задаёт следующий вопрос
                question = llm_response.get("question", "Расскажите подробнее о ситуации")
                options = llm_response.get("options")
                
                # Используем input_type от LLM если есть, иначе определяем по options
                input_type = llm_response.get("input_type")
                if not input_type:
                    input_type = "options" if options else "textarea"
                
                # Для autocomplete не нужны options
                if input_type.startswith("autocomplete_"):
                    options = None
                
                # Форматируем опции
                formatted_options = None
                if options:
                    formatted_options = [{"id": opt, "text": opt} for opt in options]
                
                response = {
                    "message": question,
                    "options": formatted_options,
                    "input_type": input_type,
                    "step": "gathering"
                }
        else:
            # Fallback если LLM недоступен - используем базовые вопросы
            response = self._get_fallback_question(state, user_input)
        
        state.add_message("assistant", response["message"], response.get("options"), response["input_type"])
        return response
    
    def _get_fallback_question(self, state: DialogState, user_input: str) -> Dict:
        """Fallback вопросы если LLM недоступен"""
        qa_count = len(state.qa_pairs)
        category = state.data.get("category", "other")
        
        # Базовый набор вопросов
        questions = [
            {
                "message": "В чём именно заключается проблема? Опишите кратко.",
                "options": None,
                "input_type": "textarea",
                "step": "gathering"
            },
            {
                "message": "Когда это произошло? Выберите или напишите свой вариант:",
                "options": [
                    {"id": "today", "text": "Сегодня"},
                    {"id": "week", "text": "На этой неделе"},
                    {"id": "month", "text": "В этом месяце"},
                    {"id": "long", "text": "Давно (более месяца)"},
                ],
                "input_type": "options",
                "step": "gathering"
            },
            {
                "message": "Это единичный случай или проблема повторяется?",
                "options": [
                    {"id": "once", "text": "Один раз"},
                    {"id": "sometimes", "text": "Иногда повторяется"},
                    {"id": "often", "text": "Часто"},
                    {"id": "constant", "text": "Постоянно"}
                ],
                "input_type": "options",
                "step": "gathering"
            },
            {
                "message": "Вы уже обращались куда-то с этой проблемой?",
                "options": [
                    {"id": "no", "text": "Нет, это первое обращение"},
                    {"id": "yes_org", "text": "Да, в саму организацию"},
                    {"id": "yes_gov", "text": "Да, в госорганы"},
                    {"id": "yes_both", "text": "Да, и туда и туда"}
                ],
                "input_type": "options",
                "step": "gathering"
            },
            {
                "message": "Какой результат вы хотите получить?",
                "options": [
                    {"id": "fix", "text": "Исправить ситуацию"},
                    {"id": "compensate", "text": "Получить компенсацию"},
                    {"id": "punish", "text": "Наказать виновных"},
                    {"id": "all", "text": "Всё вышеперечисленное"}
                ],
                "input_type": "options",
                "step": "gathering"
            },
            {
                "message": "Есть ли у вас доказательства? (фото, видео, документы, свидетели)",
                "options": [
                    {"id": "yes_docs", "text": "Да, есть документы"},
                    {"id": "yes_photo", "text": "Да, есть фото/видео"},
                    {"id": "yes_witness", "text": "Есть свидетели"},
                    {"id": "no", "text": "Нет доказательств"}
                ],
                "input_type": "options",
                "step": "gathering"
            },
            {
                "message": "Укажите подробности: адрес, названия организаций, имена виновных лиц (если известны):",
                "options": None,
                "input_type": "textarea",
                "step": "gathering"
            }
        ]
        
        # Добавляем специфичные вопросы по категориям
        if category == "zhkh" and qa_count == 1:
            return {
                "message": "Уточните проблему с ЖКХ:",
                "options": [
                    {"id": "noise", "text": "🔊 Шум, нарушение тишины"},
                    {"id": "flooding", "text": "💧 Затопление, протечки"},
                    {"id": "garbage", "text": "🗑️ Не вывозят мусор"},
                    {"id": "heating", "text": "🌡️ Проблемы с отоплением"},
                    {"id": "elevator", "text": "🛗 Неисправный лифт"},
                    {"id": "overcharge", "text": "💸 Завышенные счета"},
                    {"id": "other", "text": "📝 Другое"}
                ],
                "input_type": "options",
                "step": "gathering"
            }
        elif category == "employer" and qa_count == 1:
            return {
                "message": "Какая проблема с работодателем?",
                "options": [
                    {"id": "salary", "text": "💰 Невыплата/задержка зарплаты"},
                    {"id": "dismissal", "text": "🚪 Незаконное увольнение"},
                    {"id": "schedule", "text": "⏰ Нарушение графика"},
                    {"id": "safety", "text": "⚠️ Нарушение охраны труда"},
                    {"id": "mobbing", "text": "😔 Травля, моббинг"},
                    {"id": "contract", "text": "📄 Нарушение договора"},
                    {"id": "other", "text": "📝 Другое"}
                ],
                "input_type": "options",
                "step": "gathering"
            }
        elif category == "shop" and qa_count == 1:
            return {
                "message": "Какая проблема с магазином/сервисом?",
                "options": [
                    {"id": "defect", "text": "🔧 Бракованный товар"},
                    {"id": "no_delivery", "text": "📦 Не доставили товар"},
                    {"id": "no_refund", "text": "💸 Не возвращают деньги"},
                    {"id": "fraud", "text": "🚨 Мошенничество"},
                    {"id": "warranty", "text": "🔨 Отказ в гарантии"},
                    {"id": "other", "text": "📝 Другое"}
                ],
                "input_type": "options",
                "step": "gathering"
            }
        elif category == "bank" and qa_count == 1:
            return {
                "message": "Какая проблема с банком/МФО?",
                "options": [
                    {"id": "fraud", "text": "💳 Мошенничество с картой"},
                    {"id": "loan", "text": "📉 Проблемы с кредитом"},
                    {"id": "collectors", "text": "📞 Давление коллекторов"},
                    {"id": "fees", "text": "💸 Скрытые комиссии"},
                    {"id": "data", "text": "🔐 Разглашение данных"},
                    {"id": "other", "text": "📝 Другое"}
                ],
                "input_type": "options",
                "step": "gathering"
            }
        
        # Если прошли достаточно вопросов - переходим к получателям
        if qa_count >= len(questions):
            return self._transition_to_recipients(state)
        
        return questions[min(qa_count, len(questions) - 1)]
    
    def _transition_to_recipients(self, state: DialogState) -> Dict:
        """Переход к выбору получателей (без сбора персональных данных)"""
        state.step = "recipients"
        
        # LLM анализирует ситуацию и рекомендует получателей
        context = {
            "category_name": state.data.get("category_name", ""),
            "qa_pairs": state.qa_pairs
        }
        
        llm_recommendations = llm_service.generate_recipients(context)
        
        options = []
        
        if llm_recommendations and llm_recommendations.get("recipients"):
            for rec_info in llm_recommendations["recipients"]:
                rec_id = rec_info.get("id")
                rec = RECIPIENTS.get(rec_id)
                is_primary = rec_info.get("priority") == "primary"
                
                if rec:
                    reason = rec_info.get("reason", rec.get("reason", ""))
                    options.append({
                        "id": rec_id,
                        "text": f"{'⭐ ' if is_primary else ''}{rec['name']}",
                        "description": reason,
                        "jurisdiction": rec.get("jurisdiction", ""),
                        "priority": "primary" if is_primary else "secondary"
                    })
                else:
                    name = rec_info.get("name", rec_id)
                    reason = rec_info.get("reason", "")
                    options.append({
                        "id": rec_id,
                        "text": f"{'⭐ ' if is_primary else ''}{name}",
                        "description": reason,
                        "jurisdiction": "",
                        "priority": "primary" if is_primary else "secondary",
                        "is_custom": True
                    })
        
        # Fallback
        if not options:
            category_id = state.data.get("category", "other")
            recommendations = RECIPIENT_RECOMMENDATIONS.get(category_id, {"primary": ["prosecution"], "secondary": []})
            
            for rec_id in recommendations["primary"] + recommendations["secondary"]:
                rec = RECIPIENTS.get(rec_id)
                if rec:
                    is_primary = rec_id in recommendations["primary"]
                    options.append({
                        "id": rec_id,
                        "text": f"{'⭐ ' if is_primary else ''}{rec['name']}",
                        "description": rec.get("reason", rec.get("description", "")),
                        "jurisdiction": rec.get("jurisdiction", ""),
                        "priority": "primary" if is_primary else "secondary"
                    })
        
        options.append({"id": "custom", "text": "📧 Другой адрес (ввести вручную)"})
        
        message = "Отлично, я собрал достаточно информации! 📝\n\n**Куда отправить жалобу?**\n\n⭐ — рекомендуемые получатели для вашей ситуации.\nПрочитайте описания и выберите подходящие:"
        
        response = {
            "message": message,
            "options": options,
            "input_type": "multiselect",
            "step": "recipients"
        }
        
        state.add_message("assistant", response["message"], response.get("options"), response["input_type"])
        return response
    
    def _handle_recipients(self, state: DialogState, user_input: str) -> Dict:
        """Обработка выбора получателей"""
        
        # Парсим выбранных получателей
        try:
            selected = json.loads(user_input) if user_input.startswith('[') else user_input.split(',')
        except:
            selected = [user_input]
        
        selected = [s.strip() for s in selected if s.strip()]
        
        # Собираем информацию о получателях
        selected_recipients = []
        for sel in selected:
            if sel == "custom":
                continue
            rec = RECIPIENTS.get(sel)
            if rec:
                selected_recipients.append({
                    "id": sel,
                    "name": rec["name"],
                    "email": rec["email"],
                    "website": rec["website"]
                })
        
        state.data["selected_recipients"] = selected_recipients
        state.step = "preview"
        
        # Генерируем текст жалобы БЕЗ персональных данных (с плейсхолдерами)
        from services.llm_service import llm_service
        
        context = {
            "category": state.data.get("category", "other"),
            "category_name": state.data.get("category_name", ""),
            "conversation": state.get_conversation_context(),
            "qa_pairs": state.qa_pairs
        }
        
        complaint_text = llm_service.generate_complaint_text(context)
        state.data["complaint_text"] = complaint_text
        
        # Формируем информацию о получателях для отображения
        recipients_info = []
        for rec in selected_recipients:
            if rec["email"]:
                recipients_info.append(f"• {rec['name']}: {rec['email']}")
            else:
                recipients_info.append(f"• {rec['name']}: через сайт {rec['website']}")
        
        recipients_text = "\n".join(recipients_info) if recipients_info else "Не выбраны"
        
        response = {
            "message": f"📋 **Предпросмотр жалобы**\n\n{complaint_text}\n\n---\n\n**Получатели:**\n{recipients_text}\n\n---\n\nВсё верно?",
            "options": [
                {"id": "send", "text": "✅ Отправить"},
                {"id": "edit", "text": "✏️ Редактировать текст"},
                {"id": "restart", "text": "🔄 Начать заново"}
            ],
            "input_type": "options",
            "step": "preview",
            "complaint_text": complaint_text
        }
        
        state.add_message("assistant", response["message"], response.get("options"), response["input_type"])
        return response
    
    def _handle_edit_complaint(self, state: DialogState, user_input: str) -> Dict:
        """Обработка редактирования текста жалобы"""
        state.data["complaint_text"] = user_input
        state.step = "preview"
        
        # Получаем получателей
        selected_recipients = state.data.get("selected_recipients", [])
        recipients_info = []
        for rec in selected_recipients:
            if rec.get("email"):
                recipients_info.append(f"• {rec['name']}: {rec['email']}")
            else:
                recipients_info.append(f"• {rec['name']}: через сайт {rec.get('website', '')}")
        
        recipients_text = "\n".join(recipients_info) if recipients_info else "Не выбраны"
        
        response = {
            "message": f"📋 **Обновлённый текст жалобы**\n\n{user_input}\n\n---\n\n**Получатели:**\n{recipients_text}\n\n---\n\nВсё верно?",
            "options": [
                {"id": "send", "text": "✅ Отправить"},
                {"id": "edit", "text": "✏️ Редактировать ещё"},
                {"id": "restart", "text": "🔄 Начать заново"}
            ],
            "input_type": "options",
            "step": "preview"
        }
        
        state.add_message("assistant", response["message"], response.get("options"), response["input_type"])
        return response
    
    def _handle_preview(self, state: DialogState, user_input: str) -> Dict:
        """Обработка действий на этапе предпросмотра"""
        
        if user_input == "send":
            from data.recipients import RECIPIENTS
            import urllib.parse
            
            recipients = state.data.get("selected_recipients", [])
            complaint_text = state.data.get("complaint_text", "")
            category_name = state.data.get("category_name", "Обращение")
            
            # Build sending results for each recipient
            results = []
            for rec in recipients:
                rec_id = rec.get("id", "")
                rec_db = RECIPIENTS.get(rec_id, {})
                rec_name = rec.get("name", rec_db.get("name", rec_id))
                rec_email = rec.get("email", rec_db.get("email", ""))
                rec_website = rec.get("website", rec_db.get("website", ""))
                
                # Build mailto link
                mailto_link = ""
                if rec_email:
                    subject = f"Жалоба: {category_name}"
                    body = complaint_text[:500] + ("\n\n[Полный текст — см. прикреплённый PDF]" if len(complaint_text) > 500 else "")
                    mailto_link = f"mailto:{rec_email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
                
                results.append({
                    "recipient_id": rec_id,
                    "recipient_name": rec_name,
                    "email": rec_email,
                    "website": rec_website,
                    "mailto_link": mailto_link,
                    "address": rec_db.get("address", ""),
                    "phone": rec_db.get("phone", ""),
                    "portal_name": rec_db.get("portal_name", ""),
                    "processing_time": rec_db.get("processing_time", "30 дней"),
                })
            
            state.data["sending_results"] = results
            state.step = "done"
            
            message_parts = ["🎉 **Жалоба готова к отправке!**\n"]
            message_parts.append(f"Получателей: **{len(results)}**\n")
            message_parts.append("---\n")
            message_parts.append("Выберите удобный способ подачи для каждого органа ⬇️")
            
            response = {
                "message": "".join(message_parts),
                "results": results,
                "input_type": "sending_results",
                "step": "done",
                "complaint_text": complaint_text
            }
        
        elif user_input == "edit":
            response = {
                "message": "Введите исправленный текст жалобы:",
                "options": None,
                "input_type": "textarea",
                "step": "edit_complaint",
                "current_text": state.data.get("complaint_text", "")
            }
            state.step = "edit_complaint"
        
        elif user_input == "restart":
            state.step = "gathering"
            state.data = {}
            state.history = []
            state.qa_pairs = []
            return self.get_initial_message()
        
        elif user_input == "retry":
            return self._handle_preview(state, "send")
        
        elif user_input == "copy":
            response = {
                "message": f"📋 **Текст жалобы для копирования:**\n\n```\n{state.data.get('complaint_text', '')}\n```",
                "options": [
                    {"id": "restart", "text": "📝 Подать ещё одну жалобу"},
                    {"id": "done", "text": "👍 Готово"}
                ],
                "input_type": "options",
                "step": "done"
            }
        
        else:
            response = {
                "message": "Выберите действие:",
                "options": [
                    {"id": "send", "text": "✅ Отправить"},
                    {"id": "edit", "text": "✏️ Редактировать текст"},
                    {"id": "restart", "text": "🔄 Начать заново"}
                ],
                "input_type": "options",
                "step": "preview"
            }
        
        state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
        return response
    
    def save_draft(self, state: DialogState) -> str:
        """Сохранить черновик"""
        draft_path = os.path.join(self.drafts_dir, f"{state.id}.json")
        with open(draft_path, 'w', encoding='utf-8') as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
        return state.id
    
    def load_draft(self, draft_id: str) -> Optional[DialogState]:
        """Загрузить черновик"""
        draft_path = os.path.join(self.drafts_dir, f"{draft_id}.json")
        if os.path.exists(draft_path):
            with open(draft_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return DialogState.from_dict(data)
        return None


# Singleton instance
dialog_service = DialogService()
