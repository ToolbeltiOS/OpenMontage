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

#: How many times a multipart upload is tried before it is called a failure.
#:
#: The first rehearsal on the dedicated bot lost one upload to
#: ConnectionResetError(54) — a reset peer part-way through a multipart POST,
#: the ordinary way a several-hundred-kilobyte body fails on a domestic
#: connection. Nothing was wrong with the file or the token, and the next
#: attempt would have worked. A text message is one small request and is left
#: alone; an upload gets three tries with a widening gap.
UPLOAD_ATTEMPTS = 3
UPLOAD_RETRY_SECONDS = 2.0


class TelegramNotConfigured(RuntimeError):
    """No token or no chat id. Raised by the load-bearing calls only."""


def credentials(env_path: Path = ENV_PATH) -> tuple[str, str]:
    """(token, chat id), from the environment or the out-of-repo .env.

    The documentary's own token wins if there is one: see `dedicated()` for
    why a shared bot cannot be made reliable.
    """
    token = (os.environ.get(DOCS_TOKEN_VAR, "")
             or os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if (not token or not chat) and env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key.strip() == DOCS_TOKEN_VAR and value:
                token = value               # the dedicated one always wins
            elif key.strip() == "TELEGRAM_BOT_TOKEN" and not token:
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


def escape(text: str) -> str:
    """For text going inside an HTML message rather than being one.

    Everything here posts with parse_mode HTML, so a script containing a bare
    "<" or an ampersand is rejected by Telegram with "can't parse entities"
    — a load-bearing message that raises on the content of the film.
    """
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))


def _upload(method: str, field: str, path: Path, caption: str) -> dict | None:
    """One multipart POST, retried through transport failures.

    The handle is reopened per attempt: a body that was half-read when the
    peer reset cannot be re-sent from the same file object.

    Only transport errors are retried. A rejection from Telegram itself — a
    file too large, a bad chat id — is deterministic, and retrying it twice
    more only delays the log line.
    """
    import requests

    for attempt in range(1, UPLOAD_ATTEMPTS + 1):
        try:
            with path.open("rb") as handle:
                return _call(method, {"caption": caption[:1024]},
                             files={field: (path.name, handle)}, timeout=180)
        except requests.exceptions.RequestException as error:
            last = error
            if attempt < UPLOAD_ATTEMPTS:
                print(f"telegram: {path.name} upload attempt {attempt} "
                      f"failed ({error}); retrying", file=sys.stderr)
                time.sleep(UPLOAD_RETRY_SECONDS * attempt)
        except Exception as error:
            print(f"telegram: {error}", file=sys.stderr)
            return None
    print(f"telegram: {path.name} failed {UPLOAD_ATTEMPTS} uploads: {last}",
          file=sys.stderr)
    return None


def send_document(path: str | Path, caption: str = "") -> dict | None:
    """Best effort, for a script or a report."""
    return _upload("sendDocument", "document", Path(path), caption)


def send_photo(path: str | Path, caption: str = "") -> dict | None:
    return _upload("sendPhoto", "photo", Path(path), caption)


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


#: The documentary's own bot. Set this and the gate knows nothing else is
#: polling; set only TELEGRAM_BOT_TOKEN and it warns, every time.
DOCS_TOKEN_VAR = "TELEGRAM_DOCS_BOT_TOKEN"


def dedicated() -> tuple[bool, str]:
    """Is this a bot nothing else polls?

    It cannot be measured, so it is DECLARED. A competing consumer is
    invisible through this API: it confirms the update and the update simply
    is not there any more, which looks exactly like nobody having written
    one. No probe distinguishes those, so the configuration has to.

    Setting TELEGRAM_DOCS_BOT_TOKEN is the declaration. Using the Shorts bot
    then becomes a thing somebody chose rather than a thing that happened.
    """
    if os.environ.get(DOCS_TOKEN_VAR):
        return True, f"{DOCS_TOKEN_VAR} is set"
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            key, _, value = line.strip().partition("=")
            if value.strip().strip('"').strip("'"):
                env[key.strip()] = True
    if env.get(DOCS_TOKEN_VAR):
        return True, f"{DOCS_TOKEN_VAR} is set"
    return False, (
        f"no {DOCS_TOKEN_VAR}: the gate is using a bot that may be shared. "
        f"A second poller confirms the update and it vanishes, which through "
        f"this API is indistinguishable from nobody having replied — so it "
        f"cannot be detected, only avoided.")


