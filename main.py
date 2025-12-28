import os
import asyncio
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from cerebras.cloud.sdk import AsyncCerebras
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
CEREBRAS_API_KEY = os.getenv("AI_API_KEY")
CHANNEL_ID = "@metaformula_life"
ADMIN_ID = 7830322013

# Прямые ссылки на ресурсы
LOGO_START_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
LOGO_AUDIT_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png"
GUIDE_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/guide.pdf"
MASTERCLASS_URL = "https://youtube.com/playlist?list=ваш_плейлист"  # Замените на реальную ссылку

# Инициализация клиентов
client = AsyncCerebras(api_key=CEREBRAS_API_KEY) if CEREBRAS_API_KEY else None
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Глобальные счетчики для мониторинга
error_counter = 0
api_failures = 0
last_error_time = None

class AuditState(StatesGroup):
    answering_questions = State()

# Вопросы для аудита (по глоссарию)
QUESTIONS = [
    "В каком моменте жизни Вы сейчас чувствуете самый сильный застой или «пробуксовку»?",
    "Опишите Ваш «фоновый шум». Какие мысли крутятся в голове сами по себе, когда Вы ничем не заняты?",
    "Назовите Вашу Доминанту: если бы Ваш «затык» был физическим предметом в теле — на что бы он был похож по форме и весу?",
    "Что Вас больше всего истощает в текущем режиме «Функции» (беге по кругу)?",
    "Какое качество в другом человеке Вас раздражает больше всего? Какую свободу он проявляет, которую Вы себе сейчас запрещаете?",
    "Как Вам кажется, сколько еще энергии у Вас осталось на поддержание Автопилота? (Напр: топливо на нуле).",
    "Готовы ли Вы прямо сейчас найти свою Точку Сдвига и перейти в Свободный ход?"
]

SYSTEM_PROMPT = """
Ты — Мета-Навигатор, когнитивный инженер проекта «Метаформула жизни». 
Твоя роль: проводник, который помогает пользователям провести аудит Автопилота.

ГЛОССАРИЙ (используй строго):
- Источник: внутренний потенциал и энергия пользователя
- Доминанта: очаг напряжения в мозге (затык), ворующий внимание
- Функция: социальный софт, роли и страхи, блокирующие Источник
- Точка Сдвига: мгновение тишины для перехвата управления (Ctrl+Alt+Del)
- Свободный ход: реализация без внутреннего трения (аналог У-вэй)
- Состояние Автора: жизнь из Центра Источника

СТИЛЬ:
- Обращение на «Вы»
- Экспертный, спокойный тон
- Без эзотерики и «воды»
- Конкретные инсайты
- Использование терминов из глоссария

СТРУКТУРА ОТЧЕТА:
# Результаты Аудита Автопилота
## Ваш Индекс Автоматизма: [X]%

---
## 🧲 Ваша Доминанта
[Анализ «затыка» как физического предмета в теле. Как он блокирует Ваш Источник?]

---
## ⚙️ Режим Функции  
[Анализ социального софта и ролей, которые создают трение. Что истощает?]

---
## 🔑 Ваша Метаформула
**[Код-фраза из 3-5 слов]**

---
## 🎯 Инструкция по активации
[Как найти Точку Сдвига и перейти в Свободный ход. Практические шаги.]

---
## 💫 Состояние Автора
[Как будет выглядеть Ваша жизнь при реализации из Источника?]
"""

async def send_admin_alert(alert_type: str, details: str, traceback_info: str = ""):
    """Отправка оповещения администратору"""
    global error_counter, api_failures
    
    try:
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        alert_messages = {
            "api_failure": "🚨 *СБОЙ API CEREBRAS*",
            "bot_crash": "💥 *КРИТИЧЕСКАЯ ОШИБКА БОТА*",
            "rate_limit": "⏱️ *ЛИМИТ API ИСЧЕРПАН*",
            "warning": "⚠️ *ПРЕДУПРЕЖДЕНИЕ*"
        }
        
        message = f"{alert_messages.get(alert_type, '⚠️ *ПРОБЛЕМА*')}\n\n"
        message += f"🕒 *Время:* {timestamp}\n"
        message += f"📊 *Тип:* {alert_type}\n\n"
        message += f"📝 *Детали:*\n{details[:500]}\n"
        
        if traceback_info:
            traceback_short = traceback_info[-1000:] if len(traceback_info) > 1000 else traceback_info
            message += f"\n🔧 *Traceback:*\n```\n{traceback_short}\n```"
        
        # Добавляем статистику
        message += f"\n📈 *Статистика:*\n• Ошибок: {error_counter}\n• Сбоев API: {api_failures}"
        
        await bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"Не удалось отправить алерт: {e}")
        return False

