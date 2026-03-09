"""
Помощник по жалобам — Flask Application
Чат-квиз для составления и отправки жалоб
"""
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config
from services.orchestrator import orchestrator, FlowStep
from services.dadata_service import dadata_service
from services.payment_service import payment_service
from services.user_service import user_service
from services.analytics_service import analytics_service
from functools import wraps

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
    """Главная страница — оркестратор v2"""
    need_init = 'dialog_state' not in session
    
    # Если пользователь авторизован, но состояние застряло на регистрации — пересоздаём
    if not need_init and session.get('user_email'):
        existing = session.get('dialog_state', {})
        if existing.get('step') == 'registration' and not existing.get('data', {}).get('is_authenticated'):
            need_init = True
    
    if need_init:
        state = DialogStateV2()
        # Capture UTM params for personalization
        utm_term = request.args.get('utm_term', '')
        utm_data = {
            'utm_term': request.args.get('utm_term', ''),
            'utm_source': request.args.get('utm_source', ''),
            'utm_medium': request.args.get('utm_medium', ''),
            'utm_campaign': request.args.get('utm_campaign', ''),
        }
        if utm_term:
            state.data['utm_term'] = utm_term
        state.data['utm_data'] = utm_data
        # Analytics: log visit
        sid = session.sid if hasattr(session, 'sid') else id(session)
        analytics_service.log_event(str(sid), 'visit', '', utm_data,
                                    ip=request.remote_addr or '',
                                    user_agent=request.headers.get('User-Agent', ''))
        # Если пользователь авторизован — пропускаем регистрацию
        if session.get('user_email'):
            state.data['is_authenticated'] = True
            user = user_service.get_user(session['user_email'])
            if user:
                state.data['user_type'] = user.get('user_type', 'individual')
                state.data['user_data'] = {
                    'fio': user.get('name', ''),
                    'address': user.get('address', ''),
                    'phone': user.get('phone', ''),
                    'email': session['user_email'],
                    'org_inn': user.get('inn', ''),
                    'org_name': user.get('org_name', ''),
                    'position': user.get('position', '')
                }
        response = orchestrator.process(state.to_dict())
        state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
        state.step = response.get("step", "registration")
        session['dialog_state'] = state.to_dict()
    
    return render_template('index.html')


@app.route('/v2')
def index_v2_redirect():
    """Backward compat: redirect /v2 to /"""
    return redirect('/')


# ==================== AUTH ====================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')


@app.route('/terms')
def terms_page():
    return render_template('terms.html')


@app.route('/login')
def login_page():
    if 'user_email' in session:
        return redirect('/account')
    return render_template('login.html', error=request.args.get('error'), email=request.args.get('email'))


@app.route('/api/login', methods=['POST'])
@limiter.limit("10 per minute")
def do_login():
    email = request.form.get('email', '')
    password = request.form.get('password', '')
    
    user, error = user_service.login(email, password)
    if error:
        return render_template('login.html', error=error, email=email)
    
    session['user_email'] = email.strip().lower()
    # Очищаем старый dialog_state, чтобы при следующем заходе создать новый с is_authenticated
    session.pop('dialog_state', None)
    next_url = request.args.get('next', '/account')
    return redirect(next_url)


@app.route('/register')
def register_page():
    if 'user_email' in session:
        return redirect('/account')
    return render_template('register.html')


@app.route('/api/register', methods=['POST'])
@limiter.limit("5 per minute")
def do_register():
    name = request.form.get('name', '')
    email = request.form.get('email', '')
    password = request.form.get('password', '')
    
    if len(password) < 6:
        return render_template('register.html', error='Пароль должен быть не менее 6 символов', name=name, email=email)
    
    user, error = user_service.register(email, password, name)
    if error:
        return render_template('register.html', error=error, name=name, email=email)
    
    session['user_email'] = email.strip().lower()
    return redirect('/account')


@app.route('/logout')
def logout():
    session.pop('user_email', None)
    return redirect('/')


@app.route('/account')
@login_required
def account_page():
    email = session['user_email']
    user = user_service.get_user(email)
    if not user:
        session.pop('user_email', None)
        return redirect('/login')
    complaints = user_service.get_complaints(email)
    
    # Compute tariff info
    tariff_info = {'name': 'Бесплатный', 'id': 'free', 'remaining': '—', 'status': 'free', 'expires': None}
    payments = user.get('payments', [])
    for p in reversed(payments):
        if p.get('status') == 'succeeded' and p.get('tariff_id') in ('standard', 'premium'):
            tariff_id = p['tariff_id']
            tariff_cfg = Config.TARIFFS.get(tariff_id, {})
            tariff_info['id'] = tariff_id
            tariff_info['name'] = tariff_cfg.get('name', tariff_id)
            tariff_info['status'] = 'active'
            
            if tariff_id == 'premium':
                # Check expiry
                paid_at = p.get('recorded_at', p.get('paid_at', ''))
                if paid_at:
                    from datetime import datetime, timedelta
                    try:
                        expiry = datetime.fromisoformat(paid_at) + timedelta(days=365)
                        if datetime.now() > expiry:
                            tariff_info = {'name': 'Бесплатный', 'id': 'free', 'remaining': '—', 'status': 'expired', 'expires': None}
                        else:
                            tariff_info['remaining'] = '∞'
                            tariff_info['expires'] = expiry.strftime('%d.%m.%Y')
                    except:
                        tariff_info['remaining'] = '∞'
                else:
                    tariff_info['remaining'] = '∞'
            elif tariff_id == 'standard':
                limit = tariff_cfg.get('complaints', 1)
                used = len(complaints)
                remaining = max(0, limit - used)
                tariff_info['remaining'] = str(remaining)
                if remaining == 0:
                    tariff_info['status'] = 'exhausted'
            break
    
    return render_template('account.html', user=user, email=email, complaints=complaints, tariff_info=tariff_info)


