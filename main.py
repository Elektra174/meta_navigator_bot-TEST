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

# Ресурсы проекта (GitHub Raw)
LOGO_START_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
LOGO_AUDIT_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png"
GUIDE_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/guide.pdf"
MASTERCLASS_URL = "https://youtube.com/playlist?list=PLyour_playlist_id"  # Замените на реальную ссылку

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

# --- ОБНОВЛЕННЫЙ СПИСОК ВОПРОСОВ ---
QUESTIONS = [
    "В какой ситуации в жизни Вы сейчас чувствуете самый сильный застой или «пробуксовку»? Опишите, что именно происходит.",
    "Опишите Ваш «фоновый шум». Какие мысли крутятся в голове сами по себе, когда Вы ничем не заняты? (Ваш умственный режим «заставки»).",
    "Если бы это препятствие было физическим объектом у Вас в теле — на что бы оно было похоже по форме, весу и где бы находилось? (Ваша Доминанта).",
    "Что именно в этой ситуации Вас выматывает больше всего? Опишите ту «стену», в которую Вы упираетесь.",
    "Какое качество в другом человеке Вас раздражает сильнее всего? Какую свободу он проявляет, которую Вы себе сейчас запрещаете?",
    "Как Вам кажется, сколько еще ресурсов Вы готовы потратить на поддержание Автопилота? (Например: топливо на нуле).",
    "Готовы ли Вы прямо сейчас попробовать перехватить управление у этого автоматизма и перейти в Состояние Автора?"
]

SYSTEM_PROMPT = """
Ты — «Мета-Навигатор», когнитивный инженер проекта «Метаформула жизни». 
Твоя роль: провести диагностику автоматизмов пользователя.

СТРУКТУРА ОТЧЕТА:
# Результаты Аудита Автопилота
## Ваш Индекс Автоматизма: [X]%

---
## 🧲 Ваша Доминанта
(Внутренний магнит, стягивающий энергию)
[Анализ образа из вопроса №3. Как этот предмет блокирует Ваш Источник].

---
## ⚙️ Функция / Дефолт-система
(Режим «заставки» мозга, холостое пережевывание мыслей)
[Анализ фонового шума из вопроса №2. Объясни, что мозг сжигает 80% энергии на этот шум].

---
## 🔑 Ваша Метаформула
### [Код-прерыватель шаблона до 5 слов]

---
## ⚡ Инструкция по применению
[Как использовать эту формулу для входа в Точку Сдвига. Практические шаги].

---
## 🎴 Состояние Автора
(Позиция силы, жизнь из Центра)
[Техническое описание режима без трения, который откроется после активации. Без обещаний «счастья»].

ПРАВИЛА:
1. Обращение строго на «Вы».
2. Тон: инженерный, диагностический, без эзотерики.
3. Формат: только Markdown заголовки (#, ##).
4. Метаформула: строго до 5 слов, краткий код.
"""

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

async def send_report_to_admin(user: types.User, answers: list, report: str):
    """Отправка отчета администратору"""
    try:
        msg = f"🔔 *НОВЫЙ АУДИТ ЗАВЕРШЕН*\n\n"
        msg += f"👤 *Юзер:* {user.full_name} (@{user.username})\n"
        msg += f"🆔 *ID:* `{user.id}`\n\n"
        msg += "*ОРИГИНАЛЬНЫЕ ОТВЕТЫ:*\n"
        for i, ans in enumerate(answers, 1):
            msg += f"{i}. {ans}\n"
        msg += f"\n\n*AI ОТЧЕТ:*\n{report}"
        
        if len(msg) > 4000:
            for x in range(0, len(msg), 4000):
                await bot.send_message(chat_id=ADMIN_ID, text=msg[x:x+4000], parse_mode="Markdown")
        else:
            await bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Не удалось отправить полный отчет: {e}")

# --- ОСНОВНЫЕ ФУНКЦИИ ---

