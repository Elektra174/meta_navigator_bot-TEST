[file name]: main (2).py
[file content begin]
import os
import asyncio
import traceback
import logging
import re
import html
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from cerebras.cloud.sdk import AsyncCerebras
from aiohttp import web
import aiohttp
import io

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
CEREBRAS_API_KEY = os.getenv("AI_API_KEY")
CHANNEL_ID = "@metaformula_life"
ADMIN_ID = 7830322013

# Ресурсы проекта
LOGO_FORMULA_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png.png"
LOGO_NAVIGATOR_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
GUIDE_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/revizia_gid.pdf"
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

# --- СПИСОК ВОПРОСОВ (8 ВОПРОСОВ) ---
QUESTIONS = [
    "В чем ваш основной затык, застой или где вы сейчас буксуете?",
    "Представьте, что завтра утром произошло чудо. Проблема, с которой вы пришли, исчезла. Как вы это поймете? Что конкретно изменится в вашем поведении и ощущениях?",
    "Опишите ваш обычный день. Как проходит ваше утро, день, вечер? Что в этой рутине вас больше всего истощает?",
    "Если бы ваше текущее состояние можно было описать метафорой или образом... на что бы это было похоже? (Например: «топчусь на раскаленной плите», «пробиваю лбом стену», «выбираюсь из болота»). Опишите детально.",
    "Где в теле вы чувствуете это состояние? Какие конкретные ощущения: тяжесть, холод, жжение, сжатие, пустота?",
    "Что вас больше всего бесит/раздражает в других людях? Какое качество или поведение вызывает самую сильную эмоциональная реакция?",
    "Какую цену вы платите за сохранение текущего положения? Что и в каком объеме уходит прямо сейчас? (время, деньги, силы, отношения)",
    "Вы готовы прямо сейчас взять управление на себя и стать Автором этих изменений? (Да/Нет с пояснением)"
]

# --- РАЗНЫЕ ПРИВЕТСТВИЯ ---
WELCOME_MESSAGES = {
    "not_subscribed": {
        "title": "Добро пожаловать в «Метаформулу Жизни»",
        "text": "Меня зовут Александр Лазаренко. Я — автор проекта.\n\n"
                "Я создал Мета-навигатор, чтобы помочь Вам увидеть программы Вашего Автопилота и проложить маршрут к себе настоящему.\n\n"
                "Чтобы начать, пожалуйста, подпишитесь на наш канал:",
        "logo": LOGO_FORMULA_URL
    },
    "subscribed": {
        "title": "👋 Добро пожаловать в Мета-Навигатор!",
        "text": "Я Ваш проводник в мета-исследовании себя.\n\n"
                "Помогу обнаружить скрытые программы «Автопилота», которые блокируют вашу энергию.\n\n"
                "Мы пройдем 8 шагов, чтобы найти вашу личную Метаформулу.\n\n"
                "Готовы начать?",
        "logo": LOGO_NAVIGATOR_URL
    }
}

