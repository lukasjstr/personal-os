"""Incoming Telegram update handler."""
import logging
import os
import tempfile

from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.ai.client import process_message
from bot.config import settings
from bot.core.user_settings import get_or_create_user
from bot.database.connection import get_session
from bot.telegram.commands import (
    handle_help,
    handle_ical,
    handle_settings,
    handle_shopping,
    handle_start,
    handle_status,
    handle_times,
    handle_toggle,
)
from bot.telegram.sender import send_message, send_typing

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a text message from Telegram."""
    if not update.message or not update.effective_user:
        return

    tg_user = update.effective_user
    chat_id = update.message.chat_id
    text = update.message.text or ""

    await send_typing(chat_id)

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            tg_user.id,
            tg_user.username,
            tg_user.first_name,
        )
        reply = await process_message(session, user, text, source="text")
        await session.commit()

    await send_message(chat_id, reply)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a photo message — describe it with vision and process."""
    if not update.message or not update.effective_user:
        return

    tg_user = update.effective_user
    chat_id = update.message.chat_id
    caption = update.message.caption or "Was siehst du auf dem Bild? Erkenne Trainingsgeräte, Gewichte, Essen oder andere relevante Dinge."

    await send_typing(chat_id)

    photo = update.message.photo[-1]
    tg_bot = context.bot
    file = await tg_bot.get_file(photo.file_id)
    file_url = file.file_path

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            tg_user.id,
            tg_user.username,
            tg_user.first_name,
        )
        reply = await process_message(
            session, user, caption,
            source="image",
            image_url=file_url,
        )
        await session.commit()

    await send_message(chat_id, reply)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a voice message — transcribe with Whisper, then process."""
    if not update.message or not update.effective_user:
        return

    tg_user = update.effective_user
    chat_id = update.message.chat_id

    await send_typing(chat_id)

    voice = update.message.voice
    tg_bot = context.bot
    file = await tg_bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        await file.download_to_drive(tmp_path)

        with open(tmp_path, "rb") as audio_file:
            transcription = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="de",
            )
        text = transcription.text.strip()
        if not text:
            await send_message(chat_id, "Konnte die Sprachnachricht nicht verstehen. Bitte nochmal.")
            return

        async with get_session() as session:
            user = await get_or_create_user(
                session,
                tg_user.id,
                tg_user.username,
                tg_user.first_name,
            )
            reply = await process_message(session, user, text, source="voice")
            await session.commit()

        await send_message(chat_id, f"🎙 _{text}_\n\n{reply}")
    finally:
        os.unlink(tmp_path)


def setup_handlers(application: Application) -> None:
    """Register all Telegram handlers."""
    # Command handlers
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("settings", handle_settings))
    application.add_handler(CommandHandler("toggle", handle_toggle))
    application.add_handler(CommandHandler("times", handle_times))
    application.add_handler(CommandHandler("status", handle_status))
    application.add_handler(CommandHandler("shopping", handle_shopping))
    application.add_handler(CommandHandler("ical", handle_ical))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