@app.route('/tariffs')
def tariffs_page():
    tariffs = payment_service.get_tariffs()
    return render_template('tariffs.html', tariffs=tariffs, user_email=session.get('user_email'))


@app.route('/api/state', methods=['GET'])
def get_state():
    """Получить состояние диалога"""
    need_init = 'dialog_state' not in session
    
    # Если пользователь авторизован, но состояние застряло на регистрации — пересоздаём
    if not need_init and session.get('user_email'):
        existing = session.get('dialog_state', {})
        if existing.get('step') == 'registration' and not existing.get('data', {}).get('is_authenticated'):
            need_init = True
    
    if need_init:
        state = DialogStateV2()
        # Capture UTM params for personalization
        utm_term = request.args.get('utm_term', '')
        if utm_term:
            state.data['utm_term'] = utm_term
        if session.get('user_email'):
            state.data['is_authenticated'] = True
            user = user_service.get_user(session['user_email'])
            if user:
                state.data['user_type'] = user.get('user_type', 'individual')
                state.data['user_data'] = {
                    'fio': user.get('name', ''),
                    'address': user.get('address', ''),
                    'phone': user.get('phone', ''),
                    'email': session['user_email'],
                    'org_inn': user.get('inn', ''),
                    'org_name': user.get('org_name', ''),
                    'position': user.get('position', '')
                }
        response = orchestrator.process(state.to_dict())
        state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
        state.step = response.get("step", "registration")
        session['dialog_state'] = state.to_dict()
    else:
        state = DialogStateV2.from_dict(session['dialog_state'])
    
    return jsonify({
        "history": state.history,
        "step": state.step,
        "data": state.data
    })