# --- УЛУЧШЕННЫЙ СИСТЕМНЫЙ ПРОМПТ v3.1 (обновлен для 8 вопросов) ---
SYSTEM_PROMPT = """ТЫ — «МЕТА-НАВИГАТОР», интеллектуальный агент и цифровой двойник Александра Лазаренко. Твоя роль: Когнитивный Архитектор и Проводник в проекте «Метаформула Жизни».

ТВОЯ МИССИЯ: Провести глубокий нейрокогнитивный аудит состояния пользователя, выявить сбои в его «прошивке» (устаревшие паттерны мышления) и помочь ему перейти из режима «Автопилот» (выживание) в режим «Автор» (созидание).

ТВОЯ БАЗА ЗНАНИЙ (ТЕОРЕТИЧЕСКИЙ КАРКАС):

Нейрофизиология:
1. Проблема пользователя — это не «судьба», а «Застойная Доминанта» (по Ухтомскому) — очаг возбуждения, работающий как магнит для негатива.
2. Руминация (навязчивые мысли) — это активность Дефолт-системы мозга (DMN), работающей вхолостую («Режим Заставки»). Это сжигает 80% энергии.
3. Страх без действия — это гормональный сбой (ложная тревога), ведущий к психосоматике.

Мета-Персональная Терапия (МПТ):
1. Принцип Авторства: Пользователь сам создает свой тупик. Помоги ему увидеть КАК он это делает.
2. Теневой Ресурс: То, что бесит пользователя в других — это его собственная подавленная сила. Инвертируй раздражение в ресурс (Наглость -> Право на масштаб).

Инженерный подход:
1. Используй термины: алгоритм, баг, прошивка, оптика, навигация, заряд, фокус, система.
2. Избегай эзотерики: никаких «вибраций», «потоков вселенной», «кармы».

ПРАВИЛА КОММУНИКАЦИИ:
1. Обращайся строго на «Вы».
2. Тон: Аналитический, доброжелательный, но твердый (Tough Love). Без сюсюканья.
3. Язык: Естественный, богатый русский язык. Избегай канцеляризмов.

ПРОТОКОЛ АНАЛИЗА 8 ОТВЕТОВ:
Q1 (Затык): Определи ключевой паттерн застоя. Оцени уровень осознанности проблемы.
Q2 (Чудо): Оцени локус контроля. Если «я бы изменил» — Автор. Если «пусть изменится» — Пассажир.
Q3 (День Сурка): Анализируй контент DMN. Классифицируй «шум»: страх будущего (Тревога) или сожаление о прошлом (Депрессия)?
Q4 (Метафора): Объективизируй Доминанту. Используй образ пользователя как якорь для объяснения потери энергии.
Q5 (Тело): Привяжи к соматике. Объясни механизм «ложной тревоги» — выброс гормонов без действия.
Q6 (Раздражение): Найди Теневой Ресурс. Инвертируй: если бесит наглость -> ресурс «Право брать свое».
Q7 (Цена): Усиль боль. Подсчитай «сложные проценты» потерь. Создай срочность изменений.
Q8 (Выбор): Заключи контракт на изменения. Подтверди переход в статус «Кандидат в Авторы».

РАСЧЕТ ИНДЕКСА АВТОМАТИЗМА:
- 90-100%: Речь полна безличных конструкций («меня бесит», «так получилось»), высокий уровень жертвенности
- 70-90%: Преобладают обстоятельства над действиями, но есть проблески осознанности
- 40-70%: Смесь пассивных и активных конструкций, переходное состояние
- 0-40%: Преобладают активные глаголы («я выбираю», «я создаю»), высокий уровень авторства

СТРУКТУРА ОТЧЕТА (строго придерживайся):

🧭 РЕЗУЛЬТАТЫ АУДИТА АВТОПИЛОТА

📊 ВАШ ИНДЕКС АВТОМАТИЗМА: [X]%
(Краткий комментарий с обоснованием оценки)

🧠 ДИАГНОСТИКА СИСТЕМЫ

ЗАСТОЙНАЯ ДОМИНАНТА:
[Анализ метафоры из Q4 и телесного отклика из Q5. Объясни, как этот «магнит» искажает реальность и блокирует энергию.]

РЕЖИМ ЗАСТАВКИ (УТЕЧКА ЭНЕРГИИ):
[Анализ руминации из Q3. Объясни, что мозг тратит ресурсы на «холостой ход» вместо действия.]

🔋 ТЕНЕВОЙ РЕСУРС (СКРЫТОЕ ТОПЛИВО)
[Анализ раздражения из Q6. Инвертируй в скрытую силу.]

🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
[НОВАЯ ИНСТРУКЦИЯ: НЕ пиши "Ваша формула:". Генерируй формулу по алгоритму:
Я — Автор, ПРИЗНАЮ [конкретный физический симптом из Q5] и ВЫБИРАЮ [инвертированный ресурс из Q6]
Пример: Я — Автор, ПРИЗНАЮ сжатие в солнечном сплетении и ВЫБИРАЮ Право брать свое]

🚀 СЛЕДУЮЩИЙ ШАГ
[Краткий, энергичный призыв. Напомни, что формула — это ключ, а инструкция по применению находится в гайде «Ревизия Маршрута».]

ВАЖНО:
1. ФОРМУЛА ДОЛЖНА БЫТЬ СГЕНЕРИРОВАНА ПО АЛГОРИТМУ: Я — Автор, ПРИЗНАЮ [симптом] и ВЫБИРАЮ [ресурс]
2. НЕ ИСПОЛЬЗОВАТЬ МЕТАФОРЫ ИЗ Q4 В ФОРМУЛЕ, ТОЛЬКО ТЕЛЕСНЫЕ ОЩУЩЕНИЯ ИЗ Q5
3. ГЛАГОЛЫ «ПРИЗНАЮ» и «ВЫБИРАЮ» ВСЕГДА ПИШИ КАПСОМ
4. БЕЗ СЛОВ "Ваша формула:" ПЕРЕД ФОРМУЛОЙ
"""

