"""SQLAlchemy ORM models for Personal OS."""
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSON
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
    morning_brief_time: Mapped[str] = mapped_column(String(5), default="06:30")
    evening_review_time: Mapped[str] = mapped_column(String(5), default="21:00")
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


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), default="personal")  # health, business, personal, fitness, finance
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, paused, abandoned
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="objectives")
    key_results: Mapped[list["KeyResult"]] = relationship(back_populates="objective", cascade="all, delete-orphan")
    brain_dumps: Mapped[list["BrainDump"]] = relationship(back_populates="linked_objective")


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


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_result_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("key_results.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo, in_progress, done, cancelled
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="tasks")
    key_result: Mapped[Optional["KeyResult"]] = relationship(back_populates="tasks")
    logs: Mapped[list["Log"]] = relationship(back_populates="task")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="linked_task")


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


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    schedule_cron: Mapped[str] = mapped_column(String(100), nullable=False)  # cron expression
    frequency_human: Mapped[str] = mapped_column(String(100))  # "Jeden Dienstag", "Täglich"
    linked_key_result_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("key_results.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="routines")
    linked_key_result: Mapped[Optional["KeyResult"]] = relationship(back_populates="routines")
    completions: Mapped[list["RoutineCompletion"]] = relationship(back_populates="routine", cascade="all, delete-orphan")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(back_populates="linked_routine")


class RoutineCompletion(Base):
    __tablename__ = "routine_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(Integer, ForeignKey("routines.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    logged_via: Mapped[str] = mapped_column(String(20), default="telegram")  # telegram, auto, dashboard
    notes: Mapped[Optional[str]] = mapped_column(Text)

    routine: Mapped["Routine"] = relationship(back_populates="completions")
    user: Mapped["User"] = relationship(back_populates="routine_completions")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    event_type: Mapped[str] = mapped_column(String(30), default="reminder")  # training, meeting, routine, deadline, reminder
    linked_task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"))
    linked_routine_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("routines.id", ondelete="SET NULL"))
    ical_uid: Mapped[str] = mapped_column(String(255), unique=True, default=lambda: f"{uuid.uuid4()}@personal-os")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="calendar_events")
    linked_task: Mapped[Optional["Task"]] = relationship(back_populates="calendar_events")
    linked_routine: Mapped[Optional["Routine"]] = relationship(back_populates="calendar_events")


class BrainDump(Base):
    __tablename__ = "brain_dumps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_interpretation: Mapped[Optional[str]] = mapped_column(Text)
    linked_objective_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("objectives.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="brain_dumps")
    linked_objective: Mapped[Optional["Objective"]] = relationship(back_populates="brain_dumps")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    user: Mapped["User"] = relationship(back_populates="conversations")
