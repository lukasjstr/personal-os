"""Phase 2: Reminder engine — process and send due scheduled reminders."""
import logging

logger = logging.getLogger(__name__)


async def process_reminders() -> None:
    """Check all pending ScheduledReminders and send those that are due.

    Phase 2: Runs every minute via scheduler.
    Fetches all reminders with status='pending' and scheduled_for <= now.
    Sends each via Telegram, marks as sent.
    Handles repeat_rule to schedule next occurrence.
    """
    raise NotImplementedError("Phase 2")


async def generate_water_reminders(user_id: int, kr_id: int) -> None:
    """Auto-generate daily water reminders when a water key result is created.

    Phase 2: Creates ScheduledReminder entries for 09:00, 13:00, 17:00 daily.
    Linked to the water key result for dynamic progress display.
    """
    raise NotImplementedError("Phase 2")


async def generate_task_reminders(user_id: int, task_id: int) -> None:
    """Auto-generate deadline reminders for a task with a due_date.

    Phase 2: Creates reminders at 7 days, 3 days, and 1 day before due date.
    """
    raise NotImplementedError("Phase 2")


async def generate_routine_reminders(user_id: int, routine_id: int) -> None:
    """Auto-generate routine reminder based on schedule_cron.

    Phase 2: Creates a recurring ScheduledReminder that fires 30 minutes
    before each routine's scheduled time.
    """
    raise NotImplementedError("Phase 2")


async def send_routine_reminders() -> None:
    """Legacy Phase 1 stub — replaced by process_reminders() in Phase 2."""
    logger.info("Routine reminders: Phase 2 not yet active")
