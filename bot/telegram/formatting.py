"""Telegram message formatting helpers."""


def escape_md(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special = r"\_*[]()~`>#+-=|{}.!"
    for char in special:
        text = text.replace(char, f"\\{char}")
    return text


def format_progress_bar(current: float, target: float, width: int = 10) -> str:
    """Return a text progress bar."""
    if target <= 0:
        return "░" * width
    pct = min(1.0, current / target)
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


def truncate(text: str, max_length: int = 4000) -> str:
    """Truncate message to Telegram's limit."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