@app.route('/api/chat', methods=['POST'])
@limiter.limit("30 per minute")
def chat():
    """Обработка сообщения через оркестратор"""
    try:
        data = request.get_json()
        user_input = data.get('message', '').strip()
        company_data = data.get('company_data')
        
        if not user_input:
            return jsonify({"error": "Пустое сообщение"}), 400
        
        if 'dialog_state' not in session:
            return jsonify({"error": "Сессия не найдена. Обновите страницу."}), 400
        
        state = DialogStateV2.from_dict(session['dialog_state'])
        current_step = state.step
        
        # Сохраняем данные из DaData если пришли
        if company_data:
            existing = state.data.get('company_data', {})
            if company_data.get('inn'):
                existing.update(company_data)
            elif company_data.get('fio'):
                existing['user_fio'] = company_data.get('fio')
            elif company_data.get('address') and not company_data.get('inn'):
                existing['user_address'] = company_data.get('address')
            else:
                existing.update(company_data)
            state.data['company_data'] = existing
        
        display_text = data.get('display_text', '').strip()
        
        # Сохраняем ввод пользователя (отображаемый текст для истории)
        state.add_message("user", display_text or user_input)
        
        # Обрабатываем в зависимости от шага
        if current_step == "registration":
            # Если пользователь уже авторизован — пропускаем регистрацию
            if session.get('user_email') and not state.data.get('is_authenticated'):
                state.data['is_authenticated'] = True
                user = user_service.get_user(session['user_email'])
                if user:
                    state.data['user_type'] = user.get('user_type', 'individual')
                    state.data['user_data'] = {
                        'fio': user.get('name', ''),
                        'address': user.get('address', ''),
                        'phone': user.get('phone', ''),
                        'email': session['user_email'],
                        'org_inn': user.get('inn', ''),
                        'org_name': user.get('org_name', ''),
                        'position': user.get('position', '')
                    }
                # Пропускаем обработку ввода — оркестратор перенаправит на категории
            else:
                # Пошаговый сбор профиля
                if 'registration' not in state.data:
                    state.data['registration'] = {}
                reg = state.data['registration']
            
                if not reg.get('consent_given'):
                    # Обработка согласия на обработку ПД (ФЗ-152)
                    if user_input == 'consent_accept':
                        reg['consent_given'] = True
                        reg['consent_at'] = datetime.now().isoformat()
                    elif user_input == 'consent_decline':
                        response = {
                            'message': '⚠️ Без согласия на обработку персональных данных мы не можем предоставить услуги сервиса.\n\nЭто требование **Федерального закона от 27.07.2006 № 152-ФЗ «О персональных данных»**.\n\nВы можете ознакомиться с документами и вернуться:\n• [Политика конфиденциальности](/privacy)\n• [Пользовательское соглашение](/terms)',
                            'options': [
                                {"id": "consent_accept", "text": "✅ Принимаю"},
                                {"id": "consent_decline", "text": "❌ Не принимаю"}
                            ],
                            'input_type': 'options',
                            'step': 'registration',
                            'can_go_back': False
                        }
                        state.add_message('assistant', response['message'], response.get('options'), response.get('input_type', 'options'))
                        session['dialog_state'] = state.to_dict()
                        session.modified = True
                        return jsonify(response)
                elif not reg.get('user_type'):
                    reg['user_type'] = user_input
                    state.data['user_type'] = user_input
                elif not reg.get('fio'):
                    reg['fio'] = user_input
                elif not reg.get('address'):
                    reg['address'] = user_input
                elif not reg.get('phone'):
                    reg['phone'] = user_input
                elif not reg.get('email'):
                    reg['email'] = user_input
                elif not reg.get('password'):
                    reg['password'] = user_input
                elif reg['user_type'] in ('organization', 'ip') and not reg.get('org_inn'):
                    reg['org_inn'] = user_input
                    if company_data:
                        reg['org_name'] = company_data.get('name', user_input)
                        reg['org_address'] = company_data.get('address', '')
                elif reg['user_type'] in ('organization', 'ip') and not reg.get('position'):
                    reg['position'] = user_input
        
        elif current_step == "category":
            from data.recipients import COMPLAINT_CATEGORIES
            category = COMPLAINT_CATEGORIES.get(user_input.lower(), {})
            state.data["category"] = user_input.lower()
            state.data["category_name"] = category.get("name", user_input)
            state.step = "quiz"
        
        elif current_step == "quiz":
            # Handle target suggestion responses
            if user_input.startswith("target_selected:"):
                # User selected targets from Perplexity suggestions
                selected_names = user_input.replace("target_selected:", "").strip()
                state.data["target_description"] = selected_names
                # Store as Q&A pair
                last_assistant = None
                for msg in reversed(state.history):
                    if msg["role"] == "assistant":
                        last_assistant = msg
                        break
                if last_assistant:
                    question = last_assistant["content"].split("\n")[0]
                    state.add_qa_pair(question, selected_names)
                    
            elif user_input == "target_skip":
                # User skipped target suggestions — continue with free text
                free_text = state.data.get("pending_target_text", user_input)
                state.data["target_description"] = free_text
                last_assistant = None
                for msg in reversed(state.history):
                    if msg["role"] == "assistant":
                        last_assistant = msg
                        break
                if last_assistant:
                    question = last_assistant["content"].split("\n")[0]
                    state.add_qa_pair(question, free_text)
                    
            else:
                # Normal quiz flow
                last_assistant = None
                for msg in reversed(state.history):
                    if msg["role"] == "assistant":
                        last_assistant = msg
                        break
                
                # Check if this is the FIRST quiz answer for org categories
                # and no company was selected from DaData (free text)
                is_first_question = len(state.qa_pairs) == 0
                is_org_category = state.data.get("category", "") in [
                    "shop", "bank", "employer", "zhkh", "contractor",
                    "utilities", "landlord", "tax", "medical",
                    "competitor", "subcontractor"
                ]
                has_company_data = company_data and company_data.get("inn")
                
                if is_first_question and is_org_category and not has_company_data:
                    # Free text — call Perplexity to identify targets
                    state.data["pending_target_text"] = user_input
                    try:
                        from services.contact_verification_service import contact_verification_service
                        category_name = state.data.get("category_name", "")
                        suggestions = contact_verification_service.identify_target(user_input, category_name)
                        
                        if suggestions and len(suggestions) > 0:
                            # Return target suggestions to frontend
                            response = {
                                "message": f"По запросу «{user_input}» найдены возможные варианты. Выберите подходящих:",
                                "input_type": "target_suggestions",
                                "target_suggestions": suggestions,
                                "step": "quiz",
                                "can_go_back": True
                            }
                            state.add_message("assistant", response["message"], None, "target_suggestions")
                            state.step = "quiz"
                            session['dialog_state'] = state.to_dict()
                            session.modified = True
                            return jsonify(response)
                    except Exception as e:
                        print(f"[IDENTIFY TARGET] Error: {e}")
                    
                    # Fallback — just continue with free text
                    state.data["target_description"] = user_input
                
                if last_assistant:
                    question = last_assistant["content"].split("\n")[0]
                    state.add_qa_pair(question, user_input)
        
        elif current_step == "preview":
            if user_input == "approve":
                state.step = "recipients"
            elif user_input == "edit":
                state.step = "edit_complaint"
        
        elif current_step == "edit_complaint":
            # Пользователь отправил свои замечания — оркестратор перегенерирует
            pass
        
        elif current_step == "recipients" and user_input not in ["approve", "regenerate"]:
            from data.recipients import RECIPIENTS
            selected_ids = [r.strip() for r in user_input.split(",")]
            
            recipient_options = state.data.get("recipient_options", [])
            recipient_map = {opt.get("id"): opt for opt in recipient_options}
            
            selected = []
            for rid in selected_ids:
                if rid in recipient_map:
                    opt = recipient_map[rid]
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
                    rec = RECIPIENTS.get(rid, {"id": rid, "name": rid})
                    selected.append({
                        "id": rid, 
                        "name": rec.get("name", rid), 
                        "email": rec.get("email"),
                        "website": rec.get("website")
                    })
            state.data["selected_recipients"] = selected
            state.step = "sending"
        
        elif current_step == "confirm_send":
            if user_input == "send":
                state.step = "sending"
            elif user_input == "back":
                state.step = "recipients"
        
        # Вызываем оркестратор
        response = orchestrator.process(state.to_dict(), user_input)
        
        # Автоматическая регистрация при завершении сбора профиля
        if response.get('step') == 'registration_complete':
            reg = state.data.get('registration', {})
            email = reg.get('email', '').strip().lower()
            password = reg.get('password', '')
            name = reg.get('fio', '')
            
            # Регистрируем пользователя
            user, error = user_service.register(email, password, name)
            if error:
                # Email уже занят — пробуем залогиниться
                existing_user, login_error = user_service.login(email, password)
                if login_error:
                    # Пароль неверный — сообщаем
                    response = {
                        'message': f'⚠️ Аккаунт с email **{email}** уже существует, но пароль не совпадает. Попробуйте другой email или пароль.',
                        'step': 'registration',
                        'input_type': 'text',
                        'can_go_back': False
                    }
                    # Сброс email и password для повторного ввода
                    state.data['registration'].pop('email', None)
                    state.data['registration'].pop('password', None)
                    state.add_message('assistant', response['message'], response.get('options'), response.get('input_type', 'options'))
                    state.step = 'registration'
                    session['dialog_state'] = state.to_dict()
                    session.modified = True
                    return jsonify(response)
            
            # Успешная регистрация или логин — сохраняем профиль
            session['user_email'] = email
            session['user_name'] = name or email.split('@')[0]
            state.data['is_authenticated'] = True
            
            # Сохраняем расширенные данные профиля
            user_service.update_profile(email, {
                'user_type': reg.get('user_type', 'individual'),
                'phone': reg.get('phone', ''),
                'address': reg.get('address', ''),
                'inn': reg.get('org_inn', ''),
                'org_name': reg.get('org_name', ''),
                'position': reg.get('position', ''),
                'consent_at': reg.get('consent_at', ''),
                'consent_given': True,
            })
            
            # Заполняем user_data для жалобы
            state.data['user_data'] = {
                'fio': reg.get('fio', ''),
                'address': reg.get('address', ''),
                'phone': reg.get('phone', ''),
                'email': email,
                'org_inn': reg.get('org_inn', ''),
                'org_name': reg.get('org_name', ''),
                'position': reg.get('position', '')
            }
            
            # Показываем приветственное сообщение и категории
            state.add_message('assistant', f'✅ Профиль создан! Добро пожаловать, **{name}**!', None, 'options')
            response = orchestrator.process(state.to_dict(), None)
        
        # Сохраняем результат генерации жалобы
        if response.get("complaint_text"):
            state.data["complaint_text"] = response["complaint_text"]
        
        # Сохраняем опции получателей
        if response.get("step") == "recipients" and response.get("options"):
            state.data["recipient_options"] = response["options"]
        
        # Обновляем шаг
        new_step = response.get("step", state.step)
        state.step = new_step
        
        # Добавляем ответ в историю
        state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
        
        # Сохраняем состояние
        session['dialog_state'] = state.to_dict()
        session.modified = True
        
        # === ANALYTICS: log funnel step ===
        try:
            sid = session.sid if hasattr(session, 'sid') else str(id(session))
            utm_data = state.data.get('utm_data', {})
            ip = request.remote_addr or ''
            ua = request.headers.get('User-Agent', '')
            
            # Map orchestrator steps to funnel steps
            if current_step == 'registration':
                reg = state.data.get('registration', {})
                if user_input == 'consent_accept':
                    analytics_service.log_event(sid, 'consent', '', utm_data, ip, ua)
                elif reg.get('consent_given'):
                    # Determine sub-step based on what was just filled
                    if not reg.get('user_type') or user_input in ('individual', 'ip', 'organization'):
                        analytics_service.log_event(sid, 'reg_user_type', user_input, utm_data, ip, ua)
                    elif reg.get('fio') and not reg.get('address'):
                        analytics_service.log_event(sid, 'reg_fio', '', utm_data, ip, ua)
                    elif reg.get('address') and not reg.get('phone'):
                        analytics_service.log_event(sid, 'reg_address', '', utm_data, ip, ua)
                    elif reg.get('phone') and not reg.get('email'):
                        analytics_service.log_event(sid, 'reg_phone', '', utm_data, ip, ua)
                    elif reg.get('email') and not reg.get('password'):
                        analytics_service.log_event(sid, 'reg_email', '', utm_data, ip, ua)
                    elif reg.get('password'):
                        analytics_service.log_event(sid, 'reg_password', '', utm_data, ip, ua)
            
            if new_step == 'category' and current_step != 'category':
                analytics_service.log_event(sid, 'category', state.data.get('category', ''), utm_data, ip, ua)
            
            if current_step == 'category' and new_step == 'quiz':
                analytics_service.log_event(sid, 'category', state.data.get('category', ''), utm_data, ip, ua)
            
            if current_step == 'quiz':
                q_num = len(state.qa_pairs)
                q_key = f'quiz_q{min(q_num, 5)}'
                analytics_service.log_event(sid, q_key, f'q{q_num}', utm_data, ip, ua)
            
            if new_step == 'preview' and response.get('complaint_text'):
                analytics_service.log_event(sid, 'complaint_generated', '', utm_data, ip, ua)
            
            if new_step == 'recipients':
                analytics_service.log_event(sid, 'recipients_selected', '', utm_data, ip, ua)
            
            if response.get('input_type') == 'sending_results':
                analytics_service.log_event(sid, 'complaint_sent', '', utm_data, ip, ua)
        except Exception as e:
            print(f'[ANALYTICS] Error: {e}')
        
        # === ТРЕКИНГ СОБЫТИЙ ВОРОНКИ ===
        email_user = session.get('user_email')
        resp_step = response.get('step', '')
        resp_input_type = response.get('input_type', '')
        
        if email_user:
            try:
                # 1. Жалоба сгенерирована (показан preview)
                if resp_step == 'preview' and response.get('complaint_text'):
                    user_service.add_event(email_user, 'complaint_generated', {
                        'category': state.data.get('category_name', '')
                    })
                
                # 2. Открыт выбор получателей
                if resp_step == 'recipients' and resp_input_type == 'multi_select':
                    user_service.add_event(email_user, 'recipients_opened')
                
                # 3. Получатели выбраны → переход к отправке
                if resp_step == 'sending' and state.data.get('selected_recipients'):
                    recipients_names = [r.get('name', '') for r in state.data.get('selected_recipients', [])]
                    user_service.add_event(email_user, 'channels_selected', {
                        'recipients': recipients_names
                    })
                
                # 4. Результаты отправки (жалоба отправлена)
                if resp_input_type == 'sending_results' and response.get('results'):
                    user_service.add_event(email_user, 'complaint_sent', {
                        'recipients_count': len(response.get('results', []))
                    })
            except Exception as e:
                print(f'[EVENT TRACK] Error: {e}')
        
        # Сохраняем sending_results в state.data для восстановления при перезагрузке страницы
        if response.get('input_type') == 'sending_results' and response.get('results'):
            state.data['sending_results'] = response['results']
            session['dialog_state'] = state.to_dict()
            session.modified = True
        
        # Автосохранение жалобы в профиль пользователя
        if response.get('input_type') == 'sending_results' and response.get('results') and email_user:
            try:
                user_service.save_complaint(email_user, {
                    'category_name': state.data.get('category_name', ''),
                    'complaint_text': state.data.get('complaint_text', ''),
                    'recipients': response.get('results', []),
                })
            except Exception as e:
                print(f'[COMPLAINT SAVE] Error: {e}')
        
        # Формируем ответ
        resp = {
            "message": response["message"],
            "options": response.get("options"),
            "input_type": response.get("input_type", "options"),
            "step": response.get("step"),
            "complaint_text": response.get("complaint_text"),
            "can_go_back": response.get("can_go_back", True),
            "results": response.get("results"),
            "pdf_download_url": response.get("pdf_download_url")
        }
        
        # Передаём данные пользователя для обновления шапки
        if session.get('user_email'):
            user = user_service.get_user(session['user_email'])
            if user:
                resp['user_name'] = user.get('name', '') or session['user_email'].split('@')[0]
                resp['user_email'] = session['user_email']
        
        return jsonify(resp)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Ошибка: {str(e)}"}), 500


