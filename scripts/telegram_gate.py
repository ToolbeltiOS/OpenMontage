#!/usr/bin/env python3
"""The one place a human is in the loop: the script gate.

WHY THE SCRIPT AND NOTHING ELSE
-------------------------------
Everything downstream of the script is mechanical and gated by a measurement
— the rhythm, the leads, the frame order, the type lock, the mix. The script
is the only artifact where being wrong is invisible to every gate in the
repository and obvious to a viewer. So it is the only thing that waits for a
person.

WHAT IT POSTS
-------------
The title, the act outline, the full script as a .txt, and the hero style
frames. Four things, because a reply of "ok" has to be an informed one: the
outline says what the film argues, the script says how, and the frames say
what it will look like.

THE REPLY
---------
    ok              continue
    no              abort
    anything else   notes. They are applied to the script, and the gate
                    posts ONCE more. A second round of notes aborts, because
                    a conversation at two in the morning is a conversation
                    the person did not agree to have.
    silence         ABORT, never continue. A film that publishes because
                    nobody said no is what this exists to prevent.

AND IF THE GATE CANNOT SHOW, IT SAYS SO TOO. The script and the frames go up
as multipart uploads, and the first rehearsal on the dedicated bot lost one of
them to a reset peer. An upload is retried three times now, and anything that
still will not go is named in the message that asks for the reply — because an
"ok" given to a missing frame is indistinguishable from an informed one.

AND IF THE GATE CANNOT READ, IT SAYS SO. The first live rehearsal returned
"no reply in 12h" while the owner was looking at their reply: another process
was polling the same bot token and consuming the messages. Silence and
deafness are different failures and only one of them is the person's fault.

    python scripts/telegram_gate.py --project <id> --script <path> --hours 12
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

import script_beats  # noqa: E402
import telegram  # noqa: E402

#: How many style frames go with the script. Eight is what the playbook calls
#: a hero set and what fits on a phone screen as a strip.
HERO_FRAMES = 8


def outline_of(script: dict) -> list[str]:
    """The act outline, from the script artifact.

    This read `script["acts"]`, and `script.schema.json` is
    `additionalProperties: false` with no `acts` key — the artifact carries
    `sections`. So for every schema-valid script the outline posted EMPTY and
    the generated .txt fell back to a raw JSON dump: one of the gate's four
    things silently missing, in the message whose whole job is to make an
    "ok" an informed one. The dry run did not catch it because its fixture
    was written in the shape the code read rather than the shape the schema
    allows, so the join it proved was one no real artifact can make.

    `acts` is still read, because run #1's artifacts are on disk in that
    shape and a gate that cannot show an old script is no better.
    """
    lines: list[str] = []

    for section in (script.get("sections") or []):
        label = section.get("label") or section.get("id") or "section"
        lines.append(f"<b>{label}</b>")
        for beat in script_beats.parse_section(section.get("text", ""))[:6]:
            opener = beat["text"].split(". ")[0][:110]
            tag = beat["type"] + (f"|{beat['register']}" if beat["register"] else "")
            lines.append(f"  · <i>{tag}</i> {opener}")

    for act in (script.get("acts") or []):            # run #1's shape
        title = act.get("title") or act.get("name") or f"Act {act.get('number', '?')}"
        beats = act.get("beats") or []
        lines.append(f"<b>{act.get('number', '')} {title}</b>")
        for beat in beats[:6]:
            text = (beat if isinstance(beat, str)
                    else beat.get("summary") or beat.get("title") or "")
            if text:
                lines.append(f"  · {text[:110]}")

    return lines


def post_script_as_text(script_path: Path) -> None:
    """The fallback when the attachment will not upload.

    The script is the one thing the reply is actually about, so it is not
    allowed to go missing quietly. Sent in whole messages; `require` raises if
    even this cannot be delivered, and a gate that cannot show the script is a
    gate that must not collect an "ok".
    """
    # Escape first, then split. A line of narration containing "<" or "&"
    # grows when escaped, so measuring the raw text is measuring the wrong
    # string and the message comes back too long.
    limit = telegram.MAX_MESSAGE - 80          # the <pre> wrapper and the label
    chunks, current = [], ""
    for line in script_path.read_text().splitlines(keepends=True):
        line = telegram.escape(line)
        if len(current) + len(line) > limit and current:
            chunks.append(current)
            current = ""
        current += line[:limit]
    if current:
        chunks.append(current)
    telegram.require(f"The attachment would not upload — the script follows "
                     f"as {len(chunks)} message(s).")
    for i, chunk in enumerate(chunks, 1):
        telegram.require(f"<i>script {i}/{len(chunks)}</i>\n<pre>{chunk}</pre>")


def fact_line(project: str, script_path: Path) -> str:
    """One line on the fact gate, beside the script it is about.

    COMPUTED HERE, not passed in from the runner. The number has to be about
    the script in the message — the runner's own run of the gate happens
    before the notes loop, and a script revised after notes would otherwise be
    shown next to the figure for the script it replaced.

    The runner fails the run when anything is uncovered, so in an unattended
    run this reads zero by construction. It is worth sending anyway: it says
    the gate ran, and how much of the script it had an opinion about.

    Never raises. A reporting extra must not be the reason an approval
    request fails to send.
    """
    try:
        sys.path.insert(0, str(ROOT / "lib"))
        from verify_fact_coverage import check

        brief = ROOT / "projects" / project / "artifacts" / "research_brief.json"
        problems, m = check(json.loads(script_path.read_text()),
                            json.loads(brief.read_text()))
        line = (f"fact gate: {m['sentences_needing_a_claim']} sentences need "
                f"a claim, {m['sentences_uncovered']} uncovered")
        dead = len(m.get("ids_that_do_not_resolve") or [])
        if dead:
            # Coverage can read zero while a section cites ids that are not
            # there, because one resolving id covers a whole section. Say so
            # rather than let the zero carry more than it means.
            line += f" — but {dead} cited claim id(s) do not resolve"
        line += f"; framing: {m['framing_sentences']} sentences"
        if m.get("framing_blocked"):
            line += f" ({m['framing_blocked']} not exempted)"
        if m.get("exempt_sections"):
            line += f" (exempt: {', '.join(m['exempt_sections'])})"
        return line
    except Exception as exc:                       # never block the approval
        return f"fact gate: could not be summarised ({type(exc).__name__})"


def post(project: str, script_path: Path, frames: list[Path],
         title: str, outline: list[str], attempt: int = 1) -> dict:
    """Post the four things, and report what of it actually arrived.

    The header and the instruction are load-bearing (`require`). The script
    and the frames used to be best effort with no retry, which meant a reset
    peer part-way through one upload could ask for approval of a film the
    person could not see — and the "ok" would look identical to an informed
    one. Now an upload that fails is said out loud, in the same message that
    asks for the reply.
    """
    header = (f"<b>{title}</b>\n"
              f"<i>{project}</i> — script gate"
              + (" (revised)" if attempt > 1 else "") + "\n"
              + f"<i>{fact_line(project, script_path)}</i>\n\n"
              + "\n".join(outline[:40]))
    telegram.require(header)

    report = {"script": True, "frames_sent": 0,
              "frames_expected": len(frames[:HERO_FRAMES]), "missing": []}

    if telegram.send_document(script_path, caption="the full script") is None:
        report["script"] = False
        post_script_as_text(script_path)

    for frame in frames[:HERO_FRAMES]:
        if telegram.send_photo(frame) is None:
            report["missing"].append(frame.name)
        else:
            report["frames_sent"] += 1

    note = ""
    if not report["script"]:
        note += "\n\n<i>The .txt attachment failed; the script is above as text.</i>"
    if report["missing"]:
        note += (f"\n\n<i>{len(report['missing'])} of "
                 f"{report['frames_expected']} style frames would not upload "
                 f"({', '.join(report['missing'][:4])}). Reply <b>no</b> if "
                 f"you will not approve a look you cannot see.</i>")

    telegram.require(
        "Reply <b>ok</b> to continue, <b>no</b> to abort, or send notes.\n"
        "Notes are applied and reposted once. Silence aborts." + note)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--script", required=True, help="the script artifact JSON")
    ap.add_argument("--script-text", default=None,
                    help="the .txt that is attached; defaults beside --script")
    ap.add_argument("--frames", default=None,
                    help="directory of hero style frames")
    ap.add_argument("--hours", type=float, default=12.0)
    ap.add_argument("--notes-out", default=None,
                    help="where to write notes if the reply is notes")
    ap.add_argument("--attempt", type=int, default=1)
    args = ap.parse_args()

    script_path = Path(args.script)
    if not script_path.exists():
        # The real failure this guards: the script stage exited 0 and wrote
        # nothing. Without it the gate dies on a traceback at two in the
        # morning and the Telegram message says "unexpected exit 1".
        message = (f"no script at {script_path} — the script stage produced "
                   f"nothing to approve")
        print(message, file=sys.stderr)
        telegram.send(f"<b>Script gate cannot run</b>\n{message}")
        return 5
    script = json.loads(script_path.read_text())
    title = script.get("title") or args.project
    outline = outline_of(script)

    text_path = (Path(args.script_text) if args.script_text
                 else script_path.with_suffix(".txt"))
    if not text_path.exists():
        # the attachment is the point; build it from the artifact
        body = []
        for section in (script.get("sections") or []):
            body.append(f"\n\n=== {section.get('label') or section.get('id')} "
                        f"===\n")
            body.append(section.get("text") or "")
        for act in (script.get("acts") or []):        # run #1's shape
            body.append(f"\n\n=== {act.get('number','')} "
                        f"{act.get('title') or ''} ===\n")
            for beat in (act.get("beats") or []):
                body.append(beat if isinstance(beat, str)
                            else (beat.get("narration") or beat.get("text") or ""))
        text_path.write_text("\n".join(filter(None, body)) or
                             json.dumps(script, indent=1))

    frames = []
    if args.frames:
        frames = sorted(Path(args.frames).glob("*.png")) + \
                 sorted(Path(args.frames).glob("*.jpg"))

    # Before posting, not after: a gate that posts and then cannot read has
    # wasted the whole window and blamed someone who answered.
    readable, why = telegram.exclusive()
    if not readable:
        print(f"cannot read replies: {why}", file=sys.stderr)
        telegram.send(f"<b>Script gate cannot run</b>\n{why}")
        return 6

    offset = telegram.drain()
    report = post(args.project, text_path, frames, title, outline, args.attempt)
    print(f"posted: script={'attached' if report['script'] else 'AS TEXT'}, "
          f"frames {report['frames_sent']}/{report['frames_expected']}")

    verdict, text = telegram.await_reply(offset, args.hours)
    print(f"gate: {verdict}")

    if verdict == "ok":
        telegram.send("Approved. Rendering.")
        return 0
    if verdict == "no":
        telegram.send("Aborted, as asked.")
        return 2
    if verdict == "unreadable":
        telegram.send(
            f"<b>The gate could not read this chat</b>\n"
            f"Every poll failed: {text[:300]}\n\n"
            f"Your reply may have arrived and been consumed by another "
            f"process polling the same bot. Aborting — this is not a "
            f"timeout and it is not your fault.")
        return 6
    if verdict == "timeout":
        telegram.send(
            f"No reply in {args.hours:g}h — aborting. Silence is not approval.")
        return 3

    notes_path = Path(args.notes_out) if args.notes_out else \
        script_path.with_name("script_notes.txt")
    notes_path.write_text(text + "\n")
    print(f"notes -> {notes_path}")
    if args.attempt > 1:
        telegram.send("Second round of notes — aborting. Let us do this awake.")
        return 4
    telegram.send("Notes received. Applying them and reposting once.")
    return 10                               # the runner applies and re-posts


if __name__ == "__main__":
    raise SystemExit(main())
