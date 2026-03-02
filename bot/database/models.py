"""SQLAlchemy ORM models for Personal OS — all 15 tables."""
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Berlin")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    # settings JSON structure:
    # {
    #   "priorities_enabled": true,
    #   "review_enabled": true,
    #   "proactive_enabled": true,
    #   "reflection_enabled": true,
    #   "morning_brief_time": "06:30",
    #   "evening_review_time": "21:00",
    #   "weekly_reflection_day": "sunday",
    #   "weekly_reflection_time": "19:00",
    #   "shopping_reminder_day": "saturday",
    #   "shopping_reminder_time": "10:00",
    #   "ical_token": "uuid4-string"
    # }
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    api_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    objectives: Mapped[list["Objective"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    logs: Mapped[list["Log"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    routines: Mapped[list["Routine"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    brain_dumps: Mapped[list["BrainDump"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    routine_completions: Mapped[list["RoutineCompletion"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    daily_briefs: Mapped[list["DailyBrief"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    scheduled_reminders: Mapped[list["ScheduledReminder"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    weekly_reflections: Mapped[list["WeeklyReflection"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    weekly_priorities: Mapped[list["WeeklyPriority"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    user_insights: Mapped[list["UserInsight"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    fitness_splits: Mapped[list["FitnessSplit"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    shopping_defaults: Mapped[list["ShoppingDefault"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id}>"


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), default="personal")  # health, business, personal, fitness, finance, learning
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, paused, abandoned
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    priority_weight: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    parent_objective_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="objectives")
    key_results: Mapped[list["KeyResult"]] = relationship(back_populates="objective", cascade="all, delete-orphan")
    brain_dumps: Mapped[list["BrainDump"]] = relationship(back_populates="linked_objective")
    weekly_priorities: Mapped[list["WeeklyPriority"]] = relationship(back_populates="linked_objective")
    parent_objective: Mapped[Optional["Objective"]] = relationship(
        "Objective",
        foreign_keys="[Objective.parent_objective_id]",
        back_populates="sub_objectives",
        remote_side="Objective.id",
    )
    sub_objectives: Mapped[list["Objective"]] = relationship(
        "Objective",
        foreign_keys="[Objective.parent_objective_id]",
        back_populates="parent_objective",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        foreign_keys="[Task.objective_id]",
        back_populates="objective",
    )

    def __repr__(self) -> str:
        return f"<Objective id={self.id} title={self.title!r}>"


class KeyResult(Base):
    __tablename__ = "key_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[int] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(20), default="number")  # percentage, number, boolean, streak, checklist
    target_value: Mapped[Optional[float]] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[Optional[str]] = mapped_column(String(50))
    frequency: Mapped[str] = mapped_column(String(20), default="weekly")  # daily, weekly, monthly, once
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, failed
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    objective: Mapped["Objective"] = relationship(back_populates="key_results")
    tasks: Mapped[list["Task"]] = relationship(back_populates="key_result")
    logs: Mapped[list["Log"]] = relationship(back_populates="key_result")
    routines: Mapped[list["Routine"]] = relationship(back_populates="linked_key_result")
    scheduled_reminders: Mapped[list["ScheduledReminder"]] = relationship(back_populates="linked_key_result")
    weekly_priorities: Mapped[list["WeeklyPriority"]] = relationship(back_populates="linked_key_result")

    def __repr__(self) -> str:
        return f"<KeyResult id={self.id} title={self.title!r}>"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_result_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("key_results.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    objective_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="SET NULL"), index=True)
    parent_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    blocked_by_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo, in_progress, done, cancelled
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1=highest, 5=lowest
    category: Mapped[str] = mapped_column(String(30), default="general")  # general, shopping, errand, work, personal
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="tasks")
    key_result: Mapped[Optional["KeyResult"]] = relationship(back_populates="tasks")
    objective: Mapped[Optional["Objective"]] = relationship(
        "Objective",
        foreign_keys="[Task.objective_id]",
        back_populates="tasks",
    )
    parent_task: Mapped[Optional["Task"]] = relationship(
        "Task",
        foreign_keys="[Task.parent_task_id]",
        back_populates="sub_tasks",
        remote_side="Task.id",
    )
    sub_tasks: Mapped[list["Task"]] = relationship(
        "Task",
        foreign_keys="[Task.parent_task_id]",
        back_populates="parent_task",
    )
    blocked_by: Mapped[Optional["Task"]] = relationship(
        "Task",
        foreign_keys="[Task.blocked_by_task_id]",
        remote_side="Task.id",
    )
    logs: Mapped[list["Log"]] = relationship(back_populates="task")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="linked_task")
    scheduled_reminders: Mapped[list["ScheduledReminder"]] = relationship(back_populates="linked_task")
    weekly_priorities: Mapped[list["WeeklyPriority"]] = relationship(back_populates="linked_task")

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title!r} status={self.status}>"


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key_result_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("key_results.id", ondelete="SET NULL"), index=True)
    task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    log_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # workout, water, food, mood, progress, note, general
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="text")  # text, image, voice
    raw_input: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="logs")
    key_result: Mapped[Optional["KeyResult"]] = relationship(back_populates="logs")
    task: Mapped[Optional["Task"]] = relationship(back_populates="logs")

    def __repr__(self) -> str:
        return f"<Log id={self.id} type={self.log_type}>"


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(100))  # cron expression, optional
    frequency_human: Mapped[str] = mapped_column(String(100))  # "Jeden Dienstag", "Täglich"
    linked_key_result_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("key_results.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused
    time_of_day: Mapped[str] = mapped_column(String(20), default="anytime")  # morning, midday, evening, anytime
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="routines")
    linked_key_result: Mapped[Optional["KeyResult"]] = relationship(back_populates="routines")
    completions: Mapped[list["RoutineCompletion"]] = relationship(back_populates="routine", cascade="all, delete-orphan")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="linked_routine")
    scheduled_reminders: Mapped[list["ScheduledReminder"]] = relationship(back_populates="linked_routine")

    def __repr__(self) -> str:
        return f"<Routine id={self.id} title={self.title!r}>"


class RoutineCompletion(Base):
    __tablename__ = "routine_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(Integer, ForeignKey("routines.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)

    routine: Mapped["Routine"] = relationship(back_populates="completions")
    user: Mapped["User"] = relationship(back_populates="routine_completions")

    def __repr__(self) -> str:
        return f"<RoutineCompletion id={self.id} routine_id={self.routine_id}>"


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    event_type: Mapped[str] = mapped_column(String(30), default="reminder")  # training, meeting, routine, deadline, reminder, errand
    linked_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"))
    linked_routine_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routines.id", ondelete="SET NULL"))
    ical_uid: Mapped[str] = mapped_column(String(255), unique=True, default=lambda: f"{uuid.uuid4()}@personal-os")
    reminder_minutes_before: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="calendar_events")
    linked_task: Mapped[Optional["Task"]] = relationship(back_populates="calendar_events")
    linked_routine: Mapped[Optional["Routine"]] = relationship(back_populates="calendar_events")

    def __repr__(self) -> str:
        return f"<CalendarEvent id={self.id} title={self.title!r}>"


class BrainDump(Base):
    __tablename__ = "brain_dumps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_interpretation: Mapped[Optional[str]] = mapped_column(Text)
    linked_objective_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="brain_dumps")
    linked_objective: Mapped[Optional["Objective"]] = relationship(back_populates="brain_dumps")

    def __repr__(self) -> str:
        return f"<BrainDump id={self.id}>"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="conversations")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} role={self.role}>"


# ─── Phase 2 Tables (created now, used in Phase 2) ───────────────────────────

class DailyBrief(Base):
    __tablename__ = "daily_briefs"
    __table_args__ = (UniqueConstraint("user_id", "brief_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    brief_date: Mapped[date] = mapped_column(Date, nullable=False)
    priorities: Mapped[dict] = mapped_column(JSON, default=list)
    routines_snapshot: Mapped[dict] = mapped_column(JSON, default=list)
    calendar_snapshot: Mapped[dict] = mapped_column(JSON, default=list)
    warnings: Mapped[dict] = mapped_column(JSON, default=list)
    user_adjusted: Mapped[bool] = mapped_column(Boolean, default=False)
    adjusted_priorities: Mapped[Optional[dict]] = mapped_column(JSON)
    brief_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    review_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    day_score: Mapped[Optional[int]] = mapped_column(Integer)
    day_notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="daily_briefs")

    def __repr__(self) -> str:
        return f"<DailyBrief id={self.id} date={self.brief_date}>"


class ScheduledReminder(Base):
    __tablename__ = "scheduled_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # water, routine, task_nudge, task_deadline, calendar_prep,
    # streak_warning, progress_nudge, shopping, next_action, custom
    message: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    repeat_rule: Mapped[Optional[str]] = mapped_column(String(100))
    # "daily:09:00,13:00,17:00" or "weekly:mon:09:00" or null for one-time
    linked_key_result_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("key_results.id", ondelete="SET NULL"))
    linked_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"))
    linked_routine_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routines.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, sent, cancelled, snoozed
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="scheduled_reminders")
    linked_key_result: Mapped[Optional["KeyResult"]] = relationship(back_populates="scheduled_reminders")
    linked_task: Mapped[Optional["Task"]] = relationship(back_populates="scheduled_reminders")
    linked_routine: Mapped[Optional["Routine"]] = relationship(back_populates="scheduled_reminders")

    def __repr__(self) -> str:
        return f"<ScheduledReminder id={self.id} type={self.reminder_type}>"


# ─── Phase 3 Tables (created now, used in Phase 3) ───────────────────────────

class WeeklyReflection(Base):
    __tablename__ = "weekly_reflections"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, in_progress, completed, skipped
    current_question: Mapped[int] = mapped_column(Integer, default=0)
    stats_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    biggest_win: Mapped[Optional[str]] = mapped_column(Text)
    biggest_blocker: Mapped[Optional[str]] = mapped_column(Text)
    key_learning: Mapped[Optional[str]] = mapped_column(Text)
    week_score: Mapped[Optional[int]] = mapped_column(Integer)
    raw_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    priorities_next_week: Mapped[Optional[dict]] = mapped_column(JSON)
    ai_summary: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="weekly_reflections")

    def __repr__(self) -> str:
        return f"<WeeklyReflection id={self.id} week={self.week_start}>"


class WeeklyPriority(Base):
    __tablename__ = "weekly_priorities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    linked_objective_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="SET NULL"))
    linked_key_result_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("key_results.id", ondelete="SET NULL"))
    linked_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, carried_over
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="weekly_priorities")
    linked_objective: Mapped[Optional["Objective"]] = relationship(back_populates="weekly_priorities")
    linked_key_result: Mapped[Optional["KeyResult"]] = relationship(back_populates="weekly_priorities")
    linked_task: Mapped[Optional["Task"]] = relationship(back_populates="weekly_priorities")

    def __repr__(self) -> str:
        return f"<WeeklyPriority id={self.id} rank={self.priority_rank}>"


class UserInsight(Base):
    __tablename__ = "user_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # productivity_pattern, habit, blocker, strength, preference
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    data_basis: Mapped[Optional[dict]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)  # reflection, auto_detected, user_stated
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="user_insights")

    def __repr__(self) -> str:
        return f"<UserInsight id={self.id} type={self.insight_type}>"


# ─── Phase 5.3 — Fitness Splits ──────────────────────────────────────────────

class FitnessSplit(Base):
    __tablename__ = "fitness_splits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    exercises: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # exercises JSON structure:
    # [{"name": "Bankdrücken", "sets": 4, "reps": "8-10", "target_weight": 80}]
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer)  # 0=Mon, 6=Sun
    order_in_rotation: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="fitness_splits")

    def __repr__(self) -> str:
        return f"<FitnessSplit id={self.id} name={self.name!r}>"


# ─── Phase 5.4 — Shopping Defaults ───────────────────────────────────────────

class ShoppingDefault(Base):
    __tablename__ = "shopping_defaults"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="shopping_defaults")

    def __repr__(self) -> str:
        return f"<ShoppingDefault id={self.id} title={self.title!r}>"


# ─── Phase 7.1 — Achievements ─────────────────────────────────────────────────

class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    emoji: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    condition_type: Mapped[str] = mapped_column(Text, nullable=False)
    condition_value: Mapped[int] = mapped_column(Integer, nullable=False)

    user_achievements: Mapped[list["UserAchievement"]] = relationship(back_populates="achievement")

    def __repr__(self) -> str:
        return f"<Achievement id={self.id} key={self.key!r}>"


class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_id: Mapped[int] = mapped_column(Integer, ForeignKey("achievements.id"), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    achievement: Mapped["Achievement"] = relationship(back_populates="user_achievements")

    def __repr__(self) -> str:
        return f"<UserAchievement user_id={self.user_id} achievement_id={self.achievement_id}>"
