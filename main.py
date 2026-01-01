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

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
CEREBRAS_API_KEY = os.getenv("AI_API_KEY")
CHANNEL_ID = "@metaformula_life"
ADMIN_ID = 7830322013

# Ресурсы проекта
LOGO_FORMULA_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png.png"
LOGO_NAVIGATOR_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
# Используем прямой URL к PDF на GitHub
GUIDE_URL = "https://github.com/Elektra174/meta_navigator_bot/raw/main/reviziaguide.pdf"
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

# --- СПИСОК ВОПРОСОВ ---
QUESTIONS = [
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
                "Мы пройдем 7 шагов, чтобы найти вашу личную Метаформулу.\n\n"
                "Готовы начать?",
        "logo": LOGO_NAVIGATOR_URL
    }
}

# --- УЛУЧШЕННЫЙ СИСТЕМНЫЙ ПРОМПТ v3.0 "Архитектор Метаформулы" ---
SYSTEM_PROMPT = """ТЫ — «Архитектор Метаформулы», эксперт по нейробиологии и когнитивной лингвистике. Твоя задача — собрать персональную «Метаформулу» для клиента на основе данных его аудита.

ВАЖНОЕ ОГРАНИЧЕНИЕ: Метаформула — это НЕ аффирмация, НЕ лозунг и НЕ позитивное мышление. Это технический протокол перехвата управления у лимбической системы через метод Affect Labeling (вербальная маркировка).

НЕ ДОПУСКАЙ общих фраз типа «я иду к счастью» или «я выхожу из болота».

АЛГОРИТМ СБОРКИ МЕТАФОРМУЛЫ (строгая формула):

Я — Автор + ПРИЗНАЮ [Симптом/Зажим] + ВЫБИРАЮ [Теневой ресурс]

КОМПОНЕНТЫ ДЛЯ СБОРКИ:

1. ПОЗИЦИЯ: Всегда фиксированная — «Я — Автор».
2. СИМПТОМ (баг): Конкретное телесное ощущение или зажим, который клиент указал в аудите.
   - Ищем в ответах Q4: физическое проявление в теле
   - Примеры: сжатие в груди, ком в горле, тяжесть в плечах, напряжение в шее
3. ТЕНЕВОЙ РЕСУРС (топливо): Инвертированный ресурс из того, что клиента раздражает в других.
   - Ищем в ответах Q5: что бесит/раздражает
   - Инвертируем: если бесит наглость → ресурс «Право брать свое»
   - Примеры: Наглость → Право брать свое; Безответственность → Право на отдых; Лживость → Право на правду

ИНСТРУКЦИЯ ПО ОБРАБОТКЕ:

1. Если клиент описал проблему метафорой (например, «болото» в Q3), найди в его ответах Q4 физическое проявление этой метафоры в теле. В формулу должен идти именно «датчик» (телесное ощущение).
2. Глаголы «ПРИЗНАЮ» и «ВЫБИРАЮ» должны быть выделены капсом, так как они являются операционными командами для мозга.
3. Формула должна быть короткой, сухой и инструментальной.
4. Избегай объяснений, комментариев, дополнений. Только чистая формула.

ПРИМЕРЫ ПРАВИЛЬНОЙ РАБОТЫ:

Вход: 
- Q4: зажим в челюсти, скрежет зубами
- Q5: бесит чужая расслабленность
Твоя Метаформула: «Я — Автор, ПРИЗНАЮ зажим в челюсти и ВЫБИРАЮ Право на отдых»

Вход:
- Q3: как будто топчусь на месте
- Q4: сжатие в солнечном сплетении
- Q5: раздражает наглость других
Твоя Метаформула: «Я — Автор, ПРИЗНАЮ сжатие в солнечном сплетении и ВЫБИРАЮ Право брать свое»

СТРУКТУРА ОТЧЕТА (только формула):

🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
[Только одна готовая формула по алгоритму]

ВАЖНО:
1. ТОЛЬКО ОДНА ФОРМУЛА
2. ТОЛЬКО СТРОГО ПО АЛГОРИТМУ: Я — Автор, ПРИЗНАЮ [симптом] и ВЫБИРАЮ [ресурс]
3. БЕЗ КОММЕНТАРИЕВ, БЕЗ ОБЪЯСНЕНИЙ, БЕЗ ДОПОЛНИТЕЛЬНОГО ТЕКСТА
4. НЕ ИСПОЛЬЗОВАТЬ МЕТАФОРЫ ИЗ Q3 В ФОРМУЛЕ, ТОЛЬКО ТЕЛЕСНЫЕ ОЩУЩЕНИЯ ИЗ Q4
5. ГЛАГОЛЫ «ПРИЗНАЮ» и «ВЫБИРАЮ» ВСЕГДА КАПСОМ
"""

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
            "В течение следующих 7 шагов мы проведем диагностику вашей «прошивки». "
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
                "Архитектор Метаформулы анализирует ваши ответы и собирает персональный нейро-ключ..."
            )
            
            try:
                formula = await generate_metaformula(user_answers)
                
                if formula:
                    # Формируем полный отчет с формулой
                    report = f"""🧭 РЕЗУЛЬТАТЫ АУДИТА АВТОПИЛОТА

📊 ВАШ ИНДЕКС АВТОМАТИЗМА: {calculate_automatism_index(user_answers)}%

🧠 ДИАГНОСТИКА СИСТЕМЫ

На основе ваших ответов выявлена Застойная Доминанта — очаг возбуждения, работающий как «нейронный магнит». Эта доминанта фильтрует восприятие реальности, блокируя доступ к новым возможностям.

Ваш мозг тратит значительные ресурсы на руминацию — бесконечное пережевывание прошлых сценариев или тревожное моделирование будущего. Это работа Дефолт-системы (DMN) вхолостую, «Режим Заставки».

🔋 ТЕНЕВОЙ РЕСУРС
Ваше раздражение на определенные качества в других указывает на подавленную часть вас самих. То, что вы запрещаете себе, является скрытым источником энергии.

{formula}

🚀 СЛЕДУЮЩИЙ ШАГ
Ваша Метаформула — это технический протокол перехвата управления у лимбической системы. Это ключ для активации режима «Автор»."""
                    
                    # Очищаем и отправляем отчет пользователю
                    clean_report = clean_report_for_telegram(report)
                    await message.answer(clean_report)
                    
                    # СРАЗУ отправляем PDF гайд после отчета
                    await send_guide_immediately(message)
                    
                    # Отправляем копию администратору
                    await send_admin_copy(message.from_user, user_answers, clean_report)
                else:
                    logger.error("Формула ИИ вернула пустой результат")
                    index = calculate_automatism_index(user_answers)
                    fallback_formula = "Я — Автор, ПРИЗНАЮ сжатие в солнечном сплетении и ВЫБИРАЮ Право брать свое"
                    
                    fallback_report = f"""🧭 РЕЗУЛЬТАТЫ АУДИТА АВТОПИЛОТА

📊 ВАШ ИНДЕКС АВТОМАТИЗМА: {index}%

🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
{fallback_formula}

🚀 СЛЕДУЮЩИЙ ШАГ
Ваша Метаформула — это технический протокол перехвата управления у лимбической системы. Это ключ для активации режима «Автор»."""
                    
                    await message.answer(fallback_report)
                    await send_guide_immediately(message)
                    
            except Exception as report_error:
                logger.error(f"Ошибка при генерации формулы: {report_error}")
                await send_admin_alert("formula_generation_error", str(report_error), traceback.format_exc())
                index = calculate_automatism_index(user_answers)
                fallback_formula = "Я — Автор, ПРИЗНАЮ напряжение в теле и ВЫБИРАЮ Право на действие"
                
                fallback_report = f"""🧭 РЕЗУЛЬТАТЫ АУДИТА АВТОПИЛОТА

📊 ВАШ ИНДЕКС АВТОМАТИЗМА: {index}%

🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
{fallback_formula}

🚀 СЛЕДУЮЩИЙ ШАГ
Ваша Метаформула — это технический протокол перехвата управления у лимбической системы. Это ключ для активации режима «Автор»."""
                
                await message.answer(fallback_report)
                await send_guide_immediately(message)
            
            await state.clear()
            
    except Exception as e:
        error_counter += 1
        logger.error(f"Ошибка обработки ответа: {e}")
        await send_admin_alert("process_error", str(e), traceback.format_exc())
        await message.answer(
            "⚠️ Произошла техническая ошибка при обработке вашего ответа.\n\n"
            "Пожалуйста, начните аудит заново с команды /start"
        )