async def send_report_to_admin(user: types.User, answers: list, report: str):
    """Отправка полного отчета администратору"""
    try:
        user_info = (
            "📊 *НОВЫЙ АУДИТ ЗАВЕРШЕН*\n\n"
            f"👤 *Пользователь:*\n"
            f"• ID: `{user.id}`\n"
            f"• Имя: {user.first_name or '—'}\n"
            f"• Username: @{user.username or 'нет'}\n"
            f"• Время: {datetime.now().strftime('%d.%m %H:%M')}\n\n"
        )
        
        # Добавляем ответы
        user_info += "📝 *Ответы на вопросы:*\n"
        for i, answer in enumerate(answers):
            if i < len(QUESTIONS):
                user_info += f"\n{i+1}. *{QUESTIONS[i][:50]}...*\n"
            user_info += f"   {answer[:200]}\n"
        
        # Отправляем ответы
        await bot.send_message(chat_id=ADMIN_ID, text=user_info[:4000], parse_mode="Markdown")
        
        # Отправляем отчет AI отдельно
        report_msg = f"🤖 *ОТЧЕТ AI:*\n\n{report[:3500]}"
        await bot.send_message(chat_id=ADMIN_ID, text=report_msg, parse_mode="Markdown")
        
        return True
    except Exception as e:
        await send_admin_alert("warning", f"Ошибка отправки отчета. User ID: {user.id}", str(e))
        return False

async def is_subscribed(user_id: int) -> bool:
    """Проверка подписки на канал"""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        await send_admin_alert("warning", f"Ошибка проверки подписки. User ID: {user_id}", str(e))
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    global error_counter
    
    try:
        await state.clear()
        
        if not await is_subscribed(message.from_user.id):
            # Пользователь не подписан - показываем кнопки
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="📢 Присоединиться к каналу", 
                    url="https://t.me/metaformula_life"
                )
            )
            builder.row(
                types.InlineKeyboardButton(
                    text="✅ Я в канале! Начать Аудит", 
                    callback_data="check_sub"
                )
            )
            
            await message.answer_photo(
                photo=LOGO_START_URL,
                caption=(
                    "👋 *Добро пожаловать в Мета-Навигатор*\n\n"
                    "Я — ИИ-проводник проекта «Метаформула жизни».\n\n"
                    "Помогу Вам провести аудит Автопилота, найти Доминанту "
                    "и активировать Вашу персональную Метаформулу.\n\n"
                    "📌 *Для начала работы необходимо подписаться на канал:*"
                ),
                reply_markup=builder.as_markup(),
                parse_mode="Markdown"
            )
        else:
            # Пользователь подписан - сразу начинаем аудит
            await start_audit(message, state)
            
    except Exception as e:
        error_counter += 1
        await send_admin_alert(
            "bot_crash",
            f"Ошибка в /start. User: {message.from_user.id}",
            traceback.format_exc()
        )
        await message.answer("⚠️ Произошла техническая ошибка. Попробуйте позже.")

@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    """Проверка подписки после нажатия кнопки"""
    await callback.answer()  # Убираем "часики"
    
    if await is_subscribed(callback.from_user.id):
        await callback.message.answer("✅ Доступ подтвержден. Запускаю аудит...")
        await start_audit(callback.message, state)
    else:
        await callback.answer("❌ Вы еще не подписаны на канал!", show_alert=True)

async def start_audit(message: types.Message, state: FSMContext):
    """Начало процедуры аудита"""
    try:
        # Инициализируем состояние: current_q=0, answers=[]
        await state.update_data(current_q=0, answers=[])
        
        # Отправляем логотип аудита
        try:
            await message.answer_photo(
                photo=LOGO_AUDIT_URL,
                caption=(
                    "🌀 *НАЧИНАЕМ АУДИТ АВТОПИЛОТА*\n\n"
                    "Сейчас я задам Вам 7 вопросов.\n"
                    "Отвечайте искренне — это Ваш диалог с собой.\n\n"
                    "Каждый ответ приближает к Вашей Метаформуле."
                ),
                parse_mode="Markdown"
            )
        except:
            await message.answer("🌀 *НАЧИНАЕМ АУДИТ АВТОПИЛОТА*...", parse_mode="Markdown")
        
        await asyncio.sleep(1)
        
        # Отправляем первый вопрос
        await message.answer(f"📝 *Вопрос 1 из 7:*\n\n{QUESTIONS[0]}", parse_mode="Markdown")
        await state.set_state(AuditState.answering_questions)
        
    except Exception as e:
        global error_counter
        error_counter += 1
        await send_admin_alert(
            "bot_crash", 
            f"Ошибка запуска аудита. User: {message.from_user.id}", 
            traceback.format_exc()
        )
        await message.answer("⚠️ Ошибка запуска аудита. Попробуйте снова.")

