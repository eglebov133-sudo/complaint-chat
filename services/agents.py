"""
Субагенты для обработки жалоб
Каждый агент отвечает за свою часть процесса
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import json
from services.llm_service import llm_service
from data.recipients import RECIPIENTS, RECIPIENT_RECOMMENDATIONS
from config import Config


class SubAgent(ABC):
    """Базовый класс для субагентов"""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def process(self, context: Dict) -> Dict:
        """Основной метод обработки"""
        pass
    
    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, model: Optional[str] = None) -> Optional[str]:
        """Вызов LLM с заданными промптами"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return llm_service._make_request(messages, temperature=temperature, model_override=model)


class QuizAgent(SubAgent):
    """Агент для сбора информации через Q&A"""
    
    def __init__(self):
        super().__init__("QuizAgent")
        
        self.system_prompt = """Ты — дружелюбный помощник по жалобам. Твоя задача — БЫСТРО собрать ключевую информацию через 3-4 простых вопроса.

## ⚠️ КРИТИЧЕСКИЕ ПРАВИЛА

1. **НЕ ПОВТОРЯЙ** вопросы, на которые уже есть ответы!
2. **МАКСИМУМ 4 вопроса** — потом завершай квиз
3. **ВСЕГДА готовые варианты** — пользователь только кликает

## ДЕТАЛЬНЫЙ ОПРОС (8-10 вопросов):

1. **Что именно случилось?** — конкретная ситуация
2. **Когда это произошло?** — дата/период
3. **Какой ущерб?** — финансовый, моральный, материальный
4. **Сумма ущерба?** — конкретные цифры
5. **Пытались решить?** — обращались ли куда-то
6. **Какой был результат?** — что ответили/сделали
7. **Есть документы?** — договоры, чеки, переписка
8. **Есть свидетели?** — кто может подтвердить
9. **Чего хотите добиться?** — конкретный результат
10. **Дополнительные обстоятельства?** — что ещё важно

Не задавай все вопросы — адаптируйся к ответам. Если ответ уже содержит информацию для следующего вопроса, пропускай его.

## ФОРМАТ ОТВЕТА (JSON)

Следующий вопрос:
{"ready": false, "question": "Короткий вопрос?", "options": ["Вариант 1", "Вариант 2", "Вариант 3"], "input_type": "options"}

Квиз завершён (после 8+ ответов):
{"ready": true}

## ПРАВИЛА ВАРИАНТОВ
- 4-8 коротких вариантов (макс 6 слов)
- Варианты КОНКРЕТНЫЕ и РЕЛЕВАНТНЫЕ контексту разговора
- НЕ добавляй "Другое" — поле ввода всегда доступно
- input_type = "options" почти всегда"""

    def process(self, context: Dict) -> Dict:
        """Генерирует следующий вопрос или сигнализирует о готовности"""
        
        qa_pairs = context.get("qa_pairs", [])
        category_name = context.get("category_name", "Не указана")
        
        # Первый вопрос зависит от категории
        category = context.get("category", "other")
        if len(qa_pairs) == 0:
            # Категории где жалуются НА организацию — автокомплит DaData
            org_categories = ["shop", "bank", "employer", "zhkh", "contractor", 
                              "utilities", "landlord", "tax", "medical",
                              "competitor", "subcontractor"]
            
            if category in org_categories:
                question_map = {
                    "competitor": "Какая компания ведёт недобросовестную конкуренцию?",
                    "subcontractor": "На какого подрядчика / исполнителя жалуетесь?",
                }
                return {
                    "ready": False,
                    "question": question_map.get(category, "На какую организацию или компанию вы хотите пожаловаться?"),
                    "options": None,
                    "input_type": "autocomplete_company"
                }
            # Для остальных категорий (соседи, полиция, госорган, другое)
            # НЕ хардкодим — пусть LLM сгенерирует первый вопрос с кнопками-вариантами
        
        # ЖЁСТКИЙ ЛИМИТ: после 10 вопросов — принудительное завершение
        if len(qa_pairs) >= 10:
            return {"ready": True}
        
        # Формируем контекст из Q&A
        qa_context = ""
        if qa_pairs:
            for i, qa in enumerate(qa_pairs, 1):
                qa_context += f"{i}. В: {qa['question']}\n   О: {qa['answer']}\n"
        else:
            qa_context = "Диалог только начался."
        
        user_type = context.get("user_type", "individual")
        user_type_label = "организация / ИП" if user_type == "organization" else "обычный человек"
        
        user_prompt = f"""Категория: {category_name}
Заявитель: {user_type_label}

СОБРАННАЯ ИНФОРМАЦИЯ ({len(qa_pairs)} из 10 вопросов):
{qa_context}

⚠️ Варианты ответа ДОЛЖНЫ соответствовать типу заявителя ({user_type_label})!

{("Задано " + str(len(qa_pairs)) + " из 10 вопросов. Задай следующий ВАЖНЫЙ вопрос.") if len(qa_pairs) < 8 else "Собрано достаточно информации. Верни ready: true."}

JSON:"""
        
        result = self._call_llm(self.system_prompt, user_prompt, temperature=0.7)
        
        if result:
            json_str = llm_service._extract_json(result)
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    # Если LLM сказал ready И достаточно ответов — завершаем
                    if parsed.get("ready") and len(qa_pairs) >= 8:
                        return {"ready": True}
                    if parsed.get("ready") and len(qa_pairs) < 8:
                        parsed["ready"] = False  # Не хватает вопросов, продолжаем
                    return parsed
                except:
                    pass
        
        return {"ready": False, "question": "Расскажите подробнее о вашей проблеме", "options": None, "input_type": "textarea"}