async def send_guide_immediately(message: types.Message):
    """Сразу отправляет PDF гайд после отчета"""
    try:
        # Отправляем PDF файл как документ
        await message.answer_document(
            document=GUIDE_URL,
            caption=(
                "📥 **Гайд «Ревизия маршрута»**\n\n"
                "Ваш путеводитель к состоянию Автора жизни с помощью Метаформулы.\n\n"
                "Внутри вы найдете:\n"
                "• Инженерные инструкции по внедрению Метаформулы\n"
                "• Протоколы для отключения Дефолт-системы\n"
                "• Техники создания новой Доминанты\n"
                "• Систему мониторинга энергетического бюджета"
            ),
            parse_mode="Markdown"
        )
        
        # Теперь отправляем кнопку для мастер-класса
        await send_masterclass_button(message)
        
    except Exception as e:
        logger.error(f"Ошибка отправки гайда: {e}")
        try:
            # Альтернатива: отправляем сообщение с кнопкой
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text='📥 СКАЧАТЬ ГАЙД «РЕВИЗИЯ МАРШРУТА»', 
                    url=GUIDE_URL
                )
            )
            builder.row(
                types.InlineKeyboardButton(
                    text='🎬 ЗАБРАТЬ МК «СДВИГ ОПТИКИ»', 
                    url=MASTERCLASS_URL
                )
            )
            
            await message.answer(
                "📥 Чтобы получить гайд «Ревизия маршрута» и мастер-класс «Сдвиг оптики», "
                "нажмите на кнопки ниже:",
                reply_markup=builder.as_markup()
            )
        except Exception as e2:
            logger.error(f"Альтернативный метод тоже не сработал: {e2}")
            await message.answer(
                "📥 Для получения материалов перейдите по ссылкам:\n"
                f"Гайд: {GUIDE_URL}\n"
                f"Мастер-класс: {MASTERCLASS_URL}"
            )

