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
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
CEREBRAS_API_KEY = os.getenv("AI_API_KEY")
CHANNEL_ID = "@metaformula_life"
ADMIN_ID = 7830322013

# Ресурсы проекта
LOGO_FORMULA_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png.png"
LOGO_NAVIGATOR_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
GUIDE_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/revizia_guide.pdf"
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
    "В какой ситуации в жизни Вы сейчас чувствуете самый сильный застой или «пробуксовку»? Опишите кратко, что происходит.",
    "Опишите ваш «фоновый шум». Когда вы ничем не заняты, какие мысли возникают сами по себе?",
    "Если бы это состояние застоя можно было представить в виде образа... на что бы это было похоже? Опишите подробнее (форма, размер, цвет, температура..)",
    "Как этот образ Вас ограничивает? Что именно он делает, когда Вы пытаетесь двигаться вперед?",
    "Какое качество или поведение в других людях вызывает у вас самое сильное раздражение? Что они себе позволяют, что вы себе запрещаете?",
    "Какую цену вы платите за поддержание текущего состояния? Что истощается (время, внимание, силы)?",
    "Готовы ли вы прямо сейчас перехватить управление у автоматической программы и перейти в состояние осознанного автора?"
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

# --- УПРОЩЕННЫЙ СИСТЕМНЫЙ ПРОМПТ ---
SYSTEM_PROMPT = """Ты — «Мета-Навигатор», эксперт по нейрофизиологии и методу МПТ.
Проанализируй 7 ответов пользователя и создай «Код Сдвига».

ПРАВИЛА:
1. Используй точные слова из ответов
2. Не придумывай то, чего нет
3. Обращайся на "Вы"

СТРУКТУРА ОТЧЕТА:

📊 РЕЗУЛЬТАТЫ АУДИТА
Индекс Автоматизма: [X]%

🧲 ДОМИНАНТА
[Опиши образ из Ответа 3 кратко]
Этот образ является силой собственного торможения, не позволяя вам найти выход и двигаться вперед.

⚙️ ФУНКЦИЯ ДЕФОЛТ-СИСТЕМЫ
Вы тратите нейронный ресурс на поддержание проблемы, [опиши кратко].

🔑 ВАША МЕТАФОРМУЛА
[ФОРМУЛА В КАПСЛОКЕ, начни с ИСПОЛЬЗУЙТЕ или ВОЗЬМИТЕ]

⚡ ИНСТРУКЦИЯ ПО АКТИВАЦИИ
Нейрофизиология формулы: [Качество из Ответа 5] содержит энергию, необходимую для [решения из Ответа 1].
Действие: Примените формулу прямо сейчас.

🎴 СОСТОЯНИЕ АВТОРА
В этом состоянии нет страха перед будущим, есть только энергия для действия.

ПРИМЕР для ответов:
1. "не знаю чем заняться"
5. "наглость"
Формула: ИСПОЛЬЗУЙТЕ НАГЛОСТЬ, ЧТОБЫ НАЙТИ ДЕЛО
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
        msg = f"🚨 *PROBLEM: {alert_type.upper()}*\n\n"
        msg += f"⏰ *Время:* {ts}\n"
        msg += f"📝 *Детали:* {details}\n"
        if tb:
            msg += f"\n🔧 *Traceback:*\n```python\n{tb[:1000]}```"
        msg += f"\n\n📊 *Статистика:* Ошибок: {error_counter} | Сбоев API: {api_failures}"
        await bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Не удалось отправить алерт: {e}")

async def send_admin_copy(user: types.User, answers: list, report: str):
    try:
        user_info = f"👤 {user.full_name} (@{user.username})"
        text_answers = "\n".join([f"{i+1}. {a}" for i, a in enumerate(answers)])
        full_log = f"🔔 **НОВЫЙ АУДИТ ЗАВЕРШЕН**\n{user_info}\n\n**Ответы:**\n{text_answers}\n\n**Отчет ИИ:**\n{report}"
        
        if len(full_log) > 4000:
            await bot.send_message(chat_id=ADMIN_ID, text=full_log[:4000])
            await bot.send_message(chat_id=ADMIN_ID, text=full_log[4000:])
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=full_log, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Admin log error: {e}")

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
            "🔬 **Аудит Автопилота**\n\nОтвечайте искренне — каждый ответ формирует нейронную карту вашего состояния.",
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(1)
        await callback.message.answer(f"📝 *Шаг 1 из {len(QUESTIONS)}:*\n\n{QUESTIONS[0]}", parse_mode="Markdown")
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
            await message.answer(
                f"📝 *Шаг {next_step + 1} из {len(QUESTIONS)}:*\n\n{QUESTIONS[next_step]}",
                parse_mode="Markdown"
            )
        else:
            await state.update_data(answers=user_answers)
            await message.answer(
                "🌀 **Синхронизирую данные...**\nАнализирую Ваши ответы..",
                parse_mode="Markdown"
            )
            
            report = await generate_ai_report(user_answers)
            
            if report:
                # Очищаем отчет от возможных проблем с Markdown
                clean_report = sanitize_markdown(report)
                # Убираем лишнее "ТЕ" из формулы
                clean_report = clean_report.replace("ИСПОЛЬЗУЙТЕ ТЕ ", "ИСПОЛЬЗУЙТЕ ")
                await message.answer(clean_report, parse_mode="Markdown")
                
                # Отправляем кнопки после отчета
                await send_offer_buttons(message)
                
                await send_admin_copy(message.from_user, user_answers, clean_report)
            else:
                await message.answer(
                    "⚠️ *Не удалось сгенерировать отчет*\n\nПопробуйте начать аудит заново с команды /start",
                    parse_mode="Markdown"
                )
            
            await state.clear()
            
    except Exception as e:
        error_counter += 1
        logger.error(f"Ошибка обработки ответа: {e}")
        await send_admin_alert("process_error", str(e), traceback.format_exc())
        await message.answer("⚠️ Технический сбой. Пожалуйста, перезапустите бота командой /start")

async def send_offer_buttons(message: types.Message):
    """Отправка кнопок с предложениями после отчета"""
    offer_text = (
        "🎯 **Хотите глубже проработать свою Метаформулу?**\n\n"
        "1. 📥 **Гайд «Ревизия маршрута»** - пошаговый план для самостоятельной работы\n"
        "2. 🎬 **Мастер-класс «Сдвиг оптики»** - полный разбор методики с Александром Лазаренко"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text='📥 СКАЧАТЬ ГАЙД "РЕВИЗИЯ МАРШРУТА"', 
            callback_data="download_guide"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text='🎬 ЗАБРАТЬ МАСТЕР-КЛАСС «СДВИГ ОПТИКИ»', 
            url=MASTERCLASS_URL
        )
    )
    
    await message.answer(
        offer_text, 
        parse_mode="Markdown", 
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "download_guide")
async def handle_download_guide(callback: types.CallbackQuery):
    """Отправка гайда в чат"""
    await callback.answer("Отправляю гайд...")
    
    try:
        # Отправляем PDF файл с обновленной фразой
        await callback.message.answer_document(
            document=GUIDE_URL,
            caption="📥 **Гайд «Ревизия маршрута»**\n\nВаш путеводитель к состоянию Автора жизни с помощью Метаформулы."
        )
    except Exception as e:
        logger.error(f"Ошибка отправки гайда: {e}")
        await callback.answer("Ошибка отправки гайда", show_alert=True)

# --- УТИЛИТЫ ДЛЯ ОЧИСТКИ MARKDOWN ---
def sanitize_markdown(text: str) -> str:
    """Очищает текст от проблемных символов Markdown и лишних обратных слэшей"""
    # Сначала убираем обратные слэши перед символами Markdown
    replacements_to_remove = {
        r'\\#': '#',
        r'\\##': '##',
        r'\\###': '###',
        r'\\---': '---',
        r'\\-\-\-': '---',
        r'\\\.': '.',
        r'\\\-': '-',
        r'\\\*': '*',
        r'\\\_': '_',
        r'\\\[': '[',
        r'\\\]': ']',
        r'\\\(': '(',
        r'\\\)': ')',
        r'\\\~': '~',
        r'\\\`': '`',
        r'\\\>': '>',
        r'\\\+': '+',
        r'\\\=': '=',
        r'\\\|': '|',
        r'\\\{': '{',
        r'\\\}': '}',
        r'\\\!': '!',
    }
    
    # Применяем очистку от обратных слэшей
    for pattern, replacement in replacements_to_remove.items():
        text = re.sub(pattern, replacement, text)
    
    # Теперь экранируем только действительно опасные символы для Markdown
    # но не трогаем заголовки и разделители
    lines = text.split('\n')
    result_lines = []
    in_code_block = False
    
    for line in lines:
        # Проверяем, не является ли строка заголовком или разделителем
        is_header = line.strip().startswith('#') and not line.strip().startswith('\\#')
        is_divider = line.strip() == '---' or line.strip() == '\\---'
        
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            result_lines.append(line)
            continue
            
        if in_code_block or is_header or is_divider:
            # Не экранируем заголовки, разделители и код
            result_lines.append(line)
        else:
            # Экранируем только опасные символы в обычном тексте
            clean_line = line
            
            # Экранируем только определенные символы
            dangerous_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>']
            for char in dangerous_chars:
                if char in clean_line:
                    # Не экранируем если уже есть обратный слэш
                    if f'\\{char}' not in clean_line:
                        clean_line = clean_line.replace(char, f'\\{char}')
            
            result_lines.append(clean_line)
    
    text = '\n'.join(result_lines)
    
    # Убираем двойные обратные слэши
    text = text.replace('\\\\', '\\')
    
    return text

def postprocess_report(report: str, answers: list) -> str:
    """Постобработка отчета"""
    try:
        # 1. Исправляем "человек тратит" на "Вы тратите"
        report = report.replace("Человек тратит", "Вы тратите")
        report = report.replace("человек тратит", "Вы тратите")
        
        # 2. Упрощаем описание доминанты
        if "это как" in report.lower():
            # Ищем описание образа
            lines = report.split('\n')
            for i, line in enumerate(lines):
                if "это как" in line.lower() or "это похоже" in line.lower():
                    # Упрощаем описание
                    clean_line = re.sub(r'это (как|похоже на|будто)\s*', '', line, flags=re.IGNORECASE)
                    clean_line = re.sub(r'\b(я|меня|мне|мо[еёйюя])\b\s*', '', clean_line, flags=re.IGNORECASE)
                    clean_line = clean_line.strip()
                    if clean_line and clean_line[0].islower():
                        clean_line = clean_line[0].upper() + clean_line[1:]
                    lines[i] = clean_line
                    break
            report = '\n'.join(lines)
        
        # 3. Исправляем метаформулу
        formula_pattern = r"(ИСПОЛЬЗУЙ|ВОЗЬМИ|ПРИМЕНИ|НАЧНИ|СДЕЛАЙ)(.*?)(?=\n|$)"
        formula_match = re.search(formula_pattern, report, re.IGNORECASE | re.DOTALL)
        
        if formula_match:
            verb = formula_match.group(1).upper()
            rest = formula_match.group(2).strip()
            
            polite_verbs = {
                "ИСПОЛЬЗУЙ": "ИСПОЛЬЗУЙТЕ",
                "ВОЗЬМИ": "ВОЗЬМИТЕ",
                "ПРИМЕНИ": "ПРИМЕНИТЕ",
                "НАЧНИ": "НАЧНИТЕ",
                "СДЕЛАЙ": "СДЕЛАЙТЕ"
            }
            
            polite_verb = polite_verbs.get(verb, verb)
            
            # Исправляем грамматику и убираем лишнее "ТЕ"
            grammar_fixes = {
                "ЧТОБЫ НАЧНИТЕ": "ЧТОБЫ НАЧАТЬ",
                "ЧТОБЫ СДЕЛАЙТЕ": "ЧТОБЫ СДЕЛАТЬ",
                "ДЛЯ БИЗНЕСА": "ДЛЯ ДЕЛА",
                "НАЙТИ БИЗНЕС": "НАЙТИ ДЕЛО",
                "ТЕ НАГЛОСТЬ": "НАГЛОСТЬ",
                "ИСПОЛЬЗУЙТЕ ТЕ ": "ИСПОЛЬЗУЙТЕ ",
                "ВОЗЬМИТЕ ТЕ ": "ВОЗЬМИТЕ ",
                "ПРИМЕНИТЕ ТЕ ": "ПРИМЕНИТЕ ",
            }
            
            formula = f"{polite_verb} {rest}"
            for wrong, correct in grammar_fixes.items():
                if wrong in formula:
                    formula = formula.replace(wrong, correct)
            
            # Заменяем в отчете
            old_formula = f"{verb}{rest}"
            report = report.replace(old_formula, formula)
        
        # 4. Убираем "из Ответа №5"
        report = re.sub(r'из Ответа? №?\d+', '', report, flags=re.IGNORECASE)
        
        # 5. Убираем лишние #, ## и ** из отчета
        # Убираем ### в начале строк
        report = re.sub(r'^###\s*', '', report, flags=re.MULTILINE)
        # Убираем ## в начале строк
        report = re.sub(r'^##\s*', '', report, flags=re.MULTILINE)
        # Убираем # в начале строк
        report = re.sub(r'^#\s*', '', report, flags=re.MULTILINE)
        # Убираем ** вокруг текста (но оставляем для bold в других местах)
        report = re.sub(r'\*\*([^*]+)\*\*', r'\1', report)
        
        return report
        
    except Exception as e:
        logger.error(f"Ошибка в postprocess_report: {e}")
        return report  # Возвращаем оригинал в случае ошибки

# --- AI REPORT GENERATION ---
async def generate_ai_report(answers: list):
    global api_failures
    
    if not client:
        # Демо-режим для тестирования
        return """📊 РЕЗУЛЬТАТЫ АУДИТА