@dp.message(AuditState.answering_questions)
async def process_answer(message: types.Message, state: FSMContext):
    """Обработка ответов на вопросы"""
    global error_counter
    
    try:
        data = await state.get_data()
        current_q = data.get('current_q', 0)
        answers = data.get('answers', [])
        
        # Сохраняем ответ пользователя
        answers.append(message.text.strip())
        
        # Переходим к следующему вопросу
        next_q = current_q + 1
        
        if next_q < len(QUESTIONS):
            # Обновляем состояние и задаем следующий вопрос
            await state.update_data(current_q=next_q, answers=answers)
            
            # Отправляем следующий вопрос
            question_text = f"📝 *Вопрос {next_q + 1} из {len(QUESTIONS)}:*\n\n{QUESTIONS[next_q]}"
            await message.answer(question_text, parse_mode="Markdown")
            
        else:
            # Все вопросы отвечены - генерируем отчет
            await state.update_data(answers=answers)
            
            # Уведомляем пользователя
            await message.answer(
                "🌀 *Анализирую Ваши ответы...*\n\n"
                "Навигатор вычисляет Ваш Индекс Автоматизма и ищет Метаформулу.",
                parse_mode="Markdown"
            )
            
            # Генерируем AI-отчет
            report = await generate_ai_report(answers)
            
            if report:
                # Отправляем отчет пользователю
                await message.answer(report, parse_mode="Markdown")
                
                # Отправляем отчет администратору
                await send_report_to_admin(message.from_user, answers, report)
                
                # Создаем клавиатуру с финальными опциями
                builder = ReplyKeyboardBuilder()
                builder.row(
                    types.KeyboardButton(text="📥 Скачать Гайд «Ревизия Маршрута»"),
                    types.KeyboardButton(text="🎥 Смотреть Мастер-класс «Сдвиг Оптики»")
                )
                builder.row(types.KeyboardButton(text="🔄 Начать новый аудит"))
                
                # Отправляем финальное сообщение
                await message.answer(
                    "✅ *Аудит завершен*\n\n"
                    "Ваша Метаформула активирована. Что дальше?\n\n"
                    "Выберите действие:",
                    reply_markup=builder.as_markup(resize_keyboard=True),
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    "⚠️ *Ошибка генерации отчета*\n\n"
                    "Попробуйте начать аудит заново с команды /start",
                    parse_mode="Markdown"
                )
            
            # Очищаем состояние FSM
            await state.clear()
            
    except Exception as e:
        error_counter += 1
        await send_admin_alert(
            "bot_crash",
            f"Ошибка обработки ответа. User: {message.from_user.id}",
            traceback.format_exc()
        )
        await message.answer("⚠️ Ошибка обработки ответа. Попробуйте снова с /start")

