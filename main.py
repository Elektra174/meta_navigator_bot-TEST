import os
import asyncio
import traceback
import logging
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
ADMIN_ID = 7830322013  # ID Александра для отчетов

# Ресурсы проекта
LOGO_START_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png.png"
LOGO_AUDIT_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
GUIDE_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/guide.pdf"
MASTERCLASS_URL = "https://youtube.com/playlist?list=PLyour_playlist_id"  # Замените на реальную ссылку
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

# --- ОБНОВЛЕННЫЙ СПИСОК ВОПРОСОВ (MPT v2.0) ---
QUESTIONS = [
    # Шаг 1: Внешний застой
    "В какой ситуации в жизни Вы сейчас чувствуете самый сильный застой или «пробуксовку»? Опишите кратко, что происходит.",
    
    # Шаг 2: Фоновый шум (DMN)
    "Опишите ваш «фоновый шум». Когда вы ничем не заняты, какие мысли возникают сами по себе?",
    
    # Шаг 3: Телесная доминанта (исправленная логика)
    "Если бы это состояние застоя можно было представить в виде образа... на что бы это было похоже? Опишите подробнее (форма, размер, цвет, температура..)",
    
    # Шаг 4: Механизм самоограничения
    "Как этот образ Вас ограничивает? Что именно он делает, когда Вы пытаетесь двигаться вперед?",
    
    # Шаг 5: Тень (украденная сила) - явно ищем качество
    "Какое качество или поведение в других людях вызывает у вас самое сильное раздражение? Что они себе позволяют, что вы себе запрещаете?",
    
    # Шаг 6: Цена (энтропия)
    "Какую цену вы платите за поддержание текущего состояния? Что истощается (время, внимание, силы)?",
    
    # Шаг 7: Точка выбора
    "Готовы ли вы прямо сейчас перехватить управление у автоматической программы и перейти в состояние осознанного автора?"
]

# --- РАЗНЫЕ ПРИВЕТСТВИЯ ---
WELCOME_MESSAGES = {
    "not_subscribed": {
        "title": "Добро пожаловать в «Метаформулу Жизни»",
        "text": "Меня зовут Александр Лазаренко.\n\n"
                "Я — автор проекта. Я создал Мета-навигатор, чтобы помочь Вам увидеть программы Вашего Автопилота и проложить маршрут к себе настоящему.\n\n"
                "Чтобы начать, пожалуйста, подпишитесь на наш канал:"
    },
    "subscribed": {
        "title": "👋 Добро пожаловать в Мета-Навигатор!",
        "text": "Я Ваш проводник в мета-исследовании себя.\n\n"
                "Помогу обнаружить скрытые программы «Автопилота», которые блокируют вашу энергию.\n\n"
                "Мы пройдем 7 шагов, чтобы найти вашу личную **Метаформулу**.\n\n"
                "Готовы начать?"
    }
}

# --- УЛУЧШЕННЫЙ СИСТЕМНЫЙ ПРОМПТ ДЛЯ ИИ ---
SYSTEM_PROMPT = """
Ты — «Мета-Навигатор», эксперт по нейрофизиологии и методу МПТ (Мета-Персональная Терапия).
Твоя задача: проанализировать 7 ответов пользователя и создать «Код Сдвига» (Метаформулу).

ТВОЯ ЛОГИКА АНАЛИЗА:

1. **Индекс Автоматизма (0-100%):**
   - Оцени насколько человек застрял в DMN (Дефолт-системе мозга)
   - Учти: Уровень фонового шума (Шаг 2) + Яркость доминанты (Шаг 3) + Степень самоограничения (Шаг 4)

2. **Доминанта:**
   - Опиши образ из Ответа №3 не как проблему, а как сгусток сдержанной энергии самого человека (Ухтомский)
   - Объясни, что этот образ — это сила собственного торможения

3. **МЕТАФОРМУЛА (самое важное):**
   - Короткая императивная фраза (3-6 слов)
   - **АЛГОРИТМ СБОРКИ: Возьми качество, которое бесит (из Ответа №5) → Преврати его в Ресурс → Направь на решение Проблемы (из Ответа №1)**
   - Пример: Если Ответ №1 "Боюсь начать бизнес", а Ответ №5 "Бесит наглость" → Формула: "Используй наглость, чтобы начать"
   - Формула должна звучать как разрешение на активное действие

СТРУКТУРА ТВОЕГО ОТВЕТА (MarkDown):

# 📊 Результаты Аудита
## Индекс Автоматизма: [X]%

---
## 🧲 Ваша Доминанта
(Внутренний магнит застоя)
[Анализ образа из Ответа №3. Объясни, что это сила собственного торможения].

---
## ⚙️ Функция / Дефолт-система
[Краткий анализ Ответа №2 и №4. Как именно человек тратит нейронный ресурс на поддержание проблемы].

---
## 🔑 Ваша Метаформула
### [ЗДЕСЬ НАПИШИ ФРАЗУ-КОД КРУПНО]

---
## ⚡ Инструкция по активации
**Нейрофизиология формулы:** [Объясни: Тень из Ответа №5 содержит энергию, необходимую для Ответа №1].
**Действие:** [Призыв применить формулу прямо сейчас].

---
## 🎴 Состояние Автора
В этом состоянии нет страха перед будущим, есть только энергия для действия в настоящем моменте.

КРИТИЧЕСКИЕ ПРАВИЛА:
1. ТОН: научный, инженерный, без эзотерики
2. ТЕРМИНЫ: «нейронный ресурс», «доминанта», «субъектность», «дефолт-система»
3. ФОРМАТ: только Markdown заголовки (#, ##, ###)
4. МЕТАФОРМУЛА: должна явно связывать Шаг 5 и Шаг 1
"""

