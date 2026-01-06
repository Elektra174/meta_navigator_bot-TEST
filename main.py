import os
import asyncio
import traceback
import logging
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from cerebras.cloud.sdk import AsyncCerebras
from aiohttp import web, ClientSession
import aiohttp
from io import BytesIO

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
CEREBRAS_API_KEY = os.getenv("AI_API_KEY")
CHANNEL_ID = "@metaformula_life"
ADMIN_ID = 7830322013

# Ресурсы проекта
LOGO_FORMULA_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png.png"
LOGO_NAVIGATOR_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
GUIDE_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot-TEST/main/revizia_guide.pdf"
GUIDE_FILENAME = "ДЕШИФРОВКА_АВТОПИЛОТА.pdf"
MASTERCLASS_URL = "https://youtube.com/playlist?list=PLyour_playlist_id"
CHANNEL_URL = "https://t.me/metaformula_life"

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация клиентов
client = AsyncCerebras(api_key=CEREBRAS_API_KEY) if CEREBRAS_API_KEY else None
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Глобальные счетчики телеметрии
error_counter = 0
api_failures = 0
start_time = datetime.now()

class AuditState(StatesGroup):
    answering_questions = State()

# --- ОБНОВЛЕННЫЙ СПИСОК ВОПРОСОВ (8 ШАГОВ АУДИТА С НОВОЙ ТЕРМИНОЛОГИЕЙ) ---
QUESTIONS = [
    # Шаг 1: Локализация сбоя
    "🔎 **Шаг 1: Локализация сбоя.**\n\nВ какой сфере жизни ваш Автопилот сейчас «буксует» больше всего? Опишите ситуацию, где вы чувствуете невидимую стену или застой.",
    
    # Шаг 2: Проектирование Мета-маяка
    "🔭 **Шаг 2: Мета-маяк.**\n\nПредставьте, что настройки вашей программы обновились и этот затык исчез. КТО ВЫ в этой ситуации? Опишите свою эталонное состояние (например: «Масштабный Архитектор», «Спокойный Лидер», «Творец своей реальности»).",
    
    # Шаг 3: Режим заставки (Утечка энергии)
    "📉 **Шаг 3: Режим заставки.**\n\nНа какие фоновые мысли, сомнения или пустые действия ваш мозг ежедневно сливает энергию, вместо того чтобы двигаться к желаемому будущему?",
    
    # Шаг 4: Внешний образ проблемы
    "🧱 **Шаг 4: Образ преграды.**\n\nЕсли бы ваш застой был физическим предметом или образом, как бы он выглядел? (Например: «бетонная плита», «липкая трясина», «черная стена»).",
    
    # Шаг 5: Поиск датчика в теле
    "🧬 **Шаг 5: Телесный датчик.**\n\nЧто вы ощущаете глядя на этот образ? Опишит: это сжатие в груди, холод в животе, ком в горле? Это ключевой сигнал вашего старого контура.",
    
    # Шаг 6: Скан скрытой силы (Тень)
    "⚡️ **Шаг 6: Зеркало Силы.**\n\nКакое качество в других людях вас больше всего раздражает или бесит? Часто именно в этом раздражении заперт ваш ресурс, который Автопилот (Биологический контур) запрещает вам использовать.",
    
    # Шаг 7: Расчет цены бездействия
    "💸 **Шаг 7: Цена старой прошивки.**\n\nЧего вам стоит сохранение текущей ситуации? Посчитайте: сколько денег, времени или возможностей вы теряете ежемесячно, пока система работает на старых настройках?",
    
    # Шаг 8: Команда на инсталляцию
    "🚀 **Шаг 8: Смена режима.**\n\nВы готовы прямо сейчас перестать быть «пассажиром» Автопилота и занять место Автора, чтобы перепрошить свой Биологический Контур? (напишите Да или Нет)"
]

# --- РАЗНЫЕ ПРИВЕТСТВИЯ ---
WELCOME_MESSAGES = {
    "not_subscribed": {
        "title": "Добро пожаловать в «Метаформулу Жизни»",
        "text": "Меня зовут Александр Лазаренко. Я — автор проекта.\n\n"
                "Я создал Мета-навигатор, чтобы помочь Вам провести Аудит Автопилота и спроектировать ваш Мета-маяк.\n\n"
                "Чтобы начать, пожалуйста, подпишитесь на наш канал:",
        "logo": LOGO_FORMULA_URL
    },
    "subscribed": {
        "title": "👋 Добро пожаловать в Мета-Навигатор!",
        "text":  "Готовы начать??",
        "logo": LOGO_NAVIGATOR_URL
    }
}

