"""Beat types and written air, parsed out of the script's own prose.

WHY THIS EXISTS
---------------
Two defects in run #1, both of the same shape — a rule stated in the playbook
that no stage turned into a number.

The playbook said "cut on meaning, never on a fixed interval". The planner had
one hold band and gave it to every slot, so 181 of 182 shots came out between
5 and 8 seconds and every minute of the film carried 8 to 10 cuts.

The script's pause_policy said "a full beat of silence after each verdict
sentence". The delivered film held thirteen seconds of silence in twenty
minutes and never stopped talking for longer than 2.8 seconds, because nothing
downstream knew where the beats were meant to be.

So the script now carries both, in its own text, where the writer can see them:

    [beat: reveal]
    The granite had been quarried a hundred and forty miles away.
    [air 2.5s]

A marker in the prose is the only form that survives a rewrite. A beat table
kept beside the script drifts from it the first time a paragraph moves.

WHAT IT GIVES THE REST OF THE PIPELINE
--------------------------------------
- `parse_script` turns the markers into a beat list per section, with the
  clean narration text the synthesiser should actually speak.
- `narration_plan` is what the narration stage renders: one segment per beat
  plus the silence that follows it, so the gap is synthesised rather than
  hoped for.
- `measure` reports words, speech seconds, planned air and total — the film's
  duration is speech PLUS air, and measuring it the old way counts the silence
  as overrun.
- `check` fails the script stage on the conditions the playbook states.

Run it as a gate:

    python3 lib/script_beats.py projects/<id>/artifacts/script.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: `[beat: reveal]` or `[beat: reveal | awe]`.
#:
#: The register half was taught by script-director.md Step 8b and rejected
#: here: a line that does not match is not an error, it is prose, so
#: `[beat: reveal | awe]` lost the beat AND added four junk words to the count
#: this file blocks on. It was found when the first unattended run was being
#: read for a different fault, not by a test, because no test wrote the
#: marker the way the director teaches it.
#:
#: The register rides the marker rather than section metadata because its
#: grain is the paragraph — a section holds several beats and they are not
#: all in the same register — and because the section schema is
#: `additionalProperties: false` with nowhere to put one.
BEAT_RE = re.compile(
    r"^\s*\[beat:\s*([a-z_]+)\s*(?:\|\s*([a-z_]+)\s*)?\]\s*$", re.IGNORECASE)
AIR_RE = re.compile(r"^\s*\[air\s+([0-9]*\.?[0-9]+)\s*s\s*\]\s*$", re.IGNORECASE)

BEAT_TYPES = ("reveal", "exposition", "landing", "transition")
DEFAULT_BEAT = "exposition"


# ───────────────────────────── playbook ──────────────────────────────────
def load_playbook(path: str | None = None) -> dict[str, Any]:
    import yaml

    path = path or os.path.join(ROOT, "styles", "wak3up-documentary.yaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ───────────────────────────── parsing ───────────────────────────────────
def parse_section(text: str) -> list[dict[str, Any]]:
    """Split one section's prose into beats.

    A beat is a paragraph plus the air that follows it. `[beat: x]` on its own
    line opens a beat; `[air N.Ns]` on its own line closes one. A paragraph
    with no beat marker is exposition, which is the common case and should not
    need saying.
    """
    beats: list[dict[str, Any]] = []
    pending_type: str | None = None
    pending_register: str | None = None
    buf: list[str] = []

    def flush(air: float = 0.0) -> None:
        nonlocal pending_type, pending_register, buf
        body = "\n".join(buf).strip()
        if not body:
            # air before any prose attaches to the previous beat instead of
            # opening an empty one
            if air and beats:
                beats[-1]["air_after_s"] = round(beats[-1]["air_after_s"] + air, 3)
            buf = []
            pending_type = pending_register = None
            return
        beats.append({
            "index": len(beats),
            "type": pending_type or DEFAULT_BEAT,
            "register": pending_register,
            "tagged": pending_type is not None,
            "text": body,
            "words": len(body.split()),
            "air_after_s": round(air, 3),
        })
        buf = []
        pending_type = pending_register = None

    for raw in text.splitlines():
        m_beat = BEAT_RE.match(raw)
        if m_beat:
            if buf:
                flush()
            pending_type = m_beat.group(1).lower()
            pending_register = (m_beat.group(2) or "").lower() or None
            continue
        m_air = AIR_RE.match(raw)
        if m_air:
            flush(float(m_air.group(1)))
            continue
        if not raw.strip():
            if buf:
                flush()
            continue
        buf.append(raw)
    if buf:
        flush()
    return beats


def parse_script(script: dict[str, Any]) -> list[dict[str, Any]]:
    """Every section's beats, in order, each carrying its section id."""
    out: list[dict[str, Any]] = []
    for section in script.get("sections", []):
        for beat in parse_section(section.get("text", "")):
            beat = dict(beat)
            beat["section_id"] = section.get("id")
            beat["id"] = f"{section.get('id')}_b{beat['index']:02d}"
            out.append(beat)
    return out