async def is_subscribed(user_id: int) -> bool:
    """Проверка подписки на канал"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Команда /start - первое касание"""
    await state.clear()
    try:
        if not await is_subscribed(message.from_user.id):
            # Пользователь не подписан
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="Присоединиться к проекту", 
                    url="https://t.me/metaformula_life"
                )
            )
            builder.row(
                types.InlineKeyboardButton(
                    text="Я в канале! Начать Аудит", 
                    callback_data="check_sub"
                )
            )
            
            await message.answer_photo(
                photo=LOGO_START_URL,
                caption=(
                    "Добро пожаловать в «Метаформулу Жизни».\n\n"
                    "Меня зовут Александр Лазаренко. Я помогу Вам увидеть программы Вашего Автопилота и проложить маршрут к себе настоящему.\n\n"
                    "Чтобы начать, пожалуйста, подпишитесь на наш канал:"
                ),
                reply_markup=builder.as_markup()
            )
        else:
            # Пользователь уже подписан - сразу начинаем аудит
            await start_audit_flow(message, state)
            
    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await send_admin_alert("start_error", str(e), traceback.format_exc())
        await message.answer("⚠️ Произошла техническая ошибка. Попробуйте позже.")

@dp.callback_query(F.data == "check_sub")
async def handle_sub_check(callback: types.CallbackQuery, state: FSMContext):
    """Проверка подписки после нажатия кнопки"""
    await callback.answer()  # Убираем "часики"
    
    if await is_subscribed(callback.from_user.id):
        await start_audit_flow(callback.message, state)
    else:
        # Сообщение, что пользователь не подписан
        await callback.answer("❌ Вы еще не подписаны на канал! Пожалуйста, подпишитесь сначала.", show_alert=True)

async def start_audit_flow(message: types.Message, state: FSMContext):
    """Начало аудита - второе касание"""
    try:
        # Инициализируем состояние с пустым списком ответов
        await state.update_data(current_q=0, answers=[])
        
        # Второе касание: показываем logo.png
        await message.answer_photo(
            photo=LOGO_AUDIT_URL,
            caption=(
                "Ваш Авторский Маршрут начинается сейчас.\n\n"
                "Я задам 7 вопросов, чтобы помочь Вам увидеть программы Автопилота со стороны.\n\n"
                "Отвечайте искренне, доверяя первому отклику."
            )
        )
        
        await asyncio.sleep(1)
        
        # Отправляем первый вопрос
        await message.answer(f"📝 *Вопрос 1 из {len(QUESTIONS)}:*\n\n{QUESTIONS[0]}", parse_mode="Markdown")
        await state.set_state(AuditState.answering_questions)
        
    except Exception as e:
        logger.error(f"Ошибка запуска аудита: {e}")
        await send_admin_alert("audit_start_error", str(e), traceback.format_exc())
        await message.answer("⚠️ Ошибка запуска аудита. Попробуйте снова.")