# --- ОБНОВЛЕННЫЙ СИСТЕМНЫЙ ПРОМПТ (Строгий технический стиль) ---
SYSTEM_PROMPT = """ТЫ — СТАРШИЙ НЕЙРО-АРХИТЕКТОР ПРОЕКТА «МЕТАФОРМУЛА»

СТИЛЬ: Кибер-мистицизм — технический, лаконичный, экспертный, дорогой.

ЗАДАЧА: Сформировать «Техническое заключение по аудиту Автопилота (Биологического Контура)» на основе 8 ответов пользователя.

ТЕРМИНОЛОГИЯ:
- Автопилот (Биологический Контур)
- Мета-маяк (эталонное состояние из ответа №2)
- Коннектом
- Режим заставки
- Соматический маркер

АЛГОРИТМ СБОРКИ МЕТАФОРМУЛЫ (СТРОГО):
Формат: «Я — Автор. ПРИЗНАЮ [физический симптом из ответа №5] и ВЫБИРАЮ быть [роль/идентичность из ответа №2 — это и есть Мета-маяк]»
- Симптом — только физические ощущения (без метафор).
- Роль — активная, из Мета-маяка.

СТРУКТУРА ОТЧЕТА:

🧭 СТАТУС СИСТЕМЫ
[Краткое резюме: в каком состоянии находится Биологический Контур. Опиши конфликт между текущим блоком и выбранным Мета-маяком.]

📊 ИНДЕКС АВТОМАТИЗМА: [X]%
[Оценка того, насколько человек живет на Автопилоте (от 60% до 95%).]

🧠 ДИАГНОСТИКА КОНТУРА

🛑 УЗЕЛ СОПРОТИВЛЕНИЯ
[Анализ образа из ответа №4 и симптома из ответа №5. Как эта связка блокирует движение.]

💻 ХОЛОСТОЙ ХОД (РЕЖИМ ЗАСТАВКИ)
[Где происходит главная утечка ресурсов согласно ответу №3.]

🔋 РЕАКТОР ИДЕНТИЧНОСТИ
[Вскрытие скрытого ресурса из ответа №6. Как эта энергия усилит инсталляцию Мета-маяка.]

🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
[Сгенерированная формула по алгоритму выше.]

🚀 СЛЕДУЮЩИЙ ШАГ
[Инструкция: «Ваш код готов. Для физической прошивки кода в нейронную сеть переходите к Видео-практикуму».]

ПРАВИЛА ФОРМУЛИРОВОК:
- Говори технически точно: «Биологический Контур блокирует», «система утилизирует», «ресурс утекает»
- Избегай: «чувствуете», «понимаете», «осознаете»
- Используй: «система показывает», «анализ указывает», «данные свидетельствуют»

ОБРАЩЕНИЕ:
- На «Вы», но без излишней формальности
- Без «пользователь», «клиент»
- Без эмоциональных оценок
"""

# --- ФУНКЦИЯ ОТПРАВКИ ГАЙДА (КОРОТКАЯ ВЕРСИЯ) ---
async def download_and_send_pdf(message: types.Message):
    """Скачивает PDF и отправляет его с кратким описанием"""
    try:
        await message.answer("📥 **Загружаю ваш персональный гайд...**", parse_mode="Markdown")
        
        async with ClientSession() as session:
            async with session.get(GUIDE_URL) as response:
                if response.status != 200: 
                    raise Exception(f"Ошибка загрузки: {response.status}")
                pdf_data = await response.read()
        
        # Короткое описание на основе гайда
        caption_text = (
            "📘 Гайд «Дешифровка автопилота»\n\n"
            "Ваш протокол выхода из «Автопилота»:\n"
            "• Почему ум не помогает\n"
            "• Физика выгорания: газ + тормоз\n"
            "• Технология Внешнего Наблюдателя\n"
            "• Принцип Зеркала: ваша Тень = ваш ресурс\n"
            "• Механика Метаформулы\n\n"
            "Это инструкция по перепрошивке Биологического Контура."
        )

        await message.answer_document(
            document=types.BufferedInputFile(pdf_data, filename=GUIDE_FILENAME),
            caption=caption_text,
            parse_mode="Markdown"
        )
        return True
    except Exception as e:
        logger.error(f"PDF Error: {e}")
        await message.answer(f"⚠️ Ошибка загрузки гайда. Прямая ссылка: {GUIDE_URL}")
        return False

