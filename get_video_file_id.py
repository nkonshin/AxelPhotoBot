#!/usr/bin/env python3
"""
Скрипт для получения file_id видео-кружка.

Использование:
1. Отправь видео-кружок боту в личку
2. Запусти этот скрипт
3. Скопируй file_id из вывода в .env как WELCOME_VIDEO_FILE_ID
"""

import asyncio
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не найден в .env")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(F.video_note)
async def handle_video_note(message: Message):
    """Handle video note and print file_id."""
    file_id = message.video_note.file_id
    
    print("\n" + "="*60)
    print("✅ Видео-кружок получен!")
    print("="*60)
    print(f"\nfile_id: {file_id}")
    print(f"\nДобавь эту строку в .env:")
    print(f"WELCOME_VIDEO_FILE_ID={file_id}")
    print("\n" + "="*60)
    
    await message.answer(
        f"✅ file_id получен!\n\n"
        f"<code>{file_id}</code>\n\n"
        f"Добавь в .env:\n"
        f"<code>WELCOME_VIDEO_FILE_ID={file_id}</code>",
        parse_mode="HTML"
    )
    
    # Stop the bot after receiving the video
    await dp.stop_polling()


@dp.message()
async def handle_other(message: Message):
    """Handle other messages."""
    await message.answer(
        "📹 Отправь мне видео-кружок (круглое видео), "
        "чтобы получить его file_id"
    )


async def main():
    print("🤖 Бот запущен!")
    print("📹 Отправь видео-кружок боту в личку...")
    print("⏹️  Нажми Ctrl+C для остановки\n")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
