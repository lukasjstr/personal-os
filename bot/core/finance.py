"""Financial Dimension — expense/income logging, budget tracking, monthly summary."""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Budget, FinancialTransaction


CATEGORY_ALIASES: dict[str, str] = {
    # Essen
    "essen": "essen", "food": "essen", "restaurant": "essen", "kaffee": "essen",
    "grocery": "essen", "supermarkt": "essen", "lebensmittel": "essen",
    # Fitness
    "fitness": "fitness", "gym": "fitness", "sport": "fitness", "training": "fitness",
    "supplement": "fitness", "protein": "fitness",
    # Bildung
    "bildung": "bildung", "kurs": "bildung", "buch": "bildung", "udemy": "bildung",
    "weiterbildung": "bildung", "lernen": "bildung",
    # Abonnements
    "abo": "abonnements", "subscription": "abonnements", "netflix": "abonnements",
    "spotify": "abonnements", "abonnements": "abonnements",
    # Transport
    "transport": "transport", "bvg": "transport", "db": "transport", "zug": "transport",
    "taxi": "transport", "uber": "transport", "tanken": "transport",
    # Unterhaltung
    "unterhaltung": "unterhaltung", "kino": "unterhaltung", "konzert": "unterhaltung",
    "spiel": "unterhaltung",
    # Shopping
    "shopping": "shopping", "kleidung": "shopping", "amazon": "shopping",
    "elektronik": "shopping",
    # Gesundheit
    "gesundheit": "gesundheit", "arzt": "gesundheit", "apotheke": "gesundheit",
    "medikament": "gesundheit",
    # Wohnen
    "wohnen": "wohnen", "miete": "wohnen", "strom": "wohnen", "internet": "wohnen",
    "versicherung": "wohnen",
}


def normalize_category(raw: str) -> str:
    """Map free-form category text to one of the standard categories."""
    key = raw.lower().strip()
    return CATEGORY_ALIASES.get(key, "sonstiges")


async def log_expense(
    session: AsyncSession,
    user_id: int,
    amount: float,
    category: str,
    description: str,
    transaction_date: Optional[date] = None,
    is_recurring: bool = False,
) -> dict:
    """Log an expense and return budget status for the category."""
    cat = normalize_category(category)
    tx_date = transaction_date or date.today()

    tx = FinancialTransaction(
        user_id=user_id,
        amount=abs(amount),
        type="expense",
        category=cat,
        description=description,
        transaction_date=tx_date,
        is_recurring=is_recurring,
    )
    session.add(tx)
    await session.flush()

    # Check budget
    budget = await _get_budget(session, user_id, cat)
    month_spent = await _month_total(session, user_id, cat, tx_date)

    result = {
        "id": tx.id,
        "amount": amount,
        "category": cat,
        "description": description,
        "date": str(tx_date),
    }
    if budget:
        pct = min(100, int(month_spent / budget.monthly_limit * 100))
        remaining = budget.monthly_limit - month_spent
        result["budget_status"] = f"{month_spent:.0f}/{budget.monthly_limit:.0f}€ ({pct}%) — noch {max(0, remaining):.0f}€ übrig"
        if pct >= 100:
            result["budget_warning"] = f"🔴 Budget '{cat}' überschritten!"
        elif pct >= 90:
            result["budget_warning"] = f"⚠️ Budget '{cat}' fast aufgebraucht!"
    return result


async def log_income(
    session: AsyncSession,
    user_id: int,
    amount: float,
    source: str,
    transaction_date: Optional[date] = None,
) -> dict:
    """Log income."""
    tx_date = transaction_date or date.today()
    tx = FinancialTransaction(
        user_id=user_id,
        amount=abs(amount),
        type="income",
        category="einnahmen",
        description=source,
        transaction_date=tx_date,
    )
    session.add(tx)
    await session.flush()
    return {"id": tx.id, "amount": amount, "source": source, "date": str(tx_date)}