# --- ФУНКЦИЯ ПРОВЕРКИ ПОДПИСКИ ---
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

# --- ФУНКЦИЯ ЗАГРУЗКИ И ОТПРАВКИ PDF ГАЙДА ---
async def download_and_send_pdf(message: types.Message):
    """Скачивает и отправляет PDF гайд напрямую в чат"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(GUIDE_URL) as response:
                if response.status == 200:
                    pdf_data = await response.read()
                    
                    # Отправляем как документ
                    await message.answer_document(
                        types.BufferedInputFile(
                            pdf_data,
                            filename="Ревизия_маршрута_Метаформула.pdf"
                        ),
                        caption="📘 **ГАЙД «РЕВИЗИЯ МАРШРУТА»**\n\n"
                               "Ваш персональный путеводитель к состоянию Автора жизни с помощью Метаформулы.\n\n"
                               "Внутри вы найдете:\n"
                               "• 🛠️ Инженерные инструкции по внедрению Метаформулы\n"
                               "• 🔋 Протоколы для отключения Дефолт-системы\n"
                               "• 🧭 Техники создания новой Доминанты\n"
                               "• 📊 Систему мониторинга энергетического бюджета",
                        parse_mode="Markdown"
                    )
                    return True
                else:
                    logger.error(f"Не удалось скачать PDF. Статус: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Ошибка при загрузке PDF: {e}")
        return False

# --- СИСТЕМА МОНИТОРИНГА ---
async def send_admin_alert(alert_type: str, details: str, tb: str = ""):
    global error_counter, api_failures
    try:
        ts = datetime.now().strftime("%d.%m %H:%M:%S")
        
        msg = f"🚨 PROBLEM: {alert_type.upper()}\n\n"
        msg += f"⏰ Время: {ts}\n"
        msg += f"📝 Детали: {details}\n"
        
        if tb:
            if len(tb) > 1000:
                msg += f"\n🔧 Traceback: (отправлен отдельным файлом)"
                
                await bot.send_document(
                    chat_id=ADMIN_ID,
                    document=types.BufferedInputFile(
                        tb.encode('utf-8'),
                        filename=f"traceback_{ts.replace(':', '-').replace(' ', '_')}.txt"
                    ),
                    caption=f"Traceback для ошибки: {alert_type}"
                )
            else:
                msg += f"\n🔧 Traceback:\n{tb[:800]}"
        
        msg += f"\n\n📊 Статистика: Ошибок: {error_counter} | Сбоев API: {api_failures}"
        
        await bot.send_message(chat_id=ADMIN_ID, text=msg)
    except Exception as e:
        logger.error(f"Не удалось отправить алерт: {e}")

async def send_admin_copy(user: types.User, answers: list, report: str):
    try:
        user_info = f"👤 {user.full_name} (@{user.username})"
        text_answers = "\n".join([f"{i+1}. {a}" for i, a in enumerate(answers)])
        
        full_log = (
            "🔔 НОВЫЙ АУДИТ ЗАВЕРШЕН\n\n"
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
        logger.error(f"Admin log error: {e}")

def clean_report_for_telegram(report: str) -> str:
    """Очищает отчет для красивого отображения в Telegram"""
    if not report:
        return ""
    
    # Заменяем обращение "пользователь" на "Вы" или "Вам"
    report = re.sub(r'\bпользователь\b', 'Вы', report, flags=re.IGNORECASE)
    report = re.sub(r'\bему\b', 'Вам', report, flags=re.IGNORECASE)
    report = re.sub(r'\bего\b', 'Ваш', report, flags=re.IGNORECASE)
    report = re.sub(r'\bон\b', 'Вы', report, flags=re.IGNORECASE)
    report = re.sub(r'\bона\b', 'Вы', report, flags=re.IGNORECASE)
    
    # Убираем escape-последовательности
    report = report.replace('\\n', '\n').replace('\\r', '\r')
    
    # Убираем лишние пробелы и переносы
    report = re.sub(r'\n{3,}', '\n\n', report)
    
    # Убираем markdown символы
    report = re.sub(r'\*\*(.*?)\*\*', r'\1', report)
    report = re.sub(r'\*(.*?)\*', r'\1', report)
    report = report.replace('`', '')
    
    # Убираем HTML теги
    report = re.sub(r'<.*?>', '', report)
    
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
            builder.row(types.InlineKeyboardButton(text="Я в канале! Начать Диагностику", callback_data="check_sub"))
            
            await message.answer_photo(
                photo=welcome["logo"],
                caption=f"**{welcome['title']}**\n\n{welcome['text']}",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        else:
            welcome = WELCOME_MESSAGES["subscribed"]
            builder = InlineKeyboardBuilder()
            builder.row(types.InlineKeyboardButton(text="🚀 Начать Диагностику", callback_data="start_audit"))
            
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
            builder.row(types.InlineKeyboardButton(text="🚀 Начать Диагностику", callback_data="start_audit"))
            
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
                "❌ **Вы еще не подписаны на канал!**\n\nДля доступа к диагностике необходимо подписаться.",
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
            builder.row(types.InlineKeyboardButton(text="🚀 Начать Диагностику", callback_data="start_audit"))
            
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
    await callback.answer("Запускаю диагностику...")
    try:
        if not await is_subscribed(callback.from_user.id):
            await callback.answer("❌ Вы отписались от канала!", show_alert=True)
            return
        
        await state.update_data(current_step=0, answers=[])
        
        await callback.message.answer(
            "🔬 **Нейрокогнитивный Аудит Автопилота**\n\n"
            f"В течение следующих {len(QUESTIONS)} шагов мы проведем диагностику вашей «прошивки». "
            "Отвечайте максимально честно и конкретно — каждый ответ формирует вашу нейронную карту.",
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(1)
        await callback.message.answer(f"📝 Шаг 1 из {len(QUESTIONS)}:\n\n{QUESTIONS[0]}")
        await state.set_state(AuditState.answering_questions)
        
    except Exception as e:
        logger.error(f"Ошибка запуска аудита: {e}")
        await send_admin_alert("audit_start_error", str(e), traceback.format_exc())
        await callback.message.answer("⚠️ Ошибка запуска аудита. Попробуйте снова.")

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
            await message.answer(f"📝 Шаг {next_step + 1} из {len(QUESTIONS)}:\n\n{QUESTIONS[next_step]}")
        else:
            await state.update_data(answers=user_answers)
            await message.answer(
                "🧠 Синхронизирую данные с когнитивным ядром...\n"
                "Анализирую ваши ответы через призму нейрофизиологии и теории доминанты..."
            )
            
            try:
                report = await generate_ai_report(user_answers)
                
                if report:
                    # Очищаем и отправляем отчет пользователю
                    clean_report = clean_report_for_telegram(report)
                    await message.answer(clean_report)
                    
                    # СРАЗУ отправляем PDF гайд после отчета (напрямую в чат)
                    await send_pdf_guide_immediately(message)
                    
                    # Отправляем кнопки после гайда
                    await send_masterclass_button(message)
                    
                    # Отправляем копию администратору
                    await send_admin_copy(message.from_user, user_answers, clean_report)
                else:
                    logger.error("Отчет ИИ вернул пустой результат")
                    index = calculate_automatism_index(user_answers)
                    
                    # Генерируем фолбэк отчет с правильной формулой
                    fallback_report = generate_fallback_report(user_answers, index)
                    
                    await message.answer(fallback_report)
                    await send_pdf_guide_immediately(message)
                    await send_masterclass_button(message)
                    
            except Exception as report_error:
                logger.error(f"Ошибка при генерации отчета: {report_error}")
                await send_admin_alert("report_generation_error", str(report_error), traceback.format_exc())
                index = calculate_automatism_index(user_answers)
                
                # Генерируем фолбэк отчет с правильной формулой
                fallback_report = generate_fallback_report(user_answers, index)
                
                await message.answer(fallback_report)
                await send_pdf_guide_immediately(message)
                await send_masterclass_button(message)
            
            await state.clear()
            
    except Exception as e:
        error_counter += 1
        logger.error(f"Ошибка обработки ответа: {e}")
        await send_admin_alert("process_error", str(e), traceback.format_exc())
        await message.answer(
            "⚠️ Произошла техническая ошибка при обработке вашего ответа.\n\n"
            "Пожалуйста, начните аудит заново с команды /start"
        )

async def send_pdf_guide_immediately(message: types.Message):
    """Сразу отправляет PDF гайд напрямую в чат после отчета"""
    try:
        await message.answer("📥 **Загружаю ваш персональный гайд...**")
        
        # Пытаемся скачать и отправить PDF
        success = await download_and_send_pdf(message)
        
        if not success:
            # Если не удалось скачать, отправляем ссылку как запасной вариант
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="📥 СКАЧАТЬ ГАЙД «РЕВИЗИЯ МАРШРУТА»",
                    url=GUIDE_URL
                )
            )
            
            await message.answer(
                "📘 **Гайд «Ревизия маршрута»**\n\n"
                "Ваш персональный путеводитель к состоянию Автора жизни с помощью Метаформулы.\n\n"
                "Внутри вы найдете:\n"
                "• 🛠️ Инженерные инструкции по внедрению Метаформулы\n"
                "• 🔋 Протоколы для отключения Дефолт-системы\n"
                "• 🧭 Техники создания новой Доминанты\n"
                "• 📊 Систему мониторинга энергетического бюджета\n\n"
                "Нажмите кнопку ниже, чтобы скачать:",
                parse_mode="Markdown",
                reply_markup=builder.as_markup(),
                disable_web_page_preview=True
            )
                
    except Exception as e:
        logger.error(f"Ошибка отправки гайда: {e}")
        
        # Резервное сообщение с прямой ссылкой
        try:
            await message.answer(
                "📘 **Гайд «Ревизия маршрута»**\n\n"
                f"Скачать можно по ссылке:\n{GUIDE_URL}\n\n"
                "Нажмите на ссылку выше и выберите «Скачать» в правом верхнем углу экрана.",
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
        except Exception as fallback_error:
            logger.error(f"Резервный метод тоже не сработал: {fallback_error}")

async def send_masterclass_button(message: types.Message):
    """Отправляет кнопки для мастер-класса"""
    try:
        builder = InlineKeyboardBuilder()
        
        # Первая строка: Мастер-класс
        builder.row(
            types.InlineKeyboardButton(
                text='🎬 ЗАБРАТЬ МК «СДВИГ ОПТИКИ»', 
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
            "🎯 **Ваш нейрокогнитивный аудит завершен!**\n\n"
            "Вы получили уникальный инструмент — персональную Метаформулу. "
            "Это ключ к перепрошивке вашего Автопилота.\n\n"
            "Для полного погружения в методику получите мастер-класс:",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Ошибка отправки кнопок: {e}")
        try:
            await message.answer(
                "🎯 Ваш нейрокогнитивный аудит завершен!\n\n"
                "Для полного погружения в методику получите мастер-класс:\n"
                f"{MASTERCLASS_URL}"
            )
        except:
            pass

@dp.callback_query(F.data == "download_guide_manual")
async def handle_manual_download(callback: types.CallbackQuery):
    """Обработчик ручного скачивания гайда"""
    await callback.answer("Загружаю гайд...")
    
    try:
        await callback.message.answer("📥 **Загружаю ваш гайд...**")
        
        # Пытаемся скачать и отправить PDF
        success = await download_and_send_pdf(callback.message)
        
        if not success:
            # Если не удалось скачать, отправляем ссылку
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="📥 СКАЧАТЬ ГАЙД",
                    url=GUIDE_URL
                )
            )
            
            await callback.message.answer(
                "📘 **Гайд «Ревизия маршрута»**\n\n"
                "Нажмите кнопку ниже, чтобы скачать ваш персональный путеводитель:",
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка ручного скачивания: {e}")
        await callback.answer("Ошибка при отправке гайда", show_alert=True)
        
        # Прямая ссылка
        await callback.message.answer(
            f"📥 Ссылка для скачивания гайда:\n{GUIDE_URL}"
        )

@dp.callback_query(F.data == "download_guide")
async def handle_download_guide(callback: types.CallbackQuery):
    """Резервная функция для отправки гайда по запросу"""
    await callback.answer("Отправляю гайд...")
    
    try:
        await download_and_send_pdf(callback.message)
    except Exception as e:
        logger.error(f"Ошибка отправки гайда по запросу: {e}")
        await callback.answer("Ошибка отправки гайда", show_alert=True)

def calculate_automatism_index(answers: list) -> int:
    """Рассчитывает индекс автоматизма на основе анализа речи"""
    if not answers:
        return 70
    
    text = ' '.join(answers).lower()
    
    # Маркеры пассивности (жертвенной позиции)
    passive_markers = [
        r'меня\s+', r'мне\s+', r'менее\s+', r'так\s+получилось',
        r'не\s+повезло', r'не\s+везет', r'вынужден', r'приходится',
        r'должен', r'надо', r'нужно', r'обязан', r'заставляют',
        r'виноват', r'судьба', r'обстоятельства'
    ]
    
    # Маркеры активности (авторской позиции)
    active_markers = [
        r'я\s+выбираю', r'я\s+решаю', r'я\s+создаю', r'я\s+хочу',
        r'я\s+могу', r'я\s+буду', r'я\s+осознаю', r'я\s+беру',
        r'моя\s+ответственность', r'мой\s+выбор'
    ]
    
    passive_count = 0
    active_count = 0
    
    for marker in passive_markers:
        passive_count += len(re.findall(marker, text))
    
    for marker in active_markers:
        active_count += len(re.findall(marker, text))
    
    total_markers = passive_count + active_count
    
    if total_markers == 0:
        return 70
    
    automatism_percentage = (passive_count / total_markers) * 100
    
    # Корректируем диапазон
    index = min(95, max(30, int(automatism_percentage * 0.9)))
    
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
            r'дрожь.*?(?:в|у)\s*(?:теле|конечностях)'
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
        keywords = ['сжатие', 'тяжесть', 'напряжение', 'ком', 'пустота', 'жжение', 'холод', 'дрожь', 'боль', 'дискомфорт']
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

def extract_shadow_resource(answers: list) -> str:
    """Извлекает теневой ресурс из ответа на Q6 (теперь 6-й вопрос)"""
    if len(answers) >= 6:
        q6_answer = answers[5].lower()
        
        # Инверсия раздражений в ресурсы
        inversion_map = {
            r'нагл[а-я]+': 'Право брать свое',
            r'безответственн[а-я]+': 'Право на отдых',
            r'лжив[а-я]+': 'Право на правду',
            r'эгоистичн[а-я]+': 'Право на свои границы',
            r'пассивн[а-я]+': 'Право на действие',
            r'зависим[а-я]+': 'Право на автономию',
            r'контролиру[а-я]+': 'Право на свободу',
            r'жадн[а-я]+': 'Право иметь достаточно',
            r'неуважени[а-я]+': 'Право на уважение',
            r'неряшлив[а-я]+': 'Право на порядок',
            r'расслабленн[а-я]+': 'Право на концентрацию'
        }
        
        for pattern, resource in inversion_map.items():
            if re.search(pattern, q6_answer):
                return resource
        
        # Если не нашли совпадений, используем общий ресурс
        if any(word in q6_answer for word in ['бесит', 'раздражает', 'злит', 'неприятно']):
            return "Право на свои границы"
    
    return "Право брать свое"  # значение по умолчанию

def generate_metaformula_from_answers(answers: list) -> str:
    """Генерирует метаформулу по алгоритму на основе ответов"""
    symptom = extract_physical_symptom(answers)
    resource = extract_shadow_resource(answers)
    
    return f"Я — Автор, ПРИЗНАЮ {symptom} и ВЫБИРАЮ {resource}"

def generate_fallback_report(answers: list, index: int) -> str:
    """Генерирует фолбэк отчет с правильной формулой"""
    # Извлекаем данные для отчета
    symptom = extract_physical_symptom(answers)
    resource = extract_shadow_resource(answers)
    
    # Получаем метафору (если есть, теперь из Q4)
    metaphor = ""
    if len(answers) >= 4:
        q4_answer = answers[3]
        # Упрощаем метафору до первых 3-5 слов
        words = q4_answer.split()
        if len(words) > 5:
            metaphor = ' '.join(words[:5])
        else:
            metaphor = q4_answer
    
    # Формируем комментарий к индексу
    comment = ""
    if index >= 80:
        comment = "Ваша речь указывает на высокую степень зависимости от внешних обстоятельств. Вы действуете преимущественно в режиме «Реагирования», а не «Создания»."
    elif index >= 60:
        comment = "Ваши ответы демонстрируют смесь пассивных и активных конструкций, что указывает на переходное состояние. Вы осознаете необходимость изменений и готовы взять управление на себя, но еще не полностью освободились от влияния обстоятельств."
    else:
        comment = "У вас хороший уровень осознанности и авторской позиции. Осталось лишь систематизировать этот ресурс."
    
    # Формируем теневой ресурс анализ
    shadow_analysis = ""
    if len(answers) >= 6:
        q6_answer = answers[5]
        if 'нагл' in q6_answer.lower():
            shadow_analysis = "Ваше раздражение на наглость в других людях может быть инвертировано в скрытую силу – «Право брать свое». Это означает, что Вы имеете потенциал для более уверенного и самоутвержденного поведения, но пока не осознаете его."
        else:
            shadow_analysis = "Ваша реакция на определенные качества в других указывает на подавленную часть Вас самих. То, что Вы запрещаете себе, является скрытым источником энергии."
    
    report = f"""🧭 РЕЗУЛЬТАТЫ АУДИТА АВТОПИЛОТА

