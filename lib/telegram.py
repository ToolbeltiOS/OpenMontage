"""Telegram, for the one place a human is in the loop.

WHY ONE MODULE
--------------
Four stages talk to Telegram — the script gate, a stage failure, the publish
hand-off, the Tuesday metrics — and three of them run unattended at night. A
notifier that raises in one of them stops a render that was going to finish;
a notifier that swallows everything means a failed week looks exactly like a
quiet one. The difference belongs in one place:

    send / send_document      best effort. A notification that cannot be sent
                              is logged and the caller carries on.
    require / await_reply     load-bearing. These are the gate, and if the
                              gate cannot be reached the run must stop, so
                              they raise.

CREDENTIALS come from ~/Developer/wak3up-docs/.env — outside this repository,
because the repository is pushed and the token is not. TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID; both must be set or nothing here works.

    python3 lib/telegram.py --check
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

#: Outside the repository on purpose.
ENV_PATH = Path.home() / "Developer" / "wak3up-docs" / ".env"
API = "https://api.telegram.org/bot{token}/{method}"

#: Telegram's own limit on a message. A script goes as a document; a summary
#: is trimmed rather than split, because half a summary in two messages is
#: worse than a short one.
MAX_MESSAGE = 4096


class TelegramNotConfigured(RuntimeError):
    """No token or no chat id. Raised by the load-bearing calls only."""


def credentials(env_path: Path = ENV_PATH) -> tuple[str, str]:
    """(token, chat id), from the environment or the out-of-repo .env."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if (not token or not chat) and env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key.strip() == "TELEGRAM_BOT_TOKEN" and not token:
                token = value
            elif key.strip() == "TELEGRAM_CHAT_ID" and not chat:
                chat = value
    return token, chat


def configured(env_path: Path = ENV_PATH) -> bool:
    token, chat = credentials(env_path)
    return bool(token and chat)


def _call(method: str, data: dict[str, Any] | None = None,
          files: dict[str, Any] | None = None, timeout: int = 60) -> dict:
    import requests

    token, chat = credentials()
    if not token or not chat:
        raise TelegramNotConfigured(
            f"TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set, in the "
            f"environment or in {ENV_PATH}")
    payload = {"chat_id": chat, **(data or {})}
    response = requests.post(API.format(token=token, method=method),
                             data=payload, files=files, timeout=timeout)
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"telegram {method} failed: "
                           f"{body.get('description', response.text[:200])}")
    return body["result"]


def send(text: str, *, quiet: bool = False) -> dict | None:
    """Best effort. Returns None if it could not be sent."""
    try:
        return _call("sendMessage", {
            "text": text[:MAX_MESSAGE], "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": quiet})
    except Exception as error:
        print(f"telegram: {error}", file=sys.stderr)
        return None


def send_document(path: str | Path, caption: str = "") -> dict | None:
    """Best effort, for a script or a report."""
    path = Path(path)
    try:
        with path.open("rb") as handle:
            return _call("sendDocument", {"caption": caption[:1024]},
                         files={"document": (path.name, handle)}, timeout=180)
    except Exception as error:
        print(f"telegram: {error}", file=sys.stderr)
        return None


def send_photo(path: str | Path, caption: str = "") -> dict | None:
    path = Path(path)
    try:
        with path.open("rb") as handle:
            return _call("sendPhoto", {"caption": caption[:1024]},
                         files={"photo": (path.name, handle)}, timeout=180)
    except Exception as error:
        print(f"telegram: {error}", file=sys.stderr)
        return None


def require(text: str) -> dict:
    """Load-bearing. Raises if it cannot be delivered."""
    return _call("sendMessage", {"text": text[:MAX_MESSAGE],
                                 "parse_mode": "HTML",
                                 "disable_web_page_preview": True})


def updates(offset: int | None = None, timeout: int = 50) -> list[dict]:
    data: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        data["offset"] = offset
    return _call("getUpdates", data, timeout=timeout + 20)


def drain(env_path: Path = ENV_PATH) -> int:
    """Mark everything already waiting as read, and return the next offset.

    Called before a gate posts its question. Without it, a reply to LAST
    week's gate — or any message sent to the bot in between — is read as the
    answer to this one.
    """
    pending = updates(timeout=0)
    return (pending[-1]["update_id"] + 1) if pending else 0


def await_reply(offset: int, hours: float,
                poll_seconds: int = 50) -> tuple[str, str]:
    """Wait for a human. Returns (verdict, the text they sent).

    The verdict is "ok", "no", "notes" or "timeout". A timeout is NOT an
    approval: the caller aborts. Silence at two in the morning means the
    person is asleep, and a film that publishes because nobody said no is the
    thing this gate exists to prevent.
    """
    import datetime

    deadline = time.monotonic() + hours * 3600
    while time.monotonic() < deadline:
        remaining = max(1, min(poll_seconds, int(deadline - time.monotonic())))
        try:
            batch = updates(offset, timeout=remaining)
        except Exception as error:
            print(f"telegram poll: {error}", file=sys.stderr)
            time.sleep(5)
            continue
        for update in batch:
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("channel_post") or {}
            text = (message.get("text") or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in ("ok", "okay", "yes", "y", "go", "approve", "approved"):
                return "ok", text
            if lowered in ("no", "n", "stop", "abort", "cancel"):
                return "no", text
            return "notes", text
    return "timeout", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--send", default=None)
    args = ap.parse_args()

    token, chat = credentials()
    if args.check:
        print(f"env file: {ENV_PATH} ({'present' if ENV_PATH.exists() else 'MISSING'})")
        print(f"TELEGRAM_BOT_TOKEN: {'set' if token else 'NOT SET'}")
        print(f"TELEGRAM_CHAT_ID:   {'set' if chat else 'NOT SET'}")
        if not (token and chat):
            print("\nnot configured — the script gate cannot run")
            return 1
        try:
            me = _call("getMe", timeout=20)
            print(f"bot: @{me.get('username')} ({me.get('first_name')})")
        except Exception as error:
            print(f"reachable? NO — {error}")
            return 1
        print("reachable: yes")
        return 0

    if args.send:
        print("sent" if send(args.send) else "not sent")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
