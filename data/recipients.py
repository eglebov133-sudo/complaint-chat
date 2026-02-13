"""
База данных получателей жалоб
Расширенные данные с юрисдикцией, подведомственностью и причинами обращения
"""

RECIPIENTS = {
    # === ПРОКУРАТУРА (надзор за всеми) ===
    "prosecution": {
        "name": "Прокуратура РФ",
        "email": "genproc@genproc.gov.ru",
        "website": "https://epp.genproc.gov.ru/web/gprf/internet-reception",
        "jurisdiction": "Надзор за всеми органами власти и организациями",
        "reason": "Универсальный орган надзора. Обязаны реагировать если другие органы бездействуют. Могут привлечь к ответственности чиновников.",
        "when_effective": "Когда другие органы не помогли или бездействуют; при системных нарушениях; при коррупции",
        "priority": 1
    },
    
    # === ТРУДОВЫЕ СПОРЫ ===
    "git": {
        "name": "Трудовая инспекция (ГИТ)",
        "email": "git@rostrud.ru",
        "website": "https://онлайнинспекция.рф",
        "jurisdiction": "Контроль соблюдения трудового законодательства",
        "reason": "Могут провести внеплановую проверку работодателя, выдать предписание, наложить штраф. Защищают права работников.",
        "when_effective": "Невыплата зарплаты, незаконное увольнение, нарушение условий труда, отказ в отпуске",
        "priority": 1
    },
    "rostrud": {
        "name": "Роструд (Федеральная служба)",
        "email": "rostrud@rostrud.ru", 
        "website": "https://rostrud.gov.ru",
        "jurisdiction": "Вышестоящий орган над трудовыми инспекциями",
        "reason": "Обращайтесь сюда если местная ГИТ не помогла. Могут дать указания региональным инспекциям.",
        "when_effective": "Если ГИТ бездействует или вынесла неверное решение",
        "priority": 2
    },
    
    # === ЗАЩИТА ПОТРЕБИТЕЛЕЙ ===
    "rospotrebnadzor": {
        "name": "Роспотребнадзор",
        "email": "depart@gsen.ru",
        "website": "https://petition.rospotrebnadzor.ru",
        "jurisdiction": "Защита прав потребителей, санитарный контроль",
        "reason": "Могут провести проверку магазина/компании, выдать предписание, оштрафовать. Помогают вернуть деньги за товар.",
        "when_effective": "Некачественный товар, обман потребителя, отказ в возврате, навязывание услуг, антисанитария",
        "priority": 1
    },
    "ozpp": {
        "name": "Общество защиты прав потребителей",
        "email": None,
        "website": "https://ozpp.ru",
        "jurisdiction": "Общественная организация по защите прав",
        "reason": "Бесплатные консультации, помощь в составлении претензий, могут представлять в суде. Не госорган, но эффективны.",
        "when_effective": "Нужна юридическая помощь по потребительским спорам",
        "priority": 3
    },
    
    # === ЖКХ ===
    "housing_inspection": {
        "name": "Жилищная инспекция",
        "email": None,
        "website": "https://dom.gosuslugi.ru",
        "jurisdiction": "Контроль управляющих компаний и ТСЖ",
        "reason": "Могут обязать УК устранить нарушения, провести перерасчёт, лишить лицензии. Главный орган по ЖКХ.",
        "when_effective": "Проблемы с УК, некачественные услуги ЖКХ, неправильные начисления, плохое содержание дома",
        "priority": 1
    },
    "minstroyrf": {
        "name": "Минстрой России",
        "email": "info@minstroyrf.gov.ru",
        "website": "https://minstroyrf.gov.ru",
        "jurisdiction": "Федеральное министерство, курирует ЖКХ всей страны",
        "reason": "Обращайтесь при системных проблемах или если регион не справляется. Дают указания региональным органам.",
        "when_effective": "Массовые нарушения в ЖКХ, бездействие местных органов",
        "priority": 2
    },
    
    # === ПРАВООХРАНИТЕЛЬНЫЕ ОРГАНЫ ===
    "police": {
        "name": "Полиция (МВД)",
        "email": None,
        "website": "https://mvd.ru/request_main",
        "jurisdiction": "Расследование преступлений и правонарушений",
        "reason": "Обязаны принять заявление о любом преступлении. Могут возбудить уголовное дело, задержать нарушителя.",
        "when_effective": "Мошенничество, кража, угрозы, побои, вымогательство, порча имущества",
        "priority": 1
    },
    "investigative_committee": {
        "name": "Следственный комитет (СК РФ)",
        "email": None,
        "website": "https://sledcom.ru/reception",
        "jurisdiction": "Расследование тяжких преступлений",
        "reason": "Расследуют серьёзные дела: убийства, коррупцию чиновников, преступления против детей. Если полиция бездействует.",
        "when_effective": "Тяжкие преступления, коррупция должностных лиц, бездействие полиции",
        "priority": 2
    },
    "fsb": {
        "name": "ФСБ России",
        "email": None,
        "website": "https://www.fsb.ru/fsb/webreception.htm",
        "jurisdiction": "Контрразведка, терроризм, госбезопасность",
        "reason": "Принимают сообщения о терроризме, шпионаже, коррупции высокопоставленных лиц.",
        "when_effective": "Террор, экстремизм, крупная коррупция на уровне региона/страны",
        "priority": 3
    },
    
    # === ФИНАНСОВЫЙ СЕКТОР ===
    "central_bank": {
        "name": "Центральный банк РФ",
        "email": None,
        "website": "https://cbr.ru/reception/",
        "jurisdiction": "Регулирование банков, МФО, страховых компаний",
        "reason": "Главный регулятор. Могут оштрафовать банк, отозвать лицензию. Банки боятся жалоб в ЦБ.",
        "when_effective": "Незаконные списания, скрытые комиссии, отказ в обслуживании, навязывание страховок",
        "priority": 1
    },
    "aro": {
        "name": "Финансовый омбудсмен",
        "email": None,
        "website": "https://finombudsman.ru",
        "jurisdiction": "Досудебное урегулирование споров с финансовыми организациями",
        "reason": "Бесплатно решает споры до 500 тыс. ₽. Решение обязательно для банка. Быстрее и проще суда.",
        "when_effective": "Споры с банками/страховыми до 500 000 рублей",
        "priority": 1
    },
    "rosfinmonitoring": {
        "name": "Росфинмониторинг",
        "email": None,
        "website": "https://fedsfm.ru",
        "jurisdiction": "Противодействие отмыванию денег и финансированию терроризма",
        "reason": "Принимают сообщения о подозрительных финансовых операциях, отмывании денег.",
        "when_effective": "Подозрение на отмывание денег, финансирование терроризма",
        "priority": 3
    },
    
    # === АНТИМОНОПОЛЬНОЕ РЕГУЛИРОВАНИЕ ===
    "fas": {
        "name": "ФАС России (антимонопольная служба)",
        "email": "delo@fas.gov.ru",
        "website": "https://fas.gov.ru/approaches/send_to_fas",
        "jurisdiction": "Защита конкуренции, контроль рекламы и госзакупок",
        "reason": "Могут оштрафовать за незаконную рекламу, картельный сговор, завышение цен монополистом.",
        "when_effective": "Обманная реклама, завышенные цены монополиста, нарушения в госзакупках",
        "priority": 1
    },
    
    # === ПЕРСОНАЛЬНЫЕ ДАННЫЕ ===
    "roskomnadzor": {
        "name": "Роскомнадзор",
        "email": "rsoc_in@rkn.gov.ru",
        "website": "https://rkn.gov.ru/treatments/ask-question/",
        "jurisdiction": "Защита персональных данных, контроль СМИ и связи",
        "reason": "Могут оштрафовать за утечку данных, спам-звонки, незаконный сбор информации. Блокируют сайты.",
        "when_effective": "Утечка персональных данных, спам, незаконная обработка данных, передача третьим лицам",
        "priority": 1
    },
    
    # === МЕДИЦИНА ===
    "roszdravnadzor": {
        "name": "Росздравнадзор",
        "email": None,
        "website": "https://roszdravnadzor.gov.ru",
        "jurisdiction": "Контроль качества медицинской помощи",
        "reason": "Проверяют больницы и клиники, могут лишить лицензии. Главный орган по медицинским жалобам.",
        "when_effective": "Врачебная ошибка, некачественное лечение, отказ в помощи, навязывание платных услуг",
        "priority": 1
    },
    "minzdrav": {
        "name": "Минздрав России",
        "email": None,
        "website": "https://minzdrav.gov.ru",
        "jurisdiction": "Федеральное министерство здравоохранения",
        "reason": "Вышестоящий орган над Росздравнадзором. Обращайтесь при серьёзных системных проблемах.",
        "when_effective": "Системные проблемы в здравоохранении, бездействие Росздравнадзора",
        "priority": 2
    },
    "oms_fond": {
        "name": "Территориальный фонд ОМС",
        "email": None,
        "website": None,
        "jurisdiction": "Контроль оказания медпомощи по ОМС",
        "reason": "Защищают права застрахованных по ОМС. Могут наказать больницу рублём.",
        "when_effective": "Отказ в бесплатной помощи, требование оплаты за услуги по ОМС, очереди на обследования",
        "priority": 1
    },
    
    # === ОБРАЗОВАНИЕ ===
    "rosobrnadzor": {
        "name": "Рособрнадзор",
        "email": None,
        "website": "https://obrnadzor.gov.ru",
        "jurisdiction": "Контроль качества образования",
        "reason": "Проверяют школы, вузы, детсады. Могут лишить аккредитации.",
        "when_effective": "Нарушения в школе/вузе, поборы, некачественное образование, нарушение прав учащихся",
        "priority": 1
    },
    
    # === ТРАНСПОРТ ===
    "rostransnadzor": {
        "name": "Ространснадзор",
        "email": None,
        "website": "https://rostransnadzor.gov.ru",
        "jurisdiction": "Контроль безопасности на транспорте",
        "reason": "Контролируют авиа, ж/д, водный транспорт. Могут наказать перевозчика.",
        "when_effective": "Проблемы с авиа/ж/д билетами, задержки рейсов, потеря багажа, небезопасные условия",
        "priority": 1
    },
    
    # === НАЛОГИ ===
    "fns": {
        "name": "ФНС России (налоговая)",
        "email": None,
        "website": "https://www.nalog.gov.ru",
        "jurisdiction": "Налоговый контроль",
        "reason": "Принимают сообщения об уклонении от налогов, незаконном предпринимательстве.",
        "when_effective": "Работодатель не платит налоги, незаконное предпринимательство, серая зарплата",
        "priority": 2
    },
    
    # === ПРЕЗИДЕНТ И ПРАВИТЕЛЬСТВО ===
    "president_admin": {
        "name": "Администрация Президента РФ",
        "email": None,
        "website": "http://letters.kremlin.ru",
        "jurisdiction": "Приём обращений граждан к Президенту",
        "reason": "Обращения перенаправляются в соответствующие органы с контролем исполнения. Эффект 'сверху'.",
        "when_effective": "Когда все остальные органы не помогли, при системных проблемах государственного уровня",
        "priority": 3
    },
    "government_rf": {
        "name": "Правительство РФ",
        "email": None,
        "website": "https://services.government.ru/letters/",
        "jurisdiction": "Исполнительная власть страны",
        "reason": "Могут дать поручение министерствам разобраться. Эффективно при бездействии ведомств.",
        "when_effective": "Бездействие федеральных органов, межведомственные проблемы",
        "priority": 3
    },
    
    # === УПОЛНОМОЧЕННЫЕ ПО ПРАВАМ ===
    "ombudsman": {
        "name": "Уполномоченный по правам человека",
        "email": None,
        "website": "https://ombudsmanrf.org",
        "jurisdiction": "Защита прав и свобод человека",
        "reason": "Может проводить проверки, обращаться в суд в интересах граждан. Независим от власти.",
        "when_effective": "Нарушение конституционных прав, дискриминация, произвол властей",
        "priority": 2
    },
    "children_ombudsman": {
        "name": "Уполномоченный по правам ребёнка",
        "email": None,
        "website": "http://deti.gov.ru",
        "jurisdiction": "Защита прав детей",
        "reason": "Защищает права несовершеннолетних. Может вмешиваться в дела касающиеся детей.",
        "when_effective": "Нарушение прав ребёнка в школе, больнице, органами опеки",
        "priority": 1
    }
}

