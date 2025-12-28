import os
import asyncio
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from cerebras.cloud.sdk import AsyncCerebras
from aiohttp import web


# =========================
# CONFIG
# =========================
TOKEN = os.getenv("BOT_TOKEN", "").strip()
CEREBRAS_API_KEY = os.getenv("AI_API_KEY", "").strip()

CHANNEL_ID = os.getenv("CHANNEL_ID", "@metaformula_life").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "7830322013").strip())

PORT = int(os.getenv("PORT", "8080"))

# Assets
LOGO_START_URL = os.getenv(
    "LOGO_START_URL",
    "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo11.png"
).strip()

LOGO_AUDIT_URL = os.getenv(
    "LOGO_AUDIT_URL",
    "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/logo.png.png"
).strip()

GUIDE_URL = os.getenv(
    "GUIDE_URL",
    "https://raw.githubusercontent.com/Elektra174/meta_navigator_bot/main/guide.pdf"
).strip()

MASTERCLASS_URL = os.getenv("MASTERCLASS_URL", "https://www.youtube.com/").strip()


# =========================
# VALIDATION (fail-fast)
# =========================
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")
if not CEREBRAS_API_KEY:
    raise RuntimeError("AI_API_KEY is missing")


# =========================
# AI / BOT INIT
# =========================
client = AsyncCerebras(api_key=CEREBRAS_API_KEY)
bot = Bot(token=TOKEN)
dp = Dispatcher()


# =========================
# MONITORING STATE
# =========================
error_counter = 0
api_failures = 0
last_error_time: Optional[datetime] = None


# =========================
# GLOSSARY (STRICT TERMS)
# =========================
# Источник — внутренний потенциал и энергия.
# Доминанта — очаг напряжения в мозге (затык), ворующий внимание.
# Функция — социальный софт, роли и страхи, блокирующие Источник.
# Точка Сдвига — мгновение тишины для перехвата управления (Ctrl+Alt+Del).
# Свободный ход — реализация без внутреннего трения (аналог У-вэй).
# Состояние Автора — жизнь из Центра Источника.


# =========================
# QUESTIONS (ASK ONE BY ONE, STRICT TEXT)
# =========================
QUESTIONS: List[str] = [
    "В каком моменте жизни Вы сейчас чувствуете самый сильный застой или «пробуксовку»?",
    "Опишите Ваш «фоновый шум». Какие мысли крутятся в голове сами по себе, когда Вы ничем не заняты?",
    "Назовите Вашу Доминанту: если бы Ваш «затык» был физическим предметом в теле — на что бы он был похож по форме и весу?",
    "Что Вас больше всего истощает в текущем режиме «Функции» (беге по кругу)?",
    "Какое качество в другом человеке Вас раздражает больше всего? Какую свободу он проявляет, которую Вы себе сейчас запрещаете?",
    "Как Вам кажется, сколько еще энергии у Вас осталось на поддержание Автопилота? (Напр: топливо на нуле).",
    "Готовы ли Вы прямо сейчас найти свою Точку Сдвига и перейти в Свободный ход?",
]


# =========================
# SYSTEM PROMPT (ENGINEER-GUIDE, NO WATER / ESOTERICS)
# =========================
SYSTEM_PROMPT = """
Вы — ИИ-Навигатор проекта «Метаформула жизни». Ваша роль: инженер-проводник, который проводит когнитивный аудит пользователя по его 7 ответам.

ТЕРМИНЫ (использовать строго и по смыслу):
- Источник — внутренний потенциал и энергия.
- Доминанта — очаг напряжения в мозге (затык), ворующий внимание.
- Функция — социальный софт, роли и страхи, блокирующие Источник.
- Точка Сдвига — мгновение тишины для перехвата управления (Ctrl+Alt+Del).
- Свободный ход — реализация без внутреннего трения (аналог У-вэй).
- Состояние Автора — жизнь из Центра Источника.

СТИЛЬ:
- Обращение только на «Вы».
- Тон: экспертный, спокойный, без «воды» и эзотерики.
- Пишите по делу: формулировки короткие, точные, проверяемые.
- Используйте Markdown-заголовки (# и ##). Не используйте двойные звездочки (**).

СТРУКТУРА ОТЧЕТА (строго в этом порядке):
# Когнитивный аудит: ИИ-Навигатор

## Индекс Автоматизма (в %)
Дайте число 0–100 и 2–3 строки обоснования по ответам.

## Анализ Доминанты (предмета в теле)
Опишите, что именно «ворует внимание», как это проявляется телесно и когнитивно, и какой триггер поддерживает Доминанту.

## Анализ режима Функции
Опишите, какая роль/страх/обязательство удерживает пользователя в цикле и как это блокирует Источник. Укажите 2–3 типичных паттерна поведения.

## Персональная Метаформула (код-фраза)
Дайте короткую код-фразу из 5–9 слов (без эзотерики). Она должна быть практичной и запоминаемой.

## Инструкция по входу в Точку Сдвига
Дайте пошаговую инструкцию на 60–120 секунд: что сделать телом/вниманием/дыханием, чтобы найти Точку Сдвига и перейти в Свободный ход.
Добавьте 1 «аварийный протокол» на 15 секунд на случай перегруза.

Форматируйте так, чтобы это можно было сразу применить.
"""