async def set_budget(
    session: AsyncSession,
    user_id: int,
    category: str,
    monthly_limit: float,
) -> dict:
    """Create or update a monthly budget for a category."""
    cat = normalize_category(category)
    existing = await _get_budget(session, user_id, cat)
    if existing:
        existing.monthly_limit = monthly_limit
        await session.flush()
        return {"updated": True, "category": cat, "monthly_limit": monthly_limit}
    budget = Budget(user_id=user_id, category=cat, monthly_limit=monthly_limit)
    session.add(budget)
    await session.flush()
    return {"created": True, "category": cat, "monthly_limit": monthly_limit}


async def get_financial_summary(session: AsyncSession, user_id: int) -> dict:
    """Return current month's income, expenses by category, and budget status."""
    today = date.today()
    month = today.month
    year = today.year

    # All transactions this month
    result = await session.execute(
        select(FinancialTransaction).where(and_(
            FinancialTransaction.user_id == user_id,
            extract("month", FinancialTransaction.transaction_date) == month,
            extract("year", FinancialTransaction.transaction_date) == year,
        )).order_by(FinancialTransaction.transaction_date.desc())
    )
    txs = result.scalars().all()

    total_income = sum(t.amount for t in txs if t.type == "income")
    total_expenses = sum(t.amount for t in txs if t.type == "expense")

    # Group by category
    by_category: dict[str, float] = {}
    for t in txs:
        if t.type == "expense":
            by_category[t.category] = by_category.get(t.category, 0) + t.amount

    # Load budgets
    budget_result = await session.execute(
        select(Budget).where(Budget.user_id == user_id)
    )
    budgets = {b.category: b.monthly_limit for b in budget_result.scalars().all()}

    category_lines = []
    for cat, spent in sorted(by_category.items(), key=lambda x: -x[1]):
        limit = budgets.get(cat)
        if limit:
            pct = min(100, int(spent / limit * 100))
            icon = "🔴" if pct >= 100 else "🟡" if pct >= 80 else "🟢"
            category_lines.append(f"{icon} {cat}: {spent:.0f}/{limit:.0f}€ ({pct}%)")
        else:
            category_lines.append(f"  {cat}: {spent:.0f}€")

    balance = total_income - total_expenses
    savings_rate = (balance / total_income * 100) if total_income > 0 else 0

    return {
        "month": f"{today.strftime('%B %Y')}",
        "total_income": total_income,
        "total_expenses": total_expenses,
        "balance": balance,
        "savings_rate": round(savings_rate, 1),
        "by_category": by_category,
        "category_lines": category_lines,
        "recent_transactions": [
            {"amount": t.amount, "type": t.type, "category": t.category,
             "description": t.description, "date": str(t.transaction_date)}
            for t in txs[:10]
        ],
    }


async def _get_budget(session: AsyncSession, user_id: int, category: str) -> Optional[Budget]:
    result = await session.execute(
        select(Budget).where(and_(Budget.user_id == user_id, Budget.category == category))
    )
    return result.scalar_one_or_none()


async def _month_total(
    session: AsyncSession, user_id: int, category: str, ref_date: date
) -> float:
    result = await session.execute(
        select(func.sum(FinancialTransaction.amount)).where(and_(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.category == category,
            FinancialTransaction.type == "expense",
            extract("month", FinancialTransaction.transaction_date) == ref_date.month,
            extract("year", FinancialTransaction.transaction_date) == ref_date.year,
        ))
    )
    return float(result.scalar() or 0)


async def build_finance_context(session: AsyncSession, user_id: int) -> str:
    """Return a short finance summary for the AI context (<=10 lines)."""
    summary = await get_financial_summary(session, user_id)
    if summary["total_income"] == 0 and summary["total_expenses"] == 0:
        return ""

    lines = [f"=== FINANZEN {summary['month'].upper()} ==="]
    lines.append(f"  💰 Einnahmen: {summary['total_income']:.0f}€  |  Ausgaben: {summary['total_expenses']:.0f}€  |  Balance: {summary['balance']:+.0f}€")
    if summary["total_income"] > 0:
        lines.append(f"  📊 Sparquote: {summary['savings_rate']:.0f}%")
    for line in summary["category_lines"][:6]:
        lines.append(f"  {line}")
    return "\n".join(lines)