@app.route('/api/back', methods=['POST'])
def go_back():
    """Вернуться на шаг назад"""
    if 'dialog_state' not in session:
        return jsonify({"error": "Сессия не найдена"}), 400
    
    state = DialogStateV2.from_dict(session['dialog_state'])
    # Simple: remove last user + last assistant message
    if len(state.history) >= 2:
        if state.history[-1]["role"] == "user":
            state.history.pop()
        if state.history and state.history[-1]["role"] == "assistant":
            state.history.pop()
        if state.qa_pairs:
            state.qa_pairs.pop()
        session['dialog_state'] = state.to_dict()
        session.modified = True
        return jsonify({
            "success": True,
            "history": state.history,
            "step": state.step
        })
    return jsonify({"success": False, "error": "Невозможно вернуться назад"})


@app.route('/api/restart', methods=['POST'])
def restart():
    """Начать диалог заново"""
    state = DialogStateV2()
    # Если пользователь уже авторизован — пропускаем регистрацию и согласие
    if session.get('user_email'):
        state.data['is_authenticated'] = True
        user = user_service.get_user(session['user_email'])
        if user:
            state.data['user_type'] = user.get('user_type', 'individual')
            state.data['user_data'] = {
                'fio': user.get('name', ''),
                'address': user.get('address', ''),
                'phone': user.get('phone', ''),
                'email': session['user_email'],
                'org_inn': user.get('inn', ''),
                'org_name': user.get('org_name', ''),
                'position': user.get('position', '')
            }
    response = orchestrator.process(state.to_dict())
    state.add_message("assistant", response["message"], response.get("options"), response.get("input_type", "options"))
    state.step = response.get("step", "welcome")
    session['dialog_state'] = state.to_dict()
    session.modified = True
    
    return jsonify({
        "success": True,
        "history": state.history,
        "step": state.step
    })


