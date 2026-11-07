#!/usr/bin/env python3
"""The research brief, small enough to carry for three hundred turns.

WHY THIS EXISTS
---------------
`claude -p` pays for its context on EVERY turn. A 72 KB research brief read
once at turn 20 of a 308-turn stage is not read once: it is re-read 288
times, at $0.50 per million cache-read tokens. Measured on the 2026-11-06
script stage, the five largest files the agent opened — the playbook (twice,
88 KB), AGENT_GUIDE.md (50 KB), verify_fact_coverage.py (28 KB), the
pipeline manifest (27 KB) and run_weekly.sh (18 KB) — came to 258 KB, about
65,000 tokens, which the stage then re-read for the rest of its life: 19
million tokens, $9.50, for five files it had already understood.

The brief's bulk is not what the script stage uses. Of 72 KB, 37 KB is
`data_points` and most of each entry is a URL, a source name, a corroborating
URL list, and taxonomy fields the script never reads. What the script needs
from a data point is: the id to cite, the sentence it licenses, what kind of
span it covers, whether it is contested, and that a source_url EXISTS.

So this prints that. The full brief stays on disk and the fact gate still
reads IT, not this — `lib/verify_fact_coverage.py` and
`scripts/check_claims.py` resolve citations against the real ledger, so a
digest that lost a claim cannot let an unsourced sentence through. The digest
is for the writer; the gate keeps its own copy of the truth.

    scripts/brief_digest.py --project king-tut
    scripts/brief_digest.py --brief path/to/research_brief.json --max-claim 200
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

#: How much of a claim's sentence to keep. Long enough to know what the
#: claim says and write from it; the full text is one `jq` away in the brief
#: if a sentence turns out to need it.
MAX_CLAIM = 240


def host(url: str | None) -> str:
    if not url:
        return "NO SOURCE_URL"
    try:
        return urlparse(url).netloc or url[:40]
    except ValueError:
        return url[:40]


def digest(brief: dict, max_claim: int = MAX_CLAIM) -> str:
    out: list[str] = []
    topic = brief.get("topic")
    if isinstance(topic, dict):
        title = topic.get("title") or topic.get("subject") or ""
    else:
        title = str(topic or "")
    out.append(f"# RESEARCH DIGEST — {title}")
    out.append("")
    summary = brief.get("research_summary")
    if isinstance(summary, str) and summary.strip():
        out.append(summary.strip())
        out.append("")

    points = brief.get("data_points") or []
    out.append(f"## CLAIM LEDGER — {len(points)} entries")
    out.append("")
    out.append("Cite these ids and no others. An id that is not here does not")
    out.append("exist, and inventing one is what shipped easter-island with")
    out.append("fifty-four citations against a fifteen-claim ledger.")
    out.append("")
    missing = 0
    for point in points:
        if not isinstance(point, dict):
            continue
        pid = point.get("id") or "??"
        claim = " ".join(str(point.get("claim") or "").split())
        if len(claim) > max_claim:
            claim = claim[:max_claim - 1].rstrip() + "…"
        flags = []
        kind = point.get("kind")
        if kind:
            flags.append(str(kind))
        if point.get("contested"):
            flags.append("CONTESTED — narrate as disputed")
        confidence = point.get("confidence")
        if confidence and confidence != "established":
            flags.append(str(confidence))
        source = point.get("source_url")
        if not source:
            missing += 1
            flags.append("NO SOURCE_URL — NOT CITEABLE")
        tag = f"  [{', '.join(flags)}]" if flags else ""
        out.append(f"- {pid}  {claim}{tag}")
        out.append(f"      src: {host(source)}")
    out.append("")
    if missing:
        out.append(f"{missing} entr{'y' if missing == 1 else 'ies'} carry no "
                   f"source_url. Citing one fails the gate.")
        out.append("")

    gaps = brief.get("gaps") or []
    if gaps:
        out.append(f"## GAPS — {len(gaps)}: looked for, not sourced")
        out.append("")
        out.append("A sentence that needs one of these may NOT be written.")
        out.append("")
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            out.append(f"- {gap.get('looked_for')}")
            why = gap.get("why_it_matters")
            if why:
                out.append(f"      why it matters: {why}")
            closest = gap.get("closest_available")
            if closest:
                out.append(f"      closest available: {closest}")
        out.append("")

    angles = brief.get("angles_discovered") or []
    if angles:
        out.append(f"## ANGLES DISCOVERED — {len(angles)}")
        out.append("")
        for angle in angles:
            if isinstance(angle, dict):
                label = angle.get("angle") or angle.get("title") or ""
                note = angle.get("why") or angle.get("rationale") or ""
                out.append(f"- {label}" + (f" — {note}" if note else ""))
            else:
                out.append(f"- {angle}")
        out.append("")

    out.append("## WHAT IS NOT HERE")
    out.append("")
    out.append("Source URLs and names, corroborating source lists, the")
    out.append("landscape and trending sections, audience insights, expert")
    out.append("voices and visual references. They are in")
    out.append("artifacts/research_brief.json. Read a SLICE of it with python")
    out.append("if you need one — do not read the whole file: you pay for it")
    out.append("again on every turn after this one.")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--brief")
    ap.add_argument("--max-claim", type=int, default=MAX_CLAIM)
    ap.add_argument("--out", default=None,
                    help="write here as well as to stdout")
    args = ap.parse_args()

    if args.brief:
        path = Path(args.brief)
    elif args.project:
        path = ROOT / "projects" / args.project / "artifacts" / "research_brief.json"
    else:
        print("need --project or --brief", file=sys.stderr)
        return 64
    try:
        brief = json.loads(path.read_text())
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"{path} is not JSON: {exc}", file=sys.stderr)
        return 1

    text = digest(brief, args.max_claim)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
