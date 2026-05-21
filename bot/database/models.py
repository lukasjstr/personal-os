"""SQLAlchemy ORM models for Personal OS — all 15 tables."""
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, func,
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
    ical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    goal_onboardings: Mapped[list["GoalOnboarding"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    push_subscriptions: Mapped[list["PushSubscription"]] = relationship(back_populates="user", cascade="all, delete-orphan")
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
    daily_suggestions: Mapped[list["DailySuggestion"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    documents: Mapped[list["UserDocument"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    autopilot_notifications: Mapped[list["AutopilotNotification"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    action_queue_items: Mapped[list["ActionQueueItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    okr_proposal_drafts: Mapped[list["OKRProposalDraft"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    proposal_calendar_slots: Mapped[list["ProposalCalendarSlot"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    node_relations: Mapped[list["NodeRelation"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    workout_logs: Mapped[list["WorkoutLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    daily_contexts: Mapped[list["DailyContext"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    evening_checkins: Mapped[list["EveningCheckin"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    financial_transactions: Mapped[list["FinancialTransaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    automation_rules: Mapped[list["AutomationRule"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    quarterly_reviews: Mapped[list["QuarterlyReview"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    commitments: Mapped[list["Commitment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    life_profile: Mapped[Optional["LifeProfile"]] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    learning_items: Mapped[list["LearningItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    learning_reviews: Mapped[list["LearningReview"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    life_areas: Mapped[list["LifeArea"]] = relationship(back_populates="user", cascade="all, delete-orphan")

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
    # V3 P08 — audit trail for cut/pause decisions
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paused_reason: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    # V3 P10 — mission layer link
    life_area_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("life_areas.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="objectives")
    life_area: Mapped[Optional["LifeArea"]] = relationship(back_populates="objectives")
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
    routine_impacts: Mapped[list["RoutineObjectiveImpact"]] = relationship(back_populates="objective", cascade="all, delete-orphan")

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
    # V3 P09 — Friday-Cut audit trail
    cancelled_reason: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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
    objective_impacts: Mapped[list["RoutineObjectiveImpact"]] = relationship(back_populates="routine", cascade="all, delete-orphan")

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
    external_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    external_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
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


class UserDocument(Base):
    __tablename__ = "user_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    emoji: Mapped[str] = mapped_column(String(10), nullable=False, default="📄")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="documents")

    def __repr__(self) -> str:
        return f"<UserDocument id={self.id} title={self.title!r}>"


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
    # V3 P07 — Escalation
    linked_objective_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="SET NULL"))
    severity: Mapped[str] = mapped_column(String(20), default="normal", server_default="normal", nullable=False)
    escalation_step: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, sent, cancelled, snoozed, failed
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

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


# ─── Workout Tracking ─────────────────────────────────────────────────────────

class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    exercise: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logged_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="workout_logs")

    def __repr__(self) -> str:
        return f"<WorkoutLog id={self.id} exercise={self.exercise!r} weight={self.weight_kg}>"


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


# ─── Phase 8.2 — Daily AI Suggestions ────────────────────────────────────────

class DailySuggestion(Base):
    __tablename__ = "daily_suggestions"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    suggestions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # suggestions JSONB structure:
    # {
    #   "fokus_heute": [{"task": "...", "begruendung": "..."}, ...],  # 3 items
    #   "tipp": "...",
    #   "streak_warnung": "..." or null,
    #   "dimension_check": "..." or null,
    # }
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="daily_suggestions")


# ─── Phase A1 — Autopilot Notifications ──────────────────────────────────────

class AutopilotNotification(Base):
    __tablename__ = "autopilot_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Types: task_nudge, plan_reminder, streak_warning, reflection_prompt, generic
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    # pending, acknowledged, snoozed, expired
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="autopilot")
    # optional reference to a linked object
    linked_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="autopilot_notifications")

    def __repr__(self) -> str:
        return f"<AutopilotNotification id={self.id} type={self.notification_type} status={self.status}>"


# ─── Phase A3 — Action Queue ──────────────────────────────────────────────────

class ActionQueueItem(Base):
    __tablename__ = "action_queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # States: planned → suggested → accepted → completed | snoozed
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", index=True)
    # Types: task, routine, event, suggestion
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, default="task")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    # optional link to a real task
    linked_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"))
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="action_queue_items")

    def __repr__(self) -> str:
        return f"<ActionQueueItem id={self.id} state={self.state} title={self.title!r}>"


    def __repr__(self) -> str:
        return f"<DailySuggestion user_id={self.user_id} date={self.date}>"


# ─── Phase B5 — Routine-Objective Impact Scoring ──────────────────────────────

class RoutineObjectiveImpact(Base):
    __tablename__ = "routine_objective_impacts"
    __table_args__ = (UniqueConstraint("routine_id", "objective_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    routine_id: Mapped[int] = mapped_column(Integer, ForeignKey("routines.id", ondelete="CASCADE"), nullable=False, index=True)
    objective_id: Mapped[int] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False, index=True)
    impact_score: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 1 (low) – 5 (high)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    routine: Mapped["Routine"] = relationship("Routine", back_populates="objective_impacts")
    objective: Mapped["Objective"] = relationship("Objective", back_populates="routine_impacts")

    def __repr__(self) -> str:
        return f"<RoutineObjectiveImpact routine={self.routine_id} objective={self.objective_id} score={self.impact_score}>"


# ─── Phase B3 — Objective Task Suggestions ────────────────────────────────────

class ObjectiveTaskSuggestion(Base):
    __tablename__ = "objective_task_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    objective_id: Mapped[int] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1=highest, 5=lowest
    reason: Mapped[Optional[str]] = mapped_column(Text)
    # pending → accepted | rejected
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    accepted_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    objective: Mapped["Objective"] = relationship("Objective", foreign_keys="[ObjectiveTaskSuggestion.objective_id]")

    def __repr__(self) -> str:
        return f"<ObjectiveTaskSuggestion id={self.id} status={self.status} title={self.title!r}>"


# ─── CORE-2A — Proposal Draft Persistence ─────────────────────────────────────

class OKRProposalDraft(Base):
    __tablename__ = "okr_proposal_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    draft_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    executed_objective_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('objectives.id', ondelete='SET NULL'), nullable=True)

    user: Mapped["User"] = relationship(back_populates="okr_proposal_drafts")
    calendar_slots: Mapped[list["ProposalCalendarSlot"]] = relationship(back_populates="proposal_draft", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<OKRProposalDraft id={self.id} user_id={self.user_id} status={self.status}>"


# ─── CORE-3A — Proposal Calendar Slot Scaffold ───────────────────────────────

class ProposalCalendarSlot(Base):
    __tablename__ = "proposal_calendar_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    proposal_draft_id: Mapped[int] = mapped_column(Integer, ForeignKey("okr_proposal_drafts.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    slot_type: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed_block", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="proposal_calendar_slots")
    proposal_draft: Mapped["OKRProposalDraft"] = relationship(back_populates="calendar_slots")

    def __repr__(self) -> str:
        return f"<ProposalCalendarSlot id={self.id} draft={self.proposal_draft_id} status={self.status}>"


# ─── Epic 1.1 — Dependency Graph Foundation ──────────────────────────────────

VALID_NODE_TYPES = {"task", "objective", "key_result"}
VALID_RELATION_TYPES = {"blocks", "depends_on", "contributes_to", "unlocks"}


class NodeRelation(Base):
    """Explicit directed edge in the dependency graph between any two nodes.

    Supported node types: task, objective, key_result
    Supported relation types: blocks, depends_on, contributes_to, unlocks

    A→blocks→B   means A must be done before B can proceed.
    A→depends_on→B means A cannot proceed until B is done.
    A→contributes_to→B means A's completion pushes progress on B.
    A→unlocks→B  means A's completion makes B available.
    """
    __tablename__ = "node_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Source node
    from_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Target node
    to_type: Mapped[str] = mapped_column(String(32), nullable=False)
    to_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relation semantics
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Optional human-readable note for auditability
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="node_relations")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "from_type", "from_id", "to_type", "to_id", "relation_type",
            name="uq_node_relation",
        ),
        Index("ix_node_relations_from", "user_id", "from_type", "from_id"),
        Index("ix_node_relations_to", "user_id", "to_type", "to_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<NodeRelation id={self.id} "
            f"{self.from_type}:{self.from_id} -{self.relation_type}-> "
            f"{self.to_type}:{self.to_id}>"
        )


class DailyContext(Base):
    """Daily state snapshot: energy, available time, focus area.
    Collected via Telegram morning flow; powers Smart Daily Plan."""
    __tablename__ = "daily_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    energy: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)       # 1-10
    hours_available: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    focus_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # category or free text
    mood_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # AI-generated daily plan (top 3 tasks + reasoning)
    daily_plan: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="daily_contexts")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_context_user_date"),
    )


class EveningCheckin(Base):
    """Evening check-in: what was done, gaps, tomorrow prep."""
    __tablename__ = "evening_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tasks_planned: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    completed_task_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    win_of_day: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blocker: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # AI gap analysis + tomorrow plan
    gap_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="evening_checkins")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_evening_checkin_user_date"),
    )


# ─── Financial Dimension ─────────────────────────────────────────────────────

FINANCE_CATEGORIES = [
    "essen", "fitness", "bildung", "abonnements", "transport",
    "unterhaltung", "shopping", "gesundheit", "wohnen", "sonstiges",
]


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # always positive
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # income | expense
    category: Mapped[str] = mapped_column(String(60), nullable=False, default="sonstiges")
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="financial_transactions")

    def __repr__(self) -> str:
        return f"<FinancialTransaction id={self.id} type={self.type} amount={self.amount}>"


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    monthly_limit: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="budgets")

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_budget_user_category"),
    )

    def __repr__(self) -> str:
        return f"<Budget id={self.id} category={self.category} limit={self.monthly_limit}>"


# ─── Feature 5 — Automation Rule Engine ──────────────────────────────────────

class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # trigger_types: workout_skipped | energy_low | kr_completed | sleep_low | routine_skipped | kr_at_risk | manual
    trigger_conditions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # action_types: send_message | create_task | reschedule_workout | suggest_routine | update_setting
    action_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="automation_rules")

    def __repr__(self) -> str:
        return f"<AutomationRule id={self.id} trigger={self.trigger_type} action={self.action_type}>"


# ─── Feature 6 — Quarterly Review ────────────────────────────────────────────

class QuarterlyReview(Base):
    __tablename__ = "quarterly_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "year", "quarter", name="uq_quarterly_review_user_year_quarter"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4
    quarter_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # "Q1 2026"
    life_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100
    objectives_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ai_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    highlights: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    challenges: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="completed")
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # V3 P11 — Life-area scoring + user sign-off
    life_area_scores: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    suggested_next_quarter: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    user_reflection: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    previous_life_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="quarterly_reviews")

    def __repr__(self) -> str:
        return f"<QuarterlyReview id={self.id} {self.quarter_label} score={self.life_score}>"


# ─── Feature 8 — Relationship Engine ─────────────────────────────────────────

class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    relationship_type: Mapped[str] = mapped_column(String(60), default="friend")  # friend|family|colleague|mentor|partner
    contact_frequency_days: Mapped[int] = mapped_column(Integer, default=30)
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    birthday: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="contacts")
    interactions: Mapped[list["Interaction"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    commitments: Mapped[list["Commitment"]] = relationship(back_populates="contact")

    def __repr__(self) -> str:
        return f"<Contact id={self.id} name={self.name!r} type={self.relationship_type}>"


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id: Mapped[int] = mapped_column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False, index=True)
    interaction_type: Mapped[str] = mapped_column(String(60), nullable=False)  # call|message|meeting|email|other
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interacted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="interactions")
    contact: Mapped["Contact"] = relationship(back_populates="interactions")

    def __repr__(self) -> str:
        return f"<Interaction id={self.id} contact_id={self.contact_id} type={self.interaction_type}>"