# --- ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЯ О СДВИГЕ К МК ---
async def send_mk_shift_message(message: types.Message):
    """Отправляет сообщение о сдвиге к видео-практикуму через задержку"""
    await asyncio.sleep(30)  # Ждем 30 секунд
    
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text='🎬 ИНСТАЛЛИРОВАТЬ КОД В ПРАКТИКУМЕ',
                url=MASTERCLASS_URL
            )
        )
        
        mk_message = (
            "🎯 Диагностика Автопилота завершена.\n\n"
            "Вы получили свою Метаформулу — это ваш «Мета-код» для перехвата управления у Автопилота. "
            "Но чтобы этот код стал вашей новой биологической программой, нужна практическая инсталляция.\n\n"
            "Для физической прошивки кода в нейронную сеть заберите пакет инструментов:\n\n"
            "• 🎬 Видео-практикум «Код Метаформулы»\n"
            "• Аудио-код «Перехватчик Автопилота»\n"
            "• Рабочая тетрадь «Протокол отладки»"
        )
        
        await message.answer(
            mk_message,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки MK сдвига: {e}")

# --- ФУНКЦИЯ ПРОВЕРКИ ПОДПИСКИ ---
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

# --- СИСТЕМА МОНИТОРИНГА ---
async def send_admin_alert(alert_type: str, details: str, tb: str = ""):
    global error_counter, api_failures
    try:
        ts = datetime.now().strftime("%d.%m %H:%M:%S")
        
        msg = f"🚨 СИГНАЛ: {alert_type.upper()}\n\n"
        msg += f"⏰ Время: {ts}\n"
        msg += f"📝 Детали: {details}\n"
        
        if tb:
            if len(tb) > 1000:
                msg += f"\n🔧 Трассировка: (отправлена отдельным файлом)"
                
                await bot.send_document(
                    chat_id=ADMIN_ID,
                    document=types.BufferedInputFile(
                        tb.encode('utf-8'),
                        filename=f"traceback_{ts.replace(':', '-').replace(' ', '_')}.txt"
                    ),
                    caption=f"Трассировка ошибки: {alert_type}"
                )
            else:
                msg += f"\n🔧 Трассировка:\n{tb[:800]}"
        
        msg += f"\n\n📊 Статистика: Ошибок: {error_counter} | Сбоев API: {api_failures}"
        
        await bot.send_message(chat_id=ADMIN_ID, text=msg)
    except Exception as e:
        logger.error(f"Не удалось отправить алерт: {e}")

async def send_admin_copy(user: types.User, answers: list, report: str):
    try:
        user_info = f"👤 {user.full_name} (@{user.username})"
        text_answers = "\n".join([f"{i+1}. {a}" for i, a in enumerate(answers)])
        
        full_log = (
            "🔔 НОВЫЙ АУДИТ АВТОПИЛОТА ЗАВЕРШЕН\n\n"
            f"{user_info}\n\n"
            "📝 Ответы пользователя:\n"
            f"{text_answers}\n\n"
            "🧠 Отчет ИИ:\n"
            f"{report}"
        )
        
        if len(full_log) > 4000:
            await bot.send_message(chat_id=ADMIN_ID, text=full_log[:4000])
            await bot.send_message(chat_id=ADMIN_ID, text=full_log[4000:8000] if len(full_log) > 8000 else full_log[4000:])
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=full_log)
    except Exception as e:
        logger.error(f"Ошибка лога админу: {e}")