# --- ФУНКЦИЯ ПРОВЕРКИ ПОДПИСКИ ---

async def is_subscribed(user_id: int) -> bool:
    """Проверка подписки на канал"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки для пользователя {user_id}: {e}")
        return False

# --- СИСТЕМА МОНИТОРИНГА ---

async def send_admin_alert(alert_type: str, details: str, tb: str = ""):
    """Уведомление администратора о сбоях"""
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
    """Отправка логов админу"""
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

# --- ОБНОВЛЕННЫЕ ОБРАБОТЧИКИ С РАЗНЫМИ ПРИВЕТСТВИЯМИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start с проверкой подписки и разными приветствиями"""
    await state.clear()
    try:
        # Проверяем подписку
        is_sub = await is_subscribed(message.from_user.id)
        
        if not is_sub:
            # Пользователь не подписан - приветствие от Метаформулы Жизни
            welcome = WELCOME_MESSAGES["not_subscribed"]
            
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="Присоединиться к проекту", 
                    url=CHANNEL_URL
                )
            )
            builder.row(
                types.InlineKeyboardButton(
                    text="Я в канале! Начать Диагностику", 
                    callback_data="check_sub"
                )
            )
            
            caption = f"**{welcome['title']}**\n\n{welcome['text']}"
            
            await message.answer_photo(
                photo=LOGO_START_URL,
                caption=caption,
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        else:
            # Пользователь уже подписан - приветствие от Мета-Навигатора
            welcome = WELCOME_MESSAGES["subscribed"]
            
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="🚀 Начать Диагностику", 
                    callback_data="start_audit"
                )
            )
            
            caption = f"**{welcome['title']}**\n\n{welcome['text']}"
            
            await message.answer_photo(
                photo=LOGO_START_URL,
                caption=caption,
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await send_admin_alert("start_error", str(e), traceback.format_exc())
        await message.answer("⚠️ Произошла техническая ошибка. Попробуйте позже.")

@dp.callback_query(F.data == "check_sub")
async def handle_sub_check(callback: types.CallbackQuery, state: FSMContext):
    """Проверка подписки после нажатия кнопки"""
    await callback.answer()
    
    try:
        if await is_subscribed(callback.from_user.id):
            # Пользователь подписался - показываем приветствие от Мета-Навигатора
            welcome = WELCOME_MESSAGES["subscribed"]
            
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="🚀 Начать Диагностику", 
                    callback_data="start_audit"
                )
            )
            
            caption = f"**{welcome['title']}**\n\n{welcome['text']}"
            
            await callback.message.edit_caption(
                caption=caption,
                reply_markup=builder.as_markup()
            )
        else:
            # Пользователь все еще не подписан
            await callback.answer(
                "❌ Вы еще не подписаны на канал! Пожалуйста, подпишитесь сначала.", 
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        await callback.answer("Произошла ошибка при проверке подписки", show_alert=True)

@dp.callback_query(F.data == "start_audit")
async def start_audit_flow(callback: types.CallbackQuery, state: FSMContext):
    """Начало опроса (после подтверждения подписки)"""
    await callback.answer()
    
    try:
        # Дополнительная проверка подписки перед началом аудита
        if not await is_subscribed(callback.from_user.id):
            await callback.answer(
                "❌ Вы отписались от канала! Пожалуйста, подпишитесь снова.", 
                show_alert=True
            )
            return
        
        await state.update_data(current_step=0, answers=[])
        
        # Второе касание с лого
        await callback.message.answer_photo(
            photo=LOGO_AUDIT_URL,
            caption=(
                "🔬 **Мета-Персональная Терапия: Аудит Дефолт-Системы**\n\n"
                "Мы пройдем 7 шагов для диагностики автоматических программ вашего мозга (DMN).\n\n"
                "Отвечайте искренне — каждый ответ формирует нейронную карту вашего состояния."
            ),
            parse_mode="Markdown"
        )
        
        await asyncio.sleep(1)
        
        # Задаем 1-й вопрос
        await callback.message.answer(
            f"📝 *Шаг 1 из {len(QUESTIONS)}:*\n\n{QUESTIONS[0]}", 
            parse_mode="Markdown"
        )
        await state.set_state(AuditState.answering_questions)
        
    except Exception as e:
        logger.error(f"Ошибка запуска аудита: {e}")
        await send_admin_alert("audit_start_error", str(e), traceback.format_exc())
        await callback.message.answer("⚠️ Ошибка запуска аудита. Попробуйте снова.")

@dp.message(AuditState.answering_questions)
async def process_answer(message: types.Message, state: FSMContext):
    """Обработка ответов и переключение вопросов"""
    global error_counter
    
    try:
        if not message.text or not message.text.strip():
            return await message.answer("Пожалуйста, напишите текстовый ответ.")

        data = await state.get_data()
        step = data.get("current_step", 0)
        user_answers = data.get("answers", [])

        # Сохраняем ответ
        user_answers.append(message.text.strip())
        
        # Следующий шаг
        next_step = step + 1

        if next_step < len(QUESTIONS):
            # Если есть еще вопросы, задаем следующий
            await state.update_data(current_step=next_step, answers=user_answers)
            await message.answer(
                f"📝 *Шаг {next_step + 1} из {len(QUESTIONS)}:*\n\n{QUESTIONS[next_step]}",
                parse_mode="Markdown"
            )
        else:
            # Все вопросы отвечены
            await state.update_data(answers=user_answers)
            await message.answer(
                "🌀 **Синхронизирую данные...**\nАнализирую Ваши ответы и ищу точку Сдвига.",
                parse_mode="Markdown"
            )
            
            # 1. Генерация отчета через ИИ
            report = await generate_ai_report(user_answers)
            
            if report:
                # 2. Отправка отчета пользователю
                await message.answer(report, parse_mode="Markdown")
                
                # 3. Отправка ПРАКТИКИ (через 2 секунды)
                await asyncio.sleep(2)
                await send_practice(message, user_answers)
                
                # 4. Отправка копии админу
                await send_admin_copy(message.from_user, user_answers, report)
            else:
                await message.answer(
                    "⚠️ *Не удалось сгенерировать отчет*\n\n"
                    "Попробуйте начать аудит заново с команды /start",
                    parse_mode="Markdown"
                )
            
            # Сброс состояния
            await state.clear()
            
    except Exception as e:
        error_counter += 1
        logger.error(f"Ошибка обработки ответа: {e}")
        await send_admin_alert("process_error", str(e), traceback.format_exc())
        await message.answer("⚠️ Технический сбой. Пожалуйста, перезапустите бота командой /start")

# --- ПРАКТИКА "ВОЗВРАЩЕНИЕ СИЛЫ" ---

async def send_practice(message: types.Message, answers: list):
    """Отправка сообщения с практикой 'Возвращение силы'"""
    practice_text = (
        "⚡ **ПРАКТИКА: ВОЗВРАЩЕНИЕ СИЛЫ**\n\n"
        "Ваш мозг в Шаге 5 показал, где заблокирован Ваш ресурс. То, что Вас бесит в других — это Ваша «Украденная Сила».\n\n"
        "🔻 **Инструкция (делать прямо сейчас):**\n"
        "1. Вспомните того человека, который Вас бесит (из Шага 5).\n"
        "2. Встаньте. Расправьте плечи.\n"
        "3. **Наденьте его роль на себя.** На 1 минуту разрешите себе стать абсолютно таким же.\n"
        "4. Почувствуйте, как меняется Ваше тело. Где появляется энергия?\n"
        "5. Скажите вслух Вашу Метаформулу.\n\n"
        "Это топливо — Ваше. Заберите его себе."
    )
    
    # Кнопки под практикой
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="📥 Скачать Гайд по интеграции", 
            url=GUIDE_URL
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="🎬 Перейти к Мастер-классу", 
            url=MASTERCLASS_URL
        )
    )
    
    await message.answer(
        practice_text, 
        parse_mode="Markdown", 
        reply_markup=builder.as_markup()
    )