@app.route('/api/reset', methods=['POST'])
def reset():
    """Сбросить состояние"""
    if 'dialog_state' in session:
        del session['dialog_state']
    session.modified = True
    return jsonify({"success": True})


# ==================== COMPLAINTS HISTORY API ====================

@app.route('/api/complaints/history')
def complaints_history():
    """Получить историю жалоб текущего пользователя"""
    email = session.get('user_email')
    if not email:
        return jsonify({"complaints": []})
    
    user = user_service.get_user(email)
    if not user:
        return jsonify({"complaints": []})
    
    complaints = user.get('complaints', [])
    # Возвращаем в обратном порядке (новые сверху)
    return jsonify({"complaints": list(reversed(complaints))})

@app.route('/api/complaints/<complaint_id>')
def get_complaint(complaint_id):
    """Получить одну жалобу по ID для восстановления в чате"""
    email = session.get('user_email')
    if not email:
        return jsonify({"error": "Не авторизован"}), 401
    
    user = user_service.get_user(email)
    if not user:
        return jsonify({"error": "Пользователь не найден"}), 404
    
    for c in user.get('complaints', []):
        if c.get('id') == complaint_id:
            return jsonify({"complaint": c})
    
    return jsonify({"error": "Жалоба не найдена"}), 404


# ==================== EVENT TRACKING API ====================

@app.route('/api/track', methods=['POST'])
def track_event():
    """Трекинг кликов по кнопкам email/портал из фронтенда"""
    email = session.get('user_email')
    if not email:
        return jsonify({"ok": True})  # Не трекаем анонимов
    
    data = request.get_json()
    event_type = data.get('event', '')
    
    allowed_events = ['email_clicked', 'portal_clicked']
    if event_type not in allowed_events:
        return jsonify({"error": "Invalid event"}), 400
    
    metadata = data.get('meta', {})
    user_service.add_event(email, event_type, metadata)
    return jsonify({"ok": True})


