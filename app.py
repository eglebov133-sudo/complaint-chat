"""
Помощник по жалобам — Flask Application
Чат-квиз для составления и отправки жалоб
"""
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from services.dialog_service import dialog_service, DialogState
from services.dadata_service import dadata_service

# Создаём приложение
app = Flask(__name__)
app.config.from_object(Config)

# Инициализируем сессии (файловая система)
os.makedirs(Config.SESSION_FILE_DIR, exist_ok=True)
Session(app)

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"]
)


# ==================== ROUTES ====================

@app.route('/')
def index():
    """Главная страница с чатом"""
    # Инициализируем новый диалог если нет в сессии
    if 'dialog_state' not in session:
        state = DialogState()
        initial = dialog_service.get_initial_message()
        state.add_message("assistant", initial["message"], initial.get("options"), initial.get("input_type", "options"))
        state.step = initial["step"]
        session['dialog_state'] = state.to_dict()
    
    return render_template('index.html')


@app.route('/api/state', methods=['GET'])
def get_state():
    """Получить текущее состояние диалога"""
    if 'dialog_state' not in session:
        state = DialogState()
        initial = dialog_service.get_initial_message()
        state.add_message("assistant", initial["message"], initial.get("options"), initial.get("input_type", "options"))
        state.step = initial["step"]
        session['dialog_state'] = state.to_dict()
    else:
        state = DialogState.from_dict(session['dialog_state'])
    
    return jsonify({
        "history": state.history,
        "step": state.step,
        "data": state.data
    })


@app.route('/api/chat', methods=['POST'])
@limiter.limit("30 per minute")
def chat():
    """Обработка сообщения пользователя"""
    data = request.get_json()
    user_input = data.get('message', '').strip()
    company_data = data.get('company_data')  # Data from autocomplete
    
    if not user_input:
        return jsonify({"error": "Пустое сообщение"}), 400
    
    # Загружаем состояние
    if 'dialog_state' not in session:
        return jsonify({"error": "Сессия не найдена. Обновите страницу."}), 400
    
    state = DialogState.from_dict(session['dialog_state'])
    
    # Если есть данные компании из автокомплита, сохраняем их
    if company_data:
        state.data['company_data'] = company_data
        print(f"[DEBUG] company_data saved to state: {company_data}")
    
    # Обрабатываем ввод
    response = dialog_service.process_input(state, user_input)
    
    # Сохраняем состояние
    session['dialog_state'] = state.to_dict()
    session.modified = True
    
    return jsonify({
        "message": response["message"],
        "options": response.get("options"),
        "input_type": response.get("input_type", "options"),
        "step": response.get("step"),
        "complaint_text": response.get("complaint_text"),
        "current_text": response.get("current_text")
    })


@app.route('/api/back', methods=['POST'])
def go_back():
    """Вернуться на шаг назад"""
    if 'dialog_state' not in session:
        return jsonify({"error": "Сессия не найдена"}), 400
    
    state = DialogState.from_dict(session['dialog_state'])
    
    if state.go_back():
        session['dialog_state'] = state.to_dict()
        session.modified = True
        
        return jsonify({
            "success": True,
            "history": state.history,
            "step": state.step
        })
    else:
        return jsonify({"success": False, "error": "Невозможно вернуться назад"})


@app.route('/api/restart', methods=['POST'])
def restart():
    """Начать диалог заново"""
    state = DialogState()
    initial = dialog_service.get_initial_message()
    state.add_message("assistant", initial["message"], initial.get("options"), initial.get("input_type", "options"))
    state.step = initial["step"]
    session['dialog_state'] = state.to_dict()
    session.modified = True
    
    return jsonify({
        "success": True,
        "history": state.history,
        "step": state.step
    })


@app.route('/api/save-draft', methods=['POST'])
def save_draft():
    """Сохранить черновик"""
    if 'dialog_state' not in session:
        return jsonify({"error": "Сессия не найдена"}), 400
    
    state = DialogState.from_dict(session['dialog_state'])
    draft_id = dialog_service.save_draft(state)
    
    return jsonify({
        "success": True,
        "draft_id": draft_id,
        "url": f"/draft/{draft_id}"
    })