# Рекомендации получателей по типу проблемы (расширенные)
RECIPIENT_RECOMMENDATIONS = {
    "zhkh": {
        "primary": ["housing_inspection", "rospotrebnadzor"],
        "secondary": ["prosecution", "minstroyrf"]
    },
    "employer": {
        "primary": ["git", "prosecution"],
        "secondary": ["rostrud", "fns"]
    },
    "shop": {
        "primary": ["rospotrebnadzor", "fas"],
        "secondary": ["prosecution", "ozpp", "police"]
    },
    "bank": {
        "primary": ["central_bank", "aro"],
        "secondary": ["rospotrebnadzor", "roskomnadzor", "prosecution"]
    },
    "government": {
        "primary": ["prosecution"],
        "secondary": ["ombudsman", "president_admin", "investigative_committee"]
    },
    "neighbors": {
        "primary": ["police", "housing_inspection"],
        "secondary": ["prosecution", "rospotrebnadzor"]
    },
    "medical": {
        "primary": ["roszdravnadzor", "oms_fond"],
        "secondary": ["prosecution", "minzdrav", "rospotrebnadzor"]
    },
    "education": {
        "primary": ["rosobrnadzor"],
        "secondary": ["prosecution", "children_ombudsman"]
    },
    "police_complaint": {
        "primary": ["prosecution", "investigative_committee"],
        "secondary": ["ombudsman", "president_admin"]
    },
    "personal_data": {
        "primary": ["roskomnadzor"],
        "secondary": ["prosecution", "rospotrebnadzor"]
    },
    "transport": {
        "primary": ["rostransnadzor", "rospotrebnadzor"],
        "secondary": ["prosecution", "fas"]
    },
    "other": {
        "primary": ["prosecution"],
        "secondary": ["rospotrebnadzor", "ombudsman"]
    }
}

