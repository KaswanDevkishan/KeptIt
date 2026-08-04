import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from app.core.config import Settings, get_settings


class PasswordResetEmailSender(Protocol):
    def send_password_reset(self, email: str, raw_token: str) -> None: ...


class DevelopmentFileEmailSender:
    """Append reset deliveries to an ignored, developer-only outbox."""

    def __init__(self, reset_url: str, outbox_path: Path) -> None:
        self.reset_url = reset_url
        self.outbox_path = outbox_path

    def send_password_reset(self, email: str, raw_token: str) -> None:
        self.outbox_path.parent.mkdir(parents=True, exist_ok=True)
        self.outbox_path.parent.chmod(0o700)
        self.outbox_path.touch(mode=0o600, exist_ok=True)
        self.outbox_path.chmod(0o600)
        reset_link = f"{self.reset_url}#token={quote(raw_token, safe='')}"
        with self.outbox_path.open("a", encoding="utf-8") as outbox:
            outbox.write(json.dumps({"email": email, "reset_url": reset_link}) + "\n")


class DisabledEmailSender:
    def send_password_reset(self, email: str, raw_token: str) -> None:
        del email, raw_token


def build_email_sender(settings: Settings) -> PasswordResetEmailSender:
    if settings.email_backend == "development_file":
        return DevelopmentFileEmailSender(
            str(settings.frontend_password_reset_url), settings.development_email_outbox_path
        )
    return DisabledEmailSender()


def get_email_sender() -> PasswordResetEmailSender:
    return build_email_sender(get_settings())


EmailSenderFactory = Callable[[], PasswordResetEmailSender]