# --- AI REPORT GENERATION ---

async def generate_ai_report(answers: list):
    """Запрос к Cerebras для генерации отчета"""
    global api_failures
    
    if not client:
        return "⚠️ Ошибка: API ключ не настроен. Бот работает в демо-режиме."
    
    # Формируем текст для ИИ
    user_input_text = "Ответы пользователя на 7 шагов Мета-Аудита:\n\n"
    for i, ans in enumerate(answers):
        if i < len(QUESTIONS):
            user_input_text += f"ШАГ {i+1}: {QUESTIONS[i]}\n"
        user_input_text += f"ОТВЕТ: {ans}\n\n{'='*50}\n\n"
    
    # Пытаемся 3 раза с экспоненциальной задержкой
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input_text}
                ],
                model="llama-3.3-70b",
                temperature=0.4,
                max_completion_tokens=2500
            )
            
            api_failures = 0
            
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    return choice.message.content
                elif hasattr(choice, 'text'):
                    return choice.text
            
            if hasattr(response, 'text'):
                return response.text
            
            return "Не удалось обработать ответ AI."
            
        except Exception as e:
            api_failures += 1
            logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
            
            if attempt == 2:  # Последняя попытка
                await send_admin_alert("api_critical", f"3 попытки провалились: {str(e)}")
                return (
                    "⚠️ *Сервис AI временно перегружен*\n\n"
                    "Наш ИИ-навигатор сейчас недоступен.\n\n"
                    "Что делать:\n"
                    "1. Попробуйте через 15-20 минут\n"
                    "2. Начните новый аудит позже (/start)\n"
                    "3. Обратитесь в поддержку @metaformula_life"
                )
            
            # Ждем перед следующей попыткой
            await asyncio.sleep(2 ** attempt)
    
    return "❌ Не удалось получить отчет. Попробуйте позже."