# Категории жалоб (расширенные)
COMPLAINT_CATEGORIES = {
    "zhkh": {
        "name": "Управляющая компания / ЖКХ",
        "problems": [
            {"id": "noise", "name": "Шум, нарушение тишины"},
            {"id": "flooding", "name": "Затопление, протечки"},
            {"id": "garbage", "name": "Не вывозят мусор"},
            {"id": "heating", "name": "Плохое отопление"},
            {"id": "elevator", "name": "Неисправный лифт"},
            {"id": "cleaning", "name": "Не убирают подъезд/двор"},
            {"id": "overcharge", "name": "Завышенные счета"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "employer": {
        "name": "Работодатель",
        "problems": [
            {"id": "salary", "name": "Невыплата/задержка зарплаты"},
            {"id": "schedule", "name": "Нарушение графика работы"},
            {"id": "mobbing", "name": "Моббинг, травля на работе"},
            {"id": "dismissal", "name": "Незаконное увольнение"},
            {"id": "safety", "name": "Нарушение охраны труда"},
            {"id": "discrimination", "name": "Дискриминация"},
            {"id": "contract", "name": "Нарушение трудового договора"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "shop": {
        "name": "Магазин / Интернет-сервис",
        "problems": [
            {"id": "defect", "name": "Бракованный товар"},
            {"id": "no_delivery", "name": "Не доставили товар"},
            {"id": "no_refund", "name": "Не возвращают деньги"},
            {"id": "fraud", "name": "Мошенничество"},
            {"id": "warranty", "name": "Отказ в гарантийном ремонте"},
            {"id": "quality", "name": "Плохое качество услуги"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "bank": {
        "name": "Банк / МФО / Страховая",
        "problems": [
            {"id": "fraud", "name": "Мошенничество с картой/счётом"},
            {"id": "loan", "name": "Незаконное списание по кредиту"},
            {"id": "pressure", "name": "Давление коллекторов"},
            {"id": "rate", "name": "Скрытые комиссии/проценты"},
            {"id": "personal_data", "name": "Разглашение данных"},
            {"id": "service", "name": "Отказ в обслуживании"},
            {"id": "insurance", "name": "Проблемы со страховкой"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "government": {
        "name": "Госорган / Чиновник",
        "problems": [
            {"id": "corruption", "name": "Коррупция, взятка"},
            {"id": "inaction", "name": "Бездействие чиновника"},
            {"id": "rudeness", "name": "Хамство, грубость"},
            {"id": "delay", "name": "Затягивание сроков"},
            {"id": "illegal", "name": "Незаконное решение"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "neighbors": {
        "name": "Соседи",
        "problems": [
            {"id": "noise", "name": "Шум (музыка, ремонт, крики)"},
            {"id": "flooding", "name": "Затопили квартиру"},
            {"id": "smoke", "name": "Курение в подъезде"},
            {"id": "trash", "name": "Мусор на площадке"},
            {"id": "threats", "name": "Угрозы, агрессия"},
            {"id": "animals", "name": "Проблемы с животными"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "medical": {
        "name": "Больница / Поликлиника",
        "problems": [
            {"id": "error", "name": "Врачебная ошибка"},
            {"id": "refusal", "name": "Отказ в помощи"},
            {"id": "paid", "name": "Требуют деньги за бесплатное"},
            {"id": "queue", "name": "Большие очереди"},
            {"id": "rudeness", "name": "Хамство персонала"},
            {"id": "quality", "name": "Некачественное лечение"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "police_complaint": {
        "name": "Полиция (жалоба НА полицию)",
        "problems": [
            {"id": "refusal", "name": "Отказ принять заявление"},
            {"id": "inaction", "name": "Бездействие по делу"},
            {"id": "rudeness", "name": "Грубое обращение"},
            {"id": "illegal", "name": "Незаконные действия"},
            {"id": "lost_docs", "name": "Потеряли документы"},
            {"id": "other", "name": "Другое"}
        ]
    },
    "other": {
        "name": "Другое",
        "problems": []
    },
    # Категории для организаций
    "contractor": {
        "name": "Контрагент / Поставщик",
        "problems": []
    },
    "tax": {
        "name": "Налоговая инспекция",
        "problems": []
    },
    "landlord": {
        "name": "Арендодатель / Арендатор",
        "problems": []
    },
    "competitor": {
        "name": "Недобросовестная конкуренция",
        "problems": []
    },
    "utilities": {
        "name": "Коммунальные / Ресурсоснабжающие",
        "problems": []
    },
    "subcontractor": {
        "name": "Подрядчик / Исполнитель",
        "problems": []
    }
}
