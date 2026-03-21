"""Field-level encryption for sensitive data.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
Key is derived from ENCRYPTION_KEY env var via PBKDF2.

Encrypted fields are stored as base64 strings prefixed with 'enc:'.
This allows gradual migration — unencrypted values work transparently.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

ENCRYPTION_PREFIX = "enc:"
_SALT = b"personal-os-field-encryption-v1"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet | None:
    """Derive a Fernet key from the ENCRYPTION_KEY env var."""
    raw_key = os.getenv("ENCRYPTION_KEY", "")
    if not raw_key:
        logger.warning("ENCRYPTION_KEY not set — field encryption disabled")
        return None

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    derived = kdf.derive(raw_key.encode("utf-8"))
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value. Returns prefixed ciphertext or plaintext if no key."""
    if not plaintext:
        return plaintext

    f = _get_fernet()
    if f is None:
        return plaintext

    encrypted = f.encrypt(plaintext.encode("utf-8"))
    return ENCRYPTION_PREFIX + encrypted.decode("utf-8")


def decrypt_value(stored: str) -> str:
    """Decrypt a stored value. Handles both encrypted and plaintext values."""
    if not stored:
        return stored

    if not stored.startswith(ENCRYPTION_PREFIX):
        return stored  # Not encrypted — return as-is

    f = _get_fernet()
    if f is None:
        logger.error("Cannot decrypt: ENCRYPTION_KEY not set")
        return "[ENCRYPTED]"

    try:
        ciphertext = stored[len(ENCRYPTION_PREFIX):].encode("utf-8")
        return f.decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        logger.error("Decryption failed — invalid token or wrong key")
        return "[DECRYPTION_ERROR]"


def is_encrypted(value: str) -> bool:
    """Check if a value is already encrypted."""
    return bool(value) and value.startswith(ENCRYPTION_PREFIX)


def hash_value(value: str) -> str:
    """One-way hash for values that only need equality checks (e.g. API tokens)."""
    return hashlib.sha256(
        (value + os.getenv("ENCRYPTION_KEY", "")).encode("utf-8")
    ).hexdigest()


# ── Bulk migration helpers ───────────────────────────────────────────────────

async def encrypt_existing_contacts(session) -> int:
    """Encrypt phone/email fields on existing Contact records."""
    from sqlalchemy import select
    from bot.database.models import Contact

    result = await session.execute(select(Contact))
    contacts = result.scalars().all()
    count = 0

    for contact in contacts:
        changed = False
        if contact.phone and not is_encrypted(contact.phone):
            contact.phone = encrypt_value(contact.phone)
            changed = True
        if contact.email and not is_encrypted(contact.email):
            contact.email = encrypt_value(contact.email)
            changed = True
        if changed:
            count += 1

    if count:
        await session.flush()
    return count


async def encrypt_existing_finance(session) -> int:
    """Encrypt description fields on financial transactions."""
    from sqlalchemy import select
    from bot.database.models import FinancialTransaction

    result = await session.execute(select(FinancialTransaction))
    txns = result.scalars().all()
    count = 0

    for txn in txns:
        if txn.description and not is_encrypted(txn.description):
            txn.description = encrypt_value(txn.description)
            count += 1

    if count:
        await session.flush()
    return count
