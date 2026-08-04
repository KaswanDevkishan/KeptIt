from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 1024

_hasher = PasswordHasher()
_DUMMY_PASSWORD_HASH = _hasher.hash("keptit-dummy-password-not-used-for-login")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def perform_dummy_verification(password: str) -> None:
    """Spend normal verification work when no account exists to reduce timing leakage."""
    verify_password(_DUMMY_PASSWORD_HASH, password)