# =========================
# FSM
# =========================
class AuditState(StatesGroup):
    answering = State()


# =========================
# HELPERS
# =========================
def _now_str() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def _split_telegram(text: str, limit: int = 3800) -> List[str]:
    """
    Telegram hard limit ~4096; keep safety margin.
    Split by paragraphs first, then hard split if needed.
    """
    if not text:
        return [""]

    chunks: List[str] = []
    buff = ""

    for part in text.split("\n\n"):
        candidate = part if not buff else (buff + "\n\n" + part)
        if len(candidate) <= limit:
            buff = candidate
        else:
            if buff:
                chunks.append(buff)
                buff = ""
            # part may still exceed limit
            while len(part) > limit:
                chunks.append(part[:limit])
                part = part[limit:]
            buff = part

    if buff:
        chunks.append(buff)

    return chunks


async def send_admin_alert(alert_type: str, details: str, tb: str = "") -> None:
    """
    Alerts admin on API failures and bot crashes.
    """
    global error_counter, api_failures, last_error_time

    header_map = {
        "api_failure": "🚨 СБОЙ API CEREBRAS",
        "connection_error": "🔌 ПРОБЛЕМА СВЯЗИ",
        "bot_crash": "💥 КРИТИЧЕСКАЯ ОШИБКА БОТА",
        "rate_limit": "⏱️ ЛИМИТ API",
        "warning": "⚠️ ПРЕДУПРЕЖДЕНИЕ",
    }
    header = header_map.get(alert_type, "⚠️ ПРОБЛЕМА")

    msg = (
        f"{header}\n\n"
        f"🕒 Время: {_now_str()}\n"
        f"📊 Тип: {alert_type}\n\n"
        f"📝 Детали:\n{details}\n\n"
        f"📈 Статистика:\n"
        f"• Ошибок за сессию: {error_counter}\n"
        f"• Сбоев API: {api_failures}\n"
        f"• Последняя ошибка: {last_error_time.strftime('%d.%m.%Y %H:%M:%S') if last_error_time else '—'}\n"
    )

    if tb:
        tb_cut = tb[:1500]
        msg += f"\n🔧 Traceback:\n{tb_cut}"

    for chunk in _split_telegram(msg):
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=chunk)
        except Exception:
            # If admin messages fail, only stdout remains.
            print("ADMIN ALERT SEND FAILED")
            print(chunk)


async def is_subscribed(user_id: int) -> bool:
    """
    Check user subscription in CHANNEL_ID.
    """
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        # This can happen if bot isn't admin in the channel or privacy settings block it.
        await send_admin_alert(
            "warning",
            f"Ошибка проверки подписки. user_id={user_id}, channel={CHANNEL_ID}",
            traceback.format_exc(),
        )
        return False


async def send_report_to_admin(user: types.User, qa: List[Dict[str, str]], report: str) -> None:
    """
    Send admin: user info, 7 answers, final AI report.
    Split into multiple messages if needed.
    """
    try:
        username = f"@{user.username}" if user.username else "—"
        head = (
            "🔔 НОВЫЙ КОГНИТИВНЫЙ АУДИТ\n\n"
            f"👤 Пользователь:\n"
            f"• ID: {user.id}\n"
            f"• Имя: {user.first_name or '—'}\n"
            f"• Username: {username}\n"
            f"• Дата: {_now_str()}\n\n"
            "🧾 Ответы (Q/A):\n"
        )

        lines = []
        for i, item in enumerate(qa, start=1):
            q = item.get("q", "").strip()
            a = item.get("a", "").strip()
            lines.append(f"{i}) Q: {q}\n   A: {a}")

        body = "\n\n".join(lines)
        full = head + body + "\n\n📊 AI-отчет:\n\n" + (report or "—")

        for chunk in _split_telegram(full):
            await bot.send_message(chat_id=ADMIN_ID, text=chunk)

    except Exception:
        await send_admin_alert(
            "connection_error",
            f"Ошибка отправки отчета админу. user_id={user.id}",
            traceback.format_exc(),
        )


