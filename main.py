import os
import asyncio
import traceback
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from cerebras.cloud.sdk import AsyncCerebras
from aiohttp import web

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("BOT_TOKEN")
CEREBRAS_API_KEY = os.getenv("AI_API_KEY")
CHANNEL_ID = "@metaformula_life"
ADMIN_ID = 7830322013

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ссылки на ресурсы (исправлена ошибка в URL)
LOGO_START_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
LOGO_AUDIT_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png.png"  
GUIDE_URL = "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/guide.pdf"

# Проверка переменных окружения
if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен")
if not CEREBRAS_API_KEY:
    raise ValueError("AI_API_KEY не установлен")

# Инициализация клиентов
client = AsyncCerebras(api_key=CEREBRAS_API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()

class AuditState(StatesGroup):
    answering_questions = State()

QUESTIONS = [
    "1. В каком моменте жизни Вы сейчас чувствуете самый сильный застой или «пробуксовку»?",
    "2. Опишите Ваш «фоновый шум». Какие мысли крутятся в голове сами по себе, когда Вы ничем не заняты?",
    "3. Назовите Вашу Доминанту: если бы Ваш «затык» был физическим предметом в теле — на что бы он был похож?",
    "4. Что Вас больше всего истощает в текущем режиме «Функции» (беге по кругу)?",
    "5. Какое качество в других людях Вас бесит? Какую силу они проявляют, которую Вы себе сейчас запрещаете?",
    "6. Сколько энергии у Вас осталось на поддержание Автопилота? (Например: топливо на нуле).",
    "7. Готовы ли Вы прямо сейчас найти свою Точку Сдвига и перейти в Свободный ход?"
]

SYSTEM_PROMPT = """
Ты — «Мета-Навигатор», когнитивный инженер Александра Лазаренко. 
Твоя задача: провести аудит Автопилота пользователя. Александр — не учитель, он практик.
ТЕРМИНОЛОГИЯ: Источник, Состояние Автора, Функция, Доминанта, Автопилот, Точка Сдвига, Свободный ход.
ОТЧЕТ: 
# Результаты Аудита Автопилота
## Ваш Индекс Автоматизма: [X]%
## 🕳️ Ваша Доминанта: [Анализ предмета в теле]
## ⚙️ Режим Функции (Автопилот): [Анализ фонового шума]
## 🎴 Точка Сдвига: [Ресурс из 'бесячего качества']
## 🔑 Ваша Метаформула: [Код-прерыватель]
## ⚡ Активация Свободного Хода: [Инструкция]
"""

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки: {e}")
        return False

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if not await is_subscribed(message.from_user.id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(
            text="Присоединиться к проекту", 
            url="https://t.me/metaformula_life"
        ))
        builder.row(types.InlineKeyboardButton(
            text="Я в канале! Начать Аудит", 
            callback_data="check_sub"
        ))
        await message.answer_photo(
            photo=LOGO_START_URL, 
            caption="Привет. Я — Мета-Навигатор. Помогу тебе увидеть программы Автопилота и активировать Метаформулу.", 
            reply_markup=builder.as_markup()
        )
    else: 
        await start_audit(message, state)

@dp.callback_query(F.data == "check_sub")
async def check_btn(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()  # Закрываем callback
    if await is_subscribed(callback.from_user.id):
        await start_audit(callback.message, state)
    else: 
        await callback.answer("Подписка не найдена!", show_alert=True)

async def start_audit(message: types.Message, state: FSMContext):
    await state.update_data(current_q=0, answers=[])
    try:
        await message.answer_photo(
            photo=LOGO_AUDIT_URL, 
            caption="Начинаем Ревизию. Отвечай искренне."
        )
    except Exception as e:
        logger.error(f"Ошибка отправки фото: {e}")
        await message.answer("Начинаем Ревизию. Отвечай искренне.")
    
    await asyncio.sleep(1)
    await message.answer(QUESTIONS[0])  # Отправляем только первый вопрос
    await state.set_state(AuditState.answering_questions)

@dp.message(AuditState.answering_questions)
async def handle_questions(message: types.Message, state: FSMContext):
    data = await state.get_data()
    q_idx = data.get('current_q', 0)
    answers = data.get('answers', [])
    
    answers.append(message.text.strip())  # Сохраняем только текст ответа
    new_idx = q_idx + 1
    
    if new_idx < len(QUESTIONS):
        await state.update_data(current_q=new_idx, answers=answers)
        await message.answer(QUESTIONS[new_idx])
    else:
        await state.update_data(answers=answers)
        await message.answer("Система вычисляет Ваш Индекс Автоматизма... 🌀")
        
        # Получаем финальные данные
        final_data = await state.get_data()
        final_answers = final_data.get('answers', [])
        
        report = await generate_ai_report(final_answers)
        if report:
            await message.answer(report, parse_mode="Markdown")
        else:
            await message.answer("Не удалось сгенерировать отчет. Попробуйте позже.")
        
        try: 
            await message.answer_document(
                document=GUIDE_URL, 
                caption="Ваша Ревизия завершена. Изучите протокол активации в гайде."
            )
        except Exception as e: 
            logger.error(f"Ошибка отправки документа: {e}")
            await message.answer("Ваш отчет готов. Гайд в закрепе канала!")
        
        await state.clear()

async def generate_ai_report(answers):
    # Формируем полный запрос с вопросами и ответами
    user_input = "Ответы пользователя на вопросы аудита:\n\n"
    for i, answer in enumerate(answers):
        if i < len(QUESTIONS):
            user_input += f"Вопрос {i+1}: {QUESTIONS[i]}\n"
        user_input += f"Ответ: {answer}\n\n{'─' * 40}\n\n"
    
    try:
        response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            model="llama-3.3-70b", 
            temperature=0.4
        )
        
        # Обработка ответа Cerebras (структура может отличаться)
        if hasattr(response, 'choices') and len(response.choices) > 0:
            choice = response.choices[0]
            if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
                return choice.message.content
            elif hasattr(choice, 'text'):
                return choice.text
        
        # Альтернативные варианты структуры
        if hasattr(response, 'text'):
            return response.text
        
        logger.error(f"Неизвестная структура ответа Cerebras: {response}")
        return "Не удалось обработать ответ системы."
        
    except Exception as e:
        logger.error(f"Ошибка генерации отчета: {traceback.format_exc()}")
        return "⚠️ Навигатор временно перегружен. Попробуйте позже."

async def handle_health(request): 
    return web.Response(text="active")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Сервер запущен на порту {port}")
    logger.info("Бот запускается...")
    
    await dp.start_polling(bot)

if __name__ == "__main__": 
    asyncio.run(main())