def narration_plan(script: dict[str, Any]) -> dict[str, Any]:
    """What the narration stage renders: a segment per beat, and its silence.

    The air is part of the plan rather than something the mixer guesses,
    because the mixer is the stage that rebuilds the file. A gap applied by
    editing a finished render would be gone at the next re-render — the same
    way the approved music mix was lost once already.
    """
    beats = parse_script(script)
    return {
        "version": "1.0",
        "wpm": (script.get("voice_performance", {}) or {}).get("wpm")
               or load_playbook()["structure"]["words_per_minute_target"],
        "segments": [
            {
                "id": b["id"],
                "section_id": b["section_id"],
                "beat": b["type"],
                "register": b["register"],
                "text": b["text"],
                "air_after_s": b["air_after_s"],
            }
            for b in beats
        ],
    }


# ──────────────────────────── measurement ────────────────────────────────
def measure(script: dict[str, Any], wpm: float | None = None) -> dict[str, Any]:
    """Words, speech seconds, planned air and total runtime.

    The film's length is speech plus air. Run #1's duration check divided words
    by words-per-minute and stopped there, which is correct only for a film
    that never stops talking — and is exactly why asking for air used to read
    as an overrun.
    """
    pb = load_playbook()
    wpm = wpm or pb["structure"]["words_per_minute_target"]
    beats = parse_script(script)
    words = sum(b["words"] for b in beats)
    air = sum(b["air_after_s"] for b in beats)
    speech = words / wpm * 60.0
    total = speech + air
    return {
        "beats": len(beats),
        "words": words,
        "wpm": wpm,
        "speech_seconds": round(speech, 1),
        "planned_air_seconds": round(air, 1),
        "total_seconds": round(total, 1),
        "air_pct_of_total": round(100 * air / total, 1) if total else 0.0,
        "air_gaps": sum(1 for b in beats if b["air_after_s"] > 0),
        "longest_air_s": max((b["air_after_s"] for b in beats), default=0.0),
        "beats_by_type": {
            t: sum(1 for b in beats if b["type"] == t) for t in BEAT_TYPES
        },
    }