class ComplaintAgent(SubAgent):
    """Агент для генерации текста жалобы"""
    
    def __init__(self):
        super().__init__("ComplaintAgent")
        
        self.system_prompt = """Ты — элитный юрист с 20-летним опытом защиты прав граждан в суде. Твоя задача — написать МОЩНУЮ, УБЕДИТЕЛЬНУЮ жалобу, которая произведёт WOW-эффект на клиента.

## ЦЕЛЬ
Клиент должен посмотреть на жалобу и подумать: "Вау! Я бы никогда так круто не написал! Это профессионал!"

## СТРУКТУРА ИДЕАЛЬНОЙ ЖАЛОБЫ

### 1. ШАПКА (строго по формату)
В [название органа]
[адрес органа, если известен]

от [ФИО заявителя]
проживающего по адресу: [адрес]
тел.: [телефон]
email: [email]

ЖАЛОБА
(на [краткое описание предмета жалобы])

### 2. РЕКВИЗИТЫ ОТВЕТЧИКА (ОБЯЗАТЕЛЬНО!)
Если есть данные об организации-нарушителе, ОБЯЗАТЕЛЬНО укажи:
- Полное наименование организации
- ИНН
- Юридический адрес
Это критически важно для идентификации и определения подведомственности!

### 3. ВСТУПЛЕНИЕ (1 абзац)
Ёмко и профессионально изложи СУТЬ нарушения.

### 4. ФАКТИЧЕСКИЕ ОБСТОЯТЕЛЬСТВА (2-4 абзаца)
- Хронология событий (даты, факты, детали)
- Кто нарушитель (наименование организации, ИНН, адрес, ФИО должностных лиц)
- Что именно нарушено
- Какие действия предпринимались для решения

### 5. ПРАВОВОЕ ОБОСНОВАНИЕ (ключевой раздел!)
Обязательно укажи нарушенные нормы права:
- Конституция РФ (ст. 2, 17, 18, 45, 46 - права граждан)
- Закон о защите прав потребителей (если применимо)
- ЖК РФ, ТК РФ, ГК РФ, КоАП РФ — в зависимости от ситуации

### 6. ПРОСИТЕЛЬНАЯ ЧАСТЬ (чёткие требования)
"На основании изложенного, руководствуясь [ссылки на законы], ПРОШУ:
1. Провести проверку...
2. Привлечь к ответственности...
3. Обязать [нарушителя] устранить...
4. О результатах рассмотрения уведомить меня в установленный законом срок."

### 7. ПРИЛОЖЕНИЯ И ПОДПИСЬ
"Приложения: [список, если есть]

Дата: _______________
Подпись: _______________ / [ФИО]"

## СТИЛЬ
- Официальный, уверенный, НЕ просящий, а ТРЕБУЮЩИЙ
- Без эмоций, только факты и закон
- Юридически грамотный язык

## КРИТИЧЕСКИ ВАЖНО
- ⚠️ НИКОГДА НЕ ИСПОЛЬЗУЙ MARKDOWN! Текст должен быть ЧИСТЫМ — без звёздочек, решёток, кавычек для форматирования
- Используй ВСЮ информацию из диалога — каждый факт!
- ⚠️ ОБЯЗАТЕЛЬНО включи полные реквизиты ответчика (название, ИНН, юрадрес) если они предоставлены!
- ⚠️ НИКОГДА НЕ ПРИДУМЫВАЙ ДАННЫЕ! Если отчество не указано — не добавляй его!
- Если ФИО неполное — пиши как есть, БЕЗ отчества
- Жалоба должна быть объёмной и солидной (минимум 1-2 страницы)"""

    def process(self, context: Dict) -> Dict:
        """Генерирует текст жалобы"""
        
        qa_pairs = context.get("qa_pairs", [])
        category_name = context.get("category_name", "Общая жалоба")
        user_data = context.get("user_data", {})
        company_data = context.get("company_data", {})  # Реквизиты компании из DaData
        
        print(f"[DEBUG] ComplaintAgent received company_data: {company_data}")
        
        # Формируем контекст
        qa_text = ""
        if qa_pairs:
            for i, qa in enumerate(qa_pairs, 1):
                qa_text += f"{i}. {qa['question']}\n   Ответ: {qa['answer']}\n\n"
        
        # Формируем блок реквизитов организации-ответчика
        company_details = ""
        if company_data:
            company_name = company_data.get('name', company_data.get('value', 'Не указано'))
            company_inn = company_data.get('inn', 'Не указан')
            company_ogrn = company_data.get('ogrn', 'Не указан')
            company_kpp = company_data.get('kpp', 'Не указан')
            company_address = company_data.get('address', 'Не указан')
            company_director = company_data.get('director', 'Не указан')
            company_director_post = company_data.get('director_post', '')
            
            director_str = company_director
            if company_director_post:
                director_str = f"{company_director_post}: {company_director}"
            
            company_details = f"""
═══════════════════════════════════════
РЕКВИЗИТЫ ОРГАНИЗАЦИИ-ОТВЕТЧИКА (из базы данных):
═══════════════════════════════════════
Полное наименование: {company_name}
ИНН: {company_inn}
ОГРН: {company_ogrn}
КПП: {company_kpp}
Юридический адрес: {company_address}
Руководитель: {director_str}

⚠️ ОБЯЗАТЕЛЬНО ВКЛЮЧИ ЭТИ РЕКВИЗИТЫ В ТЕКСТ ЖАЛОБЫ!
"""
        
        user_prompt = f"""НАПИШИ МОЩНУЮ ЖАЛОБУ на основе собранной информации:

КАТЕГОРИЯ: {category_name}

═══════════════════════════════════════
МАТЕРИАЛЫ ДЕЛА (из опроса клиента):
═══════════════════════════════════════
{qa_text if qa_text else 'Детали не предоставлены'}
{company_details}
═══════════════════════════════════════
ДАННЫЕ ЗАЯВИТЕЛЯ:
═══════════════════════════════════════
ФИО: {user_data.get('fio', '[ФИО заявителя]')}
Адрес: {user_data.get('address', '[Адрес заявителя]')}
Телефон: {user_data.get('phone', '[Телефон]')}
Email: {user_data.get('email', '[Email]')}

⚠️ ВАЖНО: Текст должен быть БЕЗ MARKDOWN — никаких звёздочек, решёток, форматирования!
Напиши ПОЛНЫЙ текст жалобы. Шапку оставь с плейсхолдером [название органа] — получатель будет выбран позже."""
        
        # Используем Claude Sonnet 4.5 для написания текста жалобы
        result = self._call_llm(self.system_prompt, user_prompt, temperature=0.7, model=Config.COMPLAINT_MODEL)
        
        if result:
            return {
                "success": True,
                "complaint_text": result.strip(),
                "can_edit": True
            }
        
        return {
            "success": False,
            "error": "Не удалось сгенерировать жалобу"
        }


