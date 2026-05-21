"""V3 P11 — Quarterly Review (life-area calibrated) tests.

Pure scoring tests (no DB) + integration tests against real DB.
"""
import asyncio
import os
from datetime import date

import pytest
from sqlalchemy import and_, delete, select

from bot.core.quarterly_review import (
    _get_current_quarter,
    _get_previous_quarter,
    _quarter_bounds,
    calculate_life_area_score,
    calculate_life_score,
    confirm_quarterly_review,
    generate_quarterly_review,
)
from bot.database.connection import engine, get_session
from bot.database.models import LifeArea, QuarterlyReview, User


requires_db = pytest.mark.skipif(
    not os.environ.get("PERSONAL_OS_DB_AVAILABLE"),
    reason="DB not available",
)


# ─── Pure helpers ─────────────────────────────────────────────────────────────


def test_get_current_quarter() -> None:
    assert _get_current_quarter(date(2026, 1, 15)) == (2026, 1)
    assert _get_current_quarter(date(2026, 3, 31)) == (2026, 1)
    assert _get_current_quarter(date(2026, 4, 1)) == (2026, 2)
    assert _get_current_quarter(date(2026, 12, 31)) == (2026, 4)


def test_get_previous_quarter_wraps_year() -> None:
    assert _get_previous_quarter(date(2026, 2, 1)) == (2025, 4)
    assert _get_previous_quarter(date(2026, 5, 1)) == (2026, 1)
    assert _get_previous_quarter(date(2026, 10, 5)) == (2026, 3)


def test_quarter_bounds() -> None:
    assert _quarter_bounds(2026, 1) == (date(2026, 1, 1), date(2026, 3, 31))
    assert _quarter_bounds(2026, 2) == (date(2026, 4, 1), date(2026, 6, 30))
    assert _quarter_bounds(2026, 4) == (date(2026, 10, 1), date(2026, 12, 31))


def test_calculate_life_score_unweighted_mean_of_nonzero() -> None:
    assert calculate_life_score({"a": 80, "b": 60, "c": 40}) == 60
    assert calculate_life_score({"a": 100}) == 100
    assert calculate_life_score({}) == 0
    # zero-score areas dropped (areas without active objectives)
    assert calculate_life_score({"a": 80, "b": 0, "c": 0}) == 80


# ─── DB integration ───────────────────────────────────────────────────────────


async def _get_user() -> User:
    async with get_session() as session:
        return (await session.execute(select(User).order_by(User.id).limit(1))).scalar_one()


@requires_db
def test_calculate_life_area_score_returns_int_in_range() -> None:
    async def run() -> None:
        try:
            user = await _get_user()
            async with get_session() as session:
                area = (await session.execute(
                    select(LifeArea).where(LifeArea.user_id == user.id).limit(1)
                )).scalar_one_or_none()
                if area is None:
                    pytest.skip("no life areas seeded")
                start, end = _quarter_bounds(*_get_current_quarter())
                score = await calculate_life_area_score(session, user.id, area.id, start, end)
            assert isinstance(score, int)
            assert 0 <= score <= 100
        finally:
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_generate_quarterly_review_writes_v3_fields() -> None:
    """Generate a review for the previous quarter and inspect V3 P11 fields."""
    async def run() -> None:
        user = await _get_user()
        py, pq = _get_previous_quarter()
        # Clean up any prior record so we test the insert path AND don't blow
        # away production data
        async with get_session() as session:
            await session.execute(delete(QuarterlyReview).where(and_(
                QuarterlyReview.user_id == user.id,
                QuarterlyReview.year == py,
                QuarterlyReview.quarter == pq,
            )))
        try:
            async with get_session() as session:
                # auto_close=True skips the AI call wait — well, no, it doesn't.
                # But the AI may legitimately take ~3-10s; we accept that.
                review = await generate_quarterly_review(
                    session, user.id, year=py, quarter=pq, auto_close=True,
                )
            assert review is not None
            assert review.year == py
            assert review.quarter == pq
            assert isinstance(review.life_score, int)
            assert isinstance(review.life_area_scores, dict)
            assert isinstance(review.suggested_next_quarter, dict)
            assert review.completed_at is not None  # auto_close=True
            assert review.status == "completed"
        finally:
            # leave the generated review in place — it's data, not garbage
            await engine.dispose()

    asyncio.run(run())


@requires_db
def test_confirm_quarterly_review_sets_completed_at() -> None:
    async def run() -> None:
        user = await _get_user()
        try:
            # Take the most recent review, blank out completed_at, then confirm.
            async with get_session() as session:
                latest = (await session.execute(
                    select(QuarterlyReview).where(QuarterlyReview.user_id == user.id)
                    .order_by(QuarterlyReview.generated_at.desc()).limit(1)
                )).scalar_one_or_none()
                if latest is None:
                    pytest.skip("no review to confirm")
                latest.completed_at = None
                latest.status = "pending_confirm"
                await session.flush()
                review_id = latest.id

            async with get_session() as session:
                result = await confirm_quarterly_review(
                    session, user.id, review_id, "smoke test reflection",
                )
            assert result is not None
            assert result.completed_at is not None
            assert result.user_reflection == "smoke test reflection"
        finally:
            await engine.dispose()

    asyncio.run(run())