# ───────────────────────────── the gate ──────────────────────────────────
def check(script: dict[str, Any], playbook: dict[str, Any] | None = None) -> list[str]:
    """Problems that should send the script stage back. Empty means pass."""
    pb = playbook or load_playbook()
    air_rules = pb["structure"]["air"]
    allowed = set(air_rules["allowed_lengths_seconds"])
    lo_pct, hi_pct = air_rules["film_total_pct"]
    w_lo, w_hi = pb["structure"]["narrated_word_band"]
    band_lo, band_hi = pb["structure"]["duration_band_seconds"]

    beats = parse_script(script)
    m = measure(script, pb["structure"]["words_per_minute_target"])
    problems: list[str] = []

    if not beats:
        return ["script has no beats — no section text parsed"]

    registers = set(
        ((pb.get("motion") or {}).get("mood") or {}).get("registers") or [])

    for b in beats:
        if b["type"] not in BEAT_TYPES:
            problems.append(f"{b['id']}: unknown beat type {b['type']!r}")
        if b["register"] and registers and b["register"] not in registers:
            # A register the mood table does not have is not a near miss: it
            # falls back to the beat-only row, so the paragraph gets the
            # same move as every other one of its beat and the table that
            # exists to stop that is silently not consulted.
            problems.append(
                f"{b['id']}: unknown register {b['register']!r} — "
                f"the mood table has {sorted(registers)}")
        if b["air_after_s"] and b["air_after_s"] not in allowed:
            problems.append(
                f"{b['id']}: air {b['air_after_s']}s is not one of "
                f"{sorted(allowed)} — pick a written length, do not tune it")

    untagged = [b["id"] for b in beats if not b["tagged"]]
    if len(untagged) == len(beats):
        problems.append(
            "no paragraph carries a [beat: ...] marker — the planner would fall "
            "back to one hold band for the whole film, which is the defect this "
            "check exists for")

    if not (w_lo <= m["words"] <= w_hi):
        problems.append(
            f"narrated words {m['words']} outside the band {w_lo}-{w_hi}")

    if not (lo_pct <= m["air_pct_of_total"] <= hi_pct):
        problems.append(
            f"planned air is {m['air_pct_of_total']}% of runtime, outside "
            f"{lo_pct}-{hi_pct}% ({m['planned_air_seconds']}s over "
            f"{m['total_seconds']}s)")

    if not (band_lo <= m["total_seconds"] <= band_hi):
        problems.append(
            f"speech plus air is {m['total_seconds']}s, outside the duration "
            f"band {band_lo}-{band_hi}s")

    # one 4s gap per act, and a gap at least every two minutes
    longest_per_section: dict[str, float] = {}
    for b in beats:
        sid = b["section_id"]
        longest_per_section[sid] = max(longest_per_section.get(sid, 0.0), b["air_after_s"])
    acts = [s for s in longest_per_section if str(s).startswith("act")]
    for sid in acts:
        if longest_per_section[sid] < max(allowed):
            problems.append(
                f"{sid}: no {max(allowed)}s gap — every act lands its climax on "
                f"one, longest here is {longest_per_section[sid]}s")

    # cumulative speech clock, so "every two minutes" means on screen
    clock, last_gap_at = 0.0, 0.0
    for b in beats:
        clock += b["words"] / m["wpm"] * 60.0
        if b["air_after_s"] >= 1.5:
            if clock - last_gap_at > 120.0:
                problems.append(
                    f"{b['id']}: {round(clock - last_gap_at)}s between gaps of "
                    f"1.5s or longer — the rule is one every two minutes")
            last_gap_at = clock
        clock += b["air_after_s"]
    if clock - last_gap_at > 120.0:
        problems.append(
            f"the last {round(clock - last_gap_at)}s of the film carries no gap "
            f"of 1.5s or longer")

    return problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: script_beats.py <script.json> [--plan <out.json>]")
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        script = json.load(fh)

    m = measure(script)
    print(f"beats {m['beats']}  words {m['words']}  "
          f"speech {m['speech_seconds']}s  air {m['planned_air_seconds']}s "
          f"({m['air_pct_of_total']}%)  total {m['total_seconds']}s")
    print("  by type:", ", ".join(f"{k} {v}" for k, v in m["beats_by_type"].items()))
    print(f"  gaps {m['air_gaps']}, longest {m['longest_air_s']}s")

    if "--plan" in argv:
        dest = argv[argv.index("--plan") + 1]
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(narration_plan(script), fh, indent=1)
        print(f"wrote narration plan {dest}")

    problems = check(script)
    for p in problems:
        print("  -", p)
    print("SCRIPT BEATS:", "PASS" if not problems else "FAIL")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