class RecipientAgent(SubAgent):
    """Агент для рекомендации получателей жалобы"""
    
    def __init__(self):
        super().__init__("RecipientAgent")
        
        self.system_prompt = """Ты — эксперт по российскому законодательству. Проанализируй жалобу и определи РЕЛЕВАНТНЫХ получателей на РАЗНЫХ УРОВНЯХ с объяснением.

## УРОВНИ ИНСТАНЦИЙ (для каждого органа предлагай РАЗНЫЕ уровни!)

Для большинства органов существуют уровни:
- 🏠 **местный** — районный/городской уровень (быстрее рассмотрят, знают местную специфику)
- 🏛️ **региональный** — уровень субъекта РФ (если местный не помог, более серьёзный подход)
- 🏛️ **федеральный** — центральный аппарат (крайняя мера, серьёзные/системные нарушения)

## ОРГАНЫ С УРОВНЯМИ:

### ПРОКУРАТУРА
- Районная прокуратура (местный)
- Прокуратура субъекта РФ (региональный)
- Генеральная прокуратура РФ (федеральный)

### ТРУДОВАЯ ИНСПЕКЦИЯ (ГИТ)
- ГИТ города/района (местный)
- ГИТ субъекта РФ (региональный)
- Роструд (федеральный)

### РОСПОТРЕБНАДЗОР
- Территориальный отдел Роспотребнадзора (местный)
- Управление Роспотребнадзора по субъекту (региональный)
- Роспотребнадзор РФ (федеральный)

### ЖИЛИЩНАЯ ИНСПЕКЦИЯ
- Жилинспекция района (местный)
- Госжилинспекция субъекта РФ (региональный)

### ПОЛИЦИЯ
- Отдел полиции района (местный)
- УМВД по субъекту (региональный)
- МВД России (федеральный)

## ОРГАНЫ БЕЗ УРОВНЕЙ (только федеральные):
- ЦБ РФ, ФАС, СК РФ, Роскомнадзор, Росздравнадзор, Рособрнадзор, Администрация Президента

## ФОРМАТ ОТВЕТА (строго JSON):
{
    "recipients": [
        {
            "id": "prosecution_local",
            "name": "Прокуратура Колпинского района СПб",
            "level": "местный",
            "priority": "primary",
            "reason": "Начните с районной прокуратуры — быстрее отреагируют на местное нарушение",
            "effectiveness": "high"
        },
        {
            "id": "prosecution_regional",
            "name": "Прокуратура Санкт-Петербурга",
            "level": "региональный",
            "priority": "secondary",
            "reason": "Если районная не поможет — обращайтесь в городскую",
            "effectiveness": "medium"
        }
    ]
}

## ПРАВИЛА:
1. Для КАЖДОГО типа органа предлагай 2-3 УРОВНЯ
2. Объясни почему КАЖДЫЙ уровень имеет смысл
3. Укажи effectiveness: high/medium/low
4. Учитывай регион пользователя если известен (подставляй КОНКРЕТНЫЕ названия)
5. primary — рекомендуемые варианты, secondary — на случай если первые не помогут"""

    def process(self, context: Dict) -> Dict:
        """Рекомендует получателей на основе жалобы"""
        
        qa_pairs = context.get("qa_pairs", [])
        complaint_text = context.get("complaint_text", "")
        category_name = context.get("category_name", "")
        user_data = context.get("user_data", {})
        company_data = context.get("company_data", {})  # Реквизиты компании из DaData
        
        # Используем структурированные данные о местоположении от DaData
        # Приоритет: city_district > city > area > region
        company_region = company_data.get("region", "")
        company_city = company_data.get("city", "")
        company_city_district = company_data.get("city_district", "")
        company_area = company_data.get("area", "")
        company_settlement = company_data.get("settlement", "")
        company_address = company_data.get("address", "")
        
        # Формируем строку подведомственности от самого точного к общему
        jurisdiction_parts = []
        if company_city_district:
            jurisdiction_parts.append(f"Район города: {company_city_district}")
        if company_city:
            jurisdiction_parts.append(f"Город: {company_city}")
        if company_area:
            jurisdiction_parts.append(f"Район области: {company_area}")
        if company_settlement:
            jurisdiction_parts.append(f"Населённый пункт: {company_settlement}")
        if company_region:
            jurisdiction_parts.append(f"Регион: {company_region}")
        
        jurisdiction_info = "\n".join(jurisdiction_parts) if jurisdiction_parts else "Не определено из адреса"
        
        qa_text = ""
        if qa_pairs:
            for i, qa in enumerate(qa_pairs, 1):
                qa_text += f"{i}. {qa['question']}\n   Ответ: {qa['answer']}\n\n"
        
        # Формируем информацию о компании-ответчике с полными данными
        company_info = ""
        if company_data:
            company_info = f"""
ОРГАНИЗАЦИЯ-ОТВЕТЧИК:
- Наименование: {company_data.get('name', company_data.get('value', 'Не указано'))}
- ИНН: {company_data.get('inn', 'Не указан')}
- Юридический адрес: {company_address if company_address else 'Не указан'}

ПОДВЕДОМСТВЕННОСТЬ (по юридическому адресу компании):
{jurisdiction_info}
"""
        
        user_prompt = f"""Проанализируй жалобу и определи получателей на РАЗНЫХ УРОВНЯХ:

КАТЕГОРИЯ: {category_name}
{company_info}
СУТЬ ПРОБЛЕМЫ:
{qa_text if qa_text else 'Не указано'}

ТЕКСТ ЖАЛОБЫ:
{complaint_text[:2000] if complaint_text else 'Не сгенерирован'}

Для КАЖДОГО релевантного органа предложи ВСЕ УРОВНИ (местный, региональный, федеральный).
Укажи level, reason и effectiveness для каждого.
Используй КОНКРЕТНЫЕ названия органов по региону (например "Прокуратура Колпинского района г. Санкт-Петербурга").
ПОДВЕДОМСТВЕННОСТЬ определяй по адресу ОРГАНИЗАЦИИ, а не заявителя!

JSON:"""
        
        # Используем Claude Opus 4.6 для определения адресатов
        result = self._call_llm(self.system_prompt, user_prompt, temperature=0.3, model=Config.RECIPIENT_MODEL)
        
        if result:
            json_str = llm_service._extract_json(result)
            if json_str:
                try:
                    data = json.loads(json_str)
                    return self._enrich_recipients(data)
                except:
                    pass
        
        # Fallback
        return self._get_fallback_recipients(context.get("category", "other"))
    
    def _enrich_recipients(self, data: Dict) -> Dict:
        """Обогащает данные получателей информацией из базы"""
        
        enriched = []
        for rec_info in data.get("recipients", []):
            rec_id = rec_info.get("id")
            rec_db = RECIPIENTS.get(rec_id, {})
            
            enriched.append({
                "id": rec_id,
                "name": rec_info.get("name") or rec_db.get("name", rec_id),
                "priority": rec_info.get("priority", "secondary"),
                "level": rec_info.get("level", ""),  # местный/региональный/федеральный
                "reason": rec_info.get("reason", rec_db.get("reason", "")),
                "effectiveness": rec_info.get("effectiveness", "medium"),  # high/medium/low
                "email": rec_db.get("email"),
                "website": rec_db.get("website"),
                "jurisdiction": rec_db.get("jurisdiction", ""),
                "is_custom": rec_id not in RECIPIENTS
            })
        
        return {"recipients": enriched}
    
    def _get_fallback_recipients(self, category: str) -> Dict:
        """Fallback рекомендации по категории"""
        
        recommendations = RECIPIENT_RECOMMENDATIONS.get(category, {"primary": ["prosecution"], "secondary": []})
        
        enriched = []
        for rec_id in recommendations["primary"]:
            rec = RECIPIENTS.get(rec_id, {})
            enriched.append({
                "id": rec_id,
                "name": rec.get("name", rec_id),
                "priority": "primary",
                "reason": rec.get("reason", ""),
                "email": rec.get("email"),
                "website": rec.get("website"),
                "jurisdiction": rec.get("jurisdiction", ""),
                "is_custom": False
            })
        
        for rec_id in recommendations["secondary"]:
            rec = RECIPIENTS.get(rec_id, {})
            enriched.append({
                "id": rec_id,
                "name": rec.get("name", rec_id),
                "priority": "secondary",
                "reason": rec.get("reason", ""),
                "email": rec.get("email"),
                "website": rec.get("website"),
                "jurisdiction": rec.get("jurisdiction", ""),
                "is_custom": False
            })
        
        return {"recipients": enriched}


