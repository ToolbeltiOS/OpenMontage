#!/usr/bin/env python3
"""One Telegram post per illustration, one verdict per picture. Never blocks.

WHY THIS IS ITS OWN GATE
------------------------
Illustrations used to be approved at the SCRIPT gate, which runs before the
edit stage — so at that point no illustration had been authored for the film
at all. What the script gate posted was whatever happened to be sitting in
the shared library, from other films, and an "ok" on the script recorded all
of them as approved under this film's name. Measured 2026-11-11: one "ok" on
a rehearsal's script approved noah's ark picture and they-said-it's Tiryns
picture. There was also no way to refuse one picture without refusing the
whole script.

So the pictures have their own gate, and it runs where the pictures exist:
after the edit stage has generated them and before the render.

WHAT IT DOES NOT DO: BLOCK.
---------------------------
The script gate is a stop — a film nobody has read must not be made. This
one is not. A "no", or no reply by render time, DEMOTES that cut to its
fallback and the film renders anyway. The fallback is the slot's own, so a
refused illustration becomes the sourced still or the authored graphic the
cut would have been without one; the narration it was holding keeps its
picture either way.

That is why it always exits 0. A gate that could fail the run here would
turn "I was asleep" into "no film".

REPLIES
-------
    ok 2          picture 2 is approved
    no 3          picture 3 is not
    ok 1 2 5      several at once
    ok all        all of them
    no all        none of them

Each picture is posted with its number and its subject label, so a reply can
name one. Anything unanswered when the clock runs out is a no, and the
record says it was silence rather than a refusal.

    .venv/bin/python scripts/illustration_gate.py --project king-tut --hours 2
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import illustration_spec                                        # noqa: E402
from lib import telegram                                        # noqa: E402

#: Telegram caption limit is 1024; leave room for the number prefix.
CAPTION = 900


def illustration_cuts(props: dict) -> list[dict]:
    """Every cut in the props that is asking for an illustration.

    THE PROPS, NOT THE LIBRARY. The library is shared and holds other
    films' pictures; the props are this film. A picture nothing in this film
    references is not this film's to approve.
    """
    out = []
    for cut in props.get("cuts") or []:
        if cut.get("type") != "illustration":
            continue
        out.append(cut)
    return out


def picture_for(cut: dict, manifest: dict) -> tuple[str, str, Path | None]:
    """(subject, label, file) for one cut.

    `subject` is what the approval is recorded against. `label` is the short
    on-screen line if there is one — it became short on 2026-11-09 and the
    full descriptive line moved to `prompt` — and it is what makes a
    numbered post readable.
    """
    subject = cut.get("subject") or cut.get("title") or ""
    label = cut.get("subject") or subject
    path = None
    for asset in manifest.get("assets") or []:
        names = {asset.get(k) for k in ("subject", "subject_was", "prompt")}
        if subject and subject in names and asset.get("path"):
            path = ROOT / asset["path"]
            break
    if path is None:
        for key in ("image", "source", "backgroundImage"):
            value = cut.get(key)
            if isinstance(value, str) and value.endswith(
                    (".png", ".jpg", ".jpeg", ".webp")):
                path = ROOT / value
                break
    return subject, label, path


def parse(text: str, count: int) -> dict[int, str]:
    """A reply to verdicts. {picture number: "ok"|"no"}.

    Returns {} for anything it cannot read, so an unparseable message is
    neither an approval nor a refusal — it is ignored and the clock keeps
    running. Reading "okay then, but not the third one" as an approval of
    everything is the failure mode worth avoiding.
    """
    lowered = text.strip().lower()
    match = re.match(r"^(ok|okay|yes|y|approve[d]?|no|n|nope|reject)\b(.*)$",
                     lowered)
    if not match:
        return {}
    verdict = "ok" if match.group(1)[0] in "oya" else "no"
    rest = match.group(2).strip()
    if rest in ("all", "*", "everything", "both"):
        return {n: verdict for n in range(1, count + 1)}
    numbers = [int(n) for n in re.findall(r"\d+", rest)]
    numbers = [n for n in numbers if 1 <= n <= count]
    if numbers:
        return {n: verdict for n in numbers}
    if not rest and count == 1:
        return {1: verdict}
    return {}


def collect(offset: int, count: int, hours: float,
            poll_seconds: int = 50) -> tuple[dict[int, str], list[str]]:
    """Verdicts, until every picture has one or the clock runs out."""
    verdicts: dict[int, str] = {}
    seen: list[str] = []
    deadline = time.monotonic() + hours * 3600
    while time.monotonic() < deadline and len(verdicts) < count:
        remaining = max(1, min(poll_seconds, int(deadline - time.monotonic())))
        try:
            batch = telegram.updates(offset, timeout=remaining)
        except Exception as error:                             # noqa: BLE001
            print(f"telegram poll: {error}", file=sys.stderr)
            time.sleep(0.5 if "Conflict" in str(error) else 5)
            continue
        for update in batch:
            offset = update["update_id"] + 1
            message = update.get("message") or update.get("channel_post") or {}
            text = (message.get("text") or "").strip()
            if not text:
                continue
            seen.append(text)
            got = parse(text, count)
            if got:
                verdicts.update(got)
                print(f"  reply {text!r} -> {got}", flush=True)
            else:
                # SAY SO. An ignored reply the person cannot see being
                # ignored is a person who thinks they answered. "ok" with
                # three pictures up is genuinely ambiguous and is not read
                # as approving all three.
                print(f"  reply {text!r} -> could not read it, ignoring",
                      flush=True)
                telegram.send(
                    f"<i>Could not read that as a verdict, so nothing is "
                    f"recorded yet.</i>\n"
                    f"Reply <b>ok 2</b>, <b>no 3</b>, <b>ok 1 2 5</b> or "
                    f"<b>ok all</b> — a number per picture, or the word "
                    f"<b>all</b>.")
    return verdicts, seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--props", default=None)
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--apply", action="store_true", default=True,
                    help="demote refused cuts in the props (default)")
    ap.add_argument("--no-apply", dest="apply", action="store_false")
    args = ap.parse_args()

    project_dir = ROOT / "projects" / args.project
    props_path = Path(args.props) if args.props else \
        project_dir / "artifacts" / "render_props.json"
    if not props_path.exists():
        print(f"no props at {props_path} — nothing to gate", file=sys.stderr)
        return 0

    props = json.loads(props_path.read_text())
    cuts = illustration_cuts(props)
    if not cuts:
        print("no illustration cuts in this film — nothing to approve")
        return 0

    manifest_path = ROOT / illustration_spec.MANIFEST
    manifest = json.loads(manifest_path.read_text()) \
        if manifest_path.exists() else {}

    pictures = []
    for cut in cuts:
        subject, label, path = picture_for(cut, manifest)
        pictures.append({"cut": cut.get("id"), "subject": subject,
                         "label": label, "path": path})

    if not telegram.configured():
        print("telegram is not configured — every illustration stays "
              "unapproved and will fall back", file=sys.stderr)
        rows = [{"cut": p["cut"], "subject": p["subject"], "label": p["label"],
                 "verdict": "no", "why": "telegram not configured"}
                for p in pictures]
        illustration_spec.record_verdicts(args.project, rows, ROOT,
                                          by="nobody — the gate could not post")
        return _apply(args, props, props_path)

    offset = telegram.drain()
    telegram.send(
        f"<b>Illustrations for {args.project}</b>\n"
        f"{len(pictures)} picture(s) follow, numbered. These are "
        f"<b>generated</b>, not sourced — the only pictures in the film "
        f"nobody photographed.\n\n"
        f"Reply <b>ok 2</b>, <b>no 3</b>, <b>ok 1 2 5</b>, or <b>ok all</b>. "
        f"A picture you refuse, or do not answer, falls back to the still or "
        f"the graphic that cut would have used instead.\n\n"
        f"<i>The film renders either way. Nothing waits on this past "
        f"{args.hours:g}h.</i>")

    posted = 0
    for n, p in enumerate(pictures, 1):
        caption = f"{n}. {p['label']}"[:CAPTION]
        if p["path"] and p["path"].exists():
            if telegram.send_photo(p["path"], caption=caption) is not None:
                posted += 1
                p["posted"] = True
                continue
        telegram.send(f"{n}. <b>{telegram.escape(p['label'])}</b>\n"
                      f"<i>the file did not upload, so this one cannot be "
                      f"approved — it will fall back</i>")
        p["posted"] = False
    print(f"posted {posted}/{len(pictures)} picture(s)", flush=True)

    verdicts, seen = collect(offset, len(pictures), args.hours)

    rows = []
    for n, p in enumerate(pictures, 1):
        verdict = verdicts.get(n, "no")
        why = None
        # WHO DECIDED IS PART OF THE RECORD, AND SILENCE IS NOT A PERSON.
        # The default attribution is a Telegram reply, which is true of an
        # answered picture and false of every other row here. A refusal
        # nobody gave must not be filed under their name.
        by = "the owner, by Telegram reply"
        if n not in verdicts:
            why = f"no reply within {args.hours:g}h — silence is not approval"
            by = "nobody — the window closed with no reply"
        elif not p.get("posted"):
            # It cannot have been approved knowingly: nobody saw it.
            verdict, why = "no", "the picture did not upload, so it was never seen"
            by = "nobody — the picture never arrived to be judged"
        rows.append({"cut": p["cut"], "subject": p["subject"],
                     "label": p["label"], "verdict": verdict,
                     "posted": bool(p.get("posted")), "why": why, "by": by})
    path = illustration_spec.record_verdicts(args.project, rows, ROOT)
    ok = sum(1 for r in rows if r["verdict"] == "ok")
    print(f"{ok}/{len(rows)} approved -> {path.relative_to(ROOT)}")
    telegram.send(
        f"<b>Illustrations: {ok} of {len(rows)} approved</b>\n"
        f"The rest fall back to a still or an authored graphic. Rendering.")
    return _apply(args, props, props_path)


def _apply(args, props: dict, props_path: Path) -> int:
    """Demote every cut whose illustration was not approved."""
    if not args.apply:
        print("not applying verdicts (--no-apply)")
        return 0
    demoted = illustration_spec.demote_unapproved(
        props.get("cuts") or [], args.project, ROOT)
    for d in demoted:
        print(f"  demoted {d['cut']} ({d['subject'][:48]!r}) -> {d['fell_to']}")
    props_path.write_text(json.dumps(props, indent=1) + "\n")
    print(f"{len(demoted)} cut(s) demoted in {props_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
