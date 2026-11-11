"""Time-based one-time passwords (RFC 6238) and single-use recovery codes.

The implementation follows the parameters every mainstream authenticator app
accepts by default: HMAC-SHA1, 6 digits and a 30 second period.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode


TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
RECOVERY_CODE_COUNT = 8
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _time_step(timestamp: float) -> int:
    return int(timestamp // TOTP_PERIOD_SECONDS)


def _code_for_step(secret: str, step: int) -> str:
    padded_secret = secret + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded_secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def totp_code(secret: str, at_time: float | None = None) -> str:
    timestamp = time.time() if at_time is None else at_time
    return _code_for_step(secret, _time_step(timestamp))


def matching_totp_step(
    secret: str,
    code: str,
    at_time: float | None = None,
    window: int = 1,
    after_step: int | None = None,
) -> int | None:
    """Return the time step that produced ``code``, or ``None``.

    ``window`` tolerates small clock drift between server and phone.
    ``after_step`` rejects steps that were already used, so an intercepted code
    cannot be replayed while it is still inside the drift window.
    """
    timestamp = time.time() if at_time is None else at_time
    normalized_code = "".join(character for character in code if character in "0123456789")
    if len(normalized_code) != TOTP_DIGITS:
        return None
    current_step = _time_step(timestamp)
    matched = None
    for step in range(current_step - window, current_step + window + 1):
        if after_step is not None and step <= after_step:
            continue
        if hmac.compare_digest(_code_for_step(secret, step), normalized_code):
            matched = step
    return matched


def verify_totp(
    secret: str, code: str, at_time: float | None = None, window: int = 1
) -> bool:
    return matching_totp_step(secret, code, at_time=at_time, window=window) is not None


def provisioning_uri(secret: str, email: str) -> str:
    label = quote(f"BlueTide:{email}")
    query = urlencode(
        {
            "secret": secret,
            "issuer": "BlueTide",
            "algorithm": "SHA1",
            "digits": TOTP_DIGITS,
            "period": TOTP_PERIOD_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def normalize_recovery_code(code: str) -> str:
    return "".join(
        character
        for character in code.lower()
        if character.isascii() and character.isalnum()
    )


def hash_recovery_code(code: str) -> str:
    # Recovery codes carry ~49 bits of randomness each, so a fast unsalted
    # digest is enough; a slow password hash would add nothing but latency.
    return hashlib.sha256(normalize_recovery_code(code).encode("ascii")).hexdigest()


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def consume_recovery_code(stored_hashes: list[str], code: str) -> list[str] | None:
    """Return the remaining hashes when ``code`` is valid, otherwise ``None``."""
    candidate = hash_recovery_code(code)
    for index, stored in enumerate(stored_hashes):
        if hmac.compare_digest(stored, candidate):
            return stored_hashes[:index] + stored_hashes[index + 1 :]
    return None