# ==================== ADMIN ====================

ADMIN_PASSWORD = "100878"

@app.route('/admin')
def admin_page():
    if session.get('is_admin'):
        users = user_service.get_all_users()
        return render_template('admin.html', users=users)
    return render_template('admin_login.html')

@app.route('/api/admin/login', methods=['POST'])
@limiter.limit("5 per minute")
def admin_login():
    data = request.get_json()
    if data.get('password') == ADMIN_PASSWORD:
        session['is_admin'] = True
        return jsonify({"success": True})
    return jsonify({"error": "Неверный пароль"}), 401

@app.route('/api/admin/users')
def admin_users():
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    users = user_service.get_all_users()
    return jsonify({"users": users})

@app.route('/api/admin/user/<email>')
def admin_user_detail(email):
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    user = user_service.get_user(email)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user['email'] = email
    return jsonify({"user": user})

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect('/')

@app.route('/admin/login-as/<email>')
def admin_login_as(email):
    """Автологин под пользователем из админки + обновление базовой подписки"""
    if not session.get('is_admin'):
        return redirect('/admin')
    
    user = user_service.get_user(email)
    if not user:
        return redirect('/admin')
    
    # Для стандартного тарифа (290 руб) — обновляем подписку при каждом входе
    payments = user.get('payments', [])
    is_standard = any(p.get('tariff') == 'standard' for p in payments)
    if is_standard:
        # Сбрасываем счётчик: помечаем текущие стандартные платежи как succeeded
        import json
        users_file = getattr(Config, 'USERS_FILE', './data/users.json')
        with open(users_file, 'r', encoding='utf-8') as f:
            users = json.load(f)
        
        e = email.strip().lower()
        if e in users:
            for p in users[e].get('payments', []):
                if p.get('tariff') == 'standard':
                    p['status'] = 'succeeded'
                    p['recorded_at'] = datetime.now().isoformat()
            # Сбрасываем complaints чтобы лимит обнулился
            users[e]['complaints_used'] = 0
            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
    
    # Устанавливаем сессию как этого пользователя
    session['user_email'] = email.strip().lower()
    # Сбрасываем диалог
    session.pop('dialog_state', None)
    
    return redirect('/')

@app.route('/api/admin/seed-test', methods=['POST'])
def admin_seed_test():
    """Временный эндпоинт для создания тестовых аккаунтов"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    
    from werkzeug.security import generate_password_hash
    import json, os
    
    users_file = getattr(Config, 'USERS_FILE', './data/users.json')
    with open(users_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
    
    now = datetime.now().isoformat()
    
    data = request.get_json() or {}
    accounts = data.get('accounts', [])
    created = []
    
    for acc in accounts:
        email = acc['email'].strip().lower()
        if email in users:
            created.append(f"{email}: уже существует")
            continue
        
        users[email] = {
            'name': acc.get('name', ''),
            'password_hash': generate_password_hash(acc.get('password', 'test123')),
            'password_raw': acc.get('password', 'test123'),
            'created_at': now,
            'user_type': acc.get('user_type', 'individual'),
            'fio': acc.get('fio', ''),
            'phone': acc.get('phone', ''),
            'address': acc.get('address', ''),
            'payments': acc.get('payments', []),
            'complaints': [],
            'events': [],
        }
        created.append(f"{email}: создан")
    
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    
    return jsonify({"created": created, "total": len(users)})


# ==================== ANALYTICS ADMIN API ====================

@app.route('/api/admin/funnel')
def admin_funnel():
    """Aggregated funnel data"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    utm = request.args.get('utm', '')
    return jsonify(analytics_service.get_funnel(
        date_from=date_from or None,
        date_to=date_to or None,
        utm_filter=utm or None
    ))

@app.route('/api/admin/visitors')
def admin_visitors():
    """Paginated visitor list"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    page = int(request.args.get('page', 1))
    utm = request.args.get('utm', '')
    date_from = request.args.get('from', '')
    date_to = request.args.get('to', '')
    return jsonify(analytics_service.get_visitors(
        page=page,
        date_from=date_from or None,
        date_to=date_to or None,
        utm_filter=utm or None
    ))

@app.route('/api/admin/visitor/<visitor_id>')
def admin_visitor_detail(visitor_id):
    """Event timeline for a specific visitor"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    events = analytics_service.get_visitor_events(visitor_id)
    return jsonify({"events": events})


# ==================== YANDEX METRIKA ADMIN API ====================

from services.metrika_service import metrika_service

@app.route('/api/admin/metrika/status')
def admin_metrika_status():
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"configured": metrika_service.is_configured()})

@app.route('/api/admin/metrika/summary')
def admin_metrika_summary():
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return jsonify(metrika_service.get_traffic_summary(
            request.args.get('from', ''), request.args.get('to', '')))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/metrika/search')
def admin_metrika_search():
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return jsonify(metrika_service.get_search_phrases(
            request.args.get('from', ''), request.args.get('to', '')))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/metrika/sources')
def admin_metrika_sources():
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return jsonify(metrika_service.get_traffic_sources(
            request.args.get('from', ''), request.args.get('to', '')))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/metrika/utm')
def admin_metrika_utm():
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return jsonify(metrika_service.get_utm_campaigns(
            request.args.get('from', ''), request.args.get('to', '')))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/metrika/visits')