def exclusive(probe_seconds: int = 8) -> tuple[bool, str]:
    """Can this process read the chat, and does anything else want to?

    Checked BEFORE the gate posts, because a gate that posts and then cannot
    read has wasted twelve hours and blamed a person who answered.

    A webhook is detected with certainty. A competing poller is NOT, and the
    measurement says so: 995 polls over five minutes against a bot the Shorts
    handler polls every five minutes produced zero conflicts, because both
    pollers return in milliseconds and rarely overlap. The handler was caught
    running in the same window by watching for the process. A probe that
    passes here means a webhook is not set and nothing more.
    """
    import requests

    token, chat = credentials()
    if not token or not chat:
        return False, "no TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
    try:
        hook = requests.get(
            f"https://api.telegram.org/bot{token}/getWebhookInfo",
            timeout=30).json()
    except Exception as error:
        return False, f"could not reach Telegram: {error}"
    url = ((hook.get("result") or {}).get("url") or "")
    if url:
        return False, (f"a webhook is set ({url}) — getUpdates cannot be used "
                       f"while one is, so the gate could post and never read")
    try:
        updates(timeout=probe_seconds)
    except Exception as error:
        if "Conflict" in str(error):
            return False, (
                f"another process is polling this bot: {error}. The gate "
                f"would post and the other poller would consume the reply. "
                f"Give the documentary its own bot.")
        return False, f"getUpdates failed: {error}"

    own, why = dedicated()
    if not own:
        # not fatal: the gate still runs, and it says what it cannot promise
        print(f"telegram: {why}", file=sys.stderr)
        return True, f"no webhook; WARNING — {why}"
    return True, f"no webhook, and {why}"


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

    The verdict is "ok", "no", "notes", "timeout" or "unreadable".

    A TIMEOUT IS NOT AN APPROVAL: the caller aborts. Silence at two in the
    morning means the person is asleep, and a film that publishes because
    nobody said no is the thing this gate exists to prevent.

    AND "UNREADABLE" IS NOT A TIMEOUT. The first live rehearsal returned
    "timeout" while the owner was looking at their reply on screen.

    THE MECHANISM, measured rather than assumed, because the first account of
    it was wrong. The Shorts command handler polls the same bot token every
    five minutes from cron and CONFIRMS every update it reads, which removes
    it from the queue for everyone. Conflicts are rare — both pollers return
    in milliseconds when there is anything to return, so they rarely overlap
    — and the conflict is not the theft. It is the ENABLER of the theft: a
    poll terminated by Conflict used to back off five seconds, and five
    seconds is long enough for the handler to take the reply.

    So the backoff after a Conflict is short now, and the "unreadable"
    verdict below catches only the loud version of this. The quiet version —
    one stolen message, every poll succeeding, nothing in the logs — is
    indistinguishable from silence through this API, and the only real fix is
    a bot nothing else polls.
    """
    deadline = time.monotonic() + hours * 3600
    polls = failures = 0
    last_error = ""
    while time.monotonic() < deadline:
        remaining = max(1, min(poll_seconds, int(deadline - time.monotonic())))
        polls += 1
        try:
            batch = updates(offset, timeout=remaining)
        except Exception as error:
            failures += 1
            last_error = str(error)
            print(f"telegram poll: {error}", file=sys.stderr)
            # A Conflict means another poller just opened a short poll. Retry
            # almost immediately: the five-second backoff this used to take
            # is how the first rehearsal's reply was lost — the other poller
            # finished, read the message and confirmed it while this one
            # slept.
            time.sleep(0.5 if "Conflict" in str(error) else 5)
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
    if polls and failures == polls:
        # never once read the chat: this is not silence
        return "unreadable", last_error
    return "timeout", ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--exclusive", action="store_true",
                    help="can this bot's replies actually be read")
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

    if args.exclusive:
        ok, why = exclusive()
        print(("exclusive: " if ok else "NOT EXCLUSIVE: ") + why)
        return 0 if ok else 1

    if args.send:
        print("sent" if send(args.send) else "not sent")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