class Commitment(Base):
    __tablename__ = "commitments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|done|overdue
    reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="commitments")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="commitments")

    def __repr__(self) -> str:
        return f"<Commitment id={self.id} status={self.status} desc={self.description[:40]!r}>"


# ─── V3 P10 — Mission Layer: 9 Life Areas ────────────────────────────────────

class LifeArea(Base):
    """Top-level mission layer — Lukas's 9 life areas (Money, Physical, …).

    Each Objective links to one LifeArea so the strategy hierarchy is:
      LifeArea (5+ yr vision) → Objective (quarter) → KR (week) → Task/Log.
    """
    __tablename__ = "life_areas"
    __table_args__ = (
        UniqueConstraint("user_id", "short_code", name="uq_life_areas_user_short"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    short_code: Mapped[str] = mapped_column(String(40), nullable=False)
    vision: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_state: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1 (highest) - 10
    color_hex: Mapped[str] = mapped_column(String(9), default="#888780")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="life_areas")
    objectives: Mapped[list["Objective"]] = relationship(back_populates="life_area")

    def __repr__(self) -> str:
        return f"<LifeArea id={self.id} user={self.user_id} {self.short_code}>"


# ─── Feature 11 — Life Profile (Langzeit-Gedächtnis) ─────────────────────────

class LifeProfile(Base):
    """Persistent compressed life summary updated weekly via GPT-4o."""
    __tablename__ = "life_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_life_profile_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    strengths: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    patterns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    current_focus: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_updated: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    update_count: Mapped[int] = mapped_column(Integer, default=0)
    # Hand-curated identity layer (V3 P02). Structure documented in bot/core/life_profile.py.
    bedrock: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    bedrock_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Versioned snapshots, newest last. Each entry: {"snapshot": {...}, "ts": iso8601}
    bedrock_history: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="life_profile")

    def __repr__(self) -> str:
        return f"<LifeProfile user_id={self.user_id} updated={self.last_updated}>"