class SendAgent(SubAgent):
    """Агент для отправки жалобы с получением актуальных контактов"""
    
    def __init__(self):
        super().__init__("SendAgent")
        self._verification_service = None
    
    @property
    def verification_service(self):
        if self._verification_service is None:
            from services.contact_verification_service import contact_verification_service
            self._verification_service = contact_verification_service
        return self._verification_service
    
    def process(self, context: Dict) -> Dict:
        """Подготавливает данные для отправки — СНАЧАЛА получает актуальные контакты"""
        
        complaint_text = context.get("complaint_text", "")
        recipients = context.get("selected_recipients", [])
        user_data = context.get("user_data", {})
        category_name = context.get("category_name", "")
        
        results = []
        
        for recipient in recipients:
            recipient_name = recipient.get("name", "Государственный орган")
            recipient_id = recipient.get("id", "")
            
            # Заменяем плейсхолдер в шапке
            final_text = complaint_text.replace("[название органа]", recipient_name)
            
            result = {
                "recipient_id": recipient_id,
                "recipient_name": recipient_name,
                "complaint_text": final_text,
                "status": "ready"
            }
            
            # СНАЧАЛА получаем актуальные контакты через Perplexity
            print(f"SendAgent: Fetching fresh contacts for {recipient_name} via Perplexity...")
            verified = self.verification_service.verify_and_get_contacts(
                recipient_name, 
                category_name
            )
            
            # Используем свежие данные от Perplexity если получены
            if verified.get("verified"):
                email = verified.get("email")
                website = verified.get("portal_url")
                portal_name = verified.get("portal_name")
                auth_method = verified.get("auth_method")
                portal_instructions = verified.get("portal_instructions")
                address = verified.get("address")
                jurisdiction_level = verified.get("jurisdiction_level")
                recommendation = verified.get("recommendation")
                print(f"SendAgent: Got fresh data - email: {email}, portal: {website}, addr: {address}")
                
                if portal_name:
                    result["portal_name"] = portal_name
                if auth_method:
                    result["auth_method"] = auth_method
                if portal_instructions:
                    result["portal_instructions"] = portal_instructions
                if address:
                    result["address"] = address
                if jurisdiction_level:
                    result["jurisdiction_level"] = jurisdiction_level
                if recommendation:
                    result["recommendation"] = recommendation
                result["source"] = verified.get("source", "Perplexity")
                result["confidence"] = verified.get("confidence", "unknown")
            else:
                # Fallback на статичные данные если Perplexity не ответил
                print(f"SendAgent: Perplexity failed, using static data for {recipient_name}")
                email = recipient.get("email")
                website = recipient.get("website")
                result["source"] = "static_database"
                result["confidence"] = "static"
            
            if email:
                result["method"] = "email"
                result["email"] = email
                result["mailto_link"] = self._generate_mailto_link(
                    email=email,
                    subject=f"Жалоба на {category_name}" if category_name else "Жалоба",
                    body=final_text,
                    user_email=user_data.get("email", "")
                )
            elif website:
                result["method"] = "portal"
            else:
                result["method"] = "manual"
            
            if website:
                result["website"] = website
            
            results.append(result)
        
        return {
            "success": True,
            "results": results,
            "total_recipients": len(results),
            "user_data": user_data,
            "category_name": category_name
        }
    
    def _generate_mailto_link(
        self, 
        email: str, 
        subject: str, 
        body: str,
        user_email: str = ""
    ) -> str:
        """Генерирует mailto ссылку с закодированными параметрами"""
        import urllib.parse
        
        # Ограничиваем длину тела письма для mailto (некоторые клиенты имеют лимит ~2000 символов в URL)
        # Показываем начало и приглашаем открыть полный текст
        max_body_length = 1500
        if len(body) > max_body_length:
            body = body[:max_body_length] + "\n\n[Полный текст жалобы прикреплён в PDF]"
        
        params = {
            "subject": subject,
            "body": body
        }
        
        # Добавляем CC на email пользователя для копии
        if user_email:
            params["cc"] = user_email
        
        query_string = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        
        return f"mailto:{email}?{query_string}"


# Экспорт агентов
quiz_agent = QuizAgent()
complaint_agent = ComplaintAgent()
recipient_agent = RecipientAgent()
send_agent = SendAgent()