def _final_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="Скачать Гайд «Ревизия Маршрута»",
        callback_data="get_guide"
    ))
    kb.row(types.InlineKeyboardButton(
        text="Смотреть Мастер-класс «Сдвиг Оптики»",
        url=MASTERCLASS_URL
    ))
    return kb.as_markup()


def _subscribe_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(
        text="Подписаться на канал",
        url=f"https://t.me/{CHANNEL_ID.lstrip('@')}"
    ))
    kb.row(types.InlineKeyboardButton(
        text="Я подписался(ась). Проверить доступ",
        callback_data="check_sub"
    ))
    return kb.as_markup()


async def start_audit(message: types.Message, state: FSMContext) -> None:
    """
    If subscribed: show LOGO_AUDIT_URL and first question.
    Must init answers correctly: answers=[] (fix answers= bug).
    """
    await state.clear()
    await state.update_data(current_q=0, answers=[])  # IMPORTANT: answers=[]

    # Audit logo
    try:
        await message.answer_photo(
            photo=LOGO_AUDIT_URL,
            caption=(
                "ИИ-Навигатор запускает когнитивный аудит.\n\n"
                "Я задам 7 вопросов. Отвечайте по одному сообщению на каждый вопрос."
            )
        )
    except Exception:
        await message.answer(
            "ИИ-Навигатор запускает когнитивный аудит.\n\n"
            "Я задам 7 вопросов. Отвечайте по одному сообщению на каждый вопрос."
        )

    await message.answer(QUESTIONS[0])
    await state.set_state(AuditState.answering)


async def generate_ai_report(qa: List[Dict[str, str]]) -> str:
    """
    Cerebras Async. messages must be list[dict].
    """
    global error_counter, api_failures, last_error_time

    user_input_lines = []
    for i, item in enumerate(qa, start=1):
        user_input_lines.append(f"{i}) {item['q']}\nОтвет: {item['a']}")
    user_input = "\n\n".join(user_input_lines)

    try:
        response = await client.chat.completions.create(
            model="llama-3.3-70b",
            temperature=0.4,
            top_p=0.9,
            max_completion_tokens=2048,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
        )

        api_failures = 0
        return (response.choices[0].message.content or "").strip() or "Ошибка: пустой ответ модели."

    except Exception as e:
        error_counter += 1
        api_failures += 1
        last_error_time = datetime.now()

        err = str(e).lower()
        if "rate limit" in err or "quota" in err or "limit" in err:
            alert_type = "rate_limit"
            details = "Исчерпан лимит запросов к Cerebras API."
        elif "connection" in err or "timeout" in err or "network" in err:
            alert_type = "connection_error"
            details = "Сбой соединения с Cerebras API (timeout/connection/network)."
        elif "authentication" in err or "key" in err or "token" in err:
            alert_type = "api_failure"
            details = "Ошибка аутентификации Cerebras API (ключ/токен)."
        elif "service unavailable" in err or "503" in err:
            alert_type = "api_failure"
            details = "Cerebras API временно недоступен (503)."
        else:
            alert_type = "api_failure"
            details = f"Неизвестная ошибка Cerebras API: {str(e)[:300]}"

        await send_admin_alert(alert_type, details, traceback.format_exc())

        # User-safe message
        if alert_type == "rate_limit":
            return (
                "⏱️ Превышен лимит запросов.\n\n"
                "Сервис генерации отчета временно недоступен. Попробуйте позже."
            )
        if alert_type == "connection_error":
            return (
                "🔌 Не удалось подключиться к сервису генерации отчета.\n\n"
                "Попробуйте через несколько минут."
            )
        return (
            "🚧 Сервис генерации отчета временно недоступен.\n\n"
            "Попробуйте позже."
        )


# =========================
# HANDLERS
# =========================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    global error_counter
    try:
        await state.clear()

        if not await is_subscribed(message.from_user.id):
            # Subscription gate
            try:
                await message.answer_photo(
                    photo=LOGO_START_URL,
                    caption=(
                        "Чтобы начать когнитивный аудит, требуется подписка на канал проекта.\n\n"
                        f"Канал: {CHANNEL_ID}"
                    ),
                    reply_markup=_subscribe_keyboard()
                )
            except Exception:
                await message.answer(
                    "Чтобы начать когнитивный аудит, требуется подписка на канал проекта.\n\n"
                    f"Канал: {CHANNEL_ID}",
                    reply_markup=_subscribe_keyboard()
                )
            return

        # If subscribed: audit logo + first question immediately
        await start_audit(message, state)

    except Exception:
        error_counter += 1
        await send_admin_alert(
            "bot_crash",
            f"Ошибка /start. user_id={message.from_user.id}",
            traceback.format_exc(),
        )
        await message.answer("⚠️ Техническая ошибка. Попробуйте позже.")