Индекс Автоматизма: 80%

🧲 ДОМИНАНТА
Карусель, которая раскрутилась и дезориентирует, не позволяя остановиться и осмотреться.
Этот образ является силой собственного торможения, не позволяя вам найти выход и двигаться вперед.

⚙️ ФУНКЦИЯ ДЕФОЛТ-СИСТЕМЫ
Вы тратите нейронный ресурс на поддержание неопределенности и страха, связанных с новым проектом, и на постоянные мысли о том, получится ли и будет ли востребован.

🔑 ВАША МЕТАФОРМУЛА
ИСПОЛЬЗУЙТЕ НАГЛОСТЬ, ЧТОБЫ ОСТАНОВИТЬ КАРУСЕЛЬ И НАЙТИ СВОЙ ПУТЬ

⚡ ИНСТРУКЦИЯ ПО АКТИВАЦИИ
Нейрофизиология формулы: Наглость содержит энергию, необходимую для того, чтобы преодолеть неопределенность и страх, и двигаться вперед в новом проекте.
Действие: Примените формулу прямо сейчас, позволяя себе быть более наглым и уверенным в своих силах.

🎴 СОСТОЯНИЕ АВТОРА
В этом состоянии нет страха перед будущим, есть только энергия для действия, и Вы можете уверенно двигаться вперед, осознавая свой путь и принимая решения, необходимые для успеха."""
    
    user_input_text = "Ответы пользователя на 7 шагов Мета-Аудита:\n\n"
    for i, ans in enumerate(answers):
        if i < len(QUESTIONS):
            user_input_text += f"ШАГ {i+1}: {QUESTIONS[i]}\n"
        user_input_text += f"ОТВЕТ: {ans}\n\n"
    
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input_text}
                ],
                model="llama-3.3-70b",
                temperature=0.4,
                max_completion_tokens=2000
            )
            
            api_failures = 0
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    content = choice.message.content
                    content = postprocess_report(content, answers)
                    return content
                elif hasattr(choice, 'text'):
                    return choice.text
            
            if hasattr(response, 'text'):
                return response.text
            
            return """📊 РЕЗУЛЬТАТЫ АУДИТА
