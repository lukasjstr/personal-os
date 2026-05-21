"""Incoming Telegram update handler."""
import logging
import os
import tempfile
from typing import Optional

from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.ai.client import process_message
from bot.config import settings
from bot.core.daily_intelligence import (
    _evening_ci_state,
    handle_ci_all,
    handle_ci_none,
    handle_ci_skip_win,
    handle_ci_task_toggle,
    handle_ci_win_text,
    handle_ctx_energy,
    handle_ctx_focus,
    handle_ctx_time,
)
from bot.core.kr_updater import (
    handle_kr_cancel,
    handle_kr_confirm,
    send_kr_confirmation,
)
from bot.core.next_action import (
    handle_next_done,
    handle_next_skip,
    send_next_action,
)
from bot.core.goal_onboarding import (
    get_active_onboarding,
    handle_onboarding_answer,
    handle_onboarding_callback,
)
from bot.core.user_settings import get_or_create_user
from bot.core.weekly_reflections import get_active_reflection, handle_reflection_answer
from bot.database.connection import get_session
from bot.telegram.commands import (
    handle_cut,
    handle_goal,
    handle_help,
    handle_ical,
    handle_next,
    handle_organize,
    handle_plan,
    handle_settings,
    handle_shopping,
    handle_start,
    handle_status,
    handle_times,
    handle_toggle,
    handle_token,
    handle_woche,
)
from bot.telegram.sender import send_message, send_typing

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callback queries for daily intelligence flows."""
    query = update.callback_query
    if not query or not update.effective_user:
        return

    await query.answer()  # acknowledge the button press immediately

    tg_user = update.effective_user
    data = query.data or ""

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            tg_user.id,
            tg_user.username,
            tg_user.first_name,
        )
        bot = context.bot

        try:
            # Morning context: energy
            if data.startswith("ctx_energy_"):
                await handle_ctx_energy(bot, user, data)

            # Morning context: time available
            elif data.startswith("ctx_time_"):
                await handle_ctx_time(bot, user, data)

            # Morning context: focus area
            elif data.startswith("ctx_focus_"):
                await handle_ctx_focus(bot, user, session, data)
                await session.commit()

            # Evening check-in: individual task toggle
            elif data.startswith("ci_task_"):
                await handle_ci_task_toggle(bot, user, session, data)

            # Evening check-in: nothing done
            elif data == "ci_none":
                await handle_ci_none(bot, user, session)

            # Evening check-in: everything done
            elif data == "ci_all":
                await handle_ci_all(bot, user, session)

            # Evening check-in: skip win-of-day
            elif data == "ci_skip_win":
                await handle_ci_skip_win(bot, user, session)
                await session.commit()

            # Streak risk view (acknowledge — full task list shown via text commands)
            elif data.startswith("streak_view_"):
                await bot.send_message(
                    chat_id=tg_user.id,
                    text="📋 Nutze /status oder frage mich nach deinen Tasks für dieses Ziel.",
                )

            # /next: mark done
            elif data.startswith("next_done_"):
                task_id = int(data.split("_")[-1])
                await handle_next_done(bot, user, session, task_id)

            # /next: skip to next task
            elif data.startswith("next_skip_"):
                task_id = int(data.split("_")[-1])
                await handle_next_skip(bot, user, session, task_id)

            # KR update: confirm
            elif data.startswith("kr_confirm_"):
                parts = data.split("_")
                kr_id = int(parts[2])
                new_value_encoded = int(parts[3])
                await handle_kr_confirm(bot, user, session, kr_id, new_value_encoded)

            # KR update: cancel
            elif data == "kr_cancel":
                await handle_kr_cancel(bot, user)

            # Daily prompt callbacks
            elif data == "prompt_skip":
                from bot.core.smart_detector import clear_pending_prompt
                clear_pending_prompt(user.id)
                await bot.send_message(
                    chat_id=tg_user.id,
                    text="👍 Kein Problem — bis morgen!",
                )

            elif data == "prompt_journal_open":
                from bot.core.smart_detector import set_pending_prompt
                set_pending_prompt(user.id, "journal")
                await bot.send_message(
                    chat_id=tg_user.id,
                    text="✍️ Los geht's — schreib deinen Journal-Eintrag:",
                )

            elif data == "prompt_gratitude_open":
                from bot.core.smart_detector import set_pending_prompt
                set_pending_prompt(user.id, "gratitude")
                await bot.send_message(
                    chat_id=tg_user.id,
                    text="🙏 Schreib deine 3 Dinge — wofür bist du heute dankbar?",
                )

            # Post-event follow-up: "yes" responses → forward to AI as text input
            elif any(data.startswith(p) for p in [
                "followup_workout_done_", "followup_cardio_done_", "followup_supp_done_",
                "followup_learn_done_", "followup_routine_done_", "followup_deadline_done_",
                "followup_meeting_good_",
            ]):
                event_id = data.split("_")[-1]
                label_map = {
                    "followup_workout_done": "Training gemacht",
                    "followup_cardio_done": "Cardio gemacht",
                    "followup_supp_done": "Supplemente genommen",
                    "followup_learn_done": "Lerneinheit gemacht",
                    "followup_routine_done": "Routine erledigt",
                    "followup_deadline_done": "Deadline abgegeben",
                    "followup_meeting_good": "Meeting war produktiv",
                    "followup_food_log": "Mahlzeit loggen",
                }
                prefix = "_".join(data.split("_")[:-1])
                label = label_map.get(prefix, "Erledigt")
                synthetic = f"✅ {label} (Kalender-Event #{event_id})"
                await process_message(user, synthetic, session)
                await session.commit()

            # Post-event follow-up: "food log" → set pending prompt
            elif data.startswith("followup_food_log_"):
                from bot.core.smart_detector import set_pending_prompt
                set_pending_prompt(user.id, "food")
                await bot.send_message(
                    chat_id=tg_user.id,
                    text="🍽️ Was hast du gegessen? Beschreib kurz deine Mahlzeit:",
                )

            # Post-event follow-up: "no/skip" responses → acknowledge
            elif any(data.startswith(p) for p in [
                "followup_workout_skip_", "followup_cardio_skip_", "followup_supp_skip_",
                "followup_learn_skip_", "followup_routine_skip_", "followup_food_skip_",
                "followup_meeting_notes_", "followup_sleep_good_", "followup_sleep_bad_",
                "followup_deadline_open_",
            ]):
                if "meeting_notes" in data:
                    await bot.send_message(
                        chat_id=tg_user.id,
                        text="📝 Schreib deine Meeting-Notizen — ich speichere sie im Tagebuch:",
                    )
                    from bot.core.smart_detector import set_pending_prompt
                    set_pending_prompt(user.id, "journal")
                elif "sleep_bad" in data:
                    await bot.send_message(chat_id=tg_user.id, text="😴 Notiert — schlaf heute früher!")
                elif "deadline_open" in data:
                    await bot.send_message(chat_id=tg_user.id, text="⚠️ Noch offen — soll ich eine Erinnerung setzen?")
                else:
                    await bot.send_message(chat_id=tg_user.id, text="👍 Kein Problem — kein Eintrag gespeichert.")

            # Goal onboarding: confirm / adjust / cancel
            elif data.startswith("goal_confirm_") or data.startswith("goal_adjust_") or data.startswith("goal_cancel_"):
                onboarding = await get_active_onboarding(session, user.id)
                if onboarding:
                    reply = await handle_onboarding_callback(session, user, onboarding, data)
                    await session.commit()
                    await bot.send_message(
                        chat_id=tg_user.id,
                        text=reply,
                        parse_mode="Markdown",
                    )
                else:
                    await bot.send_message(
                        chat_id=tg_user.id,
                        text="Kein aktives Ziel-Onboarding gefunden.",
                    )

            # Routine time adjustment (from action_engine Rule 6)
            elif data.startswith("routine_adjust_"):
                parts = data.split("_")  # routine_adjust_{id}_{time}
                if len(parts) >= 4:
                    routine_id = int(parts[2])
                    new_time = parts[3]  # morning, midday, evening, pause
                    from bot.database.models import Routine
                    routine = (await session.execute(
                        select(Routine).where(and_(
                            Routine.id == routine_id,
                            Routine.user_id == user.id,
                        ))
                    )).scalar_one_or_none()
                    if routine:
                        if new_time == "pause":
                            routine.status = "paused"
                            reply = f"⏸ Routine '{routine.title}' pausiert."
                        else:
                            routine.time_of_day = new_time
                            time_labels = {"morning": "Morgens", "midday": "Mittags", "evening": "Abends"}
                            reply = f"✅ Routine '{routine.title}' auf {time_labels.get(new_time, new_time)} verschoben."
                        await session.commit()
                        await bot.send_message(chat_id=tg_user.id, text=reply)
                    else:
                        await bot.send_message(chat_id=tg_user.id, text="Routine nicht gefunden.")

            else:
                logger.debug("Unhandled callback query data: %s", data)

        except Exception:
            logger.exception("Error handling callback query '%s' for user %s", data, user.id)


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

        # Check for active evening check-in win-of-day input
        state = _evening_ci_state.get(user.id)
        if state and state.get("step") == "win":
            consumed = await handle_ci_win_text(context.bot, user, session, text)
            if consumed:
                await session.commit()
                return

        # Check for active goal onboarding
        onboarding = await get_active_onboarding(session, user.id)
        if onboarding:
            reply_text, keyboard_data = await handle_onboarding_answer(
                session, user, onboarding, text
            )
            await session.commit()
            if keyboard_data:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])
                     for btn in row]
                    for row in keyboard_data
                ])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=reply_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            else:
                await send_message(chat_id, reply_text)
            return

        # V3 P09 — Friday-Cut pending reply
        from bot.core.smart_detector import get_pending_prompt, clear_pending_prompt
        if get_pending_prompt(user.id) == "friday_cut":
            from bot.core.friday_cut import cut_task, cut_free_text
            reply: str
            # Try to interpret as task id ("123", "/cut 123", "#123")
            stripped = text.strip().lstrip("/cut").lstrip().lstrip("#").strip()
            task_id: Optional[int] = None
            if stripped.isdigit():
                task_id = int(stripped)
            if task_id is not None:
                task = await cut_task(session, user.id, task_id)
                if task is not None:
                    reply = f"Gestrichen: #{task.id} {task.title}. Nächste Woche leichter."
                else:
                    reply = f"Task #{task_id} nicht gefunden. Schick den Text der weg soll."
                    # Keep pending so user can retry
                    clear_pending_prompt(user.id) if reply.startswith("Gestrichen") else None
                    await session.commit()
                    await send_message(chat_id, reply)
                    return
            else:
                dump = await cut_free_text(session, user.id, text)
                reply = f"Gestrichen (Freitext, BrainDump#{dump.id}). Nächste Woche leichter."
            clear_pending_prompt(user.id)
            await session.commit()
            await send_message(chat_id, reply)
            return

        # Check for active reflection session
        reflection = await get_active_reflection(session, user.id)
        if reflection:
            reply = await handle_reflection_answer(session, user, reflection, text)
            await session.commit()
        else:
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


async def _transcribe_audio(file_id: str, suffix: str, tg_bot) -> str:
    """Download a Telegram audio file and transcribe it with Whisper. Returns transcript."""
    file = await tg_bot.get_file(file_id)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await file.download_to_drive(tmp_path)
        with open(tmp_path, "rb") as audio_file:
            transcription = await openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                # No language param → Whisper auto-detects (German, English, mixed)
            )
        return transcription.text.strip()
    finally:
        os.unlink(tmp_path)


async def _handle_audio_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_id: str,
    suffix: str,
    duration_seconds: int = 0,
) -> None:
    """Shared handler for voice, video_note, and audio file inputs."""
    if not update.message or not update.effective_user:
        return

    tg_user = update.effective_user
    chat_id = update.message.chat_id

    await send_typing(chat_id)

    try:
        text = await _transcribe_audio(file_id, suffix, context.bot)
    except Exception:
        logger.exception("Whisper transcription failed")
        await send_message(chat_id, "❌ Transkription fehlgeschlagen — bitte nochmal versuchen.")
        return

    if not text:
        await send_message(chat_id, "🎙 Konnte nichts verstehen — bitte deutlicher sprechen.")
        return

    dur = f" ({duration_seconds}s)" if duration_seconds else ""
    await send_message(chat_id, f"🎙 Verstanden{dur}: _{text}_")
    await send_typing(chat_id)

    async with get_session() as session:
        user = await get_or_create_user(
            session,
            tg_user.id,
            tg_user.username,
            tg_user.first_name,
        )

        # Check active goal onboarding
        onboarding = await get_active_onboarding(session, user.id)
        if onboarding:
            reply_text, keyboard_data = await handle_onboarding_answer(
                session, user, onboarding, text
            )
            await session.commit()
            if keyboard_data:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])
                     for btn in row]
                    for row in keyboard_data
                ])
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=reply_text,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            else:
                await send_message(chat_id, reply_text)
            return

        # Check active reflection session
        reflection = await get_active_reflection(session, user.id)
        if reflection:
            reply = await handle_reflection_answer(session, user, reflection, text)
        else:
            reply = await process_message(session, user, text, source="voice")
        await session.commit()

    await send_message(chat_id, reply)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a voice message — transcribe with Whisper, then process."""
    if not update.message or not update.message.voice:
        return
    voice = update.message.voice
    await _handle_audio_input(update, context, voice.file_id, ".ogg", voice.duration)


async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle round video messages (video notes) — transcribe audio track with Whisper."""
    if not update.message or not update.message.video_note:
        return
    vn = update.message.video_note
    await _handle_audio_input(update, context, vn.file_id, ".mp4", vn.duration)


async def handle_audio_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle audio file uploads — transcribe with Whisper."""
    if not update.message or not update.message.audio:
        return
    audio = update.message.audio
    duration = audio.duration or 0
    await _handle_audio_input(update, context, audio.file_id, ".mp3", duration)


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
    application.add_handler(CommandHandler("token", handle_token))
    application.add_handler(CommandHandler("organize", handle_organize))
    application.add_handler(CommandHandler("next", handle_next))
    application.add_handler(CommandHandler("goal", handle_goal))
    application.add_handler(CommandHandler("plan", handle_plan))
    application.add_handler(CommandHandler("woche", handle_woche))
    application.add_handler(CommandHandler("cut", handle_cut))

    # Inline button callbacks (daily intelligence flows)
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
    application.add_handler(MessageHandler(filters.AUDIO, handle_audio_file))