@app.route('/draft/<draft_id>')
def load_draft(draft_id):
    """Загрузить черновик"""
    state = dialog_service.load_draft(draft_id)
    
    if state:
        session['dialog_state'] = state.to_dict()
        session.modified = True
        return redirect(url_for('index'))
    else:
        return "Черновик не найден", 404


@app.route('/api/send', methods=['POST'])
@limiter.limit("5 per minute")
def send_complaint():
    """Отправить жалобу (отдельный endpoint с жёстким rate limiting)"""
    if 'dialog_state' not in session:
        return jsonify({"error": "Сессия не найдена"}), 400
    
    state = DialogState.from_dict(session['dialog_state'])
    
    # Обрабатываем как команду "send"
    response = dialog_service.process_input(state, "send")
    
    session['dialog_state'] = state.to_dict()
    session.modified = True
    
    return jsonify({
        "message": response["message"],
        "options": response.get("options"),
        "input_type": response.get("input_type", "options"),
        "step": response.get("step")
    })


# ==================== AUTOCOMPLETE API ====================

@app.route('/api/suggest/company', methods=['GET'])
@limiter.limit("60 per minute")
def suggest_company():
    """Поиск компаний по названию или ИНН"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify({"suggestions": []})
    
    # Если похоже на ИНН (только цифры), ищем по ИНН
    if query.isdigit() and len(query) >= 10:
        company = dadata_service.find_company_by_inn(query)
        if company:
            return jsonify({"suggestions": [company]})
        return jsonify({"suggestions": []})
    
    # Иначе ищем по названию
    suggestions = dadata_service.suggest_company(query, count=7)
    return jsonify({"suggestions": suggestions})


@app.route('/api/suggest/address', methods=['GET'])
@limiter.limit("60 per minute")
def suggest_address():
    """Подсказки адресов"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 3:
        return jsonify({"suggestions": []})
    
    suggestions = dadata_service.suggest_address(query, count=7)
    return jsonify({"suggestions": suggestions})