@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: types.CallbackQuery, state: FSMContext) -> None:
    global error_counter
    try:
        if await is_subscribed(callback.from_user.id):
            await callback.answer("Доступ подтвержден.")
            # start audit
            if callback.message:
                await start_audit(callback.message, state)
        else:
            await callback.answer("Подписка не найдена. Подпишитесь на канал и попробуйте снова.", show_alert=True)
    except Exception:
        error_counter += 1
        await send_admin_alert(
            "bot_crash",
            f"Ошибка check_sub. user_id={callback.from_user.id}",
            traceback.format_exc(),
        )


@dp.message(AuditState.answering)
async def handle_audit_answer(message: types.Message, state: FSMContext) -> None:
    """
    Ask questions strictly one by one after receiving previous answer.
    """
    global error_counter

    try:
        if not message.text or not message.text.strip():
            await message.answer("Ответ должен быть текстом. Напишите ответ одним сообщением.")
            return

        data = await state.get_data()
        q_idx = int(data.get("current_q", 0))
        answers: List[Dict[str, str]] = data.get("answers", [])  # answers=[] fix already in start_audit

        # Guard
        if q_idx < 0 or q_idx >= len(QUESTIONS):
            await state.clear()
            await message.answer("Сессия сбилась. Запустите заново: /start")
            return

        # Store Q/A
        answers.append({"q": QUESTIONS[q_idx], "a": message.text.strip()})

        next_idx = q_idx + 1
        if next_idx < len(QUESTIONS):
            await state.update_data(current_q=next_idx, answers=answers)
            await message.answer(QUESTIONS[next_idx])
            return

        # Final: generate report
        await state.update_data(current_q=next_idx, answers=answers)
        await message.answer("Принято. Формирую отчет аудита...")

        report = await generate_ai_report(answers)

        # Send report to user
        # NOTE: Telegram Markdown is limited; still sending as requested.
        for chunk in _split_telegram(report):
            await message.answer(chunk)

        # Send full data to admin
        await send_report_to_admin(message.from_user, answers, report)

        # Final buttons
        await message.answer(
            "Дальше — два варианта.",
            reply_markup=_final_keyboard()
        )

        await state.clear()

    except Exception:
        error_counter += 1
        await send_admin_alert(
            "bot_crash",
            f"Ошибка обработки ответов. user_id={message.from_user.id}",
            traceback.format_exc(),
        )
        await message.answer("⚠️ Ошибка обработки. Запустите заново: /start")
        await state.clear()


@dp.callback_query(F.data == "get_guide")
async def cb_get_guide(callback: types.CallbackQuery) -> None:
    global error_counter
    try:
        if callback.message:
            # Send PDF
            await callback.message.answer_document(
                document=GUIDE_URL,
                caption="Гайд «Ревизия Маршрута»."
            )
        await callback.answer()
    except Exception:
        error_counter += 1
        await send_admin_alert(
            "bot_crash",
            f"Ошибка отправки гайда. user_id={callback.from_user.id}",
            traceback.format_exc(),
        )
        await callback.answer("Не удалось отправить PDF. Попробуйте позже.", show_alert=True)


# Optional: global error catcher for unhandled exceptions in updates
@dp.errors()
async def global_error_handler(event: types.ErrorEvent) -> bool:
    global error_counter
    error_counter += 1
    await send_admin_alert(
        "bot_crash",
        "Необработанная ошибка в обработке апдейта.",
        traceback.format_exc(),
    )
    return True


# =========================
# HEALTH CHECK (Render)
# =========================
async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="ok")


async def start_web_server() -> None:
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()


async def send_startup_notification() -> None:
    try:
        me = await bot.get_me()
        msg = (
            "✅ БОТ ЗАПУЩЕН\n\n"
            f"🕒 Время: {_now_str()}\n"
            f"🤖 Bot: @{me.username}\n"
            f"📌 Канал проверки подписки: {CHANNEL_ID}\n"
            f"🌐 Health: 0.0.0.0:{PORT}/health\n"
        )
        await bot.send_message(chat_id=ADMIN_ID, text=msg)
    except Exception:
        print("Startup notification failed")
        print(traceback.format_exc())


# =========================
# MAIN
# =========================
async def main() -> None:
    await start_web_server()
    await send_startup_notification()

    try:
        await dp.start_polling(bot)
    except Exception:
        await send_admin_alert(
            "bot_crash",
            "Бот полностью остановлен (start_polling crashed).",
            traceback.format_exc(),
        )
        raise


if __name__ == "__main__":
    asyncio.run(main())
