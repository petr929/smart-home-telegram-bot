"""Учебный Telegram-бот «Умный дом». Датчики в этом примере виртуальные."""

import os
import random
import sqlite3
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path

import speech_recognition as sr
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DB_PATH = Path(__file__).with_name("smart_home.db")

# Состояния виртуальных устройств. В настоящей системе их заменяют показания датчиков.
house = {
    "light": False,
    "motion": False,
    "door_open": False,
    "temperature": 22.0,
}


def save_event(event: str) -> None:
    """Добавляет событие в SQLite, чтобы история переживала перезапуск."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO history (event, created_at) VALUES (?, ?)",
            (event, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def read_history(limit: int = 10) -> list[tuple[str, str]]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        return connection.execute(
            "SELECT created_at, event FROM history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 Включить свет", callback_data="light_on"),
         InlineKeyboardButton("🌑 Выключить свет", callback_data="light_off")],
        [InlineKeyboardButton("🚶 Проверить движение", callback_data="motion"),
         InlineKeyboardButton("🚪 Проверить дверь", callback_data="door")],
        [InlineKeyboardButton("🌡 Обновить температуру", callback_data="temperature"),
         InlineKeyboardButton("🏠 Статус дома", callback_data="status")],
        [InlineKeyboardButton("📜 История", callback_data="history")],
    ])


def status_text() -> str:
    return (
        "🏠 *Статус умного дома*\n\n"
        f"💡 Свет: {'включён' if house['light'] else 'выключен'}\n"
        f"🚶 Движение: {'обнаружено' if house['motion'] else 'не обнаружено'}\n"
        f"🚪 Дверь: {'открыта' if house['door_open'] else 'закрыта'}\n"
        f"🌡 Температура: {house['temperature']:.1f} °C\n\n"
        "_Показания датчиков демонстрационные._"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    save_event("Пользователь открыл главное меню")
    await update.message.reply_text(
        "Привет! Я учебный бот «Умный дом». Выбери действие кнопкой или отправь "
        "голосовое сообщение: например, «включи свет» или «статус дома».\n\n"
        "Команды: /start, /status, /history, /help",
        reply_markup=main_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Как пользоваться:\n"
        "• Нажимай кнопки для управления виртуальными устройствами.\n"
        "• Отправь голосовое сообщение с простой командой.\n"
        "• /status — текущее состояние.\n"
        "• /history — последние 10 событий.\n\n"
        "Голосовое распознавание использует онлайн-сервис Google и требует интернет."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(status_text(), parse_mode="Markdown", reply_markup=main_keyboard())


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = read_history()
    if not rows:
        text = "История пока пустая."
    else:
        text = "📜 Последние события:\n\n" + "\n".join(
            f"{stamp} — {event}" for stamp, event in rows
        )
    await update.message.reply_text(text, reply_markup=main_keyboard())


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action = query.data
    message = ""

    if action == "light_on":
        house["light"] = True
        message = "Свет включён."
    elif action == "light_off":
        house["light"] = False
        message = "Свет выключен."
    elif action == "motion":
        house["motion"] = random.choice([True, False])
        message = "Движение обнаружено!" if house["motion"] else "Движения нет."
        if house["motion"]:
            house["light"] = True
            message += " Автоматика включила свет."
    elif action == "door":
        house["door_open"] = not house["door_open"]
        message = "Дверь открыта." if house["door_open"] else "Дверь закрыта."
    elif action == "temperature":
        house["temperature"] = round(random.uniform(18.0, 28.0), 1)
        message = f"Новое тестовое значение: {house['temperature']:.1f} °C."
    elif action == "status":
        await query.message.reply_text(status_text(), parse_mode="Markdown", reply_markup=main_keyboard())
        return
    elif action == "history":
        rows = read_history()
        history_text = "📜 Последние события:\n\n" + "\n".join(
            f"{stamp} — {event}" for stamp, event in rows
        ) if rows else "История пока пустая."
        await query.message.reply_text(history_text, reply_markup=main_keyboard())
        return

    save_event(message)
    await query.message.reply_text(message, reply_markup=main_keyboard())


def apply_voice_command(text: str) -> str:
    """Преобразует распознанную фразу в одну из простых команд."""
    command = text.lower().replace("ё", "е")
    if "свет" in command and any(word in command for word in ("включ", "зажги", "зажечь")):
        house["light"] = True
        result = "Голосовая команда: свет включён."
    elif "свет" in command and any(word in command for word in ("выключ", "погаси", "потуши")):
        house["light"] = False
        result = "Голосовая команда: свет выключен."
    elif "статус" in command or "состояние" in command:
        return status_text()
    elif "температур" in command:
        result = f"Сейчас тестовая температура {house['temperature']:.1f} °C."
    elif "двер" in command:
        result = "Дверь открыта." if house["door_open"] else "Дверь закрыта."
    elif "движен" in command:
        result = "Движение обнаружено." if house["motion"] else "Движения не обнаружено."
    else:
        return "Команду не понял. Попробуй сказать «включи свет», «выключи свет» или «статус дома»."
    save_event(result)
    return result


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice = update.message.voice
    await update.message.reply_text("Распознаю голосовую команду…")
    try:
        file = await context.bot.get_file(voice.file_id)
        with tempfile.TemporaryDirectory() as temp_dir:
            ogg_path = Path(temp_dir) / "voice.ogg"
            wav_path = Path(temp_dir) / "voice.wav"
            await file.download_to_drive(ogg_path)
            # Telegram обычно присылает OGG/Opus; ffmpeg переводит его в WAV.
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(ogg_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            recognizer = sr.Recognizer()
            with sr.AudioFile(str(wav_path)) as source:
                audio = recognizer.record(source)
            phrase = recognizer.recognize_google(audio, language="ru-RU")
        save_event(f"Распознана голосовая команда: {phrase}")
        result = apply_voice_command(phrase)
        await update.message.reply_text(f"🎙 Распознано: «{phrase}»\n\n{result}", parse_mode="Markdown", reply_markup=main_keyboard())
    except sr.UnknownValueError:
        await update.message.reply_text("Не удалось разобрать речь. Попробуй сказать короче и чётче.", reply_markup=main_keyboard())
    except sr.RequestError:
        await update.message.reply_text("Сервис распознавания недоступен. Проверь интернет и попробуй снова.")
    except FileNotFoundError:
        await update.message.reply_text("Не найден ffmpeg. Установи его и перезапусти бота.")
    except subprocess.CalledProcessError:
        await update.message.reply_text("Не получилось обработать аудио. Попробуй отправить голосовое ещё раз.")
    except Exception as error:
        print(f"Ошибка обработки голосового сообщения: {error}")
        await update.message.reply_text("Не получилось обработать голосовое сообщение. Проверь установку зависимостей.")


def main() -> None:
    if not TOKEN:
        raise SystemExit(
            "Не найден TELEGRAM_BOT_TOKEN. Создай файл .env и добавь токен от @BotFather."
        )
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.VOICE, voice_message))
    print("Бот запущен. Для остановки нажми Ctrl+C.")
    app.run_polling()


if __name__ == "__main__":
    main()