def clean_report_for_telegram(report: str) -> str:
    """Постобработка технического заключения"""
    try:
        if not report:
            return report
            
        # Рассчитываем индекс
        automatism_index = calculate_automatism_index([])
        
        # Вставляем индекс в отчет
        if "ИНДЕКС" in report and "%" in report:
            report = re.sub(
                r'ИНДЕКС[ А-Я]+:\s*\[?X\]?%',
                f'ИНДЕКС АВТОМАТИЗМА: {automatism_index}%',
                report,
                flags=re.IGNORECASE
            )
        
        # Убираем все английские слова
        report = re.sub(r'\b[a-zA-Z]+\b', '', report)
        
        # Исправляем технические пометы
        report = re.sub(r'[Qq]\d+', '', report)
        report = re.sub(r'вопрос[ауе]?\s*\d+', '', report, flags=re.IGNORECASE)
        
        # Исправляем кривые грамматические конструкции
        grammar_fixes = {
            r'ступить на применять': 'начать применять',
            r'имеете силу ступить': 'можете начать',
            r'склонны к самоуверению': 'проявляете избыточную уверенность',
            r'имеете возможность': 'можете',
            r'управление своей жизни': 'управление своей жизнью',
            r'осуществлять действие': 'действовать',
            r'принять к действию': 'перейти к действию',
            r'стоит действовать': 'необходимо действовать',
            r'Ваши языковые шаблоны': 'Ваши речевые паттерны',
            r'вы уже довольно сильно автоматизированы': 'Биологический Контур высокоавтоматизирован',
            r'есть еще потенциал для роста': 'имеется ресурс для оптимизации контура',
            r'вы сейчас застряли': 'Биологический Контур находится в состоянии блокировки',
            r'тратите много энергии': 'происходит значительная утечка энергии',
            r'чувствуете, что': 'данные указывают, что',
            r'вам кажется': 'анализ показывает',
            r'вы понимаете': 'система демонстрирует',
            r'вы осознаете': 'наблюдается'
        }
        
        for error, correction in grammar_fixes.items():
            report = re.sub(error, correction, report, flags=re.IGNORECASE)
        
        # Убираем дублирование значков
        icon_pattern = r'([🧭📊🧠🛑💻🔋🔑🚀])\s*\1'
        report = re.sub(icon_pattern, r'\1', report)
        
        # Обрабатываем случаи, когда значки идут подряд без пробелов
        icon_pattern_no_space = r'([🧭📊🧠🛑💻🔋🔑🚀])\1'
        report = re.sub(icon_pattern_no_space, r'\1', report)
        
        # Убираем повторы между разделами
        lines = report.split('\n')
        unique_lines = []
        seen_content = set()
        
        for line in lines:
            # Проверяем, не является ли это заголовком
            if re.match(r'^[🧭📊🧠🛑💻🔋🔑🚀]', line.strip()):
                unique_lines.append(line)
                continue
                
            # Для обычных строк убираем повторяющийся контент
            line_content = re.sub(r'[^\w\s]', '', line.lower()).strip()
            if line_content and len(line_content) > 10:
                if line_content not in seen_content:
                    seen_content.add(line_content)
                    unique_lines.append(line)
            else:
                unique_lines.append(line)
        
        report = '\n'.join(unique_lines)
        
        # Убираем канцеляризмы
        bureaucratic = {
            'в связи с тем, что': 'поскольку',
            'является': '',
            'осуществлять': 'выполнять',
            'производить': 'создавать',
            'имеет место быть': 'наблюдается',
            'на данный момент': 'сейчас',
            'в рамках': 'в',
            'посредством': 'через',
            'в целях': 'для'
        }
        
        for can, simple in bureaucratic.items():
            report = report.replace(can, simple)
        
        # Проверяем структуру разделов - ОБНОВЛЕННЫЕ ЗАГОЛОВКИ
        section_fixes = {
            r'ЗАСТОЙНАЯ ДОМИНАНТА\s*\(.*?\)': '🛑 УЗЕЛ СОПРОТИВЛЕНИЯ',
            r'РЕЖИМ ЗАСТАВКИ\s*\(.*?\)': '💻 ХОЛОСТОЙ ХОД (РЕЖИМ ЗАСТАВКИ)',
            r'ТЕНЕВАЯ ИДЕНТИЧНОСТЬ\s*\(.*?\)': '🔋 РЕАКТОР ИДЕНТИЧНОСТИ',
            r'ВОЗВРАТ РЕСУРСА\s*\(.*?\)': '🔋 РЕАКТОР ИДЕНТИЧНОСТИ',
            r'ВАША МЕТАФОРМУЛА\s*\(.*?\)': '🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)'
        }
        
        for old, new in section_fixes.items():
            report = re.sub(old, new, report, flags=re.IGNORECASE)
        
        # Убираем лишние пробелы и пустые строки
        report = re.sub(r'\n{3,}', '\n\n', report)
        report = re.sub(r'[ \t]{2,}', ' ', report)
        
        # Убираем markdown разметку
        report = re.sub(r'[*_`]+', '', report)
        
        # Проверяем формулу (обновленный алгоритм с Мета-маяком)
        formula_pattern = r'🔑 ВАША МЕТАФОРМУЛА.*?\n(.+?)(?=\n\n|\n🚀|\n🎯|$)'
        match = re.search(formula_pattern, report, re.DOTALL | re.IGNORECASE)
        
        if match:
            formula = match.group(1).strip()
            # Проверяем, соответствует ли формула новому алгоритму
            if not ("Я — Автор" in formula and "ПРИЗНАЮ" in formula and "ВЫБИРАЮ" in formula and "быть" in formula):
                # Заменяем на правильную формулу
                correct_formula = generate_metaformula_from_answers([])
                report = report.replace(formula, correct_formula)
        
        # Заменяем обращение "пользователь" на "Вы"
        report = re.sub(r'\bпользователь\b', 'Вы', report, flags=re.IGNORECASE)
        
        # Заменяем старые термины на новые
        report = re.sub(r'\bАвтопилот\b', 'Автопилот (Биологический контур)', report, flags=re.IGNORECASE)
        
        return report
        
    except Exception as e:
        logger.error(f"Ошибка в clean_report_for_telegram: {e}")
        return report

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    try:
        is_sub = await is_subscribed(message.from_user.id)
        
        if not is_sub:
            welcome = WELCOME_MESSAGES["not_subscribed"]
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="Присоединиться к проекту", url=CHANNEL_URL))
            builder.row(types.InlineKeyboardButton(text="Я в канале! Начать Аудит Контура", callback_data="check_sub"))
            
            await message.answer_photo(
                photo=welcome["logo"],
                caption=f"**{welcome['title']}**\n\n{welcome['text']}",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        else:
            welcome = WELCOME_MESSAGES["subscribed"]
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="🚀 Начать Аудит Контура", callback_data="start_audit"))
            
            await message.answer_photo(
                photo=welcome["logo"],
                caption=f"**{welcome['title']}**\n\n{welcome['text']}",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await send_admin_alert("start_error", str(e), traceback.format_exc())
        await message.answer("⚠️ Произошла техническая ошибка. Попробуйте позже.")

@dp.callback_query(F.data == "check_sub")
async def handle_sub_check(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Проверяю подписку...")
    try:
        await asyncio.sleep(0.5)
        is_sub = await is_subscribed(callback.from_user.id)
        
        if is_sub:
            welcome = WELCOME_MESSAGES["subscribed"]
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="🚀 Начать Аудит Контура", callback_data="start_audit"))
            
            try:
                await callback.message.edit_media(
                    media=types.InputMediaPhoto(
                        media=welcome["logo"],
                        caption=f"**{welcome['title']}**\n\n{welcome['text']}",
                        parse_mode="Markdown"
                    ),
                    reply_markup=builder.as_markup()
                )
            except:
                await callback.message.answer_photo(
                    photo=welcome["logo"],
                    caption=f"**{welcome['title']}**\n\n{welcome['text']}",
                    reply_markup=builder.as_markup(),
                    parse_mode="Markdown"
                )
        else:
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
            builder.row(types.InlineKeyboardButton(text="✅ Я уже подписался", callback_data="check_sub_again"))
            
            await callback.message.answer(
                "❌ **Вы еще не подписаны на канал!**\n\nДля доступа к аудиту Автопилота необходимо подписаться.",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
            await callback.answer("Вы еще не подписаны!", show_alert=True)
                
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        await callback.answer("Ошибка при проверке подписки", show_alert=True)

@dp.callback_query(F.data == "check_sub_again")
async def handle_sub_check_again(callback: types.CallbackQuery):
    await callback.answer("Проверяю еще раз...")
    try:
        is_sub = await is_subscribed(callback.from_user.id)
        
        if is_sub:
            welcome = WELCOME_MESSAGES["subscribed"]
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="🚀 Начать Аудит Автопилота", callback_data="start_audit"))
            
            try:
                await callback.message.delete()
            except:
                pass
                
            await callback.message.answer_photo(
                photo=welcome["logo"],
                caption=f"**{welcome['title']}**\n\n{welcome['text']}",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        else:
            await callback.answer("❌ Вы все еще не подписаны!", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка повторной проверки: {e}")
        await callback.answer("Ошибка проверки", show_alert=True)

@dp.callback_query(F.data == "start_audit")
async def start_audit_flow(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Запускаю аудит Автопилота...")
    try:
        if not await is_subscribed(callback.from_user.id):
            await callback.answer("❌ Вы отписались от канала!", show_alert=True)
            return
        
        await state.update_data(current_step=0, answers=[])
        
        await callback.message.answer(
            "🔬 **Запуск аудита Автопилота.**\n\n"
            "Я помогу вам найти скрытые настройки вашего «Автопилота (Биологического контура)», которые блокируют движение. "
            "Мы пройдем по 8 точкам и спроектируем ваш Мета-маяк — эталонное состояние вашей глубинной идентичности. "
            "Отвечайте максимально честно — это поможет собрать вашу личную Метаформулу.",
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(1)
        await callback.message.answer(QUESTIONS[0])
        await state.set_state(AuditState.answering_questions)
        
    except Exception as e:
        logger.error(f"Ошибка запуска аудита: {e}")
        await send_admin_alert("audit_start_error", str(e), traceback.format_exc())
        await callback.message.answer("⚠️ Ошибка запуска аудита. Попробуйте снова.")

# --- ОБНОВЛЕННАЯ ФУНКЦИЯ ДЛЯ НЕМЕДЛЕННОЙ ОТПРАВКИ КНОПОК ---
async def send_immediate_masterclass_button(message: types.Message):
    """Отправляет кнопки для мастер-класса сразу после гайда"""
    try:
        builder = InlineKeyboardBuilder()
        
        # Первая строка: Видео-практикум
        builder.row(
            types.InlineKeyboardButton(
                text='🎬 ИНСТАЛЛИРОВАТЬ КОД В ПРАКТИКУМЕ', 
                url=MASTERCLASS_URL
            )
        )
        
        # Вторая строка: Дополнительная кнопка для гайда
        builder.row(
            types.InlineKeyboardButton(
                text='📥 ЕЩЕ РАЗ СКАЧАТЬ ГАЙД',
                callback_data="download_guide_manual"
            )
        )
        
        await message.answer(
            "📘 **Ваш персональный протокол «Дешифровка Автопилота» готов.**\n\n"
            "Вы получили свой Мета-код (Метаформулу) — это ваш код для перехвата управления у Автопилота. "
            "Но чтобы этот код стал вашей новой биологической программой, нужна практическая инсталляция.\n\n"
            "Для физической прошивки кода в нейронную сеть получите Видео-практикум:",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки кнопок: {e}")
        try:
            await message.answer(
                "📘 Ваш персональный протокол «Дешифровка Автопилота» готов.\n\n"
                "Для физической прошивки кода получите Видео-практикум:\n"
                f"{MASTERCLASS_URL}"
            )
        except:
            pass

@dp.callback_query(F.data == "download_guide_manual")
async def handle_manual_download(callback: types.CallbackQuery):
    """Обработчик ручного скачивания гайда"""
    await callback.answer("Загружаю гайд...")
    
    try:
        # Скачиваем и отправляем PDF напрямую
        await download_and_send_pdf(callback.message)
            
    except Exception as e:
        logger.error(f"Ошибка ручного скачивания: {e}")
        await callback.answer("Ошибка при отправке гайда", show_alert=True)
        
        # Прямая ссылка как запасной вариант
        await callback.message.answer(
            f"📥 Ссылка для скачивания гайда:\n{GUIDE_URL}"
        )

# --- ИСПРАВЛЕННАЯ ФУНКЦИЯ ОБРАБОТКИ ОТВЕТОВ ---
@dp.message(AuditState.answering_questions)
async def process_answer(message: types.Message, state: FSMContext):
    global error_counter
    
    try:
        if not message.text or not message.text.strip():
            return await message.answer("Пожалуйста, напишите текстовый ответ.")

        data = await state.get_data()
        step = data.get("current_step", 0)
        user_answers = data.get("answers", [])

        user_answers.append(message.text.strip())
        next_step = step + 1

        if next_step < len(QUESTIONS):
            await state.update_data(current_step=next_step, answers=user_answers)
            await message.answer(QUESTIONS[next_step])
        else:
            # ФИНАЛ - ОДИН РАЗ ОТПРАВЛЯЕМ ОТЧЕТ И PDF
            await state.update_data(answers=user_answers)
            await message.answer("🧠 Синхронизирую данные с когнитивным ядром...")
            
            try:
                report = await generate_ai_report(user_answers)
                clean_report = clean_report_for_telegram(report)
                
                # Отправляем ОДИН отчет
                await message.answer(clean_report)
                
                # СРАЗУ отправляем PDF гайд в чат
                await download_and_send_pdf(message)
                
                # Отправляем первое сообщение с кнопками (немедленно)
                await send_immediate_masterclass_button(message)
                
                # ЗАПУСКАЕМ ЗАДАЧУ ОТЛОЖЕННОГО СООБЩЕНИЯ
                asyncio.create_task(send_mk_shift_message(message))
                
                # Отправляем копию администратору
                await send_admin_copy(message.from_user, user_answers, clean_report)
                
            except Exception as report_error:
                logger.error(f"Ошибка при генерации отчета: {report_error}")
                
                # Фолбэк отчет
                index = calculate_automatism_index(user_answers)
                fallback_report = generate_fallback_report(user_answers, index)
                
                await message.answer(fallback_report)
                await download_and_send_pdf(message)
                await send_immediate_masterclass_button(message)
                
                # ЗАПУСКАЕМ ЗАДАЧУ ОТЛОЖЕННОГО СООБЩЕНИЯ даже при ошибке
                asyncio.create_task(send_mk_shift_message(message))
            
            await state.clear()
            
    except Exception as e:
        error_counter += 1
        logger.error(f"Ошибка обработки ответа: {e}")
        await send_admin_alert("process_error", str(e), traceback.format_exc())
        await message.answer(
            "⚠️ Произошла техническая ошибка при обработке вашего ответа.\n\n"
            "Пожалуйста, начните аудит заново с команды /start"
        )

def calculate_automatism_index(answers: list) -> int:
    """Рассчитывает индекс автоматизма на основе анализа речи"""
    if not answers:
        return 70
    
    text = ' '.join(answers).lower()
    
    # Маркеры пассивности (жертвенной позиции)
    passive_markers = [
        r'меня\s+', r'мне\s+', r'вынужден', r'приходится',
        r'должен', r'надо', r'нужно', r'обязан', r'заставляют',
        r'виноват', r'судьба', r'обстоятельства', r'а вдруг',
        r'боюсь', r'страшно', r'переживаю', r'сомневаюсь',
        r'не знаю', r'не уверен', r'получится ли'
    ]
    
    # Маркеры активности (авторской позиции)
    active_markers = [
        r'я\s+выбираю', r'я\s+решаю', r'я\s+создаю', r'я\s+хочу',
        r'я\s+могу', r'я\s+буду', r'я\s+осознаю', r'я\s+беру',
        r'моё\s+решение', r'мой\s+выбор', r'готов\s+действовать',
        r'верю\s+в', r'чувствую\s+силу', r'внутренний\s+драйв'
    ]
    
    passive_count = 0
    active_count = 0
    
    for marker in passive_markers:
        passive_count += len(re.findall(marker, text))
    
    for marker in active_markers:
        active_count += len(re.findall(marker, text))
    
    total_markers = passive_count + active_count + 1  # +1 чтобы избежать деления на ноль
    
    automatism_percentage = (passive_count / total_markers) * 100
    
    # Корректируем диапазон (60-95%)
    index = min(95, max(60, int(automatism_percentage)))
    
    return index

def extract_physical_symptom(answers: list) -> str:
    """Извлекает физический симптом из ответа на Q5 (теперь 5-й вопрос)"""
    if len(answers) >= 5:
        q5_answer = answers[4].lower()
        
        # Паттерны для поиска физических симптомов
        symptom_patterns = [
            r'сжатие.*?(?:в|у)\s*(?:солнечн[а-я]*\s*сплетени[ия]|груд[иье]|живот[ае])',
            r'тяжесть.*?(?:в|у)\s*(?:плечах|шее|спине|голове)',
            r'напряжение.*?(?:в|у)\s*(?:шее|плечах|челюст[ия]|лице)',
            r'ком.*?(?:в|у)\s*(?:горл[еа])',
            r'пустота.*?(?:в|у)\s*(?:груд[иье]|живот[еа])',
            r'жжение.*?(?:в|у)\s*(?:груд[иье]|живот[еа])',
            r'холод.*?(?:в|у)\s*(?:конечностях|теле)',
            r'дрожь.*?(?:в|у)\s*(?:теле|конечностях)',
            r'вязк[а-я]+\s*.*?(?:в|у)\s*(?:солнечн[а-я]*|груд[иье])',
            r'сдавлен[а-я]+\s*.*?(?:в|у)\s*(?:груд[иье]|горл[еа])'
        ]
        
        for pattern in symptom_patterns:
            match = re.search(pattern, q5_answer)
            if match:
                symptom = match.group(0)
                # Делаем первую букву заглавной
                if symptom and not symptom[0].isupper():
                    symptom = symptom[0].upper() + symptom[1:]
                return symptom
        
        # Если не нашли по паттернам, ищем ключевые слова
        keywords = ['сжатие', 'тяжесть', 'напряжение', 'ком', 'пустота', 
                   'жжение', 'холод', 'дрожь', 'боль', 'дискомфорт', 'вязкость', 'давление']
        for keyword in keywords:
            if keyword in q5_answer:
                # Берем контекст вокруг ключевого слова
                start = max(0, q5_answer.find(keyword) - 20)
                end = min(len(q5_answer), q5_answer.find(keyword) + 30)
                symptom = q5_answer[start:end].strip()
                if symptom and not symptom[0].isupper():
                    symptom = symptom[0].upper() + symptom[1:]
                return symptom
    
    return "сжатие в солнечном сплетении"  # значение по умолчанию

def extract_meta_mayak_role(answers: list) -> str:
    """Извлекает роль Мета-маяка из ответа на Q2"""
    if len(answers) >= 2:
        q2_answer = answers[1]
        
        # Ищем роли, указанные в примере
        if any(role in q2_answer.lower() for role in ['архитектор', 'архитектора']):
            return "Масштабным Архитектором своей реальности"
        elif any(role in q2_answer.lower() for role in ['лидер', 'лидера']):
            return "Спокойным Лидером своей жизни"
        elif any(role in q2_answer.lower() for role in ['творец', 'творцом', 'создател']):
            return "Творцом своей реальности"
        
        # Ищем общие паттерны
        if 'я ' in q2_answer.lower():
            start = q2_answer.lower().find('я ') + 2
            # Берем следующее 3-5 слов после "я"
            words = q2_answer[start:].split()[:5]
            if words:
                role = ' '.join(words)
                # Убираем знаки препинания в конце
                role = re.sub(r'[.,!?;:]$', '', role)
                if role and not role[0].isupper():
                    role = role[0].upper() + role[1:]
                return role
    
    return "Творцом своей реальности"  # значение по умолчанию

def generate_metaformula_from_answers(answers: list) -> str:
    """Генерирует метаформулу по новому алгоритду с Мета-маяком"""
    if len(answers) >= 5:
        symptom = extract_physical_symptom(answers)
        role = extract_meta_mayak_role(answers)
        
        # Делаем симптом более поэтичным
        symptom_poetic = symptom.replace('сжатие', 'легкое сжатие').replace('тяжесть', 'присутствующую тяжесть')
        
        return f"Я — Автор. ПРИЗНАЮ {symptom_poetic} и ВЫБИРАЮ быть {role}"
    
    return "Я — Автор. ПРИЗНАЮ сжатие в солнечном сплетении и ВЫБИРАЮ быть Творцом своей реальности"

def generate_fallback_report(answers: list, index: int) -> str:
    """Генерирует техническое фолбэк заключение с новой терминологией"""
    # Извлекаем данные для отчета
    symptom = extract_physical_symptom(answers)
    role = extract_meta_mayak_role(answers)
    
    # Определяем глубинную потребность на основе Q6
    need_analysis = ""
    if len(answers) >= 6:
        q6_answer = answers[5].lower()
        
        # Анализ потребностей
        if any(word in q6_answer for word in ['контроль', 'границ', 'безопасност', 'стабильност', 'нарушен']):
            need_analysis = "Анализ указывает на блокировку потребности в Безопасности. Биологический Контур использует гиперконтроль как кривую стратегию защиты."
        elif any(word in q6_answer for word in ['свобод', 'давлен', 'ограничен', 'зависимост', 'навяза']):
            need_analysis = "Анализ указывает на блокировку потребности в Свободе/Субъектности. Биологический Контур использует пассивность как кривую стратегию защиты."
        elif any(word in q6_answer for word in ['уважен', 'признан', 'значимост', 'оценк', 'обесцениван']):
            need_analysis = "Анализ указывает на блокировку потребности в Значимости. Биологический Контур использует компенсаторное поведение как кривую стратегию защиты."
        else:
            need_analysis = "Анализ указывает на блокировку базовой потребности. Биологический Контур использует неоптимальную стратегию защиты."
    
    # Получаем метафору (если есть, теперь из Q4)
    metaphor = ""
    if len(answers) >= 4:
        q4_answer = answers[3]
        words = q4_answer.split()
        if len(words) > 5:
            metaphor = ' '.join(words[:5])
        else:
            metaphor = q4_answer
    
    # Формируем технический комментарий к индексу
    comment = ""
    if index >= 80:
        comment = "Биологический Контур высокоавтоматизирован. Автопилот удерживает большинство ресурсов."
    elif index >= 70:
        comment = "Биологический Контур частично автоматизирован. Наблюдается смешанный режим работы."
    else:
        comment = "Система демонстрирует повышенный уровень осознанности. Ресурсы доступны для перераспределения."
    
    # Формируем технический отчет с новой структурой
    report = f"""🧭 СТАТУС СИСТЕМЫ
Биологический Контур диагностирован. Конфликт между текущим блоком и выбранным Мета-маяком подтвержден.

📊 ИНДЕКС АВТОМАТИЗМА: {index}%
{comment}

🧠 ДИАГНОСТИКА КОНТУРА

🛑 УЗЕЛ СОПРОТИВЛЕНИЯ
{"Образ '" + metaphor + "' создает блокирующий контур. Система зациклена на данном паттерне." if metaphor else "Обнаружен блокирующий контур. Биологический Контур находится в состоянии ожидания."}

💻 ХОЛОСТОЙ ХОД (РЕЖИМ ЗАСТАВКИ)
{"Процессор загружен неоптимальными циклами обработки. Наблюдается утечка вычислительных ресурсов." if len(answers) >= 3 else "Зафиксирована фоновая нагрузка. Энергия утилизируется неэффективно."}

🔋 РЕАКТОР ИДЕНТИЧНОСТИ
{need_analysis}

🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор. ПРИЗНАЮ {symptom} и ВЫБИРАЮ быть {role}

🚀 СЛЕДУЮЩИЙ ШАГ
Ваш код готов. Для физической прошивки Мета-маяка в нейронную сеть переходите к Видео-практикуму."""
    
    return report

# --- AI REPORT GENERATION ---
async def generate_ai_report(answers: list):
    global api_failures
    
    if not client:
        # Демо-режим для тестирования
        try:
            index = calculate_automatism_index(answers)
            return generate_fallback_report(answers, index)
        except Exception as e:
            logger.error(f"Ошибка в демо-режиме: {e}")
            index = calculate_automatism_index(answers)
            return generate_fallback_report(answers, index)
    
    # Подготавливаем данные для ИИ
    user_input_text = "ОТВЕТЫ ПОЛЬЗОВАТЕЛЯ НА 8 ВОПРОСОВ АУДИТА БИОЛОГИЧЕСКОГО КОНТУРА:\n\n"
    for i, ans in enumerate(answers):
        user_input_text += f"ВОПРОС {i+1}: {QUESTIONS[i]}\n"
        user_input_text += f"ОТВЕТ: {ans}\n\n"
    
    user_input_text += "\n---\nПРОАНАЛИЗИРУЙ ОТВЕТЫ И СОСТАВЬ ТЕХНИЧЕСКОЕ ЗАКЛЮЧЕНИЕ ПО АУДИТУ АВТОПИЛОТА (БИОЛОГИЧЕСКОГО КОНТУРА) ПО СТРОГОЙ СТРУКТУРЕ. ИСПОЛЬЗУЙ ТЕРМИНОЛОГИЮ КИБЕР-МИСТИЦИЗМА, БЕЗ ПОВТОРОВ И ГРАММАТИЧЕСКИХ ОШИБОК."
    
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input_text}
                ],
                model="llama-3.3-70b",
                temperature=0.5,
                max_completion_tokens=1800,
                top_p=0.9
            )
            
            api_failures = 0
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                    if content:
                        return content
            
            # Если ответ пустой, генерируем фолбэк отчет
            index = calculate_automatism_index(answers)
            return generate_fallback_report(answers, index)
            
        except Exception as e:
            api_failures += 1
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
            
            if attempt == 2:
                await send_admin_alert("api_critical", f"3 попытки провалились: {str(e)}")
                index = calculate_automatism_index(answers)
                return generate_fallback_report(answers, index)
            
            await asyncio.sleep(2 ** attempt)
    
    # Фоллбек отчет
    index = calculate_automatism_index(answers)
    return generate_fallback_report(answers, index)

# --- ВЕБ-СЕРВЕР ---
async def handle_health(request):
    uptime = datetime.now() - start_time
    return web.Response(text=f"Мета-Навигатор | Время работы: {str(uptime).split('.')[0]} | Ошибок: {error_counter} | Сбоев API: {api_failures}")

async def send_startup_notification():
    try:
        bot_info = await bot.get_me()
        msg = (
            "🚀 МЕТА-НАВИГАТОР ЗАПУЩЕН\n\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m %H:%M:%S')}\n"
            f"🤖 Бот: @{bot_info.username}\n"
            f"🧠 Режим: Нейро-Архитектор (Кибер-мистицизм)\n"
            f"🔑 Cerebras API: {'✅' if CEREBRAS_API_KEY else '❌ ДЕМО-РЕЖИМ'}\n"
            f"📊 Порт: {os.environ.get('PORT', 8080)}\n"
            f"📎 PDF доставка: АКТИВНА\n"
            f"🎯 Видео-практикум: 30 сек задержка"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=msg)
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление о запуске: {e}")

async def main():
    if not TOKEN:
        logger.error("❌ ОШИБКА: BOT_TOKEN не установлен!")
        raise ValueError("BOT_TOKEN не установен")
    
    if not CEREBRAS_API_KEY:
        logger.warning("⚠️ AI_API_KEY не установен! Будет использоваться демо-режим.")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"Не удалось удалить вебхук: {e}")
    
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    await send_startup_notification()
    
    logger.info(f"✅ Мета-Навигатор запущен")
    logger.info(f"🤖 Бот: @{(await bot.get_me()).username}")
    logger.info(f"🧠 Режим: Нейро-Архитектор (Кибер-мистицизм)")
    logger.info(f"🔑 Cerebras API: {'✅' if CEREBRAS_API_KEY else '❌ ДЕМО-РЕЖИМ'}")
    logger.info(f"📎 PDF доставка: АКТИВНА")
    logger.info(f"🎯 Видео-практикум: 30 сек задержка")
    logger.info(f"🌐 Проверка: http://0.0.0.0:{port}/")
    logger.info(f"📝 Опросник: {len(QUESTIONS)} вопросов")
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.critical(f"Бот остановлен: {e}")
        await send_admin_alert("bot_crash", f"Бот остановлен: {str(e)}", traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}")
        exit(1)