# ─── Feature 6 — Knowledge Management ────────────────────────────────────────

class LearningItem(Base):
    """Spaced-repetition learning item (book, article, concept, skill, note)."""
    __tablename__ = "learning_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_type: Mapped[str] = mapped_column(String(60), nullable=False, default="note")  # book|article|concept|skill|note
    source: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    skill_level: Mapped[int] = mapped_column(Integer, default=1)  # 1-5 for skills
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)  # SM-2 ease factor
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="learning_items")
    reviews: Mapped[list["LearningReview"]] = relationship(back_populates="item", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<LearningItem id={self.id} type={self.item_type} title={self.title!r}>"


class LearningReview(Base):
    """SM-2 spaced repetition review record."""
    __tablename__ = "learning_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("learning_items.id", ondelete="CASCADE"), nullable=False, index=True)
    quality: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-5 SM-2 quality
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="learning_reviews")
    item: Mapped["LearningItem"] = relationship(back_populates="reviews")

    def __repr__(self) -> str:
        return f"<LearningReview id={self.id} item_id={self.item_id} quality={self.quality}>"


# ─── Goal Onboarding ─────────────────────────────────────────────────────────

class GoalOnboarding(Base):
    """Conversational goal onboarding — adaptive coaching dialog for new goals."""
    __tablename__ = "goal_onboardings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress", index=True)
    # in_progress, plan_review, completed, cancelled
    current_step: Mapped[int] = mapped_column(Integer, default=1)
    goal_input: Mapped[str] = mapped_column(Text, nullable=False)
    raw_answers: Mapped[dict] = mapped_column(JSON, default=dict)
    draft_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    proposal_draft_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("okr_proposal_drafts.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="goal_onboardings")

    def __repr__(self) -> str:
        return f"<GoalOnboarding id={self.id} user_id={self.user_id} status={self.status}>"


# ─── Push Subscriptions ──────────────────────────────────────────────────────

class PushSubscription(Base):
    """Web Push subscription for PWA notifications."""
    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "endpoint", name="uq_push_sub_user_endpoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="push_subscriptions")

    def __repr__(self) -> str:
        return f"<PushSubscription id={self.id} user_id={self.user_id}>"