def admin_metrika_visits():
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    try:
        return jsonify(metrika_service.get_visits_detail(
            request.args.get('from', ''), request.args.get('to', '')))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== YANDEX DIRECT ADMIN API ====================

from services.yandex_direct_service import yandex_direct_service



@app.route('/api/admin/direct/status')
def admin_direct_status():
    """Check if Yandex Direct API is configured"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({
        "configured": yandex_direct_service.is_configured(),
        "sandbox": yandex_direct_service.use_sandbox,
    })

@app.route('/api/admin/direct/campaigns')
def admin_direct_campaigns():
    """Get all campaigns"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    result = yandex_direct_service.get_campaigns()
    return jsonify(result)

@app.route('/api/admin/direct/stats')
def admin_direct_stats():
    """Get campaign statistics"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    result = yandex_direct_service.get_campaign_stats(date_from, date_to)
    return jsonify(result)

@app.route('/api/admin/direct/campaign/<int:campaign_id>/suspend', methods=['POST'])
def admin_direct_suspend(campaign_id):
    """Pause a campaign"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    result = yandex_direct_service.suspend_campaign(campaign_id)
    return jsonify(result)

@app.route('/api/admin/direct/campaign/<int:campaign_id>/resume', methods=['POST'])
def admin_direct_resume(campaign_id):
    """Resume a campaign"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    result = yandex_direct_service.resume_campaign(campaign_id)
    return jsonify(result)

@app.route('/api/admin/direct/ads')
def admin_direct_ads():
    """Get ads"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    campaign_ids = request.args.getlist('campaign_id')
    result = yandex_direct_service.get_ads(campaign_ids or None)
    return jsonify(result)

@app.route('/api/admin/direct/keywords')
def admin_direct_keywords():
    """Get keywords"""
    if not session.get('is_admin'):
        return jsonify({"error": "Forbidden"}), 403
    campaign_ids = request.args.getlist('campaign_id')
    result = yandex_direct_service.get_keywords(campaign_ids or None)
    return jsonify(result)


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


# ==================== PAYMENT API ====================

@app.route('/api/tariffs')
def get_tariffs():
    """Получить список тарифов"""
    state_data = session.get('dialog_state', {})
    return jsonify({
        "tariffs": payment_service.get_tariffs(),
        "paid": payment_service.is_paid(state_data),
        "tariff_level": payment_service.get_tariff_level(state_data),
    })


@app.route('/api/pay', methods=['POST'])
@limiter.limit("10 per minute")
def create_payment():
    """Создать платёж в ЮКассе"""
    data = request.get_json()
    tariff_id = data.get('tariff_id')
    
    if not tariff_id or tariff_id not in Config.TARIFFS or Config.TARIFFS[tariff_id]['price'] == 0:
        return jsonify({"error": "Неверный тариф"}), 400
    
    if not Config.YOOKASSA_SHOP_ID or not Config.YOOKASSA_SECRET_KEY:
        return jsonify({"error": "Платёжная система не настроена"}), 503
    
    try:
        session_id = session.sid if hasattr(session, 'sid') else 'unknown'
        result = payment_service.create_payment(tariff_id, session_id)
        
        # Сохраняем payment_id в сессию
        if 'dialog_state' in session:
            state_data = session['dialog_state']
            if 'data' not in state_data:
                state_data['data'] = {}
            state_data['data']['payment'] = {
                'payment_id': result['payment_id'],
                'tariff_id': tariff_id,
                'status': 'pending',
                'created_at': datetime.now().isoformat(),
            }
            session['dialog_state'] = state_data
            session.modified = True
        
        return jsonify({
            "success": True,
            "confirmation_url": result['confirmation_url'],
            "payment_id": result['payment_id'],
        })
    except Exception as e:
        print(f"[PAYMENT ERROR] {e}")
        return jsonify({"error": "Ошибка создания платежа"}), 500