@app.route('/api/suggest/fio', methods=['GET'])
@limiter.limit("60 per minute")
def suggest_fio():
    """Подсказки ФИО"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify({"suggestions": []})
    
    suggestions = dadata_service.suggest_fio(query, count=5)
    return jsonify({"suggestions": suggestions})


# ==================== API V2 (Orchestrator) ====================

from services.orchestrator import orchestrator, FlowStep

class DialogStateV2:
    """Состояние диалога для v2 (с оркестратором)"""
    
    def __init__(self):
        import uuid
        from datetime import datetime
        self.id = str(uuid.uuid4())
        self.step = "welcome"
        self.history = []
        self.data = {}
        self.qa_pairs = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self):
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
    def from_dict(cls, data):
        state = cls()
        state.id = data.get("id", state.id)
        state.step = data.get("step", "welcome")
        state.history = data.get("history", [])
        state.data = data.get("data", {})
        state.qa_pairs = data.get("qa_pairs", [])
        state.created_at = data.get("created_at", state.created_at)
        state.updated_at = data.get("updated_at", state.updated_at)
        return state
    
    def add_message(self, role, content, options=None, input_type="options"):
        from datetime import datetime
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
    
    def add_qa_pair(self, question, answer):
        from datetime import datetime
        self.qa_pairs.append({
            "question": question,
            "answer": answer,
            "timestamp": datetime.now().isoformat()
        })


@app.route('/v2')
def index_v2():
    """Главная страница v2 с оркестратором"""
    if 'dialog_state_v2' not in session:
        state = DialogStateV2()
        response = orchestrator.process(state.to_dict())
        state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
        state.step = response.get("step", "welcome")
        session['dialog_state_v2'] = state.to_dict()
    
    return render_template('index.html', version="v2")


@app.route('/api/v2/state', methods=['GET'])
def get_state_v2():
    """Получить состояние для v2"""
    if 'dialog_state_v2' not in session:
        state = DialogStateV2()
        response = orchestrator.process(state.to_dict())
        state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
        state.step = response.get("step", "welcome")
        session['dialog_state_v2'] = state.to_dict()
    else:
        state = DialogStateV2.from_dict(session['dialog_state_v2'])
    
    return jsonify({
        "history": state.history,
        "step": state.step,
        "data": state.data
    })


@app.route('/api/v2/chat', methods=['POST'])
@limiter.limit("30 per minute")
def chat_v2():
    """Обработка сообщения через оркестратор"""
    try:
        data = request.get_json()
        user_input = data.get('message', '').strip()
        company_data = data.get('company_data')  # Данные компании из автокомплита
        
        if not user_input:
            return jsonify({"error": "Пустое сообщение"}), 400
        
        if 'dialog_state_v2' not in session:
            return jsonify({"error": "Сессия не найдена. Обновите страницу."}), 400
        
        state = DialogStateV2.from_dict(session['dialog_state_v2'])
        current_step = state.step
        
        # Сохраняем данные из DaData если пришли (объединяем, а не перезаписываем)
        if company_data:
            existing = state.data.get('company_data', {})
            # Если это данные о компании (есть inn) — сохраняем их
            if company_data.get('inn'):
                existing.update(company_data)
            # Если это данные об адресе/ФИО — добавляем к существующим
            elif company_data.get('fio'):
                existing['user_fio'] = company_data.get('fio')
            elif company_data.get('address') and not company_data.get('inn'):
                existing['user_address'] = company_data.get('address')
            else:
                existing.update(company_data)
            state.data['company_data'] = existing
            print(f"[DEBUG] v2: company_data merged: {existing}")
        
        # Сохраняем ввод пользователя
        state.add_message("user", user_input)
        
        # Обрабатываем в зависимости от шага
        if current_step == "user_type":
            # Выбран тип заявителя — сохраняем (шаг обновит оркестратор)
            state.data["user_type"] = user_input  # "individual" или "organization"
        
        elif current_step == "category":
            # Выбрана категория — сохраняем и переходим к quiz
            from data.recipients import COMPLAINT_CATEGORIES
            category = COMPLAINT_CATEGORIES.get(user_input.lower(), {})
            state.data["category"] = user_input.lower()
            state.data["category_name"] = category.get("name", user_input)
            state.step = "quiz"
        
        elif current_step == "quiz":
            # Сохраняем Q&A
            last_assistant = None
            for msg in reversed(state.history):
                if msg["role"] == "assistant":
                    last_assistant = msg
                    break
            if last_assistant:
                question = last_assistant["content"].split("\n")[0]
                state.add_qa_pair(question, user_input)
        
        elif current_step == "collecting_contacts":
            if not state.data.get("user_data"):
                state.data["user_data"] = {}
            ud = state.data["user_data"]
            user_type = state.data.get("user_type", "individual")
            
            if user_type == "organization":
                # ИНН → DaData заполнит остальное, потом телефон
                if not ud.get("org_name"):
                    ud["org_name"] = user_input
                    # DaData данные: ИНН, адрес, руководитель и т.д.
                    if company_data:
                        if company_data.get("inn"):
                            ud["org_inn"] = company_data["inn"]
                        if company_data.get("address"):
                            ud["address"] = company_data["address"]
                        if company_data.get("director"):
                            ud["fio"] = company_data["director"]
                            ud["position"] = company_data.get("director_post", "Руководитель")
                elif not ud.get("phone"):
                    ud["phone"] = user_input
                    state.step = "generating_complaint"
            else:
                # Физлицо: fio → address → phone → email
                if not ud.get("fio"):
                    ud["fio"] = user_input
                elif not ud.get("address"):
                    ud["address"] = user_input
                elif not ud.get("phone"):
                    ud["phone"] = user_input
                elif not ud.get("email"):
                    ud["email"] = user_input
                    state.step = "generating_complaint"
        
        elif current_step == "preview":
            if user_input == "approve":
                state.step = "recipients"
            elif user_input == "regenerate":
                state.step = "generating_complaint"
        
        elif current_step == "recipients" and user_input not in ["approve", "regenerate"]:
            from data.recipients import RECIPIENTS
            print(f"[DEBUG] Recipients user_input: {user_input}")
            selected_ids = [r.strip() for r in user_input.split(",")]
            print(f"[DEBUG] Selected IDs: {selected_ids}")
            
            # Получаем сохранённые опции получателей (содержат имена от RecipientAgent)
            recipient_options = state.data.get("recipient_options", [])
            recipient_map = {opt.get("id"): opt for opt in recipient_options}
            
            selected = []
            for rid in selected_ids:
                # Сначала ищем в опциях от RecipientAgent (имеют правильные имена)
                if rid in recipient_map:
                    opt = recipient_map[rid]
                    # Извлекаем имя без звёздочки-префикса
                    name = opt.get("text", rid)
                    if name.startswith("⭐ "):
                        name = name[2:]
                    selected.append({
                        "id": rid, 
                        "name": name,
                        "email": opt.get("email"),
                        "website": opt.get("website")
                    })
                else:
                    # Fallback на базу RECIPIENTS
                    rec = RECIPIENTS.get(rid, {"id": rid, "name": rid})
                    print(f"[DEBUG] rid={rid}, rec={rec}")
                    selected.append({
                        "id": rid, 
                        "name": rec.get("name", rid), 
                        "email": rec.get("email"),
                        "website": rec.get("website")
                    })
            print(f"[DEBUG] Final selected: {selected}")
            state.data["selected_recipients"] = selected
            state.step = "confirm_send"
        
        elif current_step == "confirm_send":
            if user_input == "send":
                state.step = "sending"
            elif user_input == "back":
                state.step = "recipients"
        
        # Вызываем оркестратор
        response = orchestrator.process(state.to_dict(), user_input)
        
        # Сохраняем результат генерации жалобы
        if response.get("complaint_text"):
            state.data["complaint_text"] = response["complaint_text"]
        
        # Сохраняем опции получателей чтобы потом извлечь имена
        if response.get("step") == "recipients" and response.get("options"):
            state.data["recipient_options"] = response["options"]
        
        # Обновляем шаг
        state.step = response.get("step", state.step)
        
        # Добавляем ответ в историю
        state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
        
        # Сохраняем состояние
        session['dialog_state_v2'] = state.to_dict()
        session.modified = True
        
        return jsonify({
            "message": response["message"],
            "options": response.get("options"),
            "input_type": response.get("input_type", "options"),
            "step": response.get("step"),
            "complaint_text": response.get("complaint_text"),
            "can_go_back": response.get("can_go_back", True),
            "results": response.get("results"),
            "pdf_download_url": response.get("pdf_download_url")
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Ошибка: {str(e)}"}), 500


# ==================== TEST ENDPOINTS ====================

@app.route('/test/preview')
def test_preview():
    """Тестовый endpoint — сразу на этап превью"""
    
    complaint_text = """В Прокуратуру РФ