Индекс Автоматизма: 70%

🧲 ДОМИНАНТА
Ваш образ из шага 3.
Этот образ является силой собственного торможения.

🔑 ВАША МЕТАФОРМУЛА
ИСПОЛЬЗУЙТЕ СВОЙ РЕСУРС

⚡ ИНСТРУКЦИЯ ПО АКТИВАЦИИ
Примените формулу для движения вперед."""
            
        except Exception as e:
            api_failures += 1
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
            
            if attempt == 2:
                await send_admin_alert("api_critical", f"3 попытки провалились: {str(e)}")
                # Возвращаем минимальный отчет вместо ошибки
                return """📊 РЕЗУЛЬТАТЫ АУДИТА
Индекс Автоматизма: 75%

🧲 ДОМИНАНТА
Ваш внутренний образ ограничения.
Это сила собственного торможения.

🔑 ВАША МЕТАФОРМУЛА
ИСПОЛЬЗУЙТЕ СВОЮ СИЛУ

⚡ ИНСТРУКЦИЯ ПО АКТИВАЦИИ
Начните действовать прямо сейчас."""
            
            await asyncio.sleep(2 ** attempt)
    
    return """📊 РЕЗУЛЬТАТЫ АУДИТА
Произошла ошибка генерации отчета. Попробуйте позже."""

# --- ВЕБ-СЕРВЕР ---
async def handle_health(request):
    uptime = datetime.now() - start_time
    return web.Response(text=f"Bot OK | Uptime: {str(uptime).split('.')[0]} | Errors: {error_counter}")

async def send_startup_notification():
    try:
        bot_info = await bot.get_me()
        msg = (
            "🚀 *МЕТА-НАВИГАТОР ЗАПУЩЕН*\n\n"
            f"⏰ *Время:* {datetime.now().strftime('%d.%m %H:%M:%S')}\n"
            f"🤖 *Бот:* @{bot_info.username}\n"
            f"🔑 *Cerebras API:* {'✅' if CEREBRAS_API_KEY else '❌ НЕТ КЛЮЧА'}\n"
            f"📊 *Порт:* {os.environ.get('PORT', 8080)}\n"
            f"🌐 *Health check:* доступен"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Не удалось отправить startup notification: {e}")

async def main():
    if not TOKEN:
        logger.error("❌ ОШИБКА: BOT_TOKEN не установлен!")
        raise ValueError("BOT_TOKEN не установлен")
    
    if not CEREBRAS_API_KEY:
        logger.warning("⚠️ AI_API_KEY не установлен! Будет использоваться демо-режим.")
    
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
    logger.info(f"🤖 Bot: @{(await bot.get_me()).username}")
    logger.info(f"🔑 Cerebras API: {'✅' if CEREBRAS_API_KEY else '❌'}")
    logger.info(f"🌐 Health check: http://0.0.0.0:{port}/")
    
    try:
        await dp.start_polling(bot)
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