@app.route('/api/payment/status')
def payment_status():
    """Проверить статус оплаты"""
    
    # === 1. СНАЧАЛА проверяем сохранённые платежи пользователя ===
    user_email = session.get('user_email')
    if user_email:
        user = user_service.get_user(user_email)
        if user:
            payments = user.get('payments', [])
            # Ищем лучший активный платёж
            best_tariff = None
            for p in payments:
                if p.get('status') != 'succeeded':
                    continue
                tariff_id = p.get('tariff', '')
                
                # Маппинг tariff из платежа → tariff_id из Config.TARIFFS
                # 'annual' → 'premium', 'standard' → 'standard'
                config_tariff_id = tariff_id
                if tariff_id == 'annual':
                    config_tariff_id = 'premium'
                
                tariff_config = Config.TARIFFS.get(config_tariff_id, {})
                
                # Проверяем срок для тарифов с ограничением по дням
                days_limit = tariff_config.get('days')
                if days_limit:
                    paid_at = p.get('recorded_at') or p.get('paid_at') or p.get('created_at', '')
                    if paid_at:
                        try:
                            expiry = datetime.fromisoformat(paid_at) + timedelta(days=days_limit)
                            if datetime.now() > expiry:
                                continue  # Истёк
                        except:
                            pass
                
                # premium > standard > free
                priority = {'premium': 2, 'standard': 1}.get(config_tariff_id, 0)
                if best_tariff is None or priority > best_tariff[0]:
                    best_tariff = (priority, config_tariff_id, tariff_config)
            
            if best_tariff:
                _, tariff_level, tariff_config = best_tariff
                return jsonify({
                    "paid": True,
                    "status": "succeeded",
                    "tariff": tariff_config.get('name', ''),
                    "tariff_level": tariff_level,
                    "can_send": tariff_config.get('sending', False),
                    "can_download": tariff_config.get('download', False),
                    "has_channels": tariff_config.get('channels', False),
                })
    
    # === 2. Фолбэк: проверяем текущую сессию (для in-progress оплаты) ===
    state_data = session.get('dialog_state', {})
    payment_info = state_data.get('data', {}).get('payment')
    
    if not payment_info or not payment_info.get('payment_id'):
        return jsonify({"paid": False, "status": "no_payment"})
    
    # Если уже подтверждён в сессии — не дёргаем API
    if payment_info.get('status') == 'succeeded':
        tariff = Config.TARIFFS.get(payment_info.get('tariff_id', ''), {})
        tariff_level = payment_service.get_tariff_level(state_data)
        return jsonify({
            "paid": True,
            "status": "succeeded",
            "tariff": tariff.get('name', ''),
            "tariff_level": tariff_level,
            "can_send": payment_service.can_send(state_data),
            "can_download": payment_service.can_download(state_data),
            "has_channels": payment_service.has_channels(state_data),
        })
    
    # Проверяем в ЮКассе
    result = payment_service.check_payment(payment_info['payment_id'])
    if result and result.get('paid'):
        payment_info['status'] = 'succeeded'
        payment_info['paid_at'] = datetime.now().isoformat()
        payment_info['complaints_used'] = 0
        session['dialog_state'] = state_data
        session.modified = True
        
        tariff = Config.TARIFFS.get(payment_info.get('tariff_id', ''), {})
        tariff_level = payment_service.get_tariff_level(state_data)
        return jsonify({
            "paid": True,
            "status": "succeeded",
            "tariff": tariff.get('name', ''),
            "tariff_level": tariff_level,
            "can_send": payment_service.can_send(state_data),
            "can_download": payment_service.can_download(state_data),
            "has_channels": payment_service.has_channels(state_data),
        })
    
    status = result.get('status', 'pending') if result else 'error'
    tariff_level = payment_service.get_tariff_level(state_data)
    return jsonify({"paid": False, "status": status, "tariff_level": tariff_level})


# ==================== DialogStateV2 ======================================

class DialogStateV2:
    """Состояние диалога (оркестратор)"""
    
    def __init__(self):
        import uuid
        from datetime import datetime
        self.id = str(uuid.uuid4())
        self.step = "registration"
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
        state.step = data.get("step", "registration")
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


# ==================== TEST ENDPOINTS ====================

@app.route('/test/preview')
def test_preview():
    """Тестовый endpoint — сразу на этап превью"""
    
    complaint_text = """В Прокуратуру РФ\n\nот Иванова Ивана Ивановича\nпроживающего по адресу: г. Москва, ул. Тестовая, д. 1, кв. 1\nтел.: +7 999 123-45-67\nemail: test@test.ru\n\nЖАЛОБА\n(на нарушение прав потребителя)\n\nТестовый текст жалобы."""
    
    state = DialogStateV2()
    state.step = "preview"
    state.data = {
        "category": "consumer_rights",
        "category_name": "Защита прав потребителей",
        "user_data": {"fio": "Иванов Иван Иванович", "address": "г. Москва", "phone": "+7 999 123-45-67", "email": "test@test.ru"},
        "complaint_text": complaint_text
    }
    preview_options = [
        {"id": "approve", "text": "✅ Одобрить и продолжить"},
        {"id": "edit", "text": "✏️ Редактировать"},
        {"id": "regenerate", "text": "🔄 Сгенерировать заново"}
    ]
    state.add_message("assistant", f"✅ **Жалоба готова!**\n\n---\n\n{complaint_text}\n\n---", preview_options, "preview")
    session['dialog_state'] = state.to_dict()
    session.modified = True
    return redirect('/')


@app.route('/test/sending')
def test_sending():
    """Тестовый endpoint — сразу на этап отправки"""
    state = DialogStateV2()
    state.step = "sending"
    state.data = {
        "category": "consumer_rights",
        "category_name": "Защита прав потребителей",
        "user_data": {"fio": "Иванов Иван Иванович", "address": "г. Москва", "phone": "+7 999 123-45-67", "email": "test@test.ru"},
        "complaint_text": "Тестовая жалоба...",
        "selected_recipients": [
            {"id": "prosecution", "name": "Прокуратура РФ", "email": "genproc@genproc.gov.ru", "website": "https://epp.genproc.gov.ru"},
            {"id": "rospotrebnadzor", "name": "Роспотребнадзор", "email": "depart@gsen.ru", "website": "https://petition.rospotrebnadzor.ru"}
        ]
    }
    state.add_message("assistant", "🔔 **Тестовый режим**: Этап отправки")
    response = orchestrator.process(state.to_dict(), "send")
    state.add_message("assistant", response.get("message", "Готово!"), response.get("options"), response.get("input_type", "sending_results"))
    if response.get("results"):
        state.data["sending_results"] = response["results"]
    session['dialog_state'] = state.to_dict()
    session.modified = True
    return redirect('/')


@app.route('/api/download-pdf')
def download_pdf():
    """Скачать жалобу в формате PDF для конкретного получателя"""
    from flask import send_file
    from io import BytesIO
    from services.pdf_service import pdf_service
    
    if 'dialog_state' not in session:
        return jsonify({"error": "Сессия не найдена"}), 400
    
    # Проверяем оплату (standard или premium)
    if not payment_service.can_download(session.get('dialog_state', {})):
        return jsonify({"error": "Оплатите тариф для скачивания PDF", "payment_required": True}), 403
    
    state_dict = session['dialog_state']
    
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