async def send_masterclass_button(message: types.Message):
    """Отправляет кнопку для мастер-класса"""
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(
                text='🎬 ЗАБРАТЬ МК «СДВИГ ОПТИКИ»', 
                url=MASTERCLASS_URL
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
        logger.error(f"Ошибка отправки кнопки мастер-класса: {e}")
        try:
            await message.answer(
                "🎯 Ваш нейрокогнитивный аудит завершен!\n\n"
                "Для полного погружения в методику получите мастер-класс:\n"
                f"{MASTERCLASS_URL}"
            )
        except:
            pass

@dp.callback_query(F.data == "download_guide")
async def handle_download_guide(callback: types.CallbackQuery):
    """Резервная функция для отправки гайда по запросу"""
    await callback.answer("Отправляю гайд...")
    
    try:
        await callback.message.answer_document(
            document=GUIDE_URL,
            caption="📥 Гайд «Ревизия маршрута» — ваше руководство по внедрению Метаформулы"
        )
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
    """Извлекает физический симптом из ответа на Q4"""
    if len(answers) >= 4:
        q4_answer = answers[3].lower()
        
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
            match = re.search(pattern, q4_answer)
            if match:
                return match.group(0)
        
        # Если не нашли по паттернам, ищем ключевые слова
        keywords = ['сжатие', 'тяжесть', 'напряжение', 'ком', 'пустота', 'жжение', 'холод', 'дрожь', 'боль', 'дискомфорт']
        for keyword in keywords:
            if keyword in q4_answer:
                # Берем контекст вокруг ключевого слова
                start = max(0, q4_answer.find(keyword) - 20)
                end = min(len(q4_answer), q4_answer.find(keyword) + 30)
                return q4_answer[start:end].strip()
    
    return "сжатие в солнечном сплетении"  # значение по умолчанию

def extract_shadow_resource(answers: list) -> str:
    """Извлекает теневой ресурс из ответа на Q5"""
    if len(answers) >= 5:
        q5_answer = answers[4].lower()
        
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
            if re.search(pattern, q5_answer):
                return resource
        
        # Если не нашли совпадений, используем общий ресурс
        if any(word in q5_answer for word in ['бесит', 'раздражает', 'злит', 'неприятно']):
            return "Право на свои границы"
    
    return "Право брать свое"  # значение по умолчанию

# --- ГЕНЕРАЦИЯ МЕТАФОРМУЛЫ ---
async def generate_metaformula(answers: list):
    global api_failures
    
    if not client:
        # Демо-режим: генерируем формулу по алгоритму
        try:
            symptom = extract_physical_symptom(answers)
            resource = extract_shadow_resource(answers)
            
            # Форматируем симптом (делаем первую букву заглавной)
            symptom = symptom.strip()
            if symptom and not symptom[0].isupper():
                symptom = symptom[0].upper() + symptom[1:]
            
            return f"""🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор, ПРИЗНАЮ {symptom} и ВЫБИРАЮ {resource}"""
        except Exception as e:
            logger.error(f"Ошибка в демо-режиме генерации формулы: {e}")
            return """🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор, ПРИЗНАЮ сжатие в солнечном сплетении и ВЫБИРАЮ Право брать свое"""
    
    # Подготавливаем данные для ИИ
    user_input_text = "ДАННЫЕ АУДИТА КЛИЕНТА:\n\n"
    
    # Важные для формулы вопросы
    important_questions = [3, 4, 5]  # Q3, Q4, Q5
    for i in important_questions:
        if i < len(answers):
            user_input_text += f"ВОПРОС {i+1}: {QUESTIONS[i]}\n"
            user_input_text += f"ОТВЕТ: {answers[i]}\n\n"
    
    user_input_text += "\n---\nСОБЕРИ МЕТАФОРМУЛУ ПО СТРОГОМУ АЛГОРИТМУ: Я — Автор, ПРИЗНАЮ [симптом из Q4] и ВЫБИРАЮ [ресурс из Q5]"
    
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input_text}
                ],
                model="llama-3.3-70b",
                temperature=0.3,  # Более низкая температура для строгого следования алгоритму
                max_completion_tokens=500,
                top_p=0.8
            )
            
            api_failures = 0
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content.strip()
                    if content:
                        # Проверяем, что формула соответствует алгоритму
                        if "Я — Автор" in content and "ПРИЗНАЮ" in content and "ВЫБИРАЮ" in content:
                            # Убираем возможные лишние символы
                            content = re.sub(r'^["«]*(.*?)["»]*$', r'\1', content)
                            return content
                        else:
                            # Если ИИ выдал не по алгоритму, генерируем сами
                            symptom = extract_physical_symptom(answers)
                            resource = extract_shadow_resource(answers)
                            symptom = symptom.strip()
                            if symptom and not symptom[0].isupper():
                                symptom = symptom[0].upper() + symptom[1:]
                            
                            return f"""🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор, ПРИЗНАЮ {symptom} и ВЫБИРАЮ {resource}"""
            
            # Если ответ пустой, генерируем сами
            symptom = extract_physical_symptom(answers)
            resource = extract_shadow_resource(answers)
            symptom = symptom.strip()
            if symptom and not symptom[0].isupper():
                symptom = symptom[0].upper() + symptom[1:]
            
            return f"""🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор, ПРИЗНАЮ {symptom} и ВЫБИРАЮ {resource}"""
            
        except Exception as e:
            api_failures += 1
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
            
            if attempt == 2:
                await send_admin_alert("api_critical", f"3 попытки провалились: {str(e)}")
                # Генерируем формулу самостоятельно
                symptom = extract_physical_symptom(answers)
                resource = extract_shadow_resource(answers)
                symptom = symptom.strip()
                if symptom and not symptom[0].isupper():
                    symptom = symptom[0].upper() + symptom[1:]
                
                return f"""🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор, ПРИЗНАЮ {symptom} и ВЫБИРАЮ {resource}"""
            
            await asyncio.sleep(2 ** attempt)
    
    # Фоллбек формула
    return """🔑 ВАША МЕТАФОРМУЛА (КОД АКТИВАЦИИ)
Я — Автор, ПРИЗНАЮ сжатие в солнечном сплетении и ВЫБИРАЮ Право брать свое"""