@dp.message(F.text == "📥 Скачать Гайд «Ревизия Маршрута»")
async def send_guide(message: types.Message):
    """Отправка PDF-гайда"""
    try:
        await message.answer_document(
            document=GUIDE_URL,
            caption=(
                "📚 *Гайд «Ревизия Маршрута»*\n\n"
                "Пошаговая инструкция по активации Вашей Метаформулы.\n"
                "Содержит практики для перехода в Свободный ход."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer(
            "⚠️ *Гайд временно недоступен*\n\n"
            f"Ссылка для скачивания: {GUIDE_URL}",
            parse_mode="Markdown"
        )

@dp.message(F.text == "🎥 Смотреть Мастер-класс «Сдвиг Оптики»")
async def send_masterclass(message: types.Message):
    """Отправка ссылки на мастер-класс"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="▶️ Смотреть на YouTube", 
            url=MASTERCLASS_URL
        )
    )
    
    await message.answer(
        "🎬 *Мастер-класс «Сдвиг Оптики»*\n\n"
        "Видео-практикум по переходу из режима Функции в Состояние Автора.\n\n"
        "Нажмите кнопку ниже для просмотра:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "🔄 Начать новый аудит")
async def restart_audit(message: types.Message, state: FSMContext):
    """Перезапуск аудита"""
    await cmd_start(message, state)

async def generate_ai_report(answers: list) -> str:
    """Генерация AI-отчета через Cerebras API"""
    global error_counter, api_failures, last_error_time
    
    if not client:
        return "❌ *Сервис AI недоступен*\n\nПопробуйте позже или обратитесь к администратору."
    
    try:
        # Формируем контекст для AI
        user_input = "Ответы пользователя на вопросы аудита:\n\n"
        for i, answer in enumerate(answers):
            if i < len(QUESTIONS):
                user_input += f"ВОПРОС {i+1}: {QUESTIONS[i]}\n"
            user_input += f"ОТВЕТ: {answer}\n\n{'='*50}\n\n"
        
        # Отправляем запрос к Cerebras API
        response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            model="llama-3.3-70b",
            temperature=0.4,
            top_p=0.9,
            max_tokens=2048
        )
        
        # Сбрасываем счетчик ошибок API при успехе
        api_failures = 0
        
        # Извлекаем ответ (структура может различаться)
        if hasattr(response, 'choices') and len(response.choices) > 0:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                return choice.message.content
            elif hasattr(choice, 'text'):
                return choice.text
        
        return "Не удалось обработать ответ AI."
        
    except Exception as e:
        error_counter += 1
        api_failures += 1
        last_error_time = datetime.now()
        
        error_msg = str(e).lower()
        
        # Определяем тип ошибки для алерта
        if "rate" in error_msg or "quota" in error_msg or "limit" in error_msg:
            alert_type = "rate_limit"
            details = "Исчерпан лимит запросов к Cerebras API"
        elif "connection" in error_msg or "timeout" in error_msg:
            alert_type = "api_failure"
            details = "Проблема соединения с Cerebras API"
        elif "auth" in error_msg or "key" in error_msg:
            alert_type = "api_failure"
            details = "Ошибка аутентификации API ключа"
        else:
            alert_type = "api_failure"
            details = f"Ошибка API: {error_msg[:200]}"
        
        # Отправляем алерт администратору
        await send_admin_alert(alert_type, details, traceback.format_exc())
        
        # Возвращаем сообщение пользователю
        return (
            "⚠️ *Сервис AI временно недоступен*\n\n"
            "Наш ИИ-навигатор перегружен.\n\n"
            "Что можно сделать:\n"
            "1. Попробуйте через 10-15 минут\n"
            "2. Начните новый аудит с /start\n"
            "3. Обратитесь в поддержку @metaformula_life"
        )

async def handle_health(request):
    """Health check endpoint для Render"""
    return web.Response(text="OK")

async def send_startup_notification():
    """Уведомление о запуске бота"""
    try:
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        bot_info = await bot.get_me()
        
        message = (
            "🚀 *МЕТА-НАВИГАТОР ЗАПУЩЕН*\n\n"
            f"🕒 *Время:* {timestamp}\n"
            f"🤖 *Бот:* @{bot_info.username}\n"
            f"🔑 *Cerebras API:* {'✅' if CEREBRAS_API_KEY else '❌'}\n"
            f"📊 *Порт:* {os.environ.get('PORT', 8080)}\n"
            f"🌐 *Health Check:* доступен"
        )
        
        await bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode="Markdown")
    except Exception as e:
        print(f"Не удалось отправить startup notification: {e}")

async def main():
    """Основная функция запуска бота"""
    
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
    
    print(f"✅ Мета-Навигатор запущен")
    print(f"🤖 Bot: @{(await bot.get_me()).username}")
    print(f"🔑 Cerebras API: {'✅ Настроен' if CEREBRAS_API_KEY else '❌ Нет ключа'}")
    print(f"🌐 Health check: http://0.0.0.0:{port}/")
    
    # Запускаем бота
    try:
        await dp.start_polling(bot)
    except Exception as e:
        # Критическая ошибка - бот упал
        await send_admin_alert(
            "bot_crash",
            "Бот полностью остановлен!",
            traceback.format_exc()
        )
        raise

if __name__ == "__main__":
    # Проверяем обязательные переменные
    if not TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        exit(1)
    
    if not CEREBRAS_API_KEY:
        print("⚠️ Внимание: AI_API_KEY не установлен! AI функции будут недоступны.")
    
    asyncio.run(main())