# --- ВЕБ-СЕРВЕР И ЗАПУСК ---

async def handle_health(request):
    """Health check endpoint для Render"""
    uptime = datetime.now() - start_time
    return web.Response(text=f"Bot OK | Uptime: {str(uptime).split('.')[0]} | Errors: {error_counter}")

async def send_startup_notification():
    """Уведомление о запуске бота"""
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
    """Основная функция запуска"""
    
    # Проверяем обязательные переменные
    if not TOKEN:
        logger.error("❌ ОШИБКА: BOT_TOKEN не установлен!")
        raise ValueError("BOT_TOKEN не установлен")
    
    if not CEREBRAS_API_KEY:
        logger.warning("⚠️ ВНИМАНИЕ: AI_API_KEY не установлен! AI функции будут недоступны.")
    
    # Запускаем веб-сервер для health check
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    # Отправляем уведомление о запуске
    await send_startup_notification()
    
    logger.info(f"✅ Мета-Навигатор запущен")
    logger.info(f"🤖 Bot: @{(await bot.get_me()).username}")
    logger.info(f"🔑 Cerebras API: {'✅ Настроен' if CEREBRAS_API_KEY else '❌ Нет ключа'}")
    logger.info(f"🌐 Health check: http://0.0.0.0:{port}/")
    logger.info(f"📊 Порт: {port}")
    
    # Запускаем бота
    try:
        await dp.start_polling(bot)
    except Exception as e:
        # Критическая ошибка - бот упал
        logger.critical(f"Бот упал: {e}")
        await send_admin_alert("bot_crash", f"Бот полностью остановлен: {str(e)}", traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске: {e}")
        exit(1)