от Иванова Ивана Ивановича
проживающего по адресу: г. Москва, ул. Тестовая, д. 1, кв. 1
тел.: +7 999 123-45-67
email: test@test.ru

ЖАЛОБА
(на нарушение прав потребителя)

Я, Иванов Иван Иванович, обращаюсь к Вам с жалобой на действия ООО "Рога и Копыта" (ИНН 1234567890).

15 января 2026 года я приобрёл в данном магазине товар (смартфон) стоимостью 50 000 рублей. При проверке дома обнаружилось, что товар неисправен — не работает экран.

Я обратился в магазин с требованием о возврате денежных средств, однако мне было отказано без объяснения причин.

ПРОШУ:
1. Провести проверку деятельности ООО "Рога и Копыта"
2. Привлечь виновных к ответственности
3. Обязать вернуть мне денежные средства в размере 50 000 рублей"""
    
    state = DialogStateV2()
    state.step = "preview"
    state.data = {
        "category": "consumer_rights",
        "category_name": "Защита прав потребителей",
        "user_data": {
            "fio": "Иванов Иван Иванович",
            "address": "г. Москва, ул. Тестовая, д. 1, кв. 1",
            "phone": "+7 999 123-45-67",
            "email": "test@test.ru"
        },
        "complaint_text": complaint_text
    }
    
    # Добавляем сообщение с превью
    preview_options = [
        {"id": "approve", "text": "✅ Одобрить и продолжить"},
        {"id": "edit", "text": "✏️ Редактировать"},
        {"id": "regenerate", "text": "🔄 Сгенерировать заново"}
    ]
    state.add_message("assistant", f"✅ **Жалоба готова!** Проверьте текст:\n\n---\n\n{complaint_text}\n\n---", preview_options, "preview")
    
    session['dialog_state_v2'] = state.to_dict()
    session.modified = True
    
    return redirect('/v2')


@app.route('/test/recipients')
def test_recipients():
    """Тестовый endpoint — сразу на этап выбора получателей"""
    
    state = DialogStateV2()
    state.step = "recipients"
    state.data = {
        "category": "consumer_rights",
        "category_name": "Защита прав потребителей",
        "user_data": {
            "fio": "Иванов Иван Иванович",
            "address": "г. Москва, ул. Тестовая, д. 1, кв. 1",
            "phone": "+7 999 123-45-67",
            "email": "test@test.ru"
        },
        "complaint_text": "Тестовая жалоба на нарушение прав потребителя..."
    }
    
    # Получаем рекомендации от orchestrator
    response = orchestrator.process(state.to_dict())
    state.add_message("assistant", response.get("message", "Выберите получателей"), response.get("options"), response.get("input_type", "multiselect"))
    
    session['dialog_state_v2'] = state.to_dict()
    session.modified = True
    
    return redirect('/v2')


@app.route('/test/sending')
def test_sending():
    """Тестовый endpoint — сразу на этап отправки"""
    
    state = DialogStateV2()
    state.step = "sending"
    state.data = {
        "category": "consumer_rights",
        "category_name": "Защита прав потребителей",
        "user_data": {
            "fio": "Иванов Иван Иванович",
            "address": "г. Москва, ул. Тестовая, д. 1, кв. 1",
            "phone": "+7 999 123-45-67",
            "email": "test@test.ru"
        },
        "complaint_text": "Тестовая жалоба на нарушение прав потребителя...",
        "selected_recipients": [
            {"id": "prosecution", "name": "Прокуратура РФ", "email": "genproc@genproc.gov.ru", "website": "https://epp.genproc.gov.ru"},
            {"id": "rospotrebnadzor", "name": "Роспотребнадзор", "email": "depart@gsen.ru", "website": "https://petition.rospotrebnadzor.ru"}
        ]
    }
    
    # Добавляем историю чтобы frontend мог отобразить
    state.add_message("assistant", "🔔 **Тестовый режим**: Этап отправки\n\nВыбранные получатели: Прокуратура РФ, Роспотребнадзор")
    
    # Запускаем orchestrator чтобы получить результаты отправки
    response = orchestrator.process(state.to_dict(), "send")
    state.add_message("assistant", response.get("message", "Готово!"), response.get("options"), response.get("input_type", "sending_results"))
    
    # Сохраняем results для frontend
    if response.get("results"):
        state.data["sending_results"] = response["results"]
    
    session['dialog_state_v2'] = state.to_dict()
    session.modified = True
    
    return redirect('/v2')


@app.route('/api/v2/reset', methods=['POST'])
def reset_v2():
    """Сбросить состояние v2"""
    if 'dialog_state_v2' in session:
        del session['dialog_state_v2']
    session.modified = True
    return jsonify({"success": True})


@app.route('/api/v2/download-pdf')
def download_pdf_v2():
    """Скачать жалобу в формате PDF для конкретного получателя"""
    from flask import send_file
    from io import BytesIO
    from services.pdf_service import pdf_service
    
    if 'dialog_state_v2' not in session:
        return jsonify({"error": "Сессия не найдена"}), 400
    
    state_dict = session['dialog_state_v2']
    
    complaint_text = state_dict.get("data", {}).get("complaint_text", "")
    user_data = state_dict.get("data", {}).get("user_data", {})
    category_name = state_dict.get("data", {}).get("category_name", "")
    selected_recipients = state_dict.get("data", {}).get("selected_recipients", [])
    
    if not complaint_text:
        return jsonify({"error": "Текст жалобы не найден"}), 400
    
    # Получаем recipient_id из параметров запроса
    recipient_id = request.args.get('recipient_id', '')
    
    # Находим получателя по ID или берём первого
    recipient_name = "Государственный орган"
    if recipient_id and selected_recipients:
        for r in selected_recipients:
            if r.get("id") == recipient_id:
                recipient_name = r.get("name", recipient_name)
                break
    elif selected_recipients:
        recipient_name = selected_recipients[0].get("name", recipient_name)
    
    # Получаем адрес органа из кэша (сохранён при показе списка получателей) или запрашиваем
    recipient_address = ""
    try:
        # Сначала пробуем кэш из state (сохранён в _handle_recipients)
        recipient_details = state_dict.get("data", {}).get("recipient_details", {})
        cached = recipient_details.get(recipient_id, {})
        
        if cached and cached.get("address"):
            recipient_address = cached["address"]
            print(f"[PDF] Using cached address for {recipient_id}: {recipient_address}")
        else:
            # Если нет в кэше — запрашиваем Perplexity
            from services.contact_verification_service import contact_verification_service
            contacts = contact_verification_service.verify_and_get_contacts(recipient_name)
            if contacts and contacts.get("address"):
                recipient_address = contacts["address"]
        
        # Если не нашли нигде — ищем в базе
        if not recipient_address and recipient_id:
            from data.recipients import RECIPIENTS
            rec = RECIPIENTS.get(recipient_id, {})
            recipient_address = rec.get("address", "")
    except Exception as e:
        print(f"[WARN] Could not get recipient address: {e}")
    
    # Заменяем плейсхолдеры в тексте жалобы
    final_text = complaint_text.replace("[название органа]", recipient_name)
    if recipient_address:
        final_text = final_text.replace("[адрес органа, если известен]", recipient_address)
        final_text = final_text.replace("[адрес органа]", recipient_address)
    else:
        # Убираем плейсхолдер если адрес не найден
        final_text = final_text.replace("[адрес органа, если известен]\n", "")
        final_text = final_text.replace("[адрес органа, если известен]", "")
        final_text = final_text.replace("[адрес органа]", "")
    
    # Генерируем PDF
    try:
        pdf_bytes = pdf_service.generate_complaint_pdf(
            complaint_text=final_text,
            recipient_name=recipient_name,
            user_data=user_data,
            category_name=category_name
        )
        
        # Отправляем файл
        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        
        # Имя файла с названием получателя
        safe_name = recipient_name.replace(" ", "_").replace("/", "_")[:30]
        filename = f"complaint_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Ошибка генерации PDF: {str(e)}"}), 500


# ==================== ERROR HANDLERS ====================

@app.errorhandler(429)
def ratelimit_error(e):
    return jsonify({
        "error": "Слишком много запросов. Подождите немного и попробуйте снова."
    }), 429


@app.errorhandler(500)
def internal_error(e):
    return jsonify({
        "error": "Внутренняя ошибка сервера. Попробуйте обновить страницу."
    }), 500


# ==================== MAIN ====================

if __name__ == '__main__':
    # Создаём необходимые директории
    os.makedirs(Config.DRAFTS_DIR, exist_ok=True)
    os.makedirs(Config.SESSION_FILE_DIR, exist_ok=True)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
