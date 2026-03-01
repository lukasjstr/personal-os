"""Incoming Telegram update handler."""
import logging
import os
import tempfile
from typing import Optional

from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application, ContextTypes

from bot.ai.client import process_message
from bot.config import settings
from bot.database.connection import get_session
from bot.database.models import User
from bot.telegram.sender import send_message, send_typing

from sqlalchemy import select

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def get_or_create_user(session, telegram_id: int, username: Optional[str], first_name: Optional[str]) -> User:
    """Get or create a User record from Telegram ID."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        import secrets
        user = User(
            telegram_id=telegram_id,
            telegram_username=username,
            first_name=first_name,
            api_token=secrets.token_urlsafe(32),
        )
        session.add(user)
        await session.flush()
        logger.info("Created new user: telegram_id=%s username=%s", telegram_id, username)
    else:
        # Update name/username if changed
        if username and user.telegram_username != username:
            user.telegram_username = username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
    return user


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

    await send_message(chat_id, reply)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a photo message — describe it with vision and process."""
    if not update.message or not update.effective_user:
        return

    tg_user = update.effective_user
    chat_id = update.message.chat_id
    caption = update.message.caption or "Was siehst du auf dem Bild? Erkenne Trainingsgeräte, Gewichte, Essen oder andere relevante Dinge."

    await send_typing(chat_id)

    # Get the largest photo
    photo = update.message.photo[-1]
    tg_bot = context.bot
    file = await tg_bot.get_file(photo.file_id)

    # Download to temp file and get URL
    file_url = file.file_path  # Telegram provides a direct URL

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

        await send_message(chat_id, f"🎙 _{text}_\n\n{reply}")
    finally:
        os.unlink(tmp_path)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.message or not update.effective_user:
        return

    tg_user = update.effective_user
    chat_id = update.message.chat_id

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            tg_user.id,
            tg_user.username,
            tg_user.first_name,
        )
        name = user.first_name or "Chef"

    await send_message(
        chat_id,
        f"👋 Hallo {name}! Ich bin dein persönlicher COO.\n\n"
        "Schick mir alles — Gedanken, Ziele, Fortschritte, Workouts.\n"
        "Ich ordne alles ein und halte dich auf Kurs.\n\n"
        "Los geht's. Was willst du erreichen?",
    )


def setup_handlers(application: Application) -> None:
    """Register all Telegram handlers."""
    from telegram.ext import CommandHandler, MessageHandler, filters

    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