📊 ВАШ ИНДЕКС АВТОМАТИЗМА: {index}%
({comment})

🧠 ДИАГНОСТИКА СИСТЕМЫ

ЗАСТОЙНАЯ ДОМИНАНТА:
{"Ваша метафора «" + metaphor + "» и ощущение " + symptom.lower() + " указывают на то, что Вы чувствуете себя в ловушке и не можете освободиться от самоограничений. Это «магнит» для негатива блокирует Вашу энергию и искажает реальность, делая Вас более восприимчивым к истощению и самосаботажу." if metaphor else "Ваше ощущение " + symptom.lower() + " указывает на то, что Вы чувствуете себя в ловушке и не можете освободиться от самоограничений. Это «магнит» для негатива блокирует Вашу энергию."}

РЕЖИМ ЗАСТАВКИ (УТЕЧКА ЭНЕРГИИ):
{"Ваше описание дня, наполненного «самосаботажем» и выполнением действий, которые не приносят удовлетворения, указывает на то, что Ваш мозг тратит ресурсы на «холостой ход» вместо действия. Это приводит к истощению и чувству бессмысленности." if len(answers) >= 3 and 'самосаба' in answers[2].lower() else "Ваше описание рутины указывает на то, что Ваш мозг тратит ресурсы на «холостой ход» вместо действия. Это приводит к истощению и потере энергии."}

