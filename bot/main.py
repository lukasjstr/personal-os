"""FastAPI application — main entry point for Personal OS."""
import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.ext import Application

from bot.api.ical import router as ical_router
from bot.api.routes import router as api_router
from bot.config import settings
from bot.database.connection import engine
from bot.database.models import Base
from bot.jobs.scheduler import setup_scheduler
from bot.telegram.handler import setup_handlers
from bot.telegram.sender import get_bot

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

telegram_app: Application | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global telegram_app

    logger.info("Starting Personal OS V2...")

    # Apply database schema (create new tables + add new columns safely)
    from bot.database.migrate import apply_v2_migrations
    await apply_v2_migrations(engine)
    logger.info("Database schema up to date")

    # Initialize Telegram Application
    telegram_app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )
    setup_handlers(telegram_app)
    await telegram_app.initialize()

    # Register webhook
    try:
        import os
        bot = get_bot()
        webhook_url = settings.telegram_webhook_url
        cert_path = settings.telegram_webhook_cert

        if os.path.exists(cert_path):
            with open(cert_path, "rb") as cert_file:
                await bot.set_webhook(
                    url=webhook_url,
                    certificate=cert_file,
                    drop_pending_updates=True,
                )
        else:
            await bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True,
            )
        logger.info("Telegram webhook registered: %s", webhook_url)
    except Exception as e:
        logger.error("Failed to register webhook: %s", e)

    # Start scheduler with all Phase 4 active jobs
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started: morning_brief, evening_review, reminders, weekly_reflection")

    yield

    # Shutdown
    logger.info("Shutting down Personal OS...")
    scheduler.shutdown(wait=False)
    if telegram_app:
        await telegram_app.shutdown()
    await engine.dispose()


app = FastAPI(
    title="Personal OS API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)
app.include_router(ical_router)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "personal-os", "version": "2.0.0"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> Response:
    """Receive and process Telegram webhook updates."""
    global telegram_app
    if not telegram_app:
        return Response(status_code=503, content="Not ready")

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception as e:
        logger.exception("Webhook processing error: %s", e)

    return Response(status_code=200)