@dp.message(AuditState.answering_questions)
async def process_audit(message: types.Message, state: FSMContext):
    """Обработка ответов на вопросы аудита"""
    global error_counter
    
    try:
        if not message.text or not message.text.strip():
            return await message.answer("Пожалуйста, напишите текстовый ответ.")
            
        data = await state.get_data()
        q_idx = data.get('current_q', 0)
        answers = data.get('answers', [])
        
        # Сохраняем чистый текст ответа
        answers.append(message.text.strip())
        new_idx = q_idx + 1
        
        if new_idx < len(QUESTIONS):
            # Обновляем состояние и задаем следующий вопрос
            await state.update_data(current_q=new_idx, answers=answers)
            await message.answer(
                f"📝 *Вопрос {new_idx + 1} из {len(QUESTIONS)}:*\n\n{QUESTIONS[new_idx]}",
                parse_mode="Markdown"
            )
        else:
            # Все вопросы отвечены
            await state.update_data(answers=answers)
            await message.answer(
                "🌀 *Анализирую Ваши ответы...*\n\n"
                "Навигатор вычисляет Ваш Индекс Автоматизма и ищет Метаформулу.",
                parse_mode="Markdown"
            )
            
            # Генерируем AI-отчет
            report = await generate_report_with_retry(answers)
            
            if report:
                # Отправляем отчет пользователю
                await message.answer(report, parse_mode="Markdown")
                
                # Отправляем отчет администратору
                await send_report_to_admin(message.from_user, answers, report)
                
                # Создаем Inline-кнопки для финального сообщения
                builder = InlineKeyboardBuilder()
                builder.row(
                    types.InlineKeyboardButton(
                        text="📥 Скачать Гайд «Ревизия Маршрута»",
                        callback_data="get_guide"
                    ),
                    types.InlineKeyboardButton(
                        text="🎥 Смотреть Мастер-класс «Сдвиг Оптики»",
                        callback_data="get_masterclass"
                    )
                )
                
                # Финальное сообщение с Inline-кнопками (сохранил ваш вариант)
                await message.answer(
                    "✅ *Аудит завершен!*\n\n"
                    "Вы получили свою Метаформулу — код для перехода в Состояние Автора.\n\n"
                    "Что дальше?",
                    reply_markup=builder.as_markup(),
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    "⚠️ *Не удалось сгенерировать отчет*\n\n"
                    "Попробуйте начать аудит заново с команды /start",
                    parse_mode="Markdown"
                )
            
            await state.clear()
            
    except Exception as e:
        error_counter += 1
        logger.error(f"Ошибка обработки ответа: {e}")
        await send_admin_alert("process_error", str(e), traceback.format_exc())
        await message.answer("⚠️ Технический сбой. Пожалуйста, перезапустите бота командой /start")

# --- ОБРАБОТЧИКИ INLINE-КНОПОК ---

@dp.callback_query(F.data == "get_guide")
async def send_guide_handler(callback: types.CallbackQuery):
    """Отправка PDF-гайда"""
    await callback.answer()  # Убираем "часики"
    
    try:
        await callback.message.answer_document(
            document=GUIDE_URL,
            caption=(
                "📚 *Гайд «Ревизия Маршрута»*\n\n"
                "Пошаговая инструкция по активации Вашей Метаформулы.\n"
                "Содержит практики для перехода в Состояние Автора.\n\n"
                "Сохраните его для работы!"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки гайда: {e}")
        await callback.message.answer(
            f"⚠️ *Не удалось отправить файл*\n\n"
            f"Скачайте гайд по ссылке:\n{GUIDE_URL}",
            parse_mode="Markdown"
        )

@dp.callback_query(F.data == "get_masterclass")
async def send_masterclass_handler(callback: types.CallbackQuery):
    """Отправка ссылки на мастер-класс"""
    await callback.answer()  # Убираем "часики"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="▶️ Смотреть на YouTube", 
            url=MASTERCLASS_URL
        )
    )
    
    await callback.message.answer(
        "🎬 *Мастер-класс «Сдвиг Оптики»*\n\n"
        "Практический видео-курс по переходу в Состояние Автора.\n\n"
        "Нажмите кнопку ниже для просмотра:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

# --- AI REPORT GENERATION ---

async def generate_report_with_retry(answers: list):
    """Генерация отчета с повторными попытками при ошибках"""
    global api_failures
    
    if not client:
        return "❌ *Сервис AI временно недоступен*\n\nПопробуйте позже или обратитесь в поддержку."
    
    # Формируем контекст для AI
    user_input = "Ответы пользователя на вопросы аудита:\n\n"
    for i, answer in enumerate(answers):
        if i < len(QUESTIONS):
            user_input += f"ВОПРОС {i+1}: {QUESTIONS[i]}\n"
        user_input += f"ОТВЕТ: {answer}\n\n{'='*50}\n\n"
    
    # Пытаемся 3 раза с экспоненциальной задержкой
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_input}
                ],
                model="llama-3.3-70b",
                temperature=0.4,
                max_completion_tokens=2500
            )
            
            # Успех - сбрасываем счетчик ошибок
            api_failures = 0
            
            # Обработка ответа
            if hasattr(response, 'choices') and len(response.choices) > 0:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                    return choice.message.content
                elif hasattr(choice, 'text'):
                    return choice.text
            
            # Альтернативные варианты структуры
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