# --- ВЕБ-СЕРВЕР ---
async def handle_health(request):
    uptime = datetime.now() - start_time
    return web.Response(text=f"Meta-Navigator v3.0 | Uptime: {str(uptime).split('.')[0]} | Errors: {error_counter} | API fails: {api_failures}")

async def send_startup_notification():
    try:
        bot_info = await bot.get_me()
        msg = (
            "🚀 МЕТА-НАВИГАТОР v3.0 ЗАПУЩЕН\n\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m %H:%M:%S')}\n"
            f"🤖 Бот: @{bot_info.username}\n"
            f"🧠 Архитектор Метаформулы: АКТИВИРОВАН\n"
            f"🔑 Cerebras API: {'✅' if CEREBRAS_API_KEY else '❌ ДЕМО-РЕЖИМ'}\n"
            f"📊 Порт: {os.environ.get('PORT', 8080)}\n"
            f"🌐 Health check: доступен\n"
            f"⚙️ Версия: Нейро-ключи по алгоритму v3.0"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=msg)
    except Exception as e:
        logger.error(f"Не удалось отправить startup notification: {e}")

async def main():
    if not TOKEN:
        logger.error("❌ ОШИБКА: BOT_TOKEN не установлен!")
        raise ValueError("BOT_TOKEN не установлен")
    
    if not CEREBRAS_API_KEY:
        logger.warning("⚠️ AI_API_KEY не установлен! Будет использоваться демо-режим.")
    
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
    
    logger.info(f"✅ Мета-Навигатор v3.0 запущен")
    logger.info(f"🤖 Bot: @{(await bot.get_me()).username}")
    logger.info(f"🧠 Архитектор Метаформулы: АКТИВИРОВАН")
    logger.info(f"🔑 Cerebras API: {'✅' if CEREBRAS_API_KEY else '❌ ДЕМО-РЕЖИМ'}")
    logger.info(f"🌐 Health check: http://0.0.0.0:{port}/")
    
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