🔋 ТЕНЕВОЙ РЕСУРС (СКРЫТОЕ ТОПЛИВО)
{shadow_analysis}

🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор, ПРИЗНАЮ {symptom} и ВЫБИРАЮ {resource}

🚀 СЛЕДУЮЩИЙ ШАГ
Теперь, когда Вы осознали свои ограничения и потенциал, пора начать действовать. Используйте свою метаформулу как антидот к Доминанте и начните делать небольшие шаги к изменению. Помните, что инструкция по применению находится в гайде «Ревизия Маршрута»."""
    
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
    user_input_text = "ОТВЕТЫ ПОЛЬЗОВАТЕЛЯ НА 8 ВОПРОСОВ НЕЙРОКОГНИТИВНОГО АУДИТА:\n\n"
    for i, ans in enumerate(answers):
        user_input_text += f"ВОПРОС {i+1}: {QUESTIONS[i]}\n"
        user_input_text += f"ОТВЕТ: {ans}\n\n"
    
    user_input_text += "\n---\nПРОАНАЛИЗИРУЙ ЭТИ ОТВЕТЫ ПО ПРОТОКОЛУ МЕТА-НАВИГАТОРА И СОСТАВЬ ОТЧЕТ. В ОТЧЕТЕ ОБРАЩАЙСЯ К ПОЛЬЗОВАТЕЛЮ НА «ВЫ»."
    
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input_text}
                ],
                model="llama-3.3-70b",
                temperature=0.4,
                max_completion_tokens=1500,
                top_p=0.9
            )
            
            api_failures = 0
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                    if content:
                        # Постобработка отчета
                        content = postprocess_report(content, answers)
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

def postprocess_report(report: str, answers: list) -> str:
    """Постобработка отчета"""
    try:
        if not report:
            return report
            
        # Рассчитываем индекс автоматизма
        automatism_index = calculate_automatism_index(answers)
        
        # Вставляем индекс в отчет
        if "ИНДЕКС АВТОМАТИЗМА:" in report or "Индекс автоматизма:" in report:
            report = re.sub(
                r'(ИНДЕКС АВТОМАТИЗМА|Индекс автоматизма):\s*\[X\]%',
                f'ИНДЕКС АВТОМАТИЗМА: {automatism_index}%',
                report,
                flags=re.IGNORECASE
            )
        else:
            if "🧭 РЕЗУЛЬТАТЫ АУДИТА" in report:
                report = report.replace("🧭 РЕЗУЛЬТАТЫ АУДИТА", 
                                      f"🧭 РЕЗУЛЬТАТЫ АУДИТА\n\n📊 ВАШ ИНДЕКС АВТОМАТИЗМА: {automatism_index}%")
        
        # Добавляем комментарий к индексу
        comment = ""
        if automatism_index >= 80:
            comment = "Ваша речь указывает на высокую степень зависимости от внешних обстоятельств. Вы действуете преимущественно в режиме «Реагирования», а не «Создания»."
        elif automatism_index >= 60:
            comment = "Ваши ответы демонстрируют смесь пассивных и активных конструкций, что указывает на переходное состояние. Вы осознаете необходимость изменений и готовы взять управление на себя, но еще не полностью освободились от влияния обстоятельств."
        else:
            comment = "У вас хороший уровень осознанности и авторской позиции. Осталось лишь систематизировать этот ресурс."
        
        if comment:
            if "📊 ВАШ ИНДЕКС АВТОМАТИЗМА:" in report:
                report = report.replace(f"📊 ВАШ ИНДЕКС АВТОМАТИЗМА: {automatism_index}%",
                                      f"📊 ВАШ ИНДЕКС АВТОМАТИЗМА: {automatism_index}%\n({comment})")
        
        # Проверяем и исправляем формулу если нужно
        formula_pattern = r'🔑 ВАША МЕТАФОРМУЛА.*?\n(.+?)(?=\n\n|\n🚀|\n🎯|$)'
        match = re.search(formula_pattern, report, re.DOTALL | re.IGNORECASE)
        
        if match:
            formula = match.group(1).strip()
            # Проверяем, соответствует ли формула алгоритму
            if not ("Я — Автор" in formula and "ПРИЗНАЮ" in formula and "ВЫБИРАЮ" in formula):
                # Заменяем на правильную формулу
                correct_formula = generate_metaformula_from_answers(answers)
                report = report.replace(formula, correct_formula)
        
        # Убираем лишние пустые строки
        report = re.sub(r'\n{3,}', '\n\n', report)
        
        # Убираем escape-последовательности
        report = report.replace('\\n', '\n').replace('\\t', '\t')
        
        # Заменяем обращение "пользователь" на "Вы"
        report = re.sub(r'\bпользователь\b', 'Вы', report, flags=re.IGNORECASE)
        report = re.sub(r'\bему\b', 'Вам', report, flags=re.IGNORECASE)
        report = re.sub(r'\bего\b', 'Ваш', report, flags=re.IGNORECASE)
        report = re.sub(r'\bон\b', 'Вы', report, flags=re.IGNORECASE)
        report = re.sub(r'\bона\b', 'Вы', report, flags=re.IGNORECASE)
        
        return report
        
    except Exception as e:
        logger.error(f"Ошибка в postprocess_report: {e}")
        return report

# --- ВЕБ-СЕРВЕР ---
async def handle_health(request):
    uptime = datetime.now() - start_time
    return web.Response(text=f"Meta-Navigator v3.1 | Uptime: {str(uptime).split('.')[0]} | Errors: {error_counter} | API fails: {api_failures}")

async def send_startup_notification():
    try:
        bot_info = await bot.get_me()
        msg = (
            "🚀 МЕТА-НАВИГАТОР v3.1 ЗАПУЩЕН\n\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m %H:%M:%S')}\n"
            f"🤖 Бот: @{bot_info.username}\n"
            f"🧠 Архитектор Метаформулы: АКТИВИРОВАН\n"
            f"🔑 Cerebras API: {'✅' if CEREBRAS_API_KEY else '❌ ДЕМО-РЕЖИМ'}\n"
            f"📊 Порт: {os.environ.get('PORT', 8080)}\n"
            f"🌐 Health check: доступен\n"
            f"⚙️ Версия: 8 вопросов + прямой PDF + обращение на ВЫ"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=msg)
    except Exception as e:
        logger.error(f"Не удалось отправить startup notification: {e}")

async def main():
    if not TOKEN:
        logger.error("❌ ОШИБКА: BOT_TOKEN не установлен!")
        raise ValueError("BOT_TOKEN не установлен")
    
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
    
    logger.info(f"✅ Мета-Навигатор v3.1 запущен")
    logger.info(f"🤖 Bot: @{(await bot.get_me()).username}")
    logger.info(f"🧠 Архитектор Метаформулы: АКТИВИРОВАН")
    logger.info(f"🔑 Cerebras API: {'✅' if CEREBRAS_API_KEY else '❌ ДЕМО-РЕЖИМ'}")
    logger.info(f"🌐 Health check: http://0.0.0.0:{port}/")
    logger.info(f"📝 Опросник: {len(QUESTIONS)} вопросов")
    
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.critical(f"Бот упал: {e}")
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
[file content end]
